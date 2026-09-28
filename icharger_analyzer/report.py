"""Compact, self-contained HTML reports with independent chart navigation."""

from __future__ import annotations

import html
import json
from pathlib import Path

import plotly.graph_objects as go
from plotly.offline import get_plotlyjs, get_plotlyjs_version

from .analytics import AnalysisResult, AnalysisWarning
from .charts import PLOTLY_CONFIG, independent_charts
from .models import ChargerLog

ASSETS = Path(__file__).with_name("assets")


def _fmt(value: object, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}{suffix}"
    return f"{value}{suffix}"


def _duration(seconds: float) -> str:
    hours, remainder = divmod(int(round(seconds)), 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _rows(items: dict[str, object]) -> str:
    return "".join(f"<tr><th>{html.escape(key)}</th><td>{html.escape(str(value))}</td></tr>" for key, value in items.items())


def _warning_rows(warnings: list[AnalysisWarning]) -> str:
    if not warnings:
        return '<tr><td colspan="6" class="muted">Автоматические предупреждения не обнаружены.</td></tr>'
    rows = []
    for warning in warnings:
        severity = {"high": "Высокая", "medium": "Средняя", "low": "Низкая"}.get(warning.severity, warning.severity)
        peak = "—" if warning.peak_value is None else f"{warning.peak_value:.3f} {html.escape(warning.unit)}"
        rows.append(
            f'<tr><td><span class="badge {html.escape(warning.severity)}">{html.escape(severity)}</span></td>'
            f"<td>{html.escape(warning.title)}</td><td>{_duration(warning.start_s)}</td><td>{_duration(warning.end_s)}</td>"
            f"<td>{peak}</td><td>{html.escape(warning.description)}</td></tr>"
        )
    return "".join(rows)


def _issue_rows(log: ChargerLog) -> str:
    if not log.issues:
        return '<tr><td colspan="3" class="muted">Повреждённых строк не найдено.</td></tr>'
    return "".join(
        f"<tr><td>{issue.line_number}</td><td>{html.escape(issue.message)}</td><td><code>{html.escape(issue.line)}</code></td></tr>"
        for issue in log.issues[:200]
    )


def _chart_sections(figures: list[tuple[str, str, go.Figure]]) -> tuple[str, str]:
    cards, options = [], []
    for group, description, dashboard in figures:
        for chart in independent_charts(dashboard):
            index = len(cards)
            title = str(chart.layout.meta["chart_title"])
            chart_id = f"chart-{index}"
            options.append(f'<option value="{index}">{index + 1:02d} · {html.escape(group)} / {html.escape(title)}</option>')
            # Escape '<' in JSON to keep filenames and trace labels out of HTML parsing.
            payload = chart.to_json().replace("<", "\\u003c").replace("&", "\\u0026")
            cards.append(f'''<section class="card chart-card" id="{chart_id}" aria-labelledby="{chart_id}-title">
<div class="chart-top"><h2 id="{chart_id}-title"><span class="chart-number">{index + 1:02d}</span>{html.escape(title)}</h2><span class="chart-unit">{html.escape(group)}</span></div>
<p class="chart-description">{html.escape(description)}</p>
<div class="chart-tools" role="group" aria-label="Управление графиком {index + 1}">
<button type="button" data-action="left" title="Сдвинуть интервал влево" aria-label="Сдвинуть влево">←</button>
<button type="button" data-action="right" title="Сдвинуть интервал вправо" aria-label="Сдвинуть вправо">→</button>
<button type="button" data-action="zoom-in" title="Приблизить по горизонтали">X +</button>
<button type="button" data-action="zoom-out" title="Отдалить по горизонтали">X −</button>
<button type="button" data-action="y-in" title="Приблизить по вертикали">Y +</button>
<button type="button" data-action="y-out" title="Отдалить по вертикали">Y −</button>
<button type="button" data-action="fit-y" title="Подобрать вертикальный масштаб по видимому участку">Авто Y</button>
<button type="button" data-action="box" aria-pressed="false" title="Выделить прямоугольник мышью для увеличения">Выделение</button>
<button type="button" data-action="reset">Сброс</button><span class="spacer"></span>
<button type="button" data-action="export" title="Сохранить этот график как PNG">PNG</button>
<button type="button" data-action="expand" aria-expanded="false">Развернуть</button>
</div>
<div class="plot-host" id="plot-{index}"></div><script type="application/json" class="plot-data">{payload}</script>
<div class="chart-range">
<label class="slider-label">Масштаб <input type="range" min="0" max="1000" value="0" step="1" data-control="zoom" aria-label="Масштаб графика {index + 1}"></label>
<label class="slider-label">Позиция <input type="range" min="0" max="1000" value="0" step="1" data-control="position" aria-label="Позиция графика {index + 1}"></label>
<output class="range-text" aria-label="Видимый диапазон"></output>
</div></section>''')
    nav = f'''<nav class="chart-nav" aria-label="Переход между графиками">
<button type="button" id="chart-prev" aria-label="Предыдущий график">↑</button>
<select id="chart-select" aria-label="Выбрать график">{''.join(options)}</select>
<button type="button" id="chart-next" aria-label="Следующий график">↓</button>
<span class="help">Перетаскивайте график · меняйте границы в нижнем обзоре · Esc — свернуть</span></nav>'''
    return nav, "".join(cards)


def _document(title: str, body: str, *, standalone: bool) -> str:
    bundle = f"<script>{get_plotlyjs()}</script>" if standalone else f'<script src="https://cdn.plot.ly/plotly-{get_plotlyjs_version()}.min.js"></script>'
    return f'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{ASSETS.joinpath('report.css').read_text(encoding='utf-8')}</style>
{bundle}</head><body><main>{body}<p class="footer">iCharger Analyzer · исходные точки сохранены · Ah — заряд, Wh — энергия</p></main>
<script id="plot-config" type="application/json">{json.dumps(PLOTLY_CONFIG)}</script>
<script>{ASSETS.joinpath('report.js').read_text(encoding='utf-8')}</script>
<noscript>Для интерактивных графиков включите JavaScript. Числовая сводка доступна выше.</noscript></body></html>'''


def _counter_inputs_html(log: ChargerLog, result: AnalysisResult) -> str:
    """Show the actual fields and one accepted nonzero counter interval."""
    first, last = log.telemetry[0], log.telemetry[-1]
    s = result.summary
    if s.battery_energy_source == "cells":
        indices = [i for i in range(11, 21) if any(r.raw_values[i] > 0 for r in log.telemetry)]
        fields = ", ".join(str(i + 1) for i in indices)
        raw_voltage = " + ".join(str(first.raw_values[i]) for i in indices)
        voltage_label = "Напряжение банки" if len(indices) == 1 else "Сумма напряжений банок"
    else:
        fields, raw_voltage, voltage_label = "8", str(first.raw_values[7]), "Напряжение силового выхода"
    rows = _rows({
        "Счётчик ёмкости · поле 9 (индекс 8)": f"{first.raw_values[8]} → {last.raw_values[8]} mAh",
        f"{voltage_label} · поле {fields}": f"Начало: ({raw_voltage}) / 1000 = {s.start_battery_voltage_v:.3f} V",
    })
    example = ""
    frame = result.telemetry
    candidates = frame.index[(frame["counter_delta_mah_signed"] != 0) & ~frame["counter_energy_skipped"]]
    if len(candidates):
        index = int(candidates[0])
        previous, current = frame.iloc[index - 1], frame.iloc[index]
        delta = abs(float(current["counter_delta_mah_signed"]))
        increment = abs(float(current["counter_incremental_energy_wh_signed"]))
        example = (
            f'<p class="note">Пример из этого лога, {previous["time_s"]:g}–{current["time_s"]:g} s: '
            f'счётчик {previous["capacity_mah_signed"]:g} → {current["capacity_mah_signed"]:g} mAh. '
            f'ΔE = ({previous["battery_voltage_v"]:.3f} + {current["battery_voltage_v"]:.3f}) / 2 '
            f'× {delta:g} / 1000 = <b>{increment:.7f} Wh</b>.</p>'
        )
    return f'<div class="table-wrap"><table>{rows}</table></div>{example}'


def write_report(log: ChargerLog, result: AnalysisResult, figures: list[go.Figure], output_file: Path, *, standalone: bool = True) -> None:
    s = result.summary
    source = "по балансиру" if s.battery_energy_source == "cells" else "по силовому выходу"
    discharge = s.counter_discharge_energy_wh > 0
    charged = s.counter_charge_energy_wh > 0
    energy = s.counter_discharge_energy_wh if discharge else s.counter_charge_energy_wh
    label = "Отдано батареей" if discharge else "Принято батареей"
    mode = "Заряд + разряд" if discharge and charged else "Разряд" if discharge else "Заряд" if charged else "Покой"
    kpis = [
        (label, _fmt(energy, 2, " Wh"), f"Счётчик mAh · {source}", "primary"),
        ("Ёмкость по счётчику", _fmt(s.capacity_counter_ah, 3, " Ah"), "Изменение счётчика mAh / 1000", ""),
        ("Конечное напряжение батареи", _fmt(s.end_battery_voltage_v, 3, " V"), f"Начало: {s.start_battery_voltage_v:.3f} V", ""),
        ("Длительность", _duration(s.duration_s), f"{s.samples:,} отсчётов · {s.nominal_sample_rate_hz:g} Hz".replace(",", " "), ""),
    ]
    kpi_html = "".join(
        f'<div class="kpi {cls}"><div class="kpi-label">{html.escape(label)}</div><div class="kpi-value">{html.escape(value)}</div><div class="kpi-note">{html.escape(note)}</div></div>'
        for label, value, note, cls in kpis
    )
    cell_label = f"{s.detected_cells}S по балансиру" if s.detected_cells else "Балансир не записан"
    metadata = {
        "Модель / прошивка": f"{log.header.model or '—'} / {log.header.firmware or '—'}",
        "Аппаратная версия": log.header.hardware or "—",
        "Серийный номер": log.header.serial_number or "—",
        "Канал / код батареи": f"{log.telemetry[0].channel} / {log.telemetry[0].battery_type_code}",
        "Интервал: медиана / min / max": f"{s.median_sample_interval_s:g} / {s.min_sample_interval_s:g} / {s.max_sample_interval_s:g} s",
        "Интервал: среднее / СКО": f"{s.mean_sample_interval_s:.3f} / {s.sample_interval_std_s:.3f} s",
        "Разрывы / повторы времени": f"{s.telemetry_gap_count} / {s.duplicate_timestamp_count}",
        "Исключено из интеграла": f"{s.integration_omitted_s:g} s",
        "Пакетов 128": s.status_record_count,
        "Максимальная мощность выхода": _fmt(s.peak_abs_power_w, 2, " W"),
        "Макс. внутренняя / внешняя температура": f"{_fmt(s.max_internal_temp_c, 1)} / {_fmt(s.max_external_temp_c, 1)} °C",
        "Последнее полное IR (оценка)": _fmt(s.latest_total_ir_mohm, 1, " mΩ"),
    }
    energy_rows = _rows({
        "По счётчику: отдано / принято": f"{s.counter_discharge_energy_wh:.6f} / {s.counter_charge_energy_wh:.6f} Wh",
        "Изменение счётчика ёмкости": f"{s.capacity_counter_ah:.3f} Ah",
        "Батарея: начало → конец": f"{s.start_battery_voltage_v:.3f} → {s.end_battery_voltage_v:.3f} V",
        "Исключённых приращений / скачков счётчика": f"{s.counter_energy_skipped_intervals} / {s.counter_jump_count}",
    })
    limitation = ""
    if s.integration_omitted_s:
        limitation += f'<p class="note warn">В расчёт Wh и интеграл Ah не вошли разрывы суммарно {s.integration_omitted_s:g} s. Показана энергия только покрытых данными участков.</p>'
    if s.battery_energy_source == "output":
        limitation += f'<p class="note">{html.escape(s.battery_energy_source_note)} Энергия на самой батарее без балансирного измерения отдельно не определяется.</p>'
    if discharge and charged:
        limitation += f'<p class="note">Смешанный цикл: отдано {s.counter_discharge_energy_wh:.2f} Wh, принято {s.counter_charge_energy_wh:.2f} Wh. Счётчик Ah показывает изменение от первой строки; энергия направлений приведена отдельно.</p>'
    if s.counter_jump_count:
        limitation += f'<p class="note warn">Подозрительные скачки или сбросы счётчика: {s.counter_jump_count}. Эти приращения исключены из расчёта Wh.</p>'
    nav, charts = _chart_sections([
        ("По времени" if i == 0 else "По ёмкости", "Масштаб, диапазон и легенда действуют только на этот график.", fig)
        for i, fig in enumerate(figures)
    ])
    name = html.escape(log.source_file.name)
    machine_summary = html.escape(json.dumps(s.as_dict(), ensure_ascii=False, indent=2))
    body = f'''<header><div class="eyebrow">Battery lab / iCharger</div><div class="header-row"><h1>Энергия и ёмкость батареи</h1><span class="pill">{mode} · {html.escape(cell_label)}</span></div><p class="subtitle">{name}</p></header>
<section class="kpis">{kpi_html}</section>
<div class="facts"><span>Батарея <b>{s.start_battery_voltage_v:.3f} → {s.end_battery_voltage_v:.3f} V</b></span><span>Пик разряда <b>{s.peak_discharge_current_a:.2f} A</b></span><span>Мин. банка <b>{_fmt(s.min_cell_voltage_v, 3, ' V')}</b></span><span>Разрывы <b>{s.telemetry_gap_count}</b></span><span>Ошибки строк <b>{len(log.issues)}</b></span></div>
{limitation}
<details class="card" open><summary>Расчёт Wh: счётчик ёмкости и напряжение банки</summary><div class="detail-grid"><div>{_counter_inputs_html(log, result)}<div class="table-wrap"><table>{energy_rows}</table></div></div><div>
<p>{html.escape(s.battery_energy_source_note)}</p>
<p class="formula">ΔQᵢ = |qᵢ − qᵢ₋₁| / 1000<br>Uсрᵢ = (Uᵢ₋₁ + Uᵢ) / 2<br>E = Σ Uсрᵢ × ΔQᵢ</p>
<p class="muted">q — знаковый счётчик в mAh, U — напряжение в V, ΔQ — приращение в Ah, E — энергия в Wh. Отданная энергия суммируется по отрицательным приращениям счётчика, принятая — по положительным. Время используется для оси графика и проверки разрывов. Дополнительное деление на 3600 не требуется.</p>
<p class="note">Wh — энергия за записанный участок испытания. Полную доступную энергию можно оценить по полному разряду при заданных условиях. Умножение Ah на начальное напряжение не учитывает изменение напряжения.</p>
<p class="note">Для нескольких последовательных банок U = сумма их напряжений. Балансирные каналы должны охватывать всю батарею. Ток не входит в эту формулу; он используется только при проверке подозрительных скачков счётчика.</p>
</div></div></details>
<details class="card"><summary>Устройство и качество записи</summary><div class="table-wrap"><table>{_rows(metadata)}</table></div><p class="note">Масштаб сопротивления пакета 128 принят по структуре файлов и сумме полей; это оценка. Сырые поля сохраняются парсером.</p></details>
<div class="section-heading"><h2>Графики</h2><span class="help">Независимое управление</span></div>{nav}{charts}
<details class="card"><summary>События и предупреждения · {len(result.warnings)}</summary><div class="table-wrap"><table><thead><tr><th>Уровень</th><th>Событие</th><th>Начало</th><th>Конец</th><th>Пик</th><th>Описание</th></tr></thead><tbody>{_warning_rows(result.warnings)}</tbody></table></div></details>
<details class="card"><summary>Ошибки разбора · {len(log.issues)}</summary><p class="muted">Телеметрия: {s.samples}. Неподдерживаемые пакеты: {html.escape(str(log.unsupported_packet_counts) if log.unsupported_packet_counts else 'нет')}. Показаны первые 200 ошибок.</p><div class="table-wrap"><table><thead><tr><th>Строка</th><th>Ошибка</th><th>Фрагмент</th></tr></thead><tbody>{_issue_rows(log)}</tbody></table></div></details>
<details class="card"><summary>Сводка JSON</summary><pre>{machine_summary}</pre></details>'''
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(_document(f"iCharger — {log.source_file.name}", body, standalone=standalone), encoding="utf-8")


def write_comparison_report(rows: list[dict[str, object]], figures: list[tuple[str, str, go.Figure]], output_file: Path, *, comparison_step_s: float, standalone: bool = True) -> None:
    table_rows = "".join(
        '<tr>'
        f'<td><a href="{html.escape(str(row["report"]), quote=True)}">{html.escape(str(row["file"]))}</a></td>'
        f'<td>{row["cells"]}</td><td>{float(row["duration_h"]):.2f}</td>'
        f'<td>{float(row["capacity_ah"]):.3f}</td><td>{float(row["counter_discharge_energy_wh"]):.2f}</td>'
        f'<td>{float(row["counter_charge_energy_wh"]):.2f}</td>'
        f'<td>{"Банки" if row["battery_energy_source"] == "cells" else "Силовой выход"}</td>'
        f'<td>{float(row["integration_omitted_s"]):g}</td><td>{float(row["median_interval_s"]):g}</td>'
        f'<td>{int(row["gap_count"])}</td><td>{html.escape(str(row["min_cell_v"]))}</td></tr>'
        for row in rows
    )
    nav, charts = _chart_sections(figures)
    body = f'''<header><div class="eyebrow">Battery lab / iCharger</div><h1>Сравнение испытаний</h1><p class="subtitle">{len(rows)} логов · отдельная линия для каждого файла · общий шаг {comparison_step_s:g} s</p></header>
<section class="card"><h2>Результаты</h2><div class="table-wrap"><table class="summary-table"><thead><tr><th>Файл</th><th>Банки</th><th>Часы</th><th>Счётчик, Ah</th><th>Отдано, Wh</th><th>Принято, Wh</th><th>Источник U</th><th>Пропущено, s</th><th>Период, s</th><th>Разрывы</th><th>Min cell, V</th></tr></thead><tbody>{table_rows}</tbody></table></div></section>
<details class="card"><summary>Как читать сравнение</summary><p class="note">Энергия рассчитана по приращениям счётчика mAh: E = Σ Uср × |Δq| / 1000. Только сравнительные линии интерполированы на сетку {comparison_step_s:g} s. Отдельные отчёты сохраняют все точки. Нажмите на имя файла в легенде, чтобы скрыть или показать линию на выбранном графике.</p><p class="note">Источник напряжения указан для каждого файла. Расчёт по балансиру и по силовому выходу относится к разным точкам измерения.</p></details>
<div class="section-heading"><h2>Графики</h2><span class="help">Независимое управление</span></div>{nav}{charts}'''
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(_document("iCharger — сравнение испытаний", body, standalone=standalone), encoding="utf-8")
