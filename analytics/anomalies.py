"""
analytics/anomalies.py

Поиск аномалий в телеметрии iCharger.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd


# ==========================================================
# Типы аномалий
# ==========================================================


class AnomalyType(str, Enum):

    VOLTAGE_DROP = "Voltage Drop"

    CURRENT_SPIKE = "Current Spike"

    TEMPERATURE_SPIKE = "Temperature Spike"

    CELL_IMBALANCE = "Cell Imbalance"

    POWER_SPIKE = "Power Spike"


# ==========================================================
# Модель аномалии
# ==========================================================


@dataclass(slots=True)
class Anomaly:

    sample: int

    time_s: float

    anomaly: AnomalyType

    value: float

    message: str


# ==========================================================
# Анализатор
# ==========================================================


class AnomalyDetector:

    """
    Автоматический поиск аномалий.
    """

    VOLTAGE_DROP_THRESHOLD = -0.15

    CURRENT_SPIKE_THRESHOLD = 3.0

    POWER_SPIKE_THRESHOLD = 50.0

    TEMPERATURE_RATE_THRESHOLD = 1.0

    CELL_DELTA_THRESHOLD = 0.020

    def detect(
        self,
        df: pd.DataFrame,
    ) -> list[Anomaly]:

        if df.empty:
            return []

        anomalies: list[Anomaly] = []

        anomalies.extend(
            self._voltage_drop(df)
        )

        anomalies.extend(
            self._current_spike(df)
        )

        anomalies.extend(
            self._power_spike(df)
        )

        anomalies.extend(
            self._temperature_spike(df)
        )

        anomalies.extend(
            self._cell_imbalance(df)
        )

        anomalies.sort(
            key=lambda item: item.sample
        )

        return anomalies

    # ---------------------------------------------------------

    def _voltage_drop(
        self,
        df: pd.DataFrame,
    ) -> list[Anomaly]:

        result = []

        rows = df[df["dV_dt"] < self.VOLTAGE_DROP_THRESHOLD]

        for _, row in rows.iterrows():

            result.append(

                Anomaly(
                    sample=int(row["sample"]),
                    time_s=float(row["time_s"]),
                    anomaly=AnomalyType.VOLTAGE_DROP,
                    value=float(row["dV_dt"]),
                    message="Резкая просадка напряжения."
                )

            )

        return result

    # ---------------------------------------------------------

    def _current_spike(
        self,
        df: pd.DataFrame,
    ) -> list[Anomaly]:

        result = []

        rows = df[
            df["dI_dt"].abs() >
            self.CURRENT_SPIKE_THRESHOLD
        ]

        for _, row in rows.iterrows():

            result.append(

                Anomaly(
                    sample=int(row["sample"]),
                    time_s=float(row["time_s"]),
                    anomaly=AnomalyType.CURRENT_SPIKE,
                    value=float(row["dI_dt"]),
                    message="Резкий скачок тока."
                )

            )

        return result

    # ---------------------------------------------------------

    def _power_spike(
        self,
        df: pd.DataFrame,
    ) -> list[Anomaly]:

        result = []

        rows = df[
            df["dP_dt"].abs() >
            self.POWER_SPIKE_THRESHOLD
        ]

        for _, row in rows.iterrows():

            result.append(

                Anomaly(
                    sample=int(row["sample"]),
                    time_s=float(row["time_s"]),
                    anomaly=AnomalyType.POWER_SPIKE,
                    value=float(row["dP_dt"]),
                    message="Резкое изменение мощности."
                )

            )

        return result

    # ---------------------------------------------------------

    def _temperature_spike(
        self,
        df: pd.DataFrame,
    ) -> list[Anomaly]:

        result = []

        rows = df[
            df["dT_dt"] >
            self.TEMPERATURE_RATE_THRESHOLD
        ]

        for _, row in rows.iterrows():

            result.append(

                Anomaly(
                    sample=int(row["sample"]),
                    time_s=float(row["time_s"]),
                    anomaly=AnomalyType.TEMPERATURE_SPIKE,
                    value=float(row["dT_dt"]),
                    message="Быстрый рост температуры."
                )

            )

        return result

    # ---------------------------------------------------------

    def _cell_imbalance(
        self,
        df: pd.DataFrame,
    ) -> list[Anomaly]:

        result = []

        rows = df[
            df["cell_delta"] >
            self.CELL_DELTA_THRESHOLD
        ]

        for _, row in rows.iterrows():

            result.append(

                Anomaly(
                    sample=int(row["sample"]),
                    time_s=float(row["time_s"]),
                    anomaly=AnomalyType.CELL_IMBALANCE,
                    value=float(row["cell_delta"]),
                    message="Обнаружена разбалансировка банок."
                )

            )

        return result