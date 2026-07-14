"""
config.py

Глобальная конфигурация проекта.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Config:

    APP_NAME: str = "iCharger Analyzer"

    VERSION: str = "1.0.0"

    OUTPUT_DIR: Path = Path("output")

    REPORT_NAME: str = "report.html"

    DASHBOARD_NAME: str = "dashboard.html"

    DARK_THEME: bool = True

    CELL_BALANCE_THRESHOLD: float = 0.020

    MAX_TEMPERATURE: float = 60.0

    HTML_TITLE: str = "iCharger Analyzer Report"


config = Config()