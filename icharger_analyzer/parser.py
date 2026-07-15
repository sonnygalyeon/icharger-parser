"""Robust parser for semicolon-delimited iCharger TXT logs."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from .models import ChargerLog, HeaderInfo, ParseIssue, StatusRecord, TelemetryRecord

TELEMETRY_PACKET = 2
STATUS_PACKET = 128
TELEMETRY_FIELDS = 22
STATUS_FIELDS = 16
MAX_CELLS = 10

_HEADER_PATTERNS = {
    "model": re.compile(r"(?:^|;)\s*@?Model\s*:\s*([^;\x00]+)", re.IGNORECASE),
    # The device itself writes the misspelling "Fireware" in supplied logs.
    "firmware": re.compile(r"(?:^|;)\s*(?:Firmware|Fireware)\s*:\s*([^;\x00]+)", re.IGNORECASE),
    "hardware": re.compile(r"(?:^|;)\s*Hardware\s*:\s*([^;\x00]+)", re.IGNORECASE),
    "serial_number": re.compile(r"(?:^|;)\s*(?:SN|Serial(?:\s*Number)?)\s*:\s*([^;\x00]+)", re.IGNORECASE),
}


class IChargerParseError(RuntimeError):
    """Raised when a file cannot be parsed into any telemetry records."""


class IChargerParser:
    """Parse an iCharger log while preserving malformed-line diagnostics."""

    def parse(self, filename: str | Path) -> ChargerLog:
        path = Path(filename)
        if not path.exists():
            raise FileNotFoundError(path)
        if not path.is_file():
            raise IsADirectoryError(path)

        log = ChargerLog(source_file=path, header=HeaderInfo())
        unsupported = Counter()

        with path.open("r", encoding="utf-8-sig", errors="replace") as stream:
            for line_number, raw_line in enumerate(stream, start=1):
                line = raw_line.strip().replace("\x00", "")
                if not line:
                    continue

                if not line.startswith("$"):
                    self._merge_header(log.header, line)
                    continue

                try:
                    values = self._parse_packet_values(line)
                    packet_type = values[1]
                    if packet_type == TELEMETRY_PACKET:
                        log.telemetry.append(self._decode_telemetry(values))
                    elif packet_type == STATUS_PACKET:
                        log.status.append(self._decode_status(values))
                    else:
                        unsupported[packet_type] += 1
                except (ValueError, IndexError) as exc:
                    log.issues.append(
                        ParseIssue(
                            line_number=line_number,
                            message=str(exc),
                            line=line[:240],
                        )
                    )

        log.unsupported_packet_counts = dict(unsupported)
        log.telemetry.sort(key=lambda item: item.timestamp_ms)
        log.status.sort(key=lambda item: item.timestamp_ms)

        if not log.telemetry:
            detail = f"; damaged lines: {len(log.issues)}" if log.issues else ""
            raise IChargerParseError(f"No valid telemetry packets found in {path}{detail}")

        return log

    @staticmethod
    def _parse_packet_values(line: str) -> list[int]:
        parts = [part.strip() for part in line[1:].split(";")]
        if len(parts) < 2:
            raise ValueError("Packet has fewer than two fields")
        try:
            return [int(part) for part in parts]
        except ValueError as exc:
            raise ValueError(f"Non-integer packet field: {exc}") from exc

    @staticmethod
    def _merge_header(header: HeaderInfo, line: str) -> None:
        header.raw = f"{header.raw}\n{line}".strip()
        for attribute, pattern in _HEADER_PATTERNS.items():
            match = pattern.search(line)
            if match:
                setattr(header, attribute, match.group(1).strip())

    @staticmethod
    def _decode_telemetry(values: list[int]) -> TelemetryRecord:
        if len(values) != TELEMETRY_FIELDS:
            raise ValueError(
                f"Telemetry packet must have {TELEMETRY_FIELDS} fields, got {len(values)}"
            )

        cells = tuple(value / 1000.0 if value > 0 else None for value in values[11:21])

        # Supplied 4010DUO SD logs and established iCharger decoders use:
        # current x 0.01 A, voltages/cells x 0.001 V, temperatures x 0.1 C,
        # capacity in mAh. Field 3 is retained as a code rather than guessed.
        return TelemetryRecord(
            channel=values[0],
            packet_type=values[1],
            timestamp_ms=values[2],
            battery_type_code=values[3],
            flags=values[4],
            current_a=values[5] * 0.01,
            input_voltage_v=values[6] * 0.001,
            pack_voltage_v=values[7] * 0.001,
            capacity_mah_signed=float(values[8]),
            internal_temp_c=values[9] * 0.1 if values[9] != 0 else None,
            external_temp_c=values[10] * 0.1 if values[10] != 0 else None,
            cell_voltages_v=cells,
            checksum=values[21],
            raw_values=tuple(values),
        )

    @staticmethod
    def _decode_status(values: list[int]) -> StatusRecord:
        if len(values) != STATUS_FIELDS:
            raise ValueError(
                f"Status packet must have {STATUS_FIELDS} fields, got {len(values)}"
            )

        # Packet 128 semantics are not publicly documented. In supplied logs,
        # field 4 equals the sum of per-cell fields 5..14. Values are therefore
        # exposed as inferred 0.1 mOhm units, while raw_values remain available.
        cell_ir = tuple(value / 10.0 if value > 0 else None for value in values[5:15])
        return StatusRecord(
            channel=values[0],
            packet_type=values[1],
            timestamp_ms=values[2],
            total_ir_mohm=values[3] / 10.0 if values[3] > 0 else None,
            cells_ir_sum_mohm=values[4] / 10.0 if values[4] > 0 else None,
            cell_ir_mohm=cell_ir,
            checksum=values[15],
            raw_values=tuple(values),
        )
