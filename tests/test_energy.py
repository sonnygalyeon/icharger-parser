from pathlib import Path

import pytest

from icharger_analyzer.analytics import analyze_log
from icharger_analyzer.models import ChargerLog, HeaderInfo
from icharger_analyzer.parser import IChargerParser


def log_from_samples(times, currents, output=3.5, cells=(4.0,)):
    log = ChargerLog(Path("energy.txt"), HeaderInfo())
    for time, current in zip(times, currents):
        values = [1, 2, int(time * 1000), 2, 0, round(current * 100), 24000, round(output * 1000), 0, 250, 0]
        values += [round(v * 1000) for v in cells] + [0] * (10 - len(cells)) + [0]
        log.telemetry.append(IChargerParser._decode_telemetry(values))
    return log


def test_constant_discharge_wh_and_voltage_sources():
    # 2 A for one hour: 8 Wh at a 4 V battery, 7 Wh at a 3.5 V output.
    log = log_from_samples(range(0, 3601, 60), [-2] * 61)
    summary = analyze_log(log).summary
    assert summary.discharge_capacity_ah == pytest.approx(2)
    assert summary.discharge_energy_wh == pytest.approx(8)
    assert summary.output_discharge_energy_wh == pytest.approx(7)
    assert summary.energy_difference_wh == pytest.approx(1)
    assert summary.charge_energy_wh == 0
    assert analyze_log(log, "output").summary.discharge_energy_wh == pytest.approx(7)


def test_multi_cell_sum_and_no_double_counting():
    log = log_from_samples([0, 1800, 3600], [-2] * 3, output=7, cells=(4, 3.8))
    result = analyze_log(log)
    assert result.summary.discharge_energy_wh == pytest.approx(15.6)
    assert result.telemetry.battery_voltage_v.eq(7.8).all()


def test_zero_crossing_charge_and_discharge_are_not_cancelled():
    summary = analyze_log(log_from_samples([0, 3600], [2, -2], output=4)).summary
    assert summary.charge_capacity_ah == pytest.approx(.5)
    assert summary.discharge_capacity_ah == pytest.approx(.5)
    assert summary.charge_energy_wh == pytest.approx(2)
    assert summary.discharge_energy_wh == pytest.approx(2)
    assert summary.battery_energy_wh == pytest.approx(4)


@pytest.mark.parametrize("cells", [(), (4, 0, 4)])
def test_absent_or_noncontiguous_cells_fall_back_to_output(cells):
    log = log_from_samples([0, 3600], [-1, -1], cells=cells)
    result = analyze_log(log)
    assert result.summary.battery_energy_source == "output"
    assert result.summary.discharge_energy_wh == pytest.approx(3.5)
    with pytest.raises(ValueError, match="нужны все"):
        analyze_log(log, "cells")


def test_intermittent_cell_uses_one_source_for_whole_log():
    log = log_from_samples([0, 1, 2], [-1] * 3, cells=(4, 4))
    log.telemetry[1].cell_voltages_v = (4, None) + (None,) * 8
    result = analyze_log(log)
    assert result.summary.battery_energy_source == "output"
    assert result.telemetry.battery_voltage_v.eq(3.5).all()


def test_gap_duplicates_and_one_sample_do_not_invent_energy():
    result = analyze_log(log_from_samples([0, 1, 1, 2, 100, 101], [-1] * 6))
    assert result.summary.integration_omitted_s == 98
    assert result.summary.duplicate_timestamp_count == 1
    assert result.summary.discharge_energy_wh == pytest.approx(4 * 3 / 3600)
    single = analyze_log(log_from_samples([0], [-2]))
    assert single.summary.discharge_energy_wh == 0


def test_irregular_intervals_use_trapezoids():
    # I=-1 A; U=4 -> 3 -> 2 V; dt=1,2 s: (3.5 + 2*2.5) Ws.
    log = log_from_samples([0, 1, 3], [-1] * 3)
    for record, voltage in zip(log.telemetry, [4, 3, 2]):
        record.cell_voltages_v = (voltage,) + (None,) * 9
    assert analyze_log(log).summary.discharge_energy_wh == pytest.approx(8.5 / 3600)


