"""
visualization/plotly_graphs.py

Построение интерактивных графиков Plotly для логов iCharger.
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go

from analytics.statistics import Statistics
from analytics.anomalies import Anomaly


class PlotlyGraphs:
    """
    Построение интерактивного Dashboard.
    """

    def __init__(self) -> None:

        self.background = "#151515"
        self.grid = "#3A3A3A"
        self.font = "#EEEEEE"

        self.colors = {
            "voltage": "#4CAF50",
            "current": "#03A9F4",
            "power": "#FF9800",
            "temperature": "#F44336",
            "delta": "#E91E63",
        }

    # =====================================================

    def create_dashboard(
        self,
        df: pd.DataFrame,
        statistics: Statistics,
        anomalies: Iterable[Anomaly] = (),
    ) -> go.Figure:
        """
        Создать интерактивный Dashboard.
        """

        figure = make_subplots(
            rows=6,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            subplot_titles=(
                "Voltage",
                "Current",
                "Power",
                "Temperature",
                "Cell Voltages",
                "Cell Delta",
            ),
        )

        self._create_voltage(figure, df)
        self._create_current(figure, df)
        self._create_power(figure, df)
        self._create_temperature(figure, df)
        self._create_cells(figure, df)
        self._create_delta(figure, df)

        self._draw_anomalies(
            figure,
            df,
            anomalies,
        )

        self._apply_layout(
            figure,
            statistics,
        )

        return figure

    # =====================================================

    def _create_voltage(
        self,
        fig: go.Figure,
        df: pd.DataFrame,
    ) -> None:

        fig.add_trace(

            go.Scatter(
                x=df["time_s"],
                y=df["voltage"],
                mode="lines",
                name="Voltage",
                line=dict(
                    color=self.colors["voltage"],
                    width=2,
                ),
            ),

            row=1,
            col=1,
        )

    # =====================================================

    def _create_current(
        self,
        fig: go.Figure,
        df: pd.DataFrame,
    ) -> None:

        fig.add_trace(

            go.Scatter(
                x=df["time_s"],
                y=df["current"],
                mode="lines",
                name="Current",
                line=dict(
                    color=self.colors["current"],
                    width=2,
                ),
            ),

            row=2,
            col=1,
        )

    # =====================================================

    def _create_power(
        self,
        fig: go.Figure,
        df: pd.DataFrame,
    ) -> None:

        fig.add_trace(

            go.Scatter(
                x=df["time_s"],
                y=df["power"],
                mode="lines",
                name="Power",
                line=dict(
                    color=self.colors["power"],
                    width=2,
                ),
            ),

            row=3,
            col=1,
        )

    # =====================================================

    def _create_temperature(
        self,
        fig: go.Figure,
        df: pd.DataFrame,
    ) -> None:
        """
        Построение графика температуры.
        """

        fig.add_trace(
            go.Scatter(
                x=df["time_s"],
                y=df["temperature"],
                mode="lines",
                name="Temperature",
                line=dict(
                    color=self.colors["temperature"],
                    width=2,
                ),
            ),
            row=4,
            col=1,
        )

    # =====================================================

    def _create_cells(
        self,
        fig: go.Figure,
        df: pd.DataFrame,
    ) -> None:
        """
        Построение графиков напряжения всех банок.
        """

        palette = [
            "#1f77b4",
            "#ff7f0e",
            "#2ca02c",
            "#d62728",
            "#9467bd",
            "#8c564b",
            "#e377c2",
            "#7f7f7f",
            "#bcbd22",
            "#17becf",
        ]

        for index in range(1, 11):

            column = f"cell{index}"

            if column not in df.columns:
                continue

            if df[column].isna().all():
                continue

            fig.add_trace(
                go.Scatter(
                    x=df["time_s"],
                    y=df[column],
                    mode="lines",
                    name=f"Cell {index}",
                    line=dict(
                        color=palette[index - 1],
                        width=1.5,
                    ),
                ),
                row=5,
                col=1,
            )

    # =====================================================

    def _create_delta(
        self,
        fig: go.Figure,
        df: pd.DataFrame,
    ) -> None:
        """
        Построение графика разбаланса банок.
        """

        fig.add_trace(
            go.Scatter(
                x=df["time_s"],
                y=df["cell_delta"],
                mode="lines",
                name="Cell Delta",
                line=dict(
                    color=self.colors["delta"],
                    width=2,
                ),
            ),
            row=6,
            col=1,
        )

    # =====================================================

    def _draw_anomalies(
        self,
        fig: go.Figure,
        df: pd.DataFrame,
        anomalies: Iterable[Anomaly],
    ) -> None:
        """
        Отрисовка аномалий поверх графиков.
        """

        if not anomalies:
            return

        for anomaly in anomalies:

            row = 1

            if anomaly.anomaly.value == "Current Spike":
                row = 2

            elif anomaly.anomaly.value == "Power Spike":
                row = 3

            elif anomaly.anomaly.value == "Temperature Spike":
                row = 4

            elif anomaly.anomaly.value == "Cell Imbalance":
                row = 6

            if anomaly.sample >= len(df):
                continue

            point = df.iloc[anomaly.sample]

            y_column = {
                1: "voltage",
                2: "current",
                3: "power",
                4: "temperature",
                6: "cell_delta",
            }[row]

            fig.add_trace(
                go.Scatter(
                    x=[point["time_s"]],
                    y=[point[y_column]],
                    mode="markers",
                    marker=dict(
                        size=10,
                        color="red",
                        symbol="x",
                    ),
                    name=anomaly.anomaly.value,
                    hovertemplate=(
                        "<b>%{text}</b><br>"
                        "Time: %{x:.2f}s<br>"
                        "Value: %{y}<extra></extra>"
                    ),
                    text=[anomaly.message],
                    showlegend=False,
                ),
                row=row,
                col=1,
            )
    
    # =====================================================

    def _apply_layout(
        self,
        fig: go.Figure,
        statistics: Statistics,
    ) -> None:
        """
        Применение общего оформления Dashboard.
        """

        title = (
            "iCharger Analysis Dashboard"
            "<br>"
            f"<sup>"
            f"Samples: {statistics.samples} | "
            f"Duration: {statistics.duration_s:.1f} s | "
            f"Max Power: {statistics.max_power:.2f} | "
            f"Max Temperature: {statistics.max_temperature:.2f}"
            f"</sup>"
        )

        fig.update_layout(

            title=dict(
                text=title,
                x=0.5,
                xanchor="center",
            ),

            template="plotly_dark",

            paper_bgcolor=self.background,
            plot_bgcolor=self.background,

            font=dict(
                color=self.font,
                size=12,
            ),

            hovermode="x unified",

            height=1500,

            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5,
            ),

            margin=dict(
                l=70,
                r=30,
                t=80,
                b=40,
            ),
        )

        fig.update_xaxes(

            title_text="Time [s]",

            showgrid=True,

            gridcolor=self.grid,

            zeroline=False,
        )

        fig.update_yaxes(

            showgrid=True,

            gridcolor=self.grid,

            zeroline=False,
        )

        subplot_titles = [
            ("Voltage", "Voltage"),
            ("Current", "Current"),
            ("Power", "Power"),
            ("Temperature", "Temperature"),
            ("Cells", "Voltage"),
            ("Cell Delta", "Delta"),
        ]

        for row, (_, ylabel) in enumerate(subplot_titles, start=1):

            fig.update_yaxes(
                title_text=ylabel,
                row=row,
                col=1,
            )

    # =====================================================

    @staticmethod
    def save_html(
        fig: go.Figure,
        filename: str,
    ) -> None:
        """
        Сохранить Dashboard в HTML.
        """

        fig.write_html(
            filename,
            include_plotlyjs="cdn",
            full_html=True,
        )

    # =====================================================

    @staticmethod
    def save_png(
        fig: go.Figure,
        filename: str,
        width: int = 1920,
        height: int = 1080,
        scale: int = 2,
    ) -> None:
        """
        Экспорт изображения.

        Требуется пакет kaleido.
        """

        fig.write_image(
            filename,
            width=width,
            height=height,
            scale=scale,
        )

    # =====================================================

    @staticmethod
    def show(
        fig: go.Figure,
    ) -> None:
        """
        Открыть интерактивное окно Plotly.
        """

        fig.show()