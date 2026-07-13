"""
parser/dataframe.py

Преобразование пакетов iCharger
в pandas.DataFrame.

Автор: iCharger Analyzer
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from .packets import TelemetryPacket


class DataFrameBuilder:
    """
    Создание DataFrame
    из телеметрических пакетов.
    """

    def __init__(self):

        self._columns = [
            "time_ms",
            "time_s",
            "current",
            "voltage",
            "power",
            "capacity",
            "energy",
            "temperature",
            "cell_count",
            "cell_delta",
            "max_cell",
            "min_cell",
        ]

    # -----------------------------------------------------

    def build(
        self,
        packets: Iterable[TelemetryPacket]
    ) -> pd.DataFrame:

        rows = []

        for packet in packets:

            rows.append(
                {
                    "time_ms": packet.timestamp_ms,

                    "time_s": packet.timestamp_ms / 1000,

                    "current": packet.current,

                    "voltage": packet.voltage,

                    "power": packet.power,

                    "capacity": packet.capacity,

                    "energy": packet.energy,

                    "temperature": packet.temperature,

                    "cell_count": packet.cell_count,

                    "cell_delta": packet.cell_delta,

                    "max_cell": packet.max_cell_voltage,

                    "min_cell": packet.min_cell_voltage,
                }
            )

        df = pd.DataFrame(
            rows,
            columns=self._columns
        )

        if df.empty:
            return df

        self._calculate(df)

        return df

    # -----------------------------------------------------

    def _calculate(
        self,
        df: pd.DataFrame
    ):

        #
        # Производные
        #

        df["dV"] = df["voltage"].diff()

        df["dI"] = df["current"].diff()

        df["dT"] = df["temperature"].diff()

        #
        # dt
        #

        dt = df["time_s"].diff()

        dt.replace(
            0,
            np.nan,
            inplace=True
        )

        #
        # Скорости изменения
        #

        df["dV_dt"] = df["dV"] / dt

        df["dI_dt"] = df["dI"] / dt

        df["dT_dt"] = df["dT"] / dt

        #
        # Скользящие средние
        #

        df["voltage_avg"] = (
            df["voltage"]
            .rolling(20)
            .mean()
        )

        df["current_avg"] = (
            df["current"]
            .rolling(20)
            .mean()
        )

        df["temperature_avg"] = (
            df["temperature"]
            .rolling(20)
            .mean()
        )

        #
        # Абсолютная мощность
        #

        df["abs_power"] = (
            df["power"]
            .abs()
        )

        #
        # КПД
        #

        if df["power"].max() != 0:

            df["power_percent"] = (
                df["power"]
                /
                df["power"].max()
                * 100
            )

        #
        # Время
        #

        df["minutes"] = (
            df["time_s"] / 60
        )

        #
        # Индекс
        #

        df.set_index(
            "time_s",
            inplace=True
        )

    # -----------------------------------------------------

    @staticmethod
    def export_csv(
        df: pd.DataFrame,
        filename: str
    ):

        df.to_csv(
            filename,
            index=True
        )

    # -----------------------------------------------------

    @staticmethod
    def info(df: pd.DataFrame):

        print()

        print("=" * 70)

        print("DataFrame")

        print("=" * 70)

        print()

        print(df.info())

        print()

        print(df.head())

        print()