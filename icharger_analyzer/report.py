"""Self-contained HTML report generation."""

from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from .analytics import AnalysisResult, AnalysisWarning
from .charts import PLOTLY_CONFIG
from .models import ChargerLog


def _fmt(value: object, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}{suffix}"
    return f"{value}{suffix}"


def _duration(seconds: float) -> str:
    seconds_int = int(round(seconds))
    hours, remainder = divmod(seconds_int, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _warning_rows(warnings: list[AnalysisWarning]) -> str:
    if not warnings:
        return '<tr><td colspan="6" class="muted">Автоматические предупреждения не обнаружены.</td></tr>'
    rows = []
    for warning in warnings:
        severity = {"high": "Высокая", "medium": "Средняя", "low": "Низкая"}.get(warning.severity, warning.severity)
        peak = "—" if warning.peak_value is None else f"{warning.peak_value:.3f} {html.escape(warning.unit)}"
        rows.append(
            "<tr>"
            f'<td><span class="badge {html.escape(warning.severity)}">{severity}</span></td>'
            f"<td>{html.escape(warning.title)}</td>"
            f"<td>{warning.start_s:.1f}</td>"
            f"<td>{warning.end_s:.1f}</td>"
            f"<td>{peak}</td>"
            f"<td>{html.escape(warning.description)}</td>"
            "</tr>"
        )
    return "".join(rows)


def _issue_rows(log: ChargerLog) -> str:
    if not log.issues:
        return '<tr><td colspan="3" class="muted">Повреждённых строк не найдено.</td></tr>'
    rows = []
    for issue in log.issues[:200]:
        rows.append(
            "<tr>"
            f"<td>{issue.line_number}</td>"
            f"<td>{html.escape(issue.message)}</td>"
            f"<td><code>{html.escape(issue.line)}</code></td>"
            "</tr>"
        )
    return "".join(rows)


def _figure_html(fig: go.Figure, *, include_plotlyjs: bool | str) -> str:
    return fig.to_html(
        full_html=False,
        include_plotlyjs=include_plotlyjs,
        config=PLOTLY_CONFIG,
        div_id=None,
    )


def write_report(
    log: ChargerLog,
    result: AnalysisResult,
    figures: list[go.Figure],
    output_file: Path,
    *,
    standalone: bool = True,
) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    summary = result.summary
    include_js: bool | str = True if standalone else "cdn"
    graph_html = []
    for index, figure in enumerate(figures):
        graph_html.append(_figure_html(figure, include_plotlyjs=include_js if index == 0 else False))

    kpis = [
        ("Длительность", _duration(summary.duration_s)),
        ("Отсчёты", f"{summary.samples:,}".replace(",", " ")),
        ("Период записи", _fmt(summary.median_sample_interval_s, 3, " s")),
        ("Частота записи", _fmt(summary.nominal_sample_rate_hz, 3, " Hz")),
        ("Разрывы телеметрии", str(summary.telemetry_gap_count)),
        ("Банки", str(summary.detected_cells)),
        ("Ёмкость по счётчику", _fmt(summary.capacity_counter_ah, 3, " Ah")),
        ("Интеграл тока", _fmt(summary.integrated_capacity_ah, 3, " Ah")),
        ("Энергия", _fmt(summary.integrated_energy_wh, 2, " Wh")),
        ("Стартовое напряжение", _fmt(summary.start_pack_voltage_v, 3, " V")),
        ("Конечное напряжение", _fmt(summary.end_pack_voltage_v, 3, " V")),
        ("Пиковый ток разряда", _fmt(summary.peak_discharge_current_a, 2, " A")),
        ("Пиковая мощность", _fmt(summary.peak_abs_power_w, 1, " W")),
        ("Минимальная банка", _fmt(summary.min_cell_voltage_v, 3, " V")),
        ("Максимальный Δ банок", _fmt(None if summary.max_cell_delta_v is None else summary.max_cell_delta_v * 1000, 1, " mV")),
        ("Макс. внутренняя температура", _fmt(summary.max_internal_temp_c, 1, " °C")),
        ("Последнее полное IR", _fmt(summary.latest_total_ir_mohm, 1, " mΩ")),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="kpi-label">{html.escape(label)}</div><div class="kpi-value">{html.escape(value)}</div></div>'
        for label, value in kpis
    )

    metadata = {
        "Модель": log.header.model or "—",
        "Прошивка": log.header.firmware or "—",
        "Аппаратная версия": log.header.hardware or "—",
        "Серийный номер": log.header.serial_number or "—",
        "Канал": str(log.telemetry[0].channel),
        "Код типа батареи": str(log.telemetry[0].battery_type_code),
        "Медианный период": f"{summary.median_sample_interval_s:.3f} s",
        "Средний период": f"{summary.mean_sample_interval_s:.3f} s",
        "Минимальный период": f"{summary.min_sample_interval_s:.3f} s",
        "Максимальный период / разрыв": f"{summary.max_sample_interval_s:.3f} s",
        "СКО периода": f"{summary.sample_interval_std_s:.3f} s",
        "Номинальная частота": f"{summary.nominal_sample_rate_hz:.3f} Hz",
        "Обнаружено разрывов": str(summary.telemetry_gap_count),
        "Пакетов 128": str(summary.status_record_count),
    }
    metadata_rows = "".join(
        f"<tr><th>{html.escape(key)}</th><td>{html.escape(value)}</td></tr>" for key, value in metadata.items()
    )

    machine_summary = html.escape(json.dumps(summary.as_dict(), ensure_ascii=False, indent=2))
    source_name = html.escape(log.source_file.name)
    document = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>iCharger — {source_name}</title>
<style>
:root {{ color-scheme: dark; --bg:#0b1220; --card:#111827; --line:#334155; --text:#e5e7eb; --muted:#94a3b8; --accent:#38bdf8; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text); font-family:Inter,Segoe UI,Arial,sans-serif; }}
.container {{ width:min(1600px,96vw); margin:0 auto; padding:28px 0 60px; }}
h1 {{ margin:0 0 6px; font-size:clamp(26px,4vw,44px); }}
h2 {{ margin:0 0 16px; }}
.subtitle,.muted {{ color:var(--muted); }}
.card {{ background:var(--card); border:1px solid #1e293b; border-radius:16px; padding:20px; margin-top:20px; box-shadow:0 14px 40px rgba(0,0,0,.2); }}
.kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:12px; margin-top:20px; }}
.kpi {{ background:#0f172a; border:1px solid #243244; border-radius:12px; padding:14px; }}
.kpi-label {{ color:var(--muted); font-size:13px; }}
.kpi-value {{ margin-top:7px; font-size:22px; font-weight:700; }}
table {{ width:100%; border-collapse:collapse; }}
th,td {{ border-bottom:1px solid #243244; text-align:left; padding:10px; vertical-align:top; }}
th {{ color:#cbd5e1; }}
.table-wrap {{ overflow:auto; }}
.badge {{ display:inline-block; border-radius:999px; padding:4px 9px; font-size:12px; font-weight:700; }}
.badge.high {{ background:#7f1d1d; color:#fecaca; }}
.badge.medium {{ background:#78350f; color:#fde68a; }}
.badge.low {{ background:#164e63; color:#cffafe; }}
code,pre {{ font-family:ui-monospace,SFMono-Regular,Consolas,monospace; }}
pre {{ white-space:pre-wrap; overflow-wrap:anywhere; background:#0f172a; padding:14px; border-radius:10px; color:#cbd5e1; }}
.note {{ border-left:4px solid var(--accent); padding:10px 14px; background:#0f172a; color:#cbd5e1; }}
.graph {{ overflow:hidden; }}
</style>
</head>
<body>
<main class="container">
<header>
<h1>iCharger Analyzer</h1>
<div class="subtitle">Источник: {source_name}</div>
</header>
<section class="kpis">{kpi_html}</section>
<section class="card">
<h2>Параметры лога</h2>
<div class="table-wrap"><table>{metadata_rows}</table></div>
<p class="note">Каждый исходный отсчёт сохраняется в CSV с абсолютным счётчиком <code>timestamp_ms</code>, временем от начала <code>elapsed_time</code>, периодом <code>dt_s</code> и мгновенной частотой <code>sample_rate_hz</code>. Последний ряд временного графика показывает стабильность записи и разрывы.</p>
<p class="note">Поля пакета 128 не опубликованы производителем. Внутреннее сопротивление показано по структуре ваших файлов и проверке суммы банков; исходные значения не теряются в парсере.</p>
</section>
<section class="card graph">{''.join(graph_html)}</section>
<section class="card">
<h2>Сгруппированные предупреждения</h2>
<div class="table-wrap"><table><thead><tr><th>Уровень</th><th>Событие</th><th>Начало, s</th><th>Конец, s</th><th>Пик</th><th>Описание</th></tr></thead><tbody>{_warning_rows(result.warnings)}</tbody></table></div>
</section>
<section class="card">
<h2>Качество исходного файла</h2>
<p>Корректных телеметрических пакетов: <b>{summary.samples}</b>. Повреждённых строк: <b>{len(log.issues)}</b>. Неподдерживаемые типы: <b>{html.escape(str(log.unsupported_packet_counts) or 'нет')}</b>.</p>
<div class="table-wrap"><table><thead><tr><th>Строка</th><th>Ошибка</th><th>Фрагмент</th></tr></thead><tbody>{_issue_rows(log)}</tbody></table></div>
</section>
<details class="card"><summary>Машиночитаемая сводка JSON</summary><pre>{machine_summary}</pre></details>
</main>
</body>
</html>"""
    output_file.write_text(document, encoding="utf-8")


def write_comparison_report(
    rows: list[dict[str, object]],
    figures: list[tuple[str, str, go.Figure]],
    output_file: Path,
    *,
    comparison_step_s: float,
    standalone: bool = True,
) -> None:
    """Write the final multi-log dashboard with several overlaid figures."""

    output_file.parent.mkdir(parents=True, exist_ok=True)
    table_rows = "".join(
        "<tr>"
        f"<td><a href=\"{html.escape(str(row['report']))}\">{html.escape(str(row['file']))}</a></td>"
        f"<td>{html.escape(str(row['cells']))}</td>"
        f"<td>{float(row['duration_h']):.2f}</td>"
        f"<td>{float(row['samples']):.0f}</td>"
        f"<td>{float(row['median_interval_s']):.3f}</td>"
        f"<td>{float(row['min_interval_s']):.3f}</td>"
        f"<td>{float(row['max_interval_s']):.3f}</td>"
        f"<td>{int(row['gap_count'])}</td>"
        f"<td>{float(row['capacity_ah']):.3f}</td>"
        f"<td>{float(row['energy_wh']):.2f}</td>"
        f"<td>{float(row['end_voltage_v']):.3f}</td>"
        f"<td>{html.escape(str(row['min_cell_v']))}</td>"
        "</tr>"
        for row in rows
    )

    figure_html: list[str] = []
    include_js: bool | str = True if standalone else "cdn"
    for index, (title, description, figure) in enumerate(figures):
        graph = _figure_html(figure, include_plotlyjs=include_js if index == 0 else False)
        figure_html.append(
            f'<section class="card graph"><h2>{html.escape(title)}</h2>'
            f'<p class="muted">{html.escape(description)}</p>{graph}</section>'
        )

    document = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>iCharger — общее сравнение</title>
<style>
:root {{ color-scheme:dark; --bg:#0b1220; --card:#111827; --line:#334155; --text:#e5e7eb; --muted:#94a3b8; --accent:#38bdf8; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text); font-family:Inter,Segoe UI,Arial,sans-serif; }}
main {{ width:min(1800px,97vw); margin:auto; padding:30px 0 70px; }}
h1 {{ margin:0 0 8px; font-size:clamp(28px,4vw,46px); }}
h2 {{ margin:0 0 8px; }}
a {{ color:var(--accent); }}
.muted {{ color:var(--muted); }}
.card {{ background:var(--card); border:1px solid #1e293b; border-radius:16px; padding:20px; margin-top:20px; box-shadow:0 14px 40px rgba(0,0,0,.2); }}
.note {{ border-left:4px solid var(--accent); padding:11px 14px; background:#0f172a; color:#cbd5e1; }}
.table-wrap {{ overflow:auto; }}
table {{ width:100%; border-collapse:collapse; white-space:nowrap; }}
th,td {{ padding:10px; border-bottom:1px solid var(--line); text-align:left; }}
th {{ position:sticky; top:0; background:#111827; color:#cbd5e1; }}
.graph {{ overflow:hidden; }}
code {{ font-family:ui-monospace,SFMono-Regular,Consolas,monospace; }}
</style>
</head>
<body>
<main>
<header>
<h1>Общее сравнение логов iCharger</h1>
<p class="muted">Все испытания наложены друг на друга отдельными линиями. Щелчок по имени файла в легенде скрывает или показывает эту линию сразу на связанных графиках.</p>
</header>
<section class="card">
<h2>Временная сетка</h2>
<p class="note">Исходные отчёты используют каждый записанный отсчёт. Только общий сравнительный график интерполируется на единую сетку с периодом <b>{comparison_step_s:g} s</b>, чтобы логи с разной частотой записи можно было корректно накладывать и чтобы HTML оставался отзывчивым.</p>
<div class="table-wrap"><table><thead><tr><th>Файл</th><th>Банки</th><th>Часы</th><th>Отсчёты</th><th>Медиана, s</th><th>Min, s</th><th>Max, s</th><th>Разрывы</th><th>Ah</th><th>Wh</th><th>Конец, V</th><th>Min cell</th></tr></thead><tbody>{table_rows}</tbody></table></div>
</section>
{''.join(figure_html)}
</main>
</body>
</html>"""
    output_file.write_text(document, encoding="utf-8")
