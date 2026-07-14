"""
reports/html_report.py

Генерация HTML-отчёта по анализу iCharger.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from analytics.statistics import Statistics
from analytics.battery import BatteryAnalysis
from analytics.anomalies import Anomaly


class HtmlReport:
    """
    Генерация HTML-отчёта.
    """

    TITLE = "iCharger Analyzer Report"

    def build(
        self,
        statistics: Statistics,
        battery: BatteryAnalysis,
        anomalies: list[Anomaly],
        plotly_html: str,
        source_file: str,
    ) -> str:

        return f"""
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<title>{self.TITLE}</title>

{self._style()}

</head>

<body>

<div class="container">

{self._header(source_file)}

{self._statistics(statistics)}

{self._battery(battery)}

{self._conclusion(statistics, battery)}

{self._anomalies(anomalies)}

{plotly_html}

{self._footer()}

</div>

</body>

</html>
"""

    # ---------------------------------------------------------

    def save(
        self,
        html: str,
        filename: str | Path,
    ) -> None:

        Path(filename).write_text(
            html,
            encoding="utf-8",
        )
    
        # ==========================================================
    # CSS
    # ==========================================================

    @staticmethod
    def _style() -> str:
        """
        CSS стили отчёта.
        """

        return """
<style>

body{

    margin:0;

    padding:40px;

    background:#121212;

    color:#ECECEC;

    font-family:Segoe UI,Arial,sans-serif;

}

.container{

    max-width:1600px;

    margin:auto;

}

.card{

    background:#1E1E1E;

    border-radius:12px;

    padding:20px;

    margin-bottom:20px;

    box-shadow:0 4px 20px rgba(0,0,0,.4);

}

h1{

    margin-top:0;

    color:#4CAF50;

}

h2{

    color:#90CAF9;

}

table{

    width:100%;

    border-collapse:collapse;

}

th{

    background:#2E2E2E;

    padding:10px;

    text-align:left;

}

td{

    padding:10px;

    border-bottom:1px solid #333;

}

.good{

    color:#66BB6A;

    font-weight:bold;

}

.warning{

    color:#FFA726;

    font-weight:bold;

}

.bad{

    color:#EF5350;

    font-weight:bold;

}

.kpi-grid{

    display:grid;

    grid-template-columns:repeat(auto-fit,minmax(220px,1fr));

    gap:18px;

}

.kpi{

    background:#252525;

    border-radius:10px;

    padding:16px;

}

.kpi-title{

    color:#AAAAAA;

    font-size:14px;

}

.kpi-value{

    font-size:28px;

    font-weight:bold;

    margin-top:8px;

}

.footer{

    margin-top:40px;

    text-align:center;

    color:#888;

}

</style>
"""

        # ==========================================================
    # HEADER
    # ==========================================================

    def _header(
        self,
        source_file: str,
    ) -> str:

        return f"""
<div class="card">

<h1>{self.TITLE}</h1>

<p>

<b>Source file:</b> {source_file}<br>

<b>Generated:</b> {datetime.now().strftime("%d.%m.%Y %H:%M:%S")}<br>

<b>Version:</b> 1.0

</p>

</div>
"""
        # ==========================================================
    # Statistics
    # ==========================================================

    def _statistics(
        self,
        statistics: Statistics,
    ) -> str:

        return f"""
<div class="card">

<h2>Test Statistics</h2>

<div class="kpi-grid">

<div class="kpi">

<div class="kpi-title">
Samples
</div>

<div class="kpi-value">
{statistics.samples}
</div>

</div>

<div class="kpi">

<div class="kpi-title">
Duration
</div>

<div class="kpi-value">
{statistics.duration_s:.1f} s
</div>

</div>

<div class="kpi">

<div class="kpi-title">
Max Voltage
</div>

<div class="kpi-value">
{statistics.max_voltage:.2f}
</div>

</div>

<div class="kpi">

<div class="kpi-title">
Average Current
</div>

<div class="kpi-value">
{statistics.avg_current:.2f}
</div>

