"""
parser/parser.py

Высокоуровневый API парсера логов iCharger.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .decoder import (
    decode_header,
    decode_line,
)

from .models import (
    Header,
    StatusRecord,
    TelemetryRecord,
)

from .validator import (
    LogValidator,
    ValidationResult,
)


# ==========================================================
# Главный объект лога
# ==========================================================

@dataclass(slots=True)
class ChargerLog:

    file: Path

    validation: ValidationResult

    headers: list[Header] = field(default_factory=list)

    telemetry: list[TelemetryRecord] = field(default_factory=list)

    status: list[StatusRecord] = field(default_factory=list)

    @property
    def samples(self) -> int:
        return len(self.telemetry)

    @property
    def duration_ms(self) -> int:

        if not self.telemetry:
            return 0

        return (
            self.telemetry[-1].timestamp_ms
            - self.telemetry[0].timestamp_ms
        )

    @property
    def duration_seconds(self) -> float:
        return self.duration_ms / 1000

    @property
    def start_time(self) -> int:

        if not self.telemetry:
            return 0

        return self.telemetry[0].timestamp_ms

    @property
    def end_time(self) -> int:

        if not self.telemetry:
            return 0

        return self.telemetry[-1].timestamp_ms


# ==========================================================
# Парсер
# ==========================================================

class LogParser:

    def __init__(self):

        self.validator = LogValidator()

    # -----------------------------------------------------

    def parse(
        self,
        filename: str | Path,
    ) -> ChargerLog:

        filename = Path(filename)

        validation = self.validator.validate(filename)

        if not validation.valid:
            raise RuntimeError(
                "\n".join(validation.errors)
            )

        log = ChargerLog(
            file=filename,
            validation=validation,
        )

        with filename.open(
            "r",
            encoding="utf-8",
            errors="ignore",
        ) as file:

            for line in file:

                line = line.strip()

                if not line:
                    continue

                #
                # Header
                #

                if not line.startswith("$"):

                    header = decode_header(line)

                    if header:

                        log.headers.append(header)

                    continue

                #
                # Packet
                #

                packet = decode_line(line)

                if isinstance(packet, TelemetryRecord):

                    log.telemetry.append(packet)

                elif isinstance(packet, StatusRecord):

                    log.status.append(packet)

        return log

    # -----------------------------------------------------

    @staticmethod
    def info(log: ChargerLog):

        print()

        print("=" * 60)

        print("iCharger Log")

        print("=" * 60)

        print()

        print(f"Samples      : {log.samples}")

        print(f"Duration     : {log.duration_seconds:.1f} s")

        print(f"Headers      : {len(log.headers)}")

        print(f"Status       : {len(log.status)}")

        print()

        for header in log.headers:

            print(f"{header.key:<20} {header.value}")