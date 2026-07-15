"""Interactive Plotly figures for iCharger analysis."""

from __future__ import annotations

from collections.abc import Iterable
from math import floor, log10

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.colors import qualitative
from plotly.subplots import make_subplots

from .analytics import AnalysisWarning, available_cell_columns, available_ir_columns

PLOTLY_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "scrollZoom": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
}


ComparisonSeries = list[tuple[str, pd.DataFrame]]


def _base_layout(fig: go.Figure, title: str, height: int) -> None:
    fig.update_layout(
        template="plotly_dark",
        title={"text": title, "x": 0.5, "xanchor": "center"},
        height=height,
        margin={"l": 76, "r": 42, "t": 82, "b": 58},
        hovermode="x unified",
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.01,
            "xanchor": "center",
            "x": 0.5,
            "groupclick": "togglegroup",
        },
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        font={"color": "#e5e7eb"},
    )
    fig.update_xaxes(showgrid=True, gridcolor="#334155", zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="#334155", zeroline=False)


def _elapsed_customdata(frame: pd.DataFrame) -> np.ndarray | None:
    if "elapsed_time" not in frame:
        return None
    return frame[["elapsed_time"]].to_numpy()


def _line(
    frame: pd.DataFrame,
    x_column: str,
    y_column: str,
    name: str,
    *,
    unit: str,
    opacity: float = 1.0,
    showlegend: bool = True,
    legendgroup: str | None = None,
    line: dict[str, object] | None = None,
) -> go.Scattergl:
    return go.Scattergl(
        x=frame[x_column],
        y=frame[y_column],
        name=name,
        mode="lines",
        opacity=opacity,
        showlegend=showlegend,
        legendgroup=legendgroup,
        line=line,
        customdata=_elapsed_customdata(frame),
        hovertemplate=(
            "%{customdata[0]}<br>%{y:.4f} " + unit + "<extra>" + name + "</extra>"
            if "elapsed_time" in frame
            else "%{x:.4f}<br>%{y:.4f} " + unit + "<extra>" + name + "</extra>"
        ),
    )