</div>

<div class="kpi">

<div class="kpi-title">
Max Power
</div>

<div class="kpi-value">
{statistics.max_power:.2f}
</div>

</div>

<div class="kpi">

<div class="kpi-title">
Max Temperature
</div>

<div class="kpi-value">
{statistics.max_temperature:.2f}
</div>

</div>

</div>

</div>
"""
        # ==========================================================
    # Battery
    # ==========================================================

    def _battery(
        self,
        battery: BatteryAnalysis,
    ) -> str:

        status = (
            '<span class="good">YES</span>'
            if battery.balanced
            else
            '<span class="bad">NO</span>'
        )

        return f"""
<div class="card">

<h2>Battery Analysis</h2>

<table>

<tr>
    <th>Parameter</th>
    <th>Value</th>
</tr>

<tr>
    <td>Detected Cells</td>
    <td>{battery.cells_count}</td>
</tr>

<tr>
    <td>Minimum Cell Voltage</td>
    <td>{battery.min_cell_voltage:.3f}</td>
</tr>

<tr>
    <td>Maximum Cell Voltage</td>
    <td>{battery.max_cell_voltage:.3f}</td>
</tr>

<tr>
    <td>Average Cell Voltage</td>
    <td>{battery.avg_cell_voltage:.3f}</td>
</tr>

<tr>
    <td>Maximum Delta</td>
    <td>{battery.max_cell_delta:.3f}</td>
</tr>

<tr>
    <td>Average Delta</td>
    <td>{battery.avg_cell_delta:.3f}</td>
</tr>

<tr>
    <td>Delta Growth</td>
    <td>{battery.delta_growth:.3f}</td>
</tr>

<tr>
    <td>Balanced</td>
    <td>{status}</td>
</tr>

</table>

</div>
"""
        # ==========================================================
    # Conclusion
    # ==========================================================

    def _conclusion(
        self,
        statistics: Statistics,
        battery: BatteryAnalysis,
    ) -> str:

        messages = []

        if battery.balanced:
            messages.append(
                '<li class="good">Battery balancing is good.</li>'
            )
        else:
            messages.append(
                '<li class="bad">Battery balancing requires attention.</li>'
            )

        if statistics.max_temperature < 45:
            messages.append(
                '<li class="good">Battery temperature is normal.</li>'
            )
        elif statistics.max_temperature < 60:
            messages.append(
                '<li class="warning">Battery temperature is elevated.</li>'
            )
        else:
            messages.append(
                '<li class="bad">Battery overheating detected.</li>'
            )

        if statistics.max_power > 0:
            messages.append(
                '<li class="good">Power profile looks valid.</li>'
            )

        return f"""
<div class="card">

<h2>Automatic Conclusion</h2>

<ul>

{''.join(messages)}

</ul>

</div>
"""
        # ==========================================================
    # Anomalies
    # ==========================================================

    def _anomalies(
        self,
        anomalies: list[Anomaly],
    ) -> str:

        rows = []

        for anomaly in anomalies:

            rows.append(
                f"""
<tr>

<td>{anomaly.sample}</td>

<td>{anomaly.time_s:.2f}</td>

<td>{anomaly.anomaly.value}</td>

<td>{anomaly.value:.3f}</td>

<td>{anomaly.message}</td>

</tr>
"""
            )

        if not rows:

            rows.append(
                """
<tr>

<td colspan="5">

<span class="good">
No anomalies detected.
</span>

</td>

</tr>
"""
            )

        return f"""
<div class="card">

<h2>Detected Anomalies</h2>

<table>

<tr>

<th>Sample</th>

<th>Time</th>

<th>Type</th>

<th>Value</th>

<th>Description</th>

</tr>

{''.join(rows)}

</table>

</div>
"""
        # ==========================================================
    # Footer
    # ==========================================================

    @staticmethod
    def _footer() -> str:

        year = datetime.now().year

        return f"""
<div class="footer">

Generated by

<b>iCharger Analyzer</b>

<br><br>

© {year}

</div>
"""