def test_mixed_channels_cannot_be_integrated_as_one_battery():
    log = log_from_samples([0, 1], [-1, -1])
    log.telemetry[1].channel = 2
    with pytest.raises(ValueError, match="Несколько каналов"):
        analyze_log(log)


def test_real_discharge_fields_and_checksum(tmp_path):
    # Exact first telemetry packet of Discharge_32, without identifying header.
    line = "$1;2;0;2;0;0;24344;4252;0;324;0;4246;0;0;0;0;0;0;0;0;0;43"
    path = tmp_path / "packet.txt"
    path.write_text(line + "\n" + line.replace("4252", "9252") + "\n$1;2;1000;2\n", encoding="utf-8")
    log = IChargerParser().parse(path)
    assert len(log.telemetry) == 1
    assert len(log.issues) == 2
    assert "Checksum mismatch" in log.issues[0].message
    assert log.telemetry[0].pack_voltage_v == pytest.approx(4.252)
    assert log.telemetry[0].cell_voltages_v[0] == pytest.approx(4.246)


def test_counter_energy_uses_increment_and_average_voltage():
    log = log_from_samples([0, 1800, 3600], [-2] * 3)
    for record, counter, voltage in zip(log.telemetry, [-500, -1500, -3500], [4, 3, 2]):
        record.capacity_mah_signed = counter
        record.cell_voltages_v = (voltage,) + (None,) * 9
    result = analyze_log(log)
    # 3.5 V * 1 Ah + 2.5 V * 2 Ah, excluding the unknown history before -500 mAh.
    assert result.summary.counter_discharge_energy_wh == pytest.approx(8.5)
    assert result.summary.counter_charge_energy_wh == 0
    assert result.summary.counter_energy_skipped_intervals == 0


def test_counter_energy_does_not_recompute_charge_from_current():
    log = log_from_samples([0, 60, 120], [-2] * 3)
    result = analyze_log(log)  # all counter values are 0
    assert result.summary.discharge_energy_wh > 0
    assert result.summary.counter_discharge_energy_wh == 0
    for record, counter in zip(log.telemetry, [0, -30, -60]):
        record.capacity_mah_signed = counter
    assert analyze_log(log).summary.counter_discharge_energy_wh == pytest.approx(.24)


def test_counter_reset_is_not_counted_as_charge():
    log = log_from_samples([0, 1, 2, 3], [-3.6] * 4)
    for record, counter in zip(log.telemetry, [-100, -101, 0, -1]):
        record.capacity_mah_signed = counter
    s = analyze_log(log).summary
    assert s.counter_discharge_energy_wh == pytest.approx(.008)
    assert s.counter_charge_energy_wh == 0
    assert s.counter_jump_count == 1
    assert s.counter_energy_skipped_intervals == 1


def test_counter_energy_gap_and_duplicate_are_not_filled_in():
    log = log_from_samples([0, 1, 1, 2, 100, 101], [-3.6] * 6)
    for record, counter in zip(log.telemetry, [0, -1, -2, -3, -101, -102]):
        record.capacity_mah_signed = counter
    s = analyze_log(log).summary
    assert s.counter_discharge_energy_wh == pytest.approx(.012)
    assert s.counter_energy_skipped_intervals == 2


def test_counter_positive_and_negative_directions():
    log = log_from_samples([0, 3600, 7200], [0, 0, 0], cells=(4, 4))
    for record, counter in zip(log.telemetry, [0, 1000, 500]):
        record.capacity_mah_signed = counter
    s = analyze_log(log).summary
    assert s.counter_charge_energy_wh == pytest.approx(8)
    assert s.counter_discharge_energy_wh == pytest.approx(4)
    assert s.counter_energy_wh == pytest.approx(12)
