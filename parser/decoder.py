"""
decoder.py

Декодирование строк логов iCharger.

Этот модуль НЕ читает файл.

Он получает одну строку

$1;2;1000;...

и превращает её в объект Python.

Все остальные части проекта работают уже с объектами,
а не со строками.
"""

from __future__ import annotations

from abc import ABC
from typing import Callable
from typing import Dict

from .models import (
    EventRecord,
    TelemetryRecord,
)

# ============================================================
# Исключения
# ============================================================


class DecodeError(Exception):
    """Ошибка декодирования строки."""


# ============================================================
# Базовый пакет
# ============================================================


class Packet(ABC):
    """
    Абстрактный пакет.

    Все типы пакетов наследуются от него.
    """

    pass


# ============================================================
# Регистрация декодеров
# ============================================================


Decoder = Callable[[list[str]], Packet]

_DECODERS: Dict[int, Decoder] = {}


def register(packet_id: int):
    """
    Декоратор регистрации декодера.

    Пример:

    @register(2)
    def decode(...):
        ...
    """

    def wrapper(func: Decoder):
        _DECODERS[packet_id] = func
        return func

    return wrapper


# ============================================================
# Главная функция
# ============================================================


def decode_line(line: str) -> Packet | None:
    """
    Декодировать одну строку.
    """

    line = line.strip()

    if not line:
        return None

    if not line.startswith("$"):
        return None

    parts = line.split(";")

    if len(parts) < 2:
        raise DecodeError("Некорректная строка.")

    try:
        packet_type = int(parts[1])

    except ValueError:
        raise DecodeError("Не удалось определить тип пакета.")

    decoder = _DECODERS.get(packet_type)

    if decoder is None:
        raise DecodeError(
            f"Неизвестный пакет {packet_type}"
        )

    return decoder(parts)

@register(2)
def decode_telemetry(parts: list[str]) -> TelemetryRecord:
    """
    Телеметрический пакет.

    $1;2;....
    """

    try:

        timestamp = int(parts[2])

        current = float(parts[5]) / 100.0

        voltage = float(parts[6]) / 1000.0

        power = voltage * current

        capacity = float(parts[7])

        temperature = float(parts[9])

    except (ValueError, IndexError):

        raise DecodeError(
            "Ошибка чтения пакета телеметрии."
        )

    return TelemetryRecord(

        timestamp_ms=timestamp,

        voltage=voltage,

        current=current,

        power=power,

        capacity=capacity,

        energy=0.0,

        temperature=temperature,

        internal_resistance=None,

        cell_voltages=[],

        balancing=False,

        raw=[
            int(x) if x.lstrip("-").isdigit() else 0
            for x in parts[2:]
        ],
    )

@register(128)
def decode_packet128(parts: list[str]) -> EventRecord:
    """
    Служебный пакет.

    Пока сохраняем как событие.

    После изучения остальных логов
    можно будет заменить отдельным классом.
    """

    timestamp = int(parts[2])

    return EventRecord(

        timestamp_ms=timestamp,

        event="PACKET128",

        description="Service packet",

    )

def available_packets() -> list[int]:
    """
    Вернуть список поддерживаемых пакетов.
    """

    return sorted(_DECODERS.keys())
