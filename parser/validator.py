"""
parser/validator.py

Проверка логов iCharger перед парсингом.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .decoder import (
    DecodeError,
    decode_header,
    decode_line,
)


# ==========================================================
# Результат проверки
# ==========================================================

@dataclass(slots=True)
class ValidationResult:
    """
    Результат проверки файла.
    """

    valid: bool = True

    errors: list[str] = field(default_factory=list)

    warnings: list[str] = field(default_factory=list)

    packet_count: int = 0

    header_count: int = 0

    broken_packets: int = 0

    def add_error(self, message: str) -> None:
        self.valid = False
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


# ==========================================================
# Валидатор
# ==========================================================

class LogValidator:

    """
    Проверяет корректность логов iCharger.
    """

    SUPPORTED_EXTENSIONS = {
        ".txt",
        ".log",
    }

    def validate(
        self,
        filename: str | Path,
    ) -> ValidationResult:

        result = ValidationResult()

        path = Path(filename)

        # -----------------------------
        # Проверка существования
        # -----------------------------

        if not path.exists():
            result.add_error(
                f"Файл '{path}' не существует."
            )
            return result

        if not path.is_file():
            result.add_error(
                f"'{path}' не является файлом."
            )
            return result

        # -----------------------------
        # Расширение
        # -----------------------------

        if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            result.add_warning(
                f"Неизвестное расширение: {path.suffix}"
            )

        # -----------------------------
        # Чтение файла
        # -----------------------------

        try:
            with path.open(
                "r",
                encoding="utf-8",
                errors="ignore",
            ) as file:

                for number, line in enumerate(file, start=1):

                    line = line.strip()

                    if not line:
                        continue

                    #
                    # Заголовок
                    #

                    if not line.startswith("$"):

                        header = decode_header(line)

                        if header is not None:
                            result.header_count += 1

                        continue

                    #
                    # Пакеты
                    #

                    try:

                        decode_line(line)

                        result.packet_count += 1

                    except DecodeError as exc:

                        result.broken_packets += 1

                        result.add_warning(
                            f"Строка {number}: {exc}"
                        )

        except OSError as exc:

            result.add_error(str(exc))

            return result

        # -----------------------------
        # Финальные проверки
        # -----------------------------

        if result.packet_count == 0:

            result.add_error(
                "Телеметрические пакеты не найдены."
            )

        if result.header_count == 0:

            result.add_warning(
                "Заголовок отсутствует."
            )

        return result