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
    mean_sample_interval_s: float
    min_sample_interval_s: float
    max_sample_interval_s: float
    sample_interval_std_s: float
    nominal_sample_rate_hz: float
    telemetry_gap_count: int
    max_telemetry_gap_s: float
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
    battery_energy_source: str
    battery_energy_source_note: str
    battery_energy_wh: float
    discharge_energy_wh: float
    charge_energy_wh: float
    output_discharge_energy_wh: float
    output_charge_energy_wh: float
    discharge_capacity_ah: float
    charge_capacity_ah: float
    energy_difference_wh: float
    start_battery_voltage_v: float
    end_battery_voltage_v: float
    integration_omitted_s: float
    duplicate_timestamp_count: int
    counter_discharge_energy_wh: float
    counter_charge_energy_wh: float
    counter_energy_wh: float
    counter_energy_skipped_intervals: int
    counter_jump_count: int

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


def _format_elapsed_time(seconds: float) -> str:
    total_ms = max(0, int(round(float(seconds) * 1000.0)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def _directional_increments(values: pd.Series, dt_s: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """Integrate positive/negative parts of a piecewise-linear signal.

    Split at a zero crossing so a charge/discharge transition cannot cancel
    real throughput. The first sample and duplicate timestamps have dt=0.
    """
    end = values.to_numpy(dtype=float)
    start = np.r_[end[0], end[:-1]]
    positive = (np.maximum(start, 0) + np.maximum(end, 0)) / 2
    negative = (np.maximum(-start, 0) + np.maximum(-end, 0)) / 2
    crossing = start * end < 0
    denominator = np.abs(start) + np.abs(end)
    correction = np.divide(
        np.abs(start * end), 2 * denominator,
        out=np.zeros_like(end), where=crossing,
    )
    hours = dt_s.to_numpy(dtype=float) / 3600
    return (positive - correction) * hours, (negative - correction) * hours


def build_telemetry_frame(log: ChargerLog, energy_voltage: str = "auto") -> pd.DataFrame:
    if energy_voltage not in {"auto", "cells", "output"}:
        raise ValueError("energy_voltage must be auto, cells or output")
    if len({record.channel for record in log.telemetry}) > 1:
        raise ValueError("Несколько каналов в одном файле: разделите CH1 и CH2 для расчёта энергии.")
    rows: list[dict[str, object]] = []
    for sample, record in enumerate(log.telemetry):
        row: dict[str, object] = {
            "sample": sample,
            "channel": record.channel,
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
    frame["elapsed_time"] = frame["time_s"].map(_format_elapsed_time)
    frame["dt_s"] = frame["time_s"].diff().fillna(0.0).clip(lower=0.0)
    frame["sample_interval_s"] = frame["dt_s"]
    frame["sample_rate_hz"] = 1.0 / frame["dt_s"].where(frame["dt_s"] > 0)

    frame["power_w"] = frame["pack_voltage_v"] * frame["current_a"]
    frame["abs_power_w"] = frame["power_w"].abs()

    # Do not invent energy over large gaps. Keep the raw dt and expose coverage.
    positive_dt = frame.loc[frame["dt_s"] > 0, "dt_s"]
    median_dt = float(positive_dt.median()) if not positive_dt.empty else 0.0
    gap_limit = max(median_dt * 2.5, median_dt + 2.0)
    frame["integration_omitted_s"] = frame["dt_s"].where(frame["dt_s"] > gap_limit, 0.0)
    frame["integration_dt_s"] = frame["dt_s"] - frame["integration_omitted_s"]

    cells = available_cell_columns(frame)
    contiguous = cells == [f"cell_{index}_v" for index in range(1, len(cells) + 1)]
    complete_cells = bool(cells) and contiguous and bool(frame[cells].notna().all().all())
    frame["cell_sum_voltage_v"] = frame[cells].sum(axis=1, min_count=len(cells)) if cells else np.nan
    if energy_voltage == "cells" and not complete_cells:
        raise ValueError("Для --energy-voltage cells нужны все обнаруженные банки в каждом отсчёте.")
    use_cells = complete_cells and energy_voltage != "output"
    source = "cells" if use_cells else "output"
    if use_cells:
        voltage_description = "Напряжение первой банки" if len(cells) == 1 else f"Сумма напряжений {len(cells)} банок"
        source_note = f"{voltage_description}; балансирные данные полны во всём логе."
    elif energy_voltage == "output":
        source_note = "Напряжение силового выхода выбрано вручную."
    else:
        source_note = "Полных балансирных данных нет; использовано напряжение силового выхода."
    frame["battery_voltage_source"] = source
    frame.attrs["battery_energy_source_note"] = source_note
    frame["battery_voltage_v"] = frame["cell_sum_voltage_v"] if use_cells else frame["pack_voltage_v"]
    frame["voltage_difference_v"] = frame["cell_sum_voltage_v"] - frame["pack_voltage_v"]
    frame["battery_power_w"] = frame["battery_voltage_v"] * frame["current_a"]

    charge_ah, discharge_ah = _directional_increments(frame["current_a"], frame["integration_dt_s"])
    charge_wh, discharge_wh = _directional_increments(frame["power_w"], frame["integration_dt_s"])
    battery_charge_wh, battery_discharge_wh = _directional_increments(
        frame["battery_power_w"], frame["integration_dt_s"]
    )
    frame["incremental_capacity_ah_signed"] = charge_ah - discharge_ah
    frame["incremental_energy_wh_signed"] = charge_wh - discharge_wh
    frame["integrated_capacity_ah_signed"] = np.cumsum(charge_ah - discharge_ah)
    frame["integrated_energy_wh_signed"] = np.cumsum(charge_wh - discharge_wh)
    frame["charge_capacity_ah"] = np.cumsum(charge_ah)
    frame["discharge_capacity_ah"] = np.cumsum(discharge_ah)
    frame["capacity_throughput_ah"] = np.cumsum(charge_ah + discharge_ah)
    # Existing output-energy columns retain their voltage source.
    frame["energy_throughput_wh"] = np.cumsum(charge_wh + discharge_wh)
    frame["output_charge_energy_wh"] = np.cumsum(charge_wh)
    frame["output_discharge_energy_wh"] = np.cumsum(discharge_wh)
    frame["charge_energy_wh"] = np.cumsum(battery_charge_wh)
    frame["discharge_energy_wh"] = np.cumsum(battery_discharge_wh)
    frame["battery_energy_throughput_wh"] = np.cumsum(battery_charge_wh + battery_discharge_wh)
    frame["battery_energy_wh_signed"] = np.cumsum(battery_charge_wh - battery_discharge_wh)
    frame["energy_difference_wh"] = frame["discharge_energy_wh"] - frame["output_discharge_energy_wh"]

    initial_counter = float(frame["capacity_mah_signed"].iloc[0])
    frame["capacity_counter_ah"] = (frame["capacity_mah_signed"] - initial_counter).abs() / 1000.0

    # Energy requested from the device's mAh counter and balance voltage:
    # V * mAh / 1000 = Wh. No extra time factor or division by 3600.
    delta_mah = frame["capacity_mah_signed"].diff().fillna(0.0)
    previous_voltage = frame["battery_voltage_v"].shift(1).fillna(frame["battery_voltage_v"])
    average_voltage = (previous_voltage + frame["battery_voltage_v"]) / 2.0
    previous_current = frame["current_a"].shift(1).fillna(frame["current_a"])
    current_limit = np.maximum(previous_current.abs(), frame["current_a"].abs())
    # Current is used only to flag likely counter resets/corruption, not to
    # compute this energy. Allow rounding and generous transient tolerance.
    opposite_direction = (
        ((previous_current < 0) & (frame["current_a"] < 0) & (delta_mah > 0))
        | ((previous_current > 0) & (frame["current_a"] > 0) & (delta_mah < 0))
    )
    implausible_jump = (current_limit > 0) & (
        delta_mah.abs() > 5 * current_limit * frame["dt_s"] / 3.6 + 2
    )
    frame["counter_jump"] = opposite_direction | implausible_jump
    frame["counter_energy_skipped"] = (delta_mah != 0) & (
        (frame["integration_dt_s"] <= 0) | frame["counter_jump"]
    )
    frame["counter_delta_mah_signed"] = delta_mah
    accepted_delta_ah = delta_mah.where(~frame["counter_energy_skipped"], 0.0) / 1000.0
    frame["counter_incremental_energy_wh_signed"] = average_voltage * accepted_delta_ah
    increments = frame["counter_incremental_energy_wh_signed"]
    frame["counter_charge_energy_wh"] = increments.clip(lower=0).cumsum()
    frame["counter_discharge_energy_wh"] = (-increments.clip(upper=0)).cumsum()
    frame["counter_energy_throughput_wh"] = increments.abs().cumsum()
    frame["counter_energy_wh_signed"] = increments.cumsum()

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
    if dt_positive.empty:
        median_dt = mean_dt = min_dt = max_dt = std_dt = sample_rate_hz = 0.0
        gap_limit = np.inf
        gap_count = 0
    else:
        median_dt = float(dt_positive.median())
        mean_dt = float(dt_positive.mean())
        min_dt = float(dt_positive.min())
        max_dt = float(dt_positive.max())
        std_dt = float(dt_positive.std(ddof=0))
        sample_rate_hz = 1.0 / median_dt if median_dt > 0 else 0.0
        gap_limit = max(median_dt * 2.5, median_dt + 2.0)
        gap_count = int((dt_positive > gap_limit).sum())

    min_cell = telemetry[cells].min().min() if cells else np.nan
    max_cell = telemetry[cells].max().max() if cells else np.nan
    max_delta = telemetry["cell_delta_v"].max() if cells else np.nan
    end_delta = _last_valid(telemetry, "cell_delta_v") if cells else None

    return AnalysisSummary(
        samples=len(telemetry),
        duration_s=float(telemetry["time_s"].iloc[-1]),
        median_sample_interval_s=median_dt,
        mean_sample_interval_s=mean_dt,
        min_sample_interval_s=min_dt,
        max_sample_interval_s=max_dt,
        sample_interval_std_s=std_dt,
        nominal_sample_rate_hz=sample_rate_hz,
        telemetry_gap_count=gap_count,
        max_telemetry_gap_s=max_dt,
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
        battery_energy_source=str(telemetry["battery_voltage_source"].iloc[0]),
        battery_energy_source_note=telemetry.attrs["battery_energy_source_note"],
        battery_energy_wh=float(telemetry["battery_energy_throughput_wh"].iloc[-1]),
        discharge_energy_wh=float(telemetry["discharge_energy_wh"].iloc[-1]),
        charge_energy_wh=float(telemetry["charge_energy_wh"].iloc[-1]),
        output_discharge_energy_wh=float(telemetry["output_discharge_energy_wh"].iloc[-1]),
        output_charge_energy_wh=float(telemetry["output_charge_energy_wh"].iloc[-1]),
        discharge_capacity_ah=float(telemetry["discharge_capacity_ah"].iloc[-1]),
        charge_capacity_ah=float(telemetry["charge_capacity_ah"].iloc[-1]),
        energy_difference_wh=float(telemetry["energy_difference_wh"].iloc[-1]),
        start_battery_voltage_v=float(telemetry["battery_voltage_v"].iloc[0]),
        end_battery_voltage_v=float(telemetry["battery_voltage_v"].iloc[-1]),
        integration_omitted_s=float(telemetry["integration_omitted_s"].sum()),
        duplicate_timestamp_count=int(telemetry["timestamp_ms"].duplicated().sum()),
        counter_discharge_energy_wh=float(telemetry["counter_discharge_energy_wh"].iloc[-1]),
        counter_charge_energy_wh=float(telemetry["counter_charge_energy_wh"].iloc[-1]),
        counter_energy_wh=float(telemetry["counter_energy_throughput_wh"].iloc[-1]),
        counter_energy_skipped_intervals=int(telemetry["counter_energy_skipped"].sum()),
        counter_jump_count=int(telemetry["counter_jump"].sum()),
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


def analyze_log(log: ChargerLog, energy_voltage: str = "auto") -> AnalysisResult:
    telemetry = build_telemetry_frame(log, energy_voltage)
    status = build_status_frame(log, int(telemetry["timestamp_ms"].iloc[0]))
    summary = calculate_summary(log, telemetry, status)
    warnings = detect_warnings(telemetry)
    return AnalysisResult(telemetry=telemetry, status=status, summary=summary, warnings=warnings)
