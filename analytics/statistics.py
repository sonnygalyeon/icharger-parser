"""
analytics/statistics.py

Расчет статистики по данным телеметрии.

Этот модуль не знает ничего о формате логов.
Он получает готовый pandas.DataFrame.

Автор: iCharger Analyzer
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(slots=True)
class Statistics:
    duration_seconds: float

    samples: int

    min_voltage: float
    max_voltage: float
    avg_voltage: float

    min_current: float
    max_current: float
    avg_current: float

    min_power: float
    max_power: float
    avg_power: float

    min_temperature: float
    max_temperature: float
    avg_temperature: float

    total_capacity: float
    total_energy: float

    max_cell_delta: float | None
    avg_cell_delta: float | None

    average_cell_voltage: float | None

    max_cell_voltage: float | None
    min_cell_voltage: float | None


class StatisticsEngine:

    """
    Расчет общей статистики.
    """

    def calculate(
        self,
        df: pd.DataFrame
    ) -> Statistics:

        if df.empty:
            raise ValueError("DataFrame пуст.")

        duration = (
            df.index.max()
            - df.index.min()
        )

        return Statistics(

            duration_seconds=float(duration),

            samples=len(df),

            min_voltage=df["voltage"].min(),
            max_voltage=df["voltage"].max(),
            avg_voltage=df["voltage"].mean(),

            min_current=df["current"].min(),
            max_current=df["current"].max(),
            avg_current=df["current"].mean(),

            min_power=df["power"].min(),
            max_power=df["power"].max(),
            avg_power=df["power"].mean(),

            min_temperature=df["temperature"].min(),
            max_temperature=df["temperature"].max(),
            avg_temperature=df["temperature"].mean(),

            total_capacity=df["capacity"].max(),
            total_energy=df["energy"].max(),

            max_cell_delta=(
                df["cell_delta"].max()
                if "cell_delta" in df
                else None
            ),

            avg_cell_delta=(
                df["cell_delta"].mean()
                if "cell_delta" in df
                else None
            ),

            average_cell_voltage=(
                (
                    df["max_cell"]
                    + df["min_cell"]
                ).mean() / 2
                if (
                    "max_cell" in df
                    and "min_cell" in df
                )
                else None
            ),

            max_cell_voltage=(
                df["max_cell"].max()
                if "max_cell" in df
                else None
            ),

            min_cell_voltage=(
                df["min_cell"].min()
                if "min_cell" in df
                else None
            ),
        )

    @staticmethod
    def to_dict(
        stats: Statistics
    ) -> dict[str, Any]:

        return stats.__dict__