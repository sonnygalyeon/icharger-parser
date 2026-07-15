"""Data-frame conversion, derived quantities, statistics, and grouped warnings."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite

import numpy as np
import pandas as pd

from .models import ChargerLog

MAX_CELLS = 10


@dataclass(slots=True)
class AnalysisSummary:
    samples: int
    duration_s: float
    median_sample_interval_s: float
    detected_cells: int
    start_pack_voltage_v: float
    end_pack_voltage_v: float
    min_pack_voltage_v: float
    max_pack_voltage_v: float
    min_cell_voltage_v: float | None
    max_cell_voltage_v: float | None
    max_cell_delta_v: float | None
    end_cell_delta_v: float | None
    peak_charge_current_a: float
    peak_discharge_current_a: float
    average_current_a: float
    peak_abs_power_w: float
    capacity_counter_ah: float
    integrated_capacity_ah: float
    integrated_energy_wh: float
    max_internal_temp_c: float | None
    max_external_temp_c: float | None
    latest_total_ir_mohm: float | None
    latest_cells_ir_sum_mohm: float | None
    parse_issue_count: int
    status_record_count: int

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class AnalysisWarning:
    severity: str
    title: str
    start_s: float
    end_s: float
    peak_value: float | None
    unit: str
    description: str


@dataclass(slots=True)
class AnalysisResult:
    telemetry: pd.DataFrame
    status: pd.DataFrame
    summary: AnalysisSummary
    warnings: list[AnalysisWarning]


def build_telemetry_frame(log: ChargerLog) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for sample, record in enumerate(log.telemetry):
        row: dict[str, object] = {
            "sample": sample,
            "timestamp_ms": record.timestamp_ms,
            "battery_type_code": record.battery_type_code,
            "flags": record.flags,
            "current_a": record.current_a,
            "input_voltage_v": record.input_voltage_v,
            "pack_voltage_v": record.pack_voltage_v,
            "capacity_mah_signed": record.capacity_mah_signed,
            "internal_temp_c": record.internal_temp_c,
            "external_temp_c": record.external_temp_c,
        }
        for index in range(MAX_CELLS):
            row[f"cell_{index + 1}_v"] = record.cell_voltages_v[index]
        rows.append(row)

    frame = pd.DataFrame(rows).sort_values("timestamp_ms", kind="stable").reset_index(drop=True)
    start_ms = float(frame["timestamp_ms"].iloc[0])
    frame["time_s"] = (frame["timestamp_ms"] - start_ms) / 1000.0
    frame["time_min"] = frame["time_s"] / 60.0
    frame["time_h"] = frame["time_s"] / 3600.0
    frame["dt_s"] = frame["time_s"].diff().fillna(0.0).clip(lower=0.0)

    frame["power_w"] = frame["pack_voltage_v"] * frame["current_a"]
    frame["abs_power_w"] = frame["power_w"].abs()

    # Signed trapezoidal integration; throughput columns use absolute values.
    previous_current = frame["current_a"].shift(1).fillna(frame["current_a"])
    previous_power = frame["power_w"].shift(1).fillna(frame["power_w"])
    frame["incremental_capacity_ah_signed"] = (
        ((frame["current_a"] + previous_current) / 2.0) * frame["dt_s"] / 3600.0
    )
    frame["incremental_energy_wh_signed"] = (
        ((frame["power_w"] + previous_power) / 2.0) * frame["dt_s"] / 3600.0
    )
    frame["integrated_capacity_ah_signed"] = frame["incremental_capacity_ah_signed"].cumsum()
    frame["integrated_energy_wh_signed"] = frame["incremental_energy_wh_signed"].cumsum()
    frame["capacity_throughput_ah"] = frame["incremental_capacity_ah_signed"].abs().cumsum()
    frame["energy_throughput_wh"] = frame["incremental_energy_wh_signed"].abs().cumsum()

    initial_counter = float(frame["capacity_mah_signed"].iloc[0])
    frame["capacity_counter_ah"] = (frame["capacity_mah_signed"] - initial_counter).abs() / 1000.0

    cell_columns = available_cell_columns(frame)
    if cell_columns:
        frame["cell_min_v"] = frame[cell_columns].min(axis=1, skipna=True)
        frame["cell_max_v"] = frame[cell_columns].max(axis=1, skipna=True)
        frame["cell_avg_v"] = frame[cell_columns].mean(axis=1, skipna=True)
        frame["cell_delta_v"] = frame["cell_max_v"] - frame["cell_min_v"]
    else:
        frame["cell_min_v"] = np.nan
        frame["cell_max_v"] = np.nan
        frame["cell_avg_v"] = np.nan
        frame["cell_delta_v"] = np.nan

    # Derivatives use actual dt, not a hard-coded one-second sample period.
    safe_dt = frame["dt_s"].replace(0.0, np.nan)
    for column, name in (
        ("pack_voltage_v", "pack_voltage_rate_v_s"),
        ("current_a", "current_rate_a_s"),
        ("power_w", "power_rate_w_s"),
        ("internal_temp_c", "internal_temp_rate_c_s"),
        ("cell_delta_v", "cell_delta_rate_v_s"),
    ):
        frame[name] = frame[column].diff().divide(safe_dt).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    return frame


def build_status_frame(log: ChargerLog, start_timestamp_ms: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for record in log.status:
        row: dict[str, object] = {
            "timestamp_ms": record.timestamp_ms,
            "time_s": (record.timestamp_ms - start_timestamp_ms) / 1000.0,
            "total_ir_mohm": record.total_ir_mohm,
            "cells_ir_sum_mohm": record.cells_ir_sum_mohm,
        }
        for index in range(MAX_CELLS):
            row[f"cell_{index + 1}_ir_mohm"] = record.cell_ir_mohm[index]
        rows.append(row)
    if not rows:
        return pd.DataFrame(columns=["timestamp_ms", "time_s", "total_ir_mohm", "cells_ir_sum_mohm"])
    return pd.DataFrame(rows).sort_values("timestamp_ms", kind="stable").reset_index(drop=True)


def available_cell_columns(frame: pd.DataFrame) -> list[str]:
    result = []
    for index in range(1, MAX_CELLS + 1):
        column = f"cell_{index}_v"
        if column in frame and frame[column].notna().any():
            result.append(column)
    return result


def available_ir_columns(frame: pd.DataFrame) -> list[str]:
    result = []
    for index in range(1, MAX_CELLS + 1):
        column = f"cell_{index}_ir_mohm"
        if column in frame and frame[column].notna().any():
            result.append(column)
    return result


def _last_valid(frame: pd.DataFrame, column: str) -> float | None:
    if column not in frame:
        return None
    values = frame[column].dropna()
    return float(values.iloc[-1]) if not values.empty else None


def _finite_or_none(value: float) -> float | None:
    return float(value) if isfinite(value) else None


def calculate_summary(log: ChargerLog, telemetry: pd.DataFrame, status: pd.DataFrame) -> AnalysisSummary:
    cells = available_cell_columns(telemetry)
    positive_current = telemetry.loc[telemetry["current_a"] > 0, "current_a"]
    negative_current = telemetry.loc[telemetry["current_a"] < 0, "current_a"]
    dt_positive = telemetry.loc[telemetry["dt_s"] > 0, "dt_s"]

    min_cell = telemetry[cells].min().min() if cells else np.nan
    max_cell = telemetry[cells].max().max() if cells else np.nan
    max_delta = telemetry["cell_delta_v"].max() if cells else np.nan
    end_delta = _last_valid(telemetry, "cell_delta_v") if cells else None

    return AnalysisSummary(
        samples=len(telemetry),
        duration_s=float(telemetry["time_s"].iloc[-1]),
        median_sample_interval_s=float(dt_positive.median()) if not dt_positive.empty else 0.0,
        detected_cells=len(cells),
        start_pack_voltage_v=float(telemetry["pack_voltage_v"].iloc[0]),
        end_pack_voltage_v=float(telemetry["pack_voltage_v"].iloc[-1]),
        min_pack_voltage_v=float(telemetry["pack_voltage_v"].min()),
        max_pack_voltage_v=float(telemetry["pack_voltage_v"].max()),
        min_cell_voltage_v=_finite_or_none(float(min_cell)),
        max_cell_voltage_v=_finite_or_none(float(max_cell)),
        max_cell_delta_v=_finite_or_none(float(max_delta)),
        end_cell_delta_v=end_delta,
        peak_charge_current_a=float(positive_current.max()) if not positive_current.empty else 0.0,
        peak_discharge_current_a=float(abs(negative_current.min())) if not negative_current.empty else 0.0,
        average_current_a=float(telemetry["current_a"].mean()),
        peak_abs_power_w=float(telemetry["abs_power_w"].max()),
        capacity_counter_ah=float(telemetry["capacity_counter_ah"].iloc[-1]),
        integrated_capacity_ah=float(telemetry["capacity_throughput_ah"].iloc[-1]),
        integrated_energy_wh=float(telemetry["energy_throughput_wh"].iloc[-1]),
        max_internal_temp_c=_finite_or_none(float(telemetry["internal_temp_c"].max(skipna=True))),
        max_external_temp_c=_finite_or_none(float(telemetry["external_temp_c"].max(skipna=True))),
        latest_total_ir_mohm=_last_valid(status, "total_ir_mohm"),
        latest_cells_ir_sum_mohm=_last_valid(status, "cells_ir_sum_mohm"),
        parse_issue_count=len(log.issues),
        status_record_count=len(status),
    )


def _group_mask(
    frame: pd.DataFrame,
    mask: pd.Series,
    *,
    severity: str,
    title: str,
    value_column: str,
    unit: str,
    description: str,
    peak_mode: str = "max",
) -> list[AnalysisWarning]:
    if frame.empty or not bool(mask.any()):
        return []

    selected = frame.loc[mask].copy()
    if selected.empty:
        return []

    positive_dt = frame.loc[frame["dt_s"] > 0, "dt_s"] if "dt_s" in frame else pd.Series(dtype=float)
    median_dt = float(positive_dt.median()) if not positive_dt.empty else 1.0
    # Brief threshold chatter (for example 2.999/3.000 V) is one physical episode.
    max_gap_s = max(10.0, median_dt * 10.0)
    groups = selected["time_s"].diff().fillna(0.0).gt(max_gap_s).cumsum()

    warnings: list[AnalysisWarning] = []
    for _, part in selected.groupby(groups):
        values = part[value_column].dropna()
        if values.empty:
            peak = None
        elif peak_mode == "min":
            peak = float(values.min())
        elif peak_mode == "absmax":
            peak = float(values.iloc[values.abs().argmax()])
        else:
            peak = float(values.max())
        warnings.append(
            AnalysisWarning(
                severity=severity,
                title=title,
                start_s=float(part["time_s"].iloc[0]),
                end_s=float(part["time_s"].iloc[-1]),
                peak_value=peak,
                unit=unit,
                description=description,
            )
        )
    return warnings


def detect_warnings(telemetry: pd.DataFrame) -> list[AnalysisWarning]:
    warnings: list[AnalysisWarning] = []
    cell_columns = available_cell_columns(telemetry)

    warnings += _group_mask(
        telemetry,
        telemetry["internal_temp_c"].fillna(-np.inf) >= 60.0,
        severity="high",
        title="Высокая внутренняя температура",
        value_column="internal_temp_c",
        unit="°C",
        description="Температура зарядного устройства достигла или превысила 60 °C.",
    )

    if cell_columns:
        warnings += _group_mask(
            telemetry,
            telemetry["cell_delta_v"].fillna(0.0) >= 0.050,
            severity="high",
            title="Сильный разбаланс банок",
            value_column="cell_delta_v",
            unit="V",
            description="Разница между самой высокой и самой низкой банкой не меньше 50 mV.",
        )
        warnings += _group_mask(
            telemetry,
            telemetry["cell_min_v"].fillna(np.inf) <= 3.00,
            severity="high",
            title="Низкое напряжение банки",
            value_column="cell_min_v",
            unit="V",
            description="Хотя бы одна измеряемая банка опустилась до 3.00 V или ниже.",
            peak_mode="min",
        )
        warnings += _group_mask(
            telemetry,
            (telemetry["cell_delta_v"].fillna(0.0) >= 0.020)
            & (telemetry["cell_delta_v"].fillna(0.0) < 0.050),
            severity="medium",
            title="Заметный разбаланс банок",
            value_column="cell_delta_v",
            unit="V",
            description="Разница между банками находится в диапазоне 20–50 mV.",
        )

    positive_dt = telemetry.loc[telemetry["dt_s"] > 0, "dt_s"]
    if not positive_dt.empty:
        expected = float(positive_dt.median())
        gap_limit = max(expected * 2.5, expected + 2.0)
        warnings += _group_mask(
            telemetry,
            telemetry["dt_s"] > gap_limit,
            severity="medium",
            title="Разрыв телеметрии",
            value_column="dt_s",
            unit="s",
            description=f"Интервал между отсчётами заметно больше типичных {expected:.2f} s.",
        )

    # Sort and collapse to a useful number in the report. Full masks remain in CSV.
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    warnings.sort(key=lambda item: (severity_rank.get(item.severity, 9), item.start_s))
    return warnings


def analyze_log(log: ChargerLog) -> AnalysisResult:
    telemetry = build_telemetry_frame(log)
    status = build_status_frame(log, int(telemetry["timestamp_ms"].iloc[0]))
    summary = calculate_summary(log, telemetry, status)
    warnings = detect_warnings(telemetry)
    return AnalysisResult(telemetry=telemetry, status=status, summary=summary, warnings=warnings)
