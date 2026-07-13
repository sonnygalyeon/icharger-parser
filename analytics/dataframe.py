"""
analytics/dataframe.py

Преобразование ChargerLog в pandas.DataFrame.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from parser.parser import ChargerLog


class DataFrameBuilder:
    """
    Построение DataFrame из телеметрии.
    """

    MAX_CELLS = 10

    def build(self, log: ChargerLog) -> pd.DataFrame:
        """
        Построить DataFrame.
        """

        rows = self._build_rows(log)

        df = pd.DataFrame(rows)

        if df.empty:
            return df

        self._add_time_columns(df)
        self._add_power(df)
        self._add_cell_statistics(df)

        return self._finalize(df)

    # ---------------------------------------------------------

    def _build_rows(
        self,
        log: ChargerLog,
    ) -> list[dict[str, Any]]:

        rows: list[dict[str, Any]] = []

        for sample, packet in enumerate(log.telemetry):

            row = {
                "sample": sample,
                "timestamp_ms": packet.timestamp_ms,
                "mode": packet.mode,
                "flags": packet.flags,
                "current": packet.current_raw,
                "voltage": packet.voltage_raw,
                "capacity": packet.capacity_raw,
                "energy": packet.energy_raw,
                "temperature": packet.temperature_raw,
            }

            for index in range(self.MAX_CELLS):

                value = None

                if index < len(packet.cells_raw):
                    value = packet.cells_raw[index]

                row[f"cell{index + 1}"] = value

            rows.append(row)

        return rows

    # ---------------------------------------------------------

    def _add_time_columns(
        self,
        df: pd.DataFrame,
    ) -> None:

        start = df["timestamp_ms"].iloc[0]

        df["time_ms"] = df["timestamp_ms"] - start

        df["time_s"] = df["time_ms"] / 1000.0

        df["time_min"] = df["time_s"] / 60.0

        df["time_h"] = df["time_min"] / 60.0

    # ---------------------------------------------------------

    def _add_power(
        self,
        df: pd.DataFrame,
    ) -> None:

        df["power"] = df["voltage"] * df["current"]

        df["abs_current"] = df["current"].abs()

        df["abs_power"] = df["power"].abs()

    # ---------------------------------------------------------

    def _add_cell_statistics(
        self,
        df: pd.DataFrame,
    ) -> None:

        cell_columns = [
            f"cell{i}"
            for i in range(1, self.MAX_CELLS + 1)
        ]

        df["cell_min"] = df[cell_columns].min(axis=1)

        df["cell_max"] = df[cell_columns].max(axis=1)

        df["cell_avg"] = df[cell_columns].mean(axis=1)

        df["cell_delta"] = (
            df["cell_max"] - df["cell_min"]
        )

    # ---------------------------------------------------------

    def _finalize(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        df = df.sort_values("timestamp_ms")

        df.reset_index(
            drop=True,
            inplace=True,
        )

        return df