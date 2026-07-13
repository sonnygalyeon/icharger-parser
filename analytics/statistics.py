"""
analytics/statistics.py

Расчёт статистики по данным телеметрии.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


# ==========================================================
# Модель статистики
# ==========================================================


@dataclass(slots=True)
class Statistics:
    """
    Итоговая статистика теста.
    """

    samples: int

    duration_s: float

    min_voltage: float
    max_voltage: float
    avg_voltage: float

    min_current: float
    max_current: float
    avg_current: float

    max_power: float
    avg_power: float

    max_temperature: float
    avg_temperature: float

    max_cell_delta: float

    capacity: float

    energy: float


# ==========================================================
# Расчёт статистики
# ==========================================================


class StatisticsCalculator:

    """
    Расчёт общей статистики.
    """

    def calculate(
        self,
        df: pd.DataFrame,
    ) -> Statistics:

        if df.empty:
            raise ValueError(
                "DataFrame пуст."
            )

        return Statistics(

            samples=len(df),

            duration_s=float(
                df["time_s"].iloc[-1]
            ),

            min_voltage=float(
                df["voltage"].min()
            ),

            max_voltage=float(
                df["voltage"].max()
            ),

            avg_voltage=float(
                df["voltage"].mean()
            ),

            min_current=float(
                df["current"].min()
            ),

            max_current=float(
                df["current"].max()
            ),

            avg_current=float(
                df["current"].mean()
            ),

            max_power=float(
                df["power"].max()
            ),

            avg_power=float(
                df["power"].mean()
            ),

            max_temperature=float(
                df["temperature"].max()
            ),

            avg_temperature=float(
                df["temperature"].mean()
            ),

            max_cell_delta=float(
                df["cell_delta"].max()
            ),

            capacity=float(
                df["capacity"].max()
            ),

            energy=float(
                df["energy"].max()
            ),
        )