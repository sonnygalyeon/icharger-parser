"""
parser/tokenizer.py

Чтение текстовых логов iCharger и разбиение их на пакеты.

Задачи:
    • открыть файл;
    • определить кодировку;
    • выделить заголовок;
    • выделить строки телеметрии;
    • создать Packet-объекты через decoder.py.

Никакой аналитики здесь нет.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from .decoder import decode_line, DecodeError
from .packets import Packet


class Tokenizer:
    """
    Основной класс чтения логов.
    """

    def __init__(self) -> None:

        self.headers: dict[str, str] = {}

        self.errors: list[str] = []

    # -----------------------------------------------------

    def parse(self, filename: str | Path) -> list[Packet]:

        filename = Path(filename)

        packets: list[Packet] = []

        with filename.open(
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as file:

            for number, line in enumerate(file, start=1):

                line = line.strip()

                if not line:
                    continue

                # -------------------------------------
                # Заголовок
                # -------------------------------------

                if not line.startswith("$"):

                    self._parse_header(line)

                    continue

                # -------------------------------------
                # Пакеты
                # -------------------------------------

                try:

                    packet = decode_line(line)

                    if packet is not None:
                        packets.append(packet)

                except DecodeError as exc:

                    self.errors.append(
                        f"Line {number}: {exc}"
                    )

        return packets

    # -----------------------------------------------------

    def _parse_header(self, line: str):

        if "=" in line:

            key, value = line.split("=", 1)

            self.headers[key.strip()] = value.strip()

        elif ":" in line:

            key, value = line.split(":", 1)

            self.headers[key.strip()] = value.strip()

    # -----------------------------------------------------

    @property
    def has_errors(self) -> bool:

        return len(self.errors) > 0

    # -----------------------------------------------------

    def print_errors(self):

        if not self.errors:

            return

        print()

        print("=" * 70)

        print("Tokenizer Errors")

        print("=" * 70)

        for error in self.errors:

            print(error)

    # -----------------------------------------------------

    def print_headers(self):

        print()

        print("=" * 70)

        print("Headers")

        print("=" * 70)

        print()

        for key, value in self.headers.items():

            print(f"{key:<20} {value}")

    # -----------------------------------------------------

    def packet_statistics(
        self,
        packets: list[Packet]
    ) -> dict[int, int]:

        statistics: dict[int, int] = {}

        for packet in packets:

            statistics.setdefault(
                packet.packet_type,
                0
            )

            statistics[
                packet.packet_type
            ] += 1

        return statistics

    # -----------------------------------------------------

    def iter_packets(
        self,
        filename: str | Path
    ) -> Iterator[Packet]:

        filename = Path(filename)

        with filename.open(
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as file:

            for line in file:

                line = line.strip()

                if not line.startswith("$"):

                    continue

                try:

                    packet = decode_line(line)

                    if packet:

                        yield packet

                except DecodeError:

                    continue