"""
reports/exporter.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go


class Exporter:

    @staticmethod
    def export_dataframe(
        df: pd.DataFrame,
        filename: Path,
    ) -> None:

        df.to_csv(
            filename,
            index=False,
        )

    @staticmethod
    def export_dashboard(
        fig: go.Figure,
        filename: Path,
    ) -> None:

        fig.write_html(
            filename,
            include_plotlyjs="cdn",
        )

    @staticmethod
    def export_png(
        fig: go.Figure,
        filename: Path,
    ) -> None:

        fig.write_image(filename)

    @staticmethod
    def save_text(
        text: str,
        filename: Path,
    ) -> None:

        filename.write_text(
            text,
            encoding="utf-8",
        )