def _add_warning_regions(fig: go.Figure, warnings: Iterable[AnalysisWarning]) -> None:
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
    """Create the detailed per-log dashboard using every original sample."""

    cell_columns = available_cell_columns(telemetry)
    has_ir = not status.empty and (
        status.get("total_ir_mohm", pd.Series(dtype=float)).notna().any()
        or bool(available_ir_columns(status))
    )
    ir_row = 7 if has_ir else None
    sampling_row = 8 if has_ir else 7
    rows = sampling_row

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
    titles.append("Период записи телеметрии и мгновенная частота")

    specs: list[list[dict[str, bool]]] = []
    for row in range(1, rows + 1):
        specs.append([{"secondary_y": row in (2, 3, sampling_row)}])

    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.021,
        subplot_titles=titles,
        specs=specs,
    )

    fig.add_trace(_line(telemetry, "time_s", "pack_voltage_v", "Батарея, V", unit="V"), row=1, col=1)
    fig.add_trace(
        _line(telemetry, "time_s", "input_voltage_v", "Вход, V", unit="V", opacity=0.65),
        row=1,
        col=1,
    )

    fig.add_trace(_line(telemetry, "time_s", "current_a", "Ток, A", unit="A"), row=2, col=1, secondary_y=False)
    fig.add_trace(
        _line(telemetry, "time_s", "power_w", "Мощность, W", unit="W", opacity=0.75),
        row=2,
        col=1,
        secondary_y=True,
    )

    fig.add_trace(
        _line(telemetry, "time_s", "capacity_counter_ah", "Счётчик ёмкости, Ah", unit="Ah"),
        row=3,
        col=1,
        secondary_y=False,
    )
    fig.add_trace(
        _line(telemetry, "time_s", "energy_throughput_wh", "Энергия, Wh", unit="Wh"),
        row=3,
        col=1,
        secondary_y=True,
    )

    if telemetry["internal_temp_c"].notna().any():
        fig.add_trace(_line(telemetry, "time_s", "internal_temp_c", "Внутренняя, °C", unit="°C"), row=4, col=1)
    if telemetry["external_temp_c"].notna().any():
        fig.add_trace(_line(telemetry, "time_s", "external_temp_c", "Внешняя, °C", unit="°C"), row=4, col=1)

    for index, column in enumerate(cell_columns, start=1):
        fig.add_trace(_line(telemetry, "time_s", column, f"Банка {index}", unit="V"), row=5, col=1)

    if cell_columns:
        delta_frame = telemetry.copy()
        delta_frame["cell_delta_mv"] = delta_frame["cell_delta_v"] * 1000.0
        fig.add_trace(_line(delta_frame, "time_s", "cell_delta_mv", "Δ банок, mV", unit="mV"), row=6, col=1)
        fig.add_hline(y=20, line_dash="dash", opacity=0.55, row=6, col=1)
        fig.add_hline(y=50, line_dash="dash", opacity=0.55, row=6, col=1)

    if has_ir and ir_row is not None:
        status_plot = status.copy()
        status_plot["elapsed_time"] = status_plot["time_s"].map(
            lambda value: pd.to_timedelta(float(value), unit="s").components
        ).map(lambda value: f"{value.hours:02d}:{value.minutes:02d}:{value.seconds:02d}")
        if status_plot["total_ir_mohm"].notna().any():
            fig.add_trace(_line(status_plot, "time_s", "total_ir_mohm", "Полное IR, mΩ", unit="mΩ"), row=ir_row, col=1)
        if status_plot["cells_ir_sum_mohm"].notna().any():
            fig.add_trace(
                _line(status_plot, "time_s", "cells_ir_sum_mohm", "Сумма IR банок, mΩ", unit="mΩ"),
                row=ir_row,
                col=1,
            )
        for index, column in enumerate(available_ir_columns(status_plot), start=1):
            fig.add_trace(
                _line(status_plot, "time_s", column, f"IR банки {index}, mΩ", unit="mΩ", opacity=0.75),
                row=ir_row,
                col=1,
            )

    sampling = telemetry.loc[telemetry["dt_s"] > 0].copy()
    if not sampling.empty:
        fig.add_trace(
            _line(sampling, "time_s", "dt_s", "Период записи, s", unit="s"),
            row=sampling_row,
            col=1,
            secondary_y=False,
        )
        fig.add_trace(
            _line(sampling, "time_s", "sample_rate_hz", "Частота записи, Hz", unit="Hz", opacity=0.72),
            row=sampling_row,
            col=1,
            secondary_y=True,
        )
        median_dt = float(sampling["dt_s"].median())
        fig.add_hline(
            y=median_dt,
            line_dash="dash",
            opacity=0.65,
            annotation_text=f"медиана {median_dt:.3f} s",
            row=sampling_row,
            col=1,
            secondary_y=False,
        )

    fig.update_yaxes(title_text="V", row=1, col=1)
    fig.update_yaxes(title_text="A", row=2, col=1, secondary_y=False)
    fig.update_yaxes(title_text="W", row=2, col=1, secondary_y=True)
    fig.update_yaxes(title_text="Ah", row=3, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Wh", row=3, col=1, secondary_y=True)
    fig.update_yaxes(title_text="°C", row=4, col=1)
    fig.update_yaxes(title_text="V", row=5, col=1)
    fig.update_yaxes(title_text="mV", row=6, col=1)
    if has_ir and ir_row is not None:
        fig.update_yaxes(title_text="mΩ", row=ir_row, col=1)
    fig.update_yaxes(title_text="s", row=sampling_row, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Hz", row=sampling_row, col=1, secondary_y=True)
    fig.update_xaxes(title_text="Прошедшее время, s (точное HH:MM:SS.mmm — в подсказке)", row=rows, col=1)

    _add_warning_regions(fig, warnings)
    _base_layout(fig, "iCharger — временные графики по исходным отсчётам", 360 * rows)
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
    fig.add_trace(_line(telemetry, "capacity_counter_ah", "pack_voltage_v", "Батарея, V", unit="V"), row=1, col=1)
    for index, column in enumerate(cell_columns, start=1):
        fig.add_trace(_line(telemetry, "capacity_counter_ah", column, f"Банка {index}", unit="V"), row=2, col=1)
    fig.update_yaxes(title_text="V", row=1, col=1)
    fig.update_yaxes(title_text="V", row=2, col=1)
    fig.update_xaxes(title_text="Ёмкость, Ah", row=2, col=1)
    _base_layout(fig, "Разрядные кривые", 900)
    return fig


def _nice_step(value: float) -> float:
    """Round a positive interval to a stable 1/2/5 × 10ⁿ value."""

    if not np.isfinite(value) or value <= 0:
        return 1.0
    exponent = floor(log10(value))
    fraction = value / (10**exponent)
    if fraction <= 1:
        nice = 1.0
    elif fraction <= 2:
        nice = 2.0
    elif fraction <= 5:
        nice = 5.0
    else:
        nice = 10.0
    return nice * (10**exponent)


def choose_comparison_step(series: ComparisonSeries, requested_step_s: float | None = None) -> float:
    """Choose one common time period for all comparison lines."""

    if requested_step_s is not None and requested_step_s > 0:
        return float(requested_step_s)
    medians: list[float] = []
    longest_duration = 0.0
    for _, frame in series:
        positive_dt = frame.loc[frame["dt_s"] > 0, "dt_s"]
        if not positive_dt.empty:
            medians.append(float(positive_dt.median()))
        if not frame.empty:
            longest_duration = max(longest_duration, float(frame["time_s"].iloc[-1]))
    native_limit = max(medians, default=1.0)
    point_limit = longest_duration / 5000.0 if longest_duration > 0 else native_limit
    return _nice_step(max(native_limit, point_limit))


def _interpolate_column(frame: pd.DataFrame, grid: np.ndarray, column: str) -> np.ndarray:
    values = frame[["time_s", column]].dropna().drop_duplicates("time_s", keep="last")
    if values.empty:
        return np.full(grid.shape, np.nan, dtype=float)
    x = values["time_s"].to_numpy(dtype=float)
    y = values[column].to_numpy(dtype=float)
    if len(values) == 1:
        return np.full(grid.shape, y[0], dtype=float)
    return np.interp(grid, x, y)


def resample_for_comparison(frame: pd.DataFrame, step_s: float) -> pd.DataFrame:
    """Interpolate a log onto a regular grid used only by the combined report."""

    duration_s = float(frame["time_s"].iloc[-1])
    if duration_s <= 0:
        grid = np.array([0.0])
    else:
        grid = np.arange(0.0, duration_s + step_s * 0.5, step_s)
        if grid[-1] < duration_s:
            grid = np.append(grid, duration_s)
        else:
            grid[-1] = min(grid[-1], duration_s)
    result = pd.DataFrame({"time_s": grid})
    result["time_min"] = result["time_s"] / 60.0
    result["time_h"] = result["time_s"] / 3600.0
    result["progress_pct"] = 100.0 * result["time_s"] / duration_s if duration_s > 0 else 0.0

    columns = (
        "pack_voltage_v",
        "current_a",
        "power_w",
        "capacity_counter_ah",
        "energy_throughput_wh",
        "internal_temp_c",
        "external_temp_c",
        "cell_min_v",
        "cell_delta_v",
    )
    for column in columns:
        if column in frame:
            result[column] = _interpolate_column(frame, grid, column)

    cells = len(available_cell_columns(frame))
    divisor = cells if cells > 0 else 1
    result["pack_voltage_per_cell_v"] = result["pack_voltage_v"] / divisor
    final_capacity = float(result["capacity_counter_ah"].iloc[-1]) if "capacity_counter_ah" in result else 0.0
    result["capacity_pct"] = (
        100.0 * result["capacity_counter_ah"] / final_capacity if final_capacity > 0 else 0.0
    )
    result["comparison_interval_s"] = step_s
    return result


def _comparison_trace(
    frame: pd.DataFrame,
    x_column: str,
    y_column: str,
    label: str,
    color: str,
    *,
    unit: str,
    showlegend: bool,
) -> go.Scattergl:
    return go.Scattergl(
        x=frame[x_column],
        y=frame[y_column],
        name=label,
        mode="lines",
        legendgroup=label,
        showlegend=showlegend,
        line={"color": color, "width": 1.7},
        hovertemplate=f"%{{x:.3f}}<br>%{{y:.4f}} {unit}<extra>{label}</extra>",
    )


def create_comparison_time_dashboard(series: ComparisonSeries, step_s: float) -> go.Figure:
    """Overlay all major measurements from multiple logs on one time dashboard."""

    prepared = [(label, resample_for_comparison(frame, step_s)) for label, frame in series]
    titles = (
        "Напряжение пакета",
        "Ток",
        "Мощность",
        "Ёмкость",
        "Энергия",
        "Внутренняя температура",
        "Минимальная банка",
        "Разбаланс банок",
        "Период объединённой временной сетки",
    )
    fig = make_subplots(rows=len(titles), cols=1, shared_xaxes=True, vertical_spacing=0.018, subplot_titles=titles)
    colors = qualitative.Plotly + qualitative.Safe + qualitative.Dark24

    metrics = (
        ("pack_voltage_v", "V"),
        ("current_a", "A"),
        ("power_w", "W"),
        ("capacity_counter_ah", "Ah"),
        ("energy_throughput_wh", "Wh"),
        ("internal_temp_c", "°C"),
        ("cell_min_v", "V"),
        ("cell_delta_v", "V"),
    )
    for series_index, (label, frame) in enumerate(prepared):
        color = colors[series_index % len(colors)]
        for row, (column, unit) in enumerate(metrics, start=1):
            if column in frame and frame[column].notna().any():
                plot_frame = frame
                plot_column = column
                plot_unit = unit
                if column == "cell_delta_v":
                    plot_frame = frame.copy()
                    plot_frame["cell_delta_mv"] = plot_frame["cell_delta_v"] * 1000.0
                    plot_column = "cell_delta_mv"
                    plot_unit = "mV"
                fig.add_trace(
                    _comparison_trace(
                        plot_frame,
                        "time_h",
                        plot_column,
                        label,
                        color,
                        unit=plot_unit,
                        showlegend=row == 1,
                    ),
                    row=row,
                    col=1,
                )
        fig.add_trace(
            go.Scattergl(
                x=frame["time_h"],
                y=frame["comparison_interval_s"],
                name=label,
                mode="lines",
                legendgroup=label,
                showlegend=False,
                line={"color": color, "width": 1.7},
                hovertemplate=f"%{{x:.3f}} h<br>%{{y:.3f}} s<extra>{label}</extra>",
            ),
            row=9,
            col=1,
        )

    y_titles = ("V", "A", "W", "Ah", "Wh", "°C", "V", "mV", "s")
    for row, title in enumerate(y_titles, start=1):
        fig.update_yaxes(title_text=title, row=row, col=1)
    fig.add_hline(y=20, line_dash="dash", opacity=0.45, row=8, col=1)
    fig.add_hline(y=50, line_dash="dash", opacity=0.45, row=8, col=1)
    fig.update_xaxes(title_text="Время от начала испытания, h", row=9, col=1)
    _base_layout(
        fig,
        f"Общий график всех логов по времени · единый период {step_s:g} s",
        3250,
    )
    return fig


def create_comparison_progress_dashboard(series: ComparisonSeries, step_s: float) -> go.Figure:
    """Compare tests with different durations and cell counts on a 0–100% axis."""

    prepared = [(label, resample_for_comparison(frame, step_s)) for label, frame in series]
    titles = (
        "Среднее напряжение одной банки по прогрессу испытания",
        "Ток",
        "Отданная ёмкость, % от результата",
        "Внутренняя температура",
        "Разбаланс банок",
    )
    fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.035, subplot_titles=titles)
    colors = qualitative.Plotly + qualitative.Safe + qualitative.Dark24
    metrics = (
        ("pack_voltage_per_cell_v", "V"),
        ("current_a", "A"),
        ("capacity_pct", "%"),
        ("internal_temp_c", "°C"),
        ("cell_delta_v", "V"),
    )
    for series_index, (label, frame) in enumerate(prepared):
        color = colors[series_index % len(colors)]
        for row, (column, unit) in enumerate(metrics, start=1):
            if column not in frame or not frame[column].notna().any():
                continue
            plot_frame = frame
            plot_column = column
            plot_unit = unit
            if column == "cell_delta_v":
                plot_frame = frame.copy()
                plot_frame["cell_delta_mv"] = plot_frame["cell_delta_v"] * 1000.0
                plot_column = "cell_delta_mv"
                plot_unit = "mV"
            fig.add_trace(
                _comparison_trace(
                    plot_frame,
                    "progress_pct",
                    plot_column,
                    label,
                    color,
                    unit=plot_unit,
                    showlegend=row == 1,
                ),
                row=row,
                col=1,
            )
    for row, title in enumerate(("V/cell", "A", "%", "°C", "mV"), start=1):
        fig.update_yaxes(title_text=title, row=row, col=1)
    fig.add_hline(y=20, line_dash="dash", opacity=0.45, row=5, col=1)
    fig.add_hline(y=50, line_dash="dash", opacity=0.45, row=5, col=1)
    fig.update_xaxes(title_text="Прогресс испытания, %", range=[0, 100], row=5, col=1)
    _base_layout(fig, "Нормированное сравнение логов", 1850)
    return fig


def create_comparison_figure(series: ComparisonSeries) -> go.Figure:
    """Backward-compatible compact comparison figure."""

    step_s = choose_comparison_step(series)
    return create_comparison_time_dashboard(series, step_s)
