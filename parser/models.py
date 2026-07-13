"""
parser/models.py

Структуры данных проекта iCharger Analyzer.

Данный модуль не содержит никакой логики.
Только описание объектов, которыми оперирует вся программа.

Используется всеми остальными модулями проекта.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional


# ============================================================
# Информация о самом лог-файле
# ============================================================

@dataclass(slots=True)
class LogInfo:
    """
    Информация, записанная в заголовке файла.
    """

    model: str
    firmware: str
    hardware: str
    serial_number: str

    source_file: Optional[Path] = None


# ============================================================
# Одна запись телеметрии
# ============================================================

@dataclass(slots=True)
class TelemetryRecord:
    """
    Одна строка телеметрии.

    Все величины приводятся к человеческим единицам
    уже во время парсинга.
    """

    timestamp_ms: int

    voltage: float          # В
    current: float          # А

    power: float            # Вт

    capacity: float         # mAh
    energy: float           # Wh

    temperature: float      # °C

    internal_resistance: Optional[float] = None

    cell_voltages: List[float] = field(default_factory=list)

    balancing: bool = False

    raw: Optional[List[int]] = None


# ============================================================
# Вспомогательные события
# ============================================================

@dataclass(slots=True)
class EventRecord:
    """
    События зарядного устройства.

    Например:

    начало зарядки

    окончание

    ошибка

    изменение режима

    балансировка

    предупреждение
    """

    timestamp_ms: int

    event: str

    description: str


# ============================================================
# Полностью загруженный лог
# ============================================================

@dataclass(slots=True)
class ChargerLog:
    """
    Полностью распарсенный лог.
    """

    info: LogInfo

    telemetry: List[TelemetryRecord] = field(default_factory=list)

    events: List[EventRecord] = field(default_factory=list)

    metadata: Dict[str, str] = field(default_factory=dict)

    @property
    def duration(self) -> timedelta:
        """
        Продолжительность записи.
        """

        if not self.telemetry:
            return timedelta()

        return timedelta(
            milliseconds=(
                self.telemetry[-1].timestamp_ms
                - self.telemetry[0].timestamp_ms
            )
        )

    @property
    def sample_count(self) -> int:
        """
        Количество измерений.
        """

        return len(self.telemetry)


# ============================================================
# Статистика анализа
# ============================================================

@dataclass(slots=True)
class Statistics:
    """
    Основная статистика,
    которая будет отображаться в отчете.
    """

    duration: timedelta

    samples: int

    max_voltage: float
    min_voltage: float
    avg_voltage: float

    max_current: float
    min_current: float
    avg_current: float

    max_power: float
    avg_power: float

    max_temperature: float
    avg_temperature: float

    total_capacity: float

    total_energy: float

    max_internal_resistance: Optional[float] = None

    avg_internal_resistance: Optional[float] = None


# ============================================================
# Найденная аномалия
# ============================================================

@dataclass(slots=True)
class Anomaly:
    """
    Найденная проблема.
    """

    timestamp_ms: int

    level: str

    title: str

    description: str


# ============================================================
# Результат анализа
# ============================================================

@dataclass(slots=True)
class AnalysisResult:
    """
    Итог работы аналитического движка.
    """

    statistics: Statistics

    anomalies: List[Anomaly] = field(default_factory=list)

    extra: Dict[str, float] = field(default_factory=dict)
