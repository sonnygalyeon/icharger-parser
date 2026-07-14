"""
analytics/battery.py

Анализ состояния аккумулятора по данным телеметрии.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


# ==========================================================
# Результат анализа
# ==========================================================

@dataclass(slots=True)
class BatteryAnalysis:
    """
    Результат анализа аккумулятора.
    """

    cells_count: int

    min_cell_voltage: float
    max_cell_voltage: float
    avg_cell_voltage: float

    max_cell_delta: float
    avg_cell_delta: float

    first_cell_delta: float
    last_cell_delta: float

    delta_growth: float

    balanced: bool


# ==========================================================
# Анализатор аккумулятора
# ==========================================================

class BatteryAnalyzer:

    """
    Выполняет анализ состояния аккумулятора.
    """

    CELL_PREFIX = "cell"

    BALANCE_THRESHOLD = 0.020

    def analyze(
        self,
        df: pd.DataFrame,
    ) -> BatteryAnalysis:

        if df.empty:
            raise ValueError("DataFrame пуст.")

        cell_columns = self._cell_columns(df)

        if not cell_columns:
            raise ValueError("Банки не обнаружены.")

        values = df[cell_columns]

        min_voltage = float(values.min().min())
        max_voltage = float(values.max().max())
        avg_voltage = float(values.stack().mean())

        first_delta = float(df["cell_delta"].iloc[0])
        last_delta = float(df["cell_delta"].iloc[-1])

        max_delta = float(df["cell_delta"].max())
        avg_delta = float(df["cell_delta"].mean())

        delta_growth = last_delta - first_delta

        balanced = max_delta <= self.BALANCE_THRESHOLD

        return BatteryAnalysis(
            cells_count=len(cell_columns),

            min_cell_voltage=min_voltage,
            max_cell_voltage=max_voltage,
            avg_cell_voltage=avg_voltage,

            max_cell_delta=max_delta,
            avg_cell_delta=avg_delta,

            first_cell_delta=first_delta,
            last_cell_delta=last_delta,

            delta_growth=delta_growth,

            balanced=balanced,
        )

    # ---------------------------------------------------------

    @staticmethod
    def _cell_columns(
        df: pd.DataFrame,
    ) -> list[str]:
        """
        Возвращает список существующих столбцов банок.
        """

        columns = []

        for column in df.columns:

            if column.startswith("cell") and column[4:].isdigit():

                if df[column].notna().any():

                    columns.append(column)

        return sorted(columns)