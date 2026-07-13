"""
tools/protocol_explorer.py

Исследование неизвестных логов iCharger.

Автор: iCharger Analyzer

Назначение:

Не декодирует значения.

Анализирует структуру пакетов.

Показывает

- типы пакетов
- число полей
- статистику
- изменяемость столбцов
"""

from pathlib import Path
from collections import defaultdict


class ProtocolExplorer:

    def __init__(self):

        self.packet_types = defaultdict(list)

    def load(self, filename: str):

        path = Path(filename)

        with path.open(
            "r",
            encoding="utf8",
            errors="ignore"
        ) as f:

            for line in f:

                line = line.strip()

                if not line.startswith("$"):
                    continue

                parts = line.split(";")

                if len(parts) < 2:
                    continue

                packet = int(parts[1])

                self.packet_types[packet].append(parts)

    def print_summary(self):

        print("=" * 60)

        print("Protocol Explorer")

        print("=" * 60)

        print()

        for packet, records in sorted(self.packet_types.items()):

            print(f"Packet {packet}")

            print("-" * 40)

            print(f"Records : {len(records)}")

            print(f"Fields  : {len(records[0])}")

            print()

    def analyze_fields(self):

        for packet, records in sorted(self.packet_types.items()):

            print()

            print("=" * 60)

            print(f"Packet {packet}")

            print("=" * 60)

            count = len(records[0])

            for field in range(count):

                values = []

                for r in records:

                    values.append(r[field])

                unique = set(values)

                print()

                print(f"Field {field}")

                if len(unique) == 1:

                    print("Constant")

                    print(next(iter(unique)))

                    continue

                numeric = True

                converted = []

                for value in values:

                    try:

                        converted.append(float(value))

                    except:

                        numeric = False

                        break

                if numeric:

                    print("Numeric")

                    print("Min :", min(converted))

                    print("Max :", max(converted))

                    print("Unique :", len(unique))

                else:

                    print("String")

                    print("Unique :", len(unique))


if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument("file")

    args = parser.parse_args()

    explorer = ProtocolExplorer()

    explorer.load(args.file)

    explorer.print_summary()

    explorer.analyze_fields()