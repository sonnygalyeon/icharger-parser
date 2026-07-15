"""Typed data models for iCharger logs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class HeaderInfo:
    model: str = ""
    firmware: str = ""
    hardware: str = ""
    serial_number: str = ""
    raw: str = ""


@dataclass(slots=True)
class ParseIssue:
    line_number: int
    message: str
    line: str = ""


@dataclass(slots=True)
class TelemetryRecord:
    channel: int
    packet_type: int
    timestamp_ms: int
    battery_type_code: int
    flags: int
    current_a: float
    input_voltage_v: float
    pack_voltage_v: float
    capacity_mah_signed: float
    internal_temp_c: Optional[float]
    external_temp_c: Optional[float]
    cell_voltages_v: tuple[Optional[float], ...]
    checksum: int
    raw_values: tuple[int, ...]


@dataclass(slots=True)
class StatusRecord:
    channel: int
    packet_type: int
    timestamp_ms: int
    total_ir_mohm: Optional[float]
    cells_ir_sum_mohm: Optional[float]
    cell_ir_mohm: tuple[Optional[float], ...]
    checksum: int
    raw_values: tuple[int, ...]


@dataclass(slots=True)
class ChargerLog:
    source_file: Path
    header: HeaderInfo
    telemetry: list[TelemetryRecord] = field(default_factory=list)
    status: list[StatusRecord] = field(default_factory=list)
    issues: list[ParseIssue] = field(default_factory=list)
    unsupported_packet_counts: dict[int, int] = field(default_factory=dict)

    @property
    def duration_s(self) -> float:
        if len(self.telemetry) < 2:
            return 0.0
        return max(0.0, (self.telemetry[-1].timestamp_ms - self.telemetry[0].timestamp_ms) / 1000.0)

    @property
    def sample_count(self) -> int:
        return len(self.telemetry)
