"""
visualization/plotly_graphs.py

Построение интерактивных графиков Plotly
для логов iCharger.

Автор: iCharger Analyzer
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


class PlotlyGraphs:

    def __init__(self, theme: str = "plotly_white"):
        self.theme = theme

    def overview(self, df: pd.DataFrame) -> go.Figure:

        fig = make_subplots(
            rows=5,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            subplot_titles=[
                "Voltage",
                "Current",
                "Power",
                "Temperature",
                "Cell Delta"
            ]
        )

        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["voltage"],
                name="Voltage",
                mode="lines"
            ),
            row=1,
            col=1
        )

        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["current"],
                name="Current",
                mode="lines"
            ),
            row=2,
            col=1
        )

        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["power"],
                name="Power",
                mode="lines"
            ),
            row=3,
            col=1
        )

        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["temperature"],
                name="Temperature",
                mode="lines"
            ),
            row=4,
            col=1
        )

        if "cell_delta" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["cell_delta"],
                    name="Cell Delta",
                    mode="lines"
                ),
                row=5,
                col=1
            )

        fig.update_layout(
            template=self.theme,
            hovermode="x unified",
            height=1200,
            showlegend=False,
            title="iCharger Telemetry Overview"
        )

        fig.update_xaxes(title="Time (s)", row=5, col=1)

        return fig

    def save_html(self, figure: go.Figure, filename: str | Path):
        figure.write_html(
            filename,
            include_plotlyjs=True
        )

    def save_png(self, figure: go.Figure, filename: str | Path):
        figure.write_image(filename)