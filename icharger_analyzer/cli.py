"""Command-line interface for iCharger Analyzer."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

import pandas as pd

from .analytics import AnalysisResult, analyze_log
from .charts import (
    choose_comparison_step,
    create_comparison_progress_dashboard,
    create_comparison_time_dashboard,
    create_discharge_curve,
    create_time_dashboard,
    resample_for_comparison,
)
from .parser import IChargerParser
from .report import write_comparison_report, write_report


def _safe_stem(path: Path) -> str:
    value = re.sub(r"[^0-9A-Za-zА-Яа-яЁё._-]+", "_", path.stem).strip("._")
    return value or "icharger_log"


def _collect_inputs(raw_inputs: list[Path]) -> list[Path]:
    result: list[Path] = []
    for item in raw_inputs:
        if item.is_dir():
            result.extend(sorted(path for path in item.iterdir() if path.suffix.lower() in {".txt", ".log"}))
        elif item.is_file():
            result.append(item)
        else:
            raise FileNotFoundError(item)
    # Preserve order and remove duplicates by resolved path.
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in result:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(path)
    return unique


def _export_csv(result: AnalysisResult, output_dir: Path, stem: str) -> None:
    result.telemetry.to_csv(output_dir / f"{stem}_telemetry.csv", index=False, encoding="utf-8-sig")
    if not result.status.empty:
        result.status.to_csv(output_dir / f"{stem}_status.csv", index=False, encoding="utf-8-sig")


def _write_summary_csv(rows: list[dict[str, object]], output_dir: Path) -> None:
    if not rows:
        return
    with (output_dir / "summary.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="icharger-analyzer",
        description="Парсер и генератор интерактивных HTML-графиков для логов iCharger.",
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="TXT/LOG-файлы или каталог с логами")
    parser.add_argument("-o", "--output", type=Path, default=Path("output"), help="Каталог результата")
    parser.add_argument("--cdn", action="store_true", help="Подключать Plotly из CDN вместо автономного HTML")
    parser.add_argument("--no-csv", action="store_true", help="Не экспортировать декодированные CSV")
    parser.add_argument(
        "--comparison-step",
        type=float,
        default=None,
        metavar="SECONDS",
        help=(
            "Единый период общего графика в секундах. "
            "По умолчанию выбирается автоматически; исходные индивидуальные отчёты не прореживаются."
        ),
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    try:
        inputs = _collect_inputs(args.inputs)
    except OSError as exc:
        print(f"Ошибка входного пути: {exc}", file=sys.stderr)
        return 2
    if not inputs:
        print("Логи не найдены.", file=sys.stderr)
        return 2

    output_dir: Path = args.output
    output_dir.mkdir(parents=True, exist_ok=True)
    parser = IChargerParser()
    comparison_series = []
    comparison_rows: list[dict[str, object]] = []
    failures = 0

    for number, path in enumerate(inputs, start=1):
        print(f"[{number}/{len(inputs)}] {path}")
        try:
            log = parser.parse(path)
            result = analyze_log(log)
            stem = _safe_stem(path)
            report_name = f"{stem}_report.html"
            time_figure = create_time_dashboard(result.telemetry, result.status, result.warnings)
            curve_figure = create_discharge_curve(result.telemetry)
            write_report(
                log,
                result,
                [time_figure, curve_figure],
                output_dir / report_name,
                standalone=not args.cdn,
            )
            if not args.no_csv:
                _export_csv(result, output_dir, stem)

            summary = result.summary
            min_cell_text = "—" if summary.min_cell_voltage_v is None else f"{summary.min_cell_voltage_v:.3f}"
            comparison_rows.append(
                {
                    "file": path.name,
                    "report": report_name,
                    "cells": summary.detected_cells,
                    "duration_h": summary.duration_s / 3600.0,
                    "samples": summary.samples,
                    "median_interval_s": summary.median_sample_interval_s,
                    "mean_interval_s": summary.mean_sample_interval_s,
                    "min_interval_s": summary.min_sample_interval_s,
                    "max_interval_s": summary.max_sample_interval_s,
                    "sample_rate_hz": summary.nominal_sample_rate_hz,
                    "gap_count": summary.telemetry_gap_count,
                    "comparison_step_s": "",
                    "capacity_ah": summary.capacity_counter_ah,
                    "energy_wh": summary.integrated_energy_wh,
                    "end_voltage_v": summary.end_pack_voltage_v,
                    "min_cell_v": min_cell_text,
                    "parse_issues": summary.parse_issue_count,
                }
            )
            comparison_series.append((path.stem, result.telemetry))
            print(
                f"    OK: {summary.samples} samples, {summary.duration_s / 3600:.2f} h, "
                f"{summary.capacity_counter_ah:.3f} Ah -> {output_dir / report_name}"
            )
        except Exception as exc:  # CLI boundary: continue with remaining files.
            failures += 1
            print(f"    ERROR: {exc}", file=sys.stderr)

    if len(comparison_series) > 1:
        if args.comparison_step is not None and args.comparison_step <= 0:
            print("--comparison-step должен быть больше нуля.", file=sys.stderr)
            return 2
        comparison_step_s = choose_comparison_step(comparison_series, args.comparison_step)
        for row in comparison_rows:
            row["comparison_step_s"] = comparison_step_s
        if not args.no_csv:
            comparison_frames = []
            for label, frame in comparison_series:
                comparison_frame = resample_for_comparison(frame, comparison_step_s)
                comparison_frame.insert(0, "source", label)
                comparison_frames.append(comparison_frame)
            pd.concat(comparison_frames, ignore_index=True).to_csv(
                output_dir / "comparison_telemetry.csv",
                index=False,
                encoding="utf-8-sig",
            )
        time_comparison = create_comparison_time_dashboard(comparison_series, comparison_step_s)
        progress_comparison = create_comparison_progress_dashboard(comparison_series, comparison_step_s)
        write_comparison_report(
            comparison_rows,
            [
                (
                    "Все параметры по времени",
                    "Каждый файл показан отдельной линией на общей временной шкале.",
                    time_comparison,
                ),
                (
                    "Нормированное сравнение 0–100%",
                    "Удобно сравнивать испытания разной длительности, ёмкости и количества банок.",
                    progress_comparison,
                ),
            ],
            output_dir / "index.html",
            comparison_step_s=comparison_step_s,
            standalone=not args.cdn,
        )
        print(f"Comparison ({comparison_step_s:g} s grid): {output_dir / 'index.html'}")

    _write_summary_csv(comparison_rows, output_dir)
    return 1 if failures else 0
