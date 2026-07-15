"""Command-line interface for iCharger Analyzer."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

from .analytics import AnalysisResult, analyze_log
from .charts import create_comparison_figure, create_discharge_curve, create_time_dashboard
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

    _write_summary_csv(comparison_rows, output_dir)
    if len(comparison_series) > 1:
        figure = create_comparison_figure(comparison_series)
        write_comparison_report(
            comparison_rows,
            figure,
            output_dir / "index.html",
            standalone=not args.cdn,
        )
        print(f"Comparison: {output_dir / 'index.html'}")

    return 1 if failures else 0
