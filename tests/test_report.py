from pathlib import Path
import json
import re

from icharger_analyzer.analytics import analyze_log
from icharger_analyzer.charts import create_time_dashboard, create_discharge_curve, independent_charts
from icharger_analyzer.parser import IChargerParser
from icharger_analyzer.report import write_report


def example():
    path = Path(__file__).resolve().parents[1] / "examples/LiIo[Discharge_30_CH1]_m5_5s_19Ah.txt"
    log = IChargerParser().parse(path)
    return log, analyze_log(log)


def test_independent_axes_preserve_samples_secondary_axes_and_thresholds():
    _, result = example()
    dashboard = create_time_dashboard(result.telemetry, result.status, result.warnings)
    charts = independent_charts(dashboard)
    assert len(charts) == 8
    assert sum(len(t.x) for chart in charts for t in chart.data) == sum(len(t.x) for t in dashboard.data)
    assert charts[1].layout.yaxis2.overlaying == "y"
    assert charts[2].layout.yaxis.title.text == "Ah"
    assert charts[2].layout.yaxis2.title.text == "Wh"
    assert {shape.y0 for shape in charts[5].layout.shapes if shape.type == "line"} == {20, 50}
    for chart in charts:
        assert chart.layout.xaxis.matches is None
        assert chart.layout.xaxis.rangeslider.visible
        assert all(trace.type == "scatter" for trace in chart.data)
        assert all(trace.xaxis == "x" for trace in chart.data)


def test_report_contains_independent_controls_and_safe_json(tmp_path):
    log, result = example()
    log.source_file = Path('</script><script>alert(1)</script>.txt')
    charts = [create_time_dashboard(result.telemetry, result.status, result.warnings), create_discharge_curve(result.telemetry)]
    report = tmp_path / "report.html"
    write_report(log, result, charts, report)
    page = report.read_text(encoding="utf-8")
    assert '<script>alert(1)</script>' not in page
    assert 'https://cdn.plot.ly/plotly-' not in page
    assert page.count('class="card chart-card"') == 10
    assert page.count('data-control="zoom"') == 10
    assert page.count('data-action="expand"') == 10
    assert f'{result.summary.discharge_energy_wh:.2f} Wh' in page
    specs = re.findall(r'<script type="application/json" class="plot-data">(.*?)</script>', page)
    assert len(specs) == 10
    assert all(json.loads(spec)["layout"]["xaxis"]["rangeslider"]["visible"] for spec in specs)
