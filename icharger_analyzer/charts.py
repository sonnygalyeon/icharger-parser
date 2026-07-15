"""Interactive Plotly figures for iCharger analysis."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .analytics import AnalysisWarning, available_cell_columns, available_ir_columns

PLOTLY_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "scrollZoom": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
}


def _base_layout(fig: go.Figure, title: str, height: int) -> None:
    fig.update_layout(
        template="plotly_dark",
        title={"text": title, "x": 0.5, "xanchor": "center"},
        height=height,
        margin={"l": 70, "r": 30, "t": 75, "b": 50},
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.01, "xanchor": "center", "x": 0.5},
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        font={"color": "#e5e7eb"},
    )
    fig.update_xaxes(showgrid=True, gridcolor="#334155", zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="#334155", zeroline=False)


def _add_warning_regions(fig: go.Figure, warnings: Iterable[AnalysisWarning], rows: int) -> None:
    del rows  # One paper-referenced rectangle spans every subplot.
    high_warnings = [warning for warning in warnings if warning.severity == "high"][:20]
    shapes = list(fig.layout.shapes) if fig.layout.shapes else []
    for warning in high_warnings:
        end_s = warning.end_s if warning.end_s > warning.start_s else warning.start_s + 0.5
        shapes.append(
            dict(
                type="rect",
                xref="x",
                yref="paper",
                x0=warning.start_s,
                x1=end_s,
                y0=0,
                y1=1,
                fillcolor="rgba(239,68,68,0.08)",
                line_width=0,
                layer="below",
            )
        )
    if shapes:
        fig.update_layout(shapes=shapes)


def create_time_dashboard(
    telemetry: pd.DataFrame,
    status: pd.DataFrame,
    warnings: list[AnalysisWarning],
) -> go.Figure:
    cell_columns = available_cell_columns(telemetry)
    has_ir = not status.empty and (
        status.get("total_ir_mohm", pd.Series(dtype=float)).notna().any()
        or bool(available_ir_columns(status))
    )
    rows = 7 if has_ir else 6
    titles = [
        "Напряжение батареи и входа",
        "Ток и мощность",
        "Отданная/принятая ёмкость и энергия",
        "Температура",
        "Напряжения банок",
        "Разброс напряжений банок",
    ]
    if has_ir:
        titles.append("Внутреннее сопротивление (пакет 128, масштаб inferred)")

    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.025,
        subplot_titles=titles,
        specs=[[{"secondary_y": True}] if row in (2, 3) else [{}] for row in range(1, rows + 1)],
    )

    x = telemetry["time_s"]
    fig.add_trace(go.Scattergl(x=x, y=telemetry["pack_voltage_v"], name="Батарея, V", mode="lines"), row=1, col=1)
    fig.add_trace(go.Scattergl(x=x, y=telemetry["input_voltage_v"], name="Вход, V", mode="lines", opacity=0.65), row=1, col=1)

    fig.add_trace(go.Scattergl(x=x, y=telemetry["current_a"], name="Ток, A", mode="lines"), row=2, col=1, secondary_y=False)
    fig.add_trace(go.Scattergl(x=x, y=telemetry["power_w"], name="Мощность, W", mode="lines", opacity=0.75), row=2, col=1, secondary_y=True)

    fig.add_trace(go.Scattergl(x=x, y=telemetry["capacity_counter_ah"], name="Счётчик ёмкости, Ah", mode="lines"), row=3, col=1, secondary_y=False)
    fig.add_trace(go.Scattergl(x=x, y=telemetry["energy_throughput_wh"], name="Энергия, Wh", mode="lines"), row=3, col=1, secondary_y=True)

    if telemetry["internal_temp_c"].notna().any():
        fig.add_trace(go.Scattergl(x=x, y=telemetry["internal_temp_c"], name="Внутренняя, °C", mode="lines"), row=4, col=1)
    if telemetry["external_temp_c"].notna().any():
        fig.add_trace(go.Scattergl(x=x, y=telemetry["external_temp_c"], name="Внешняя, °C", mode="lines"), row=4, col=1)

    for index, column in enumerate(cell_columns, start=1):
        fig.add_trace(go.Scattergl(x=x, y=telemetry[column], name=f"Банка {index}", mode="lines"), row=5, col=1)

    if cell_columns:
        fig.add_trace(go.Scattergl(x=x, y=telemetry["cell_delta_v"] * 1000.0, name="Δ банок, mV", mode="lines"), row=6, col=1)
        fig.add_hline(y=20, line_dash="dash", opacity=0.55, row=6, col=1)
        fig.add_hline(y=50, line_dash="dash", opacity=0.55, row=6, col=1)

    if has_ir:
        sx = status["time_s"]
        if status["total_ir_mohm"].notna().any():
            fig.add_trace(go.Scatter(x=sx, y=status["total_ir_mohm"], name="Полное IR, mΩ", mode="lines+markers"), row=7, col=1)
        if status["cells_ir_sum_mohm"].notna().any():
            fig.add_trace(go.Scatter(x=sx, y=status["cells_ir_sum_mohm"], name="Сумма IR банок, mΩ", mode="lines+markers"), row=7, col=1)
        for index, column in enumerate(available_ir_columns(status), start=1):
            fig.add_trace(go.Scatter(x=sx, y=status[column], name=f"IR банки {index}, mΩ", mode="lines+markers", opacity=0.75), row=7, col=1)

    fig.update_yaxes(title_text="V", row=1, col=1)
    fig.update_yaxes(title_text="A", row=2, col=1, secondary_y=False)
    fig.update_yaxes(title_text="W", row=2, col=1, secondary_y=True)
    fig.update_yaxes(title_text="Ah", row=3, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Wh", row=3, col=1, secondary_y=True)
    fig.update_yaxes(title_text="°C", row=4, col=1)
    fig.update_yaxes(title_text="V", row=5, col=1)
    fig.update_yaxes(title_text="mV", row=6, col=1)
    if has_ir:
        fig.update_yaxes(title_text="mΩ", row=7, col=1)
    fig.update_xaxes(title_text="Время, s", row=rows, col=1)

    _add_warning_regions(fig, warnings, rows)
    _base_layout(fig, "iCharger — временные графики", 390 * rows)
    return fig


def create_discharge_curve(telemetry: pd.DataFrame) -> go.Figure:
    cell_columns = available_cell_columns(telemetry)
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=("Напряжение батареи по отданной ёмкости", "Напряжения банок по отданной ёмкости"),
    )
    x = telemetry["capacity_counter_ah"]
    fig.add_trace(go.Scattergl(x=x, y=telemetry["pack_voltage_v"], name="Батарея, V", mode="lines"), row=1, col=1)
    for index, column in enumerate(cell_columns, start=1):
        fig.add_trace(go.Scattergl(x=x, y=telemetry[column], name=f"Банка {index}", mode="lines"), row=2, col=1)
    fig.update_yaxes(title_text="V", row=1, col=1)
    fig.update_yaxes(title_text="V", row=2, col=1)
    fig.update_xaxes(title_text="Ёмкость, Ah", row=2, col=1)
    _base_layout(fig, "Разрядные кривые", 900)
    return fig


def create_comparison_figure(series: list[tuple[str, pd.DataFrame]]) -> go.Figure:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=("Напряжение батареи", "Минимальная банка"),
    )
    for label, frame in series:
        fig.add_trace(go.Scattergl(x=frame["capacity_counter_ah"], y=frame["pack_voltage_v"], name=label, mode="lines"), row=1, col=1)
        if frame["cell_min_v"].notna().any():
            fig.add_trace(go.Scattergl(x=frame["capacity_counter_ah"], y=frame["cell_min_v"], name=f"{label}: min cell", mode="lines", showlegend=False), row=2, col=1)
    fig.update_yaxes(title_text="V", row=1, col=1)
    fig.update_yaxes(title_text="V", row=2, col=1)
    fig.update_xaxes(title_text="Ёмкость, Ah", row=2, col=1)
    _base_layout(fig, "Сравнение логов по отданной ёмкости", 950)
    return fig
