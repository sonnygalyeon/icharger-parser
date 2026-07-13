"""
parser/decoder.py

Декодирование строк логов iCharger.

Автор: iCharger Analyzer

Назначение:
    • разбор строк телеметрии;
    • преобразование строк в объекты моделей;
    • валидация количества полей;
    • безопасное преобразование типов.
"""

from __future__ import annotations

from typing import List

from .models import (
    Header,
    TelemetryRecord,
    StatusRecord,
)


# ==========================================================
# Исключения
# ==========================================================


class DecodeError(Exception):
    """Базовое исключение декодера."""


class InvalidPacketError(DecodeError):
    """Некорректный пакет."""


class UnsupportedPacketError(DecodeError):
    """Тип пакета не поддерживается."""


# ==========================================================
# Константы
# ==========================================================

PACKET_TELEMETRY = 2
PACKET_STATUS = 128

EXPECTED_PACKET2_FIELDS = 22
MIN_PACKET128_FIELDS = 5


# ==========================================================
# Вспомогательные функции
# ==========================================================


def _safe_int(value: str) -> int:
    """
    Безопасное преобразование строки в int.
    """

    try:
        return int(value)

    except ValueError as exc:
        raise InvalidPacketError(
            f"Невозможно преобразовать '{value}' в int."
        ) from exc


def _split_packet(line: str) -> List[str]:
    """
    Разбивает строку пакета на поля.

    Пример:

        $1;2;370000;...

    ->
        ["1","2","370000",...]
    """

    line = line.strip()

    if not line:
        raise InvalidPacketError("Пустая строка.")

    if not line.startswith("$"):
        raise InvalidPacketError(
            "Строка не начинается с '$'."
        )

    line = line[1:]

    parts = [part.strip() for part in line.split(";")]

    if len(parts) < 2:
        raise InvalidPacketError(
            "Недостаточно полей."
        )

    return parts


def _parse_cells(values: List[int]) -> list[int]:
    """
    Возвращает только реально существующие банки.

    Нулевые значения отбрасываются.
    """

    return [cell for cell in values if cell > 0]


# ==========================================================
# Packet Type = 2
# ==========================================================


def _decode_packet2(parts: List[str]) -> TelemetryRecord:
    """
    Декодирование пакета телеметрии.

    Формат:

    $1;2;
    timestamp;
    mode;
    flags;
    current;
    voltage;
    capacity;
    energy;
    temperature;
    reserved;
    cell1;
    cell2;
    cell3;
    cell4;
    cell5;
    cell6;
    cell7;
    cell8;
    cell9;
    cell10;
    checksum
    """

    if len(parts) != EXPECTED_PACKET2_FIELDS:
        raise InvalidPacketError(
            f"Packet2: ожидалось "
            f"{EXPECTED_PACKET2_FIELDS} полей, "
            f"получено {len(parts)}."
        )

    values = [_safe_int(v) for v in parts]

    channel = values[0]
    packet_type = values[1]

    timestamp = values[2]

    mode = values[3]
    flags = values[4]

    current = values[5]
    voltage = values[6]

    capacity = values[7]
    energy = values[8]

    temperature = values[9]

    reserved = values[10]

    cells = _parse_cells(
        values[11:21]
    )

    checksum = values[21]

    return TelemetryRecord(
        channel=channel,
        packet_type=packet_type,
        timestamp_ms=timestamp,
        mode=mode,
        flags=flags,
        current_raw=current,
        voltage_raw=voltage,
        capacity_raw=capacity,
        energy_raw=energy,
        temperature_raw=temperature,
        reserved_raw=reserved,
        cells_raw=cells,
        checksum=checksum,
    )

# ==========================================================
# Packet Type = 128
# ==========================================================


def _decode_packet128(parts: List[str]) -> StatusRecord:
    """
    Декодирование служебного пакета (Packet Type = 128).

    Формат пакета пока полностью не документирован,
    поэтому неизвестные поля сохраняются в raw_values.
    """

    if len(parts) < MIN_PACKET128_FIELDS:
        raise InvalidPacketError(
            f"Packet128: недостаточно полей ({len(parts)})."
        )

    values = [_safe_int(value) for value in parts]

    channel = values[0]
    packet_type = values[1]
    timestamp = values[2]

    payload = values[3:]

    return StatusRecord(
        channel=channel,
        packet_type=packet_type,
        timestamp_ms=timestamp,
        raw_values=payload,
    )


# ==========================================================
# Header
# ==========================================================


def decode_header(line: str) -> Header | None:
    """
    Декодирует строку заголовка.

    Поддерживаются форматы:

        Firmware=2.20

        Firmware : 2.20

        Firmware= 2.20
    """

    line = line.strip()

    if not line:
        return None

    if line.startswith("$"):
        return None

    separator = None

    if "=" in line:
        separator = "="

    elif ":" in line:
        separator = ":"

    if separator is None:
        return None

    key, value = line.split(separator, 1)

    key = key.strip()
    value = value.strip()

    if not key:
        return None

    return Header(
        key=key,
        value=value,
    )


# ==========================================================
# Packet Detection
# ==========================================================


def _packet_type(parts: List[str]) -> int:
    """
    Возвращает тип пакета.
    """

    if len(parts) < 2:
        raise InvalidPacketError(
            "Не удалось определить тип пакета."
        )

    return _safe_int(parts[1])


# ==========================================================
# Public Decoder
# ==========================================================


def decode_line(line: str):
    """
    Декодирует одну строку лога.

    Возвращает один из объектов:

        TelemetryRecord
        StatusRecord

    Исключения:

        DecodeError
        InvalidPacketError
        UnsupportedPacketError
    """

    parts = _split_packet(line)

    packet_type = _packet_type(parts)

    if packet_type == PACKET_TELEMETRY:
        return _decode_packet2(parts)

    if packet_type == PACKET_STATUS:
        return _decode_packet128(parts)

    raise UnsupportedPacketError(
        f"Неподдерживаемый тип пакета: {packet_type}"
    )


# ==========================================================
# Public API
# ==========================================================

__all__ = [
    "DecodeError",
    "InvalidPacketError",
    "UnsupportedPacketError",
    "decode_line",
    "decode_header",
]