import pandas as pd

from icharger_analyzer.charts import choose_comparison_step, resample_for_comparison


def _frame(duration: int) -> pd.DataFrame:
    time_s = list(range(duration + 1))
    return pd.DataFrame(
        {
            "time_s": time_s,
            "dt_s": [0.0] + [1.0] * duration,
            "pack_voltage_v": [4.2 - 0.001 * value for value in time_s],
            "current_a": [-1.0] * (duration + 1),
            "power_w": [-4.0] * (duration + 1),
            "capacity_counter_ah": [value / 3600 for value in time_s],
            "energy_throughput_wh": [value / 900 for value in time_s],
            "internal_temp_c": [25.0] * (duration + 1),
            "external_temp_c": [None] * (duration + 1),
            "cell_1_v": [4.2 - 0.001 * value for value in time_s],
            "cell_min_v": [4.2 - 0.001 * value for value in time_s],
            "cell_delta_v": [0.0] * (duration + 1),
        }
    )


def test_common_period_and_regular_grid() -> None:
    series = [("A", _frame(20)), ("B", _frame(30))]
    assert choose_comparison_step(series, 5.0) == 5.0
    sampled = resample_for_comparison(series[0][1], 5.0)
    assert sampled["time_s"].tolist() == [0.0, 5.0, 10.0, 15.0, 20.0]
    assert sampled["comparison_interval_s"].eq(5.0).all()
    assert sampled["progress_pct"].iloc[-1] == 100.0
