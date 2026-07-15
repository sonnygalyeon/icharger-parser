from pathlib import Path

from icharger_analyzer.analytics import analyze_log
from icharger_analyzer.parser import IChargerParser


def test_decode_packet_and_skip_broken_line(tmp_path: Path) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text(
        "@Model:4010DUO; Fireware:V2.20; Hardware:V2.00; SN:ABC\x00\n"
        "$1;2;0;1;0;-500;24300;21000;0;350;0;4200;4200;4200;4200;4200;0;0;0;0;0;1\n"
        "$broken\n"
        "$1;2;1000;1;0;-500;24300;20950;-1;351;0;4190;4190;4190;4190;4190;0;0;0;0;0;1\n",
        encoding="utf-8",
    )
    log = IChargerParser().parse(sample)
    result = analyze_log(log)
    assert log.header.model == "4010DUO"
    assert log.header.firmware == "V2.20"
    assert len(log.issues) == 1
    assert result.telemetry.loc[0, "current_a"] == -5.0
    assert result.telemetry.loc[0, "pack_voltage_v"] == 21.0
    assert result.summary.detected_cells == 5
