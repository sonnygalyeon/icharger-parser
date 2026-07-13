"""
parser/packets.py

Описание всех пакетов протокола iCharger.

Каждый пакет представляет одну строку лога.

Автор: iCharger Analyzer
"""

from __future__ import annotations

from dataclasses import dataclass, field
from abc import ABC
from typing import Optional


# ==========================================================
# Базовый пакет
# ==========================================================

@dataclass(slots=True)
class Packet(ABC):
    """
    Базовый пакет.

    Любой пакет обязан иметь:

        channel
        packet_type
        timestamp
    """

    channel: int
    packet_type: int
    timestamp_ms: int


# ==========================================================
# Неизвестный пакет
# ==========================================================

@dataclass(slots=True)
class UnknownPacket(Packet):
    """
    Пока неизвестный тип.
    """

    values: list[int] = field(default_factory=list)


# ==========================================================
# Пакет телеметрии
# ==========================================================

@dataclass(slots=True)
class TelemetryPacket(Packet):
    """
    Packet Type = 2
    """

    mode: int
    flags: int

    current_raw: int
    voltage_raw: int

    capacity_raw: int
    energy_raw: int

    temperature_raw: int

    cell_raw: list[int]

    checksum: int

    # ------------------------------------

    @property
    def current(self) -> float:
        return self.current_raw / 100.0

    @property
    def voltage(self) -> float:
        return self.voltage_raw / 1000.0

    @property
    def power(self) -> float:
        return self.current * self.voltage

    @property
    def capacity(self) -> float:
        return float(self.capacity_raw)

    @property
    def energy(self) -> float:
        return self.energy_raw / 100.0

    @property
    def temperature(self) -> float:
        return self.temperature_raw / 10.0

    @property
    def cell_voltages(self) -> list[float]:

        return [
            value / 1000.0
            for value in self.cell_raw
            if value > 0
        ]

    @property
    def cell_count(self) -> int:

        return len(self.cell_voltages)

    @property
    def max_cell_voltage(self) -> Optional[float]:

        if not self.cell_voltages:
            return None

        return max(self.cell_voltages)

    @property
    def min_cell_voltage(self) -> Optional[float]:

        if not self.cell_voltages:
            return None

        return min(self.cell_voltages)

    @property
    def cell_delta(self) -> Optional[float]:

        if not self.cell_voltages:
            return None

        return (
            self.max_cell_voltage
            - self.min_cell_voltage
        )


# ==========================================================
# Пакет состояния
# ==========================================================

@dataclass(slots=True)
class StatusPacket(Packet):
    """
    Packet Type = 128

    Поля пока окончательно
    не идентифицированы.
    """

    values: list[int]

    @property
    def raw(self):

        return self.values


# ==========================================================
# Заголовок файла
# ==========================================================

@dataclass(slots=True)
class HeaderPacket(Packet):
    """
    Информация из заголовка.
    """

    key: str
    value: str