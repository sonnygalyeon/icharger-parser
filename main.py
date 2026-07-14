"""
main.py

Точка входа iCharger Analyzer.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from parser.parser import LogParser

from analytics.dataframe import DataFrameBuilder
from analytics.statistics import StatisticsCalculator
from analytics.derivatives import DerivativesCalculator
from analytics.battery import BatteryAnalyzer
from analytics.anomalies import AnomalyDetector

from visualization.plotly_graphs import PlotlyGraphs

from reports.html_report import HtmlReport


# ==========================================================
# Pipeline
# ==========================================================


class AnalyzerPipeline:

    """
    Полный цикл анализа.
    """

    def run(
        self,
        input_file: Path,
        output_dir: Path,
    ) -> None:

        print("=" * 60)
        print("iCharger Analyzer")
        print("=" * 60)

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        # -----------------------------------------------------

        print("[1/8] Parsing log...")

        parser = LogParser()

        log = parser.parse(input_file)

        # -----------------------------------------------------

        print("[2/8] Building DataFrame...")

        df = DataFrameBuilder().build(log)

        # -----------------------------------------------------

        print("[3/8] Calculating derivatives...")

        DerivativesCalculator().calculate(df)

        # -----------------------------------------------------

        print("[4/8] Calculating statistics...")

        statistics = StatisticsCalculator().calculate(df)

        # -----------------------------------------------------

        print("[5/8] Battery analysis...")

        battery = BatteryAnalyzer().analyze(df)

        # -----------------------------------------------------

        print("[6/8] Detecting anomalies...")

        anomalies = AnomalyDetector().detect(df)

        # -----------------------------------------------------

        print("[7/8] Creating dashboard...")

        graphs = PlotlyGraphs()

        figure = graphs.create_dashboard(
            df,
            statistics,
            anomalies,
        )

        dashboard_file = output_dir / "dashboard.html"

        graphs.save_html(
            figure,
            dashboard_file,
        )

        # -----------------------------------------------------

        print("[8/8] Generating report...")

        plotly_html = figure.to_html(
            full_html=False,
            include_plotlyjs="cdn",
        )

        report = HtmlReport()

        html = report.build(
            statistics=statistics,
            battery=battery,
            anomalies=anomalies,
            plotly_html=plotly_html,
            source_file=input_file.name,
        )

        report_file = output_dir / "report.html"

        report.save(
            html,
            report_file,
        )

        print()

        print("Analysis completed successfully.")

        print(f"Dashboard : {dashboard_file}")

        print(f"Report    : {report_file}")


# ==========================================================
# CLI
# ==========================================================


def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description="iCharger Analyzer",
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Path to iCharger log",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("output"),
        help="Output directory",
    )

    return parser.parse_args()


# ==========================================================
# Entry Point
# ==========================================================


def main() -> int:

    args = parse_args()

    if not args.input.exists():

        print()

        print("Input file not found.")

        return 1

    AnalyzerPipeline().run(
        args.input,
        args.output,
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(main())