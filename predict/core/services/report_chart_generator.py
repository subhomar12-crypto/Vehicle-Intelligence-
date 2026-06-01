"""
Matplotlib chart generator for PDF report embedding.

Generates health bar charts and sensor trend line charts as PNG bytes.
All rendering uses Agg backend (headless, thread-safe when wrapped in asyncio.to_thread).
"""

import io
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

logger = logging.getLogger(__name__)

# PREDICT brand colors
PREDICT_RED = "#C40000"
PREDICT_DARK = "#1a1a2e"
PREDICT_GRAY = "#2a2a3e"
PREDICT_TEXT = "#e0e0e0"


def _apply_predict_style(fig, ax):
    """Apply PREDICT dark theme to a chart."""
    fig.patch.set_facecolor(PREDICT_DARK)
    ax.set_facecolor(PREDICT_GRAY)
    ax.tick_params(colors=PREDICT_TEXT)
    ax.xaxis.label.set_color(PREDICT_TEXT)
    ax.yaxis.label.set_color(PREDICT_TEXT)
    ax.title.set_color(PREDICT_TEXT)
    for spine in ax.spines.values():
        spine.set_color(PREDICT_TEXT)


class ReportChartGenerator:
    """Generates PNG chart images for PDF reports."""

    def generate_health_bar_chart(self, components: List[Dict[str, Any]]) -> Optional[bytes]:
        """
        Horizontal bar chart: component name -> health %.
        Color-coded: green (>=75), yellow (50-74), red (<50).

        Args:
            components: list of {name/component_id, health_percent}

        Returns:
            PNG bytes or None if no data.
        """
        if not components:
            return None

        names = []
        values = []
        colors = []

        for c in components:
            name = c.get("name", c.get("component_id", "Unknown"))
            pct = c.get("health_percent", 0)
            names.append(name.replace("_", " ").title())
            values.append(pct)
            if pct >= 75:
                colors.append("#4CAF50")  # green
            elif pct >= 50:
                colors.append("#FF9800")  # orange/yellow
            else:
                colors.append(PREDICT_RED)

        fig, ax = plt.subplots(figsize=(8, max(3, len(names) * 0.5)))
        _apply_predict_style(fig, ax)

        y_pos = range(len(names))
        bars = ax.barh(y_pos, values, color=colors, height=0.6, edgecolor="none")
        ax.set_yticks(y_pos)
        ax.set_yticklabels(names, fontsize=9)
        ax.set_xlim(0, 105)
        ax.set_xlabel("Health (%)")
        ax.set_title("Component Health Assessment", fontsize=13, fontweight="bold", pad=10)

        # Value labels on bars
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_width() + 1.5,
                bar.get_y() + bar.get_height() / 2,
                f"{val}%",
                va="center",
                fontsize=8,
                color=PREDICT_TEXT,
            )

        ax.invert_yaxis()
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()

    def generate_sensor_trend_chart(
        self,
        sensor_data: List[Dict[str, Any]],
        sensor_name: str,
        unit: str = "",
    ) -> Optional[bytes]:
        """
        Line chart: sensor readings over time.

        Args:
            sensor_data: list of {timestamp, value} dicts
            sensor_name: display name for the chart
            unit: unit label (e.g., "°C", "V", "%")

        Returns:
            PNG bytes or None if insufficient data.
        """
        if not sensor_data or len(sensor_data) < 3:
            return None

        timestamps = []
        values = []

        for point in sensor_data:
            ts = point.get("timestamp") or point.get("recorded_at")
            val = point.get("value")
            if ts is not None and val is not None:
                try:
                    if isinstance(ts, (int, float)):
                        timestamps.append(datetime.fromtimestamp(ts))
                    else:
                        timestamps.append(ts)
                    values.append(float(val))
                except (ValueError, TypeError, OSError):
                    continue

        if len(timestamps) < 3:
            return None

        fig, ax = plt.subplots(figsize=(8, 3.5))
        _apply_predict_style(fig, ax)

        ax.plot(timestamps, values, color=PREDICT_RED, linewidth=1.5, alpha=0.9)
        ax.fill_between(timestamps, values, alpha=0.15, color=PREDICT_RED)

        display_name = sensor_name.replace("_", " ").title()
        ax.set_title(f"{display_name} Trend", fontsize=12, fontweight="bold", pad=8)
        ylabel = f"{display_name}"
        if unit:
            ylabel += f" ({unit})"
        ax.set_ylabel(ylabel, fontsize=9)

        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
        fig.autofmt_xdate(rotation=30)

        ax.grid(True, alpha=0.2, color=PREDICT_TEXT)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()

    def generate_multi_sensor_chart(
        self,
        sensor_datasets: Dict[str, List[Dict[str, Any]]],
        title: str = "Sensor Trends",
    ) -> Optional[bytes]:
        """
        Multi-panel chart showing up to 4 sensors in subplots.

        Args:
            sensor_datasets: {sensor_name: [{timestamp, value}, ...]}

        Returns:
            PNG bytes or None if no valid data.
        """
        valid_sensors = {
            name: data for name, data in sensor_datasets.items()
            if data and len(data) >= 3
        }
        if not valid_sensors:
            return None

        n = min(len(valid_sensors), 4)
        fig, axes = plt.subplots(n, 1, figsize=(8, 2.5 * n), sharex=True)
        fig.patch.set_facecolor(PREDICT_DARK)

        if n == 1:
            axes = [axes]

        sensor_units = {
            "coolant_temp": "°C", "oil_temp": "°C", "intake_temp": "°C",
            "battery_voltage": "V", "engine_load": "%", "throttle_pos": "%",
            "fuel_level": "%", "rpm": "RPM", "speed": "km/h",
            "maf_rate": "g/s", "boost_pressure": "kPa",
        }

        for ax, (sensor_name, data) in zip(axes, list(valid_sensors.items())[:4]):
            _apply_predict_style(fig, ax)
            timestamps = []
            values = []
            for point in data:
                ts = point.get("timestamp") or point.get("recorded_at")
                val = point.get("value")
                if ts is not None and val is not None:
                    try:
                        if isinstance(ts, (int, float)):
                            timestamps.append(datetime.fromtimestamp(ts))
                        else:
                            timestamps.append(ts)
                        values.append(float(val))
                    except (ValueError, TypeError, OSError):
                        continue

            if len(timestamps) >= 2:
                ax.plot(timestamps, values, color=PREDICT_RED, linewidth=1.2, alpha=0.9)
                ax.fill_between(timestamps, values, alpha=0.1, color=PREDICT_RED)

            display = sensor_name.replace("_", " ").title()
            unit = sensor_units.get(sensor_name, "")
            label = f"{display} ({unit})" if unit else display
            ax.set_ylabel(label, fontsize=8)
            ax.grid(True, alpha=0.15, color=PREDICT_TEXT)

        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
        fig.autofmt_xdate(rotation=30)
        fig.suptitle(title, fontsize=13, fontweight="bold", color=PREDICT_TEXT, y=1.01)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()
