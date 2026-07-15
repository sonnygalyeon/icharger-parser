from pathlib import Path

import pytest

from icharger_analyzer.analytics import analyze_log
from icharger_analyzer.parser import IChargerParser


@pytest.mark.parametrize(
    "filename,cells,expected_start_v",
    [
        ("LiIo[Discharge_30_CH1]_m5_5s_19Ah.txt", 5, 20.691),
        ("LiIo[Discharge_31_CH1]_akim_6s_22Ah.txt", 6, 25.490),
        ("LiPo[Discharge_6_CH1]_copter_6s.txt", 6, 25.084),
        ("LiPo[Discharge_26_CH1]u_1s.txt", 0, 4.178),
    ],
)
def test_supplied_logs(filename: str, cells: int, expected_start_v: float) -> None:
    root = Path(__file__).resolve().parents[2]
    source = root / filename
    if not source.exists():
        pytest.skip(f"Test fixture not copied next to project: {source}")
    log = IChargerParser().parse(source)
    result = analyze_log(log)
    assert result.summary.samples > 1000
    assert result.summary.detected_cells == cells
    assert result.summary.start_pack_voltage_v == pytest.approx(expected_start_v, abs=0.001)
    assert result.summary.capacity_counter_ah > 1.0
