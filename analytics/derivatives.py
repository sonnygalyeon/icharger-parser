"""
analytics/derivatives.py

Расчёт производных параметров телеметрии.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class DerivativesCalculator:
    """
    Добавляет производные столбцы в DataFrame.

    Все расчёты выполняются "на месте".
    """

    def calculate(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        if df.empty:
            return df

        self._calculate_dt(df)
        self._calculate_voltage(df)
        self._calculate_current(df)
        self._calculate_power(df)
        self._calculate_temperature(df)
        self._calculate_cell_delta(df)

        return df

    # ---------------------------------------------------------

    @staticmethod
    def _calculate_dt(df: pd.DataFrame) -> None:
        """
        Интервал между измерениями.
        """

        df["dt"] = df["time_s"].diff()

        df["dt"] = df["dt"].fillna(0)

    # ---------------------------------------------------------

    @staticmethod
    def _safe_rate(
        value: pd.Series,
        dt: pd.Series,
    ) -> pd.Series:
        """
        Производная с защитой от деления на ноль.
        """

        derivative = value.diff()

        rate = derivative.divide(
            dt.replace(0, np.nan)
        )

        return rate.fillna(0)

    # ---------------------------------------------------------

    def _calculate_voltage(
        self,
        df: pd.DataFrame,
    ) -> None:

        df["dV"] = df["voltage"].diff().fillna(0)

        df["dV_dt"] = self._safe_rate(
            df["voltage"],
            df["dt"],
        )

    # ---------------------------------------------------------

    def _calculate_current(
        self,
        df: pd.DataFrame,
    ) -> None:

        df["dI"] = df["current"].diff().fillna(0)

        df["dI_dt"] = self._safe_rate(
            df["current"],
            df["dt"],
        )

    # ---------------------------------------------------------

    def _calculate_power(
        self,
        df: pd.DataFrame,
    ) -> None:

        df["dP"] = df["power"].diff().fillna(0)

        df["dP_dt"] = self._safe_rate(
            df["power"],
            df["dt"],
        )

    # ---------------------------------------------------------

    def _calculate_temperature(
        self,
        df: pd.DataFrame,
    ) -> None:

        df["dT"] = df["temperature"].diff().fillna(0)

        df["dT_dt"] = self._safe_rate(
            df["temperature"],
            df["dt"],
        )

    # ---------------------------------------------------------

    def _calculate_cell_delta(
        self,
        df: pd.DataFrame,
    ) -> None:

        df["dCellDelta"] = (
            df["cell_delta"]
            .diff()
            .fillna(0)
        )

        df["dCellDelta_dt"] = self._safe_rate(
            df["cell_delta"],
            df["dt"],
        )