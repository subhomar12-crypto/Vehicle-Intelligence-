"""
Analytics Tab - System and user analytics.

Tab 6 of 6 in the PREDICT Desktop GUI.
"""

import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGroupBox, QTableWidget, QTableWidgetItem, QTabWidget,
    QComboBox, QLineEdit, QGridLayout, QMessageBox, QHeaderView,
    QFileDialog
)
import csv
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from predict.desktop.theme import PredictTheme, get_card_stylesheet, get_table_stylesheet
from predict.desktop.workers import APIWorker, PollingWorker
from predict.desktop.api_client import PredictAPIClient

logger = logging.getLogger(__name__)

# Optional pyqtgraph import
try:
    import pyqtgraph as pg
    HAS_PYQTGRAPH = True
except ImportError:
    HAS_PYQTGRAPH = False

# Optional matplotlib import
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    import numpy as np
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


class MetricCard(QGroupBox):
    """Metric display card."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setTitle(title)
        self.setStyleSheet(get_card_stylesheet())
        layout = QVBoxLayout(self)

        self._value = QLabel("0")
        self._value.setStyleSheet(
            f"font-size: 32px; font-weight: bold; color: {PredictTheme.PRIMARY}"
        )
        self._value.setAlignment(Qt.AlignCenter)

        layout.addWidget(self._value)

    def set_value(self, value: str):
        """Set the metric value."""
        self._value.setText(value)


class AnalyticsTab(QWidget):
    """Tab for analytics and charts."""

    def __init__(self, api_client: PredictAPIClient, parent=None):
        super().__init__(parent)
        self._api = api_client
        self._stats_worker = None
        self._charts_available = HAS_PYQTGRAPH

        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI layout."""
        layout = QVBoxLayout(self)

        # Sub-tabs
        self._tabs = QTabWidget()

        # Overview tab
        self._overview_tab = self._create_overview_tab()
        self._tabs.addTab(self._overview_tab, "System Overview")

        # Per-user tab
        self._per_user_tab = self._create_per_user_tab()
        self._tabs.addTab(self._per_user_tab, "Per-User Analytics")

        # Fleet Health tab
        self._fleet_health_tab = self._create_fleet_health_tab()
        self._tabs.addTab(self._fleet_health_tab, "Fleet Health")

        # Maintenance Forecast tab
        self._maintenance_tab = self._create_maintenance_tab()
        self._tabs.addTab(self._maintenance_tab, "Maintenance Forecast")

        layout.addWidget(self._tabs)

        if not self._charts_available:
            msg = QLabel("Charts require pyqtgraph. Install: pip install pyqtgraph")
            msg.setStyleSheet(f"color: {PredictTheme.WARNING}; padding: 8px;")
            layout.addWidget(msg)

    def _create_overview_tab(self) -> QWidget:
        """Create system overview tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)

        # Stats row
        stats_layout = QHBoxLayout()
        self._stat_users = MetricCard("Total Users")
        self._stat_vehicles = MetricCard("Vehicles")
        self._stat_predictions = MetricCard("Predictions")
        self._stat_dtcs = MetricCard("Active DTCs")

        stats_layout.addWidget(self._stat_users)
        stats_layout.addWidget(self._stat_vehicles)
        stats_layout.addWidget(self._stat_predictions)
        stats_layout.addWidget(self._stat_dtcs)
        layout.addLayout(stats_layout)

        # Charts area (if pyqtgraph available)
        if self._charts_available:
            charts_layout = QHBoxLayout()

            # Tier distribution
            tier_group = QGroupBox("Tier Distribution")
            tier_layout = QVBoxLayout(tier_group)
            self._tier_plot = pg.PlotWidget()
            self._tier_plot.setBackground(PredictTheme.BG_PRIMARY)
            self._tier_plot.getAxis("bottom").setPen(pg.mkPen(PredictTheme.TEXT_SECONDARY))
            self._tier_plot.getAxis("left").setPen(pg.mkPen(PredictTheme.TEXT_SECONDARY))
            tier_layout.addWidget(self._tier_plot)
            charts_layout.addWidget(tier_group)

            # API traffic
            traffic_group = QGroupBox("API Traffic")
            traffic_layout = QVBoxLayout(traffic_group)
            self._traffic_plot = pg.PlotWidget()
            self._traffic_plot.setBackground(PredictTheme.BG_PRIMARY)
            self._traffic_plot.showGrid(x=True, y=True, alpha=0.3)
            traffic_layout.addWidget(self._traffic_plot)
            charts_layout.addWidget(traffic_group)

            layout.addLayout(charts_layout)
        else:
            placeholder = QLabel("Install pyqtgraph for charts")
            placeholder.setAlignment(Qt.AlignCenter)
            layout.addWidget(placeholder)

        layout.addStretch()
        return tab

    def _create_per_user_tab(self) -> QWidget:
        """Create per-user analytics tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Search
        search_layout = QHBoxLayout()
        self._user_search = QLineEdit()
        self._user_search.setPlaceholderText("Search user...")
        self._user_search.returnPressed.connect(self._on_search_user)
        search_layout.addWidget(self._user_search)

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._on_search_user)
        search_layout.addWidget(search_btn)
        search_layout.addStretch()
        layout.addLayout(search_layout)

        # Vehicle selector
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Vehicle:"))
        self._vehicle_combo = QComboBox()
        self._vehicle_combo.currentIndexChanged.connect(self._on_vehicle_selected)
        selector_layout.addWidget(self._vehicle_combo)
        selector_layout.addStretch()
        layout.addLayout(selector_layout)

        # Charts grid
        if self._charts_available:
            charts_grid = QGridLayout()

            self._chart_coolant = pg.PlotWidget(title="Coolant Temp")
            self._chart_coolant.setBackground(PredictTheme.BG_PRIMARY)
            self._chart_coolant.addLine(y=100, pen=pg.mkPen(PredictTheme.DANGER, width=1, style=Qt.DashLine))
            charts_grid.addWidget(self._chart_coolant, 0, 0)

            self._chart_battery = pg.PlotWidget(title="Battery Voltage")
            self._chart_battery.setBackground(PredictTheme.BG_PRIMARY)
            self._chart_battery.addLine(y=12.4, pen=pg.mkPen(PredictTheme.DANGER, width=1, style=Qt.DashLine))
            charts_grid.addWidget(self._chart_battery, 0, 1)

            self._chart_load = pg.PlotWidget(title="Engine Load %")
            self._chart_load.setBackground(PredictTheme.BG_PRIMARY)
            charts_grid.addWidget(self._chart_load, 1, 0)

            self._chart_rpm = pg.PlotWidget(title="RPM")
            self._chart_rpm.setBackground(PredictTheme.BG_PRIMARY)
            charts_grid.addWidget(self._chart_rpm, 1, 1)

            layout.addLayout(charts_grid)
        else:
            placeholder = QLabel("Install pyqtgraph for vehicle charts")
            placeholder.setAlignment(Qt.AlignCenter)
            layout.addWidget(placeholder)

        layout.addStretch()
        return tab

    def _start_monitors(self):
        """Start monitoring."""
        # System stats polling
        self._stats_worker = PollingWorker(self._api.get_system_stats, 30000)
        self._stats_worker.data_received.connect(self._on_stats_received)
        self._stats_worker.start()

        # Initial load
        self._load_stats()

    def _load_stats(self):
        """Load system stats."""
        worker = APIWorker(self._api.get_system_stats)
        worker.finished.connect(self._on_stats_received)
        worker.start()

    def _on_stats_received(self, result: dict):
        """Handle stats received."""
        stats = result.get("stats", {})

        self._stat_users.set_value(str(stats.get("total_users", 0)))
        self._stat_vehicles.set_value(str(stats.get("total_vehicles", 0)))
        self._stat_predictions.set_value(str(stats.get("total_predictions", 0)))
        self._stat_dtcs.set_value(str(stats.get("active_dtcs", 0)))

        # Update tier chart if available
        if self._charts_available and hasattr(self, '_tier_plot'):
            tier_data = stats.get("tier_breakdown", {})
            self._update_tier_chart(tier_data)

    def _update_tier_chart(self, tier_data: dict):
        """Update tier distribution chart."""
        if not tier_data:
            return

        tiers = list(tier_data.keys())
        counts = list(tier_data.values())

        self._tier_plot.clear()
        x = range(len(tiers))
        bars = pg.BarGraphItem(x=x, height=counts, width=0.5, brush=PredictTheme.PRIMARY)
        self._tier_plot.addItem(bars)
        self._tier_plot.getAxis("bottom").setTicks([[(i, t) for i, t in enumerate(tiers)]])

    def _on_search_user(self):
        """Search for user."""
        query = self._user_search.text().strip()
        if not query:
            return

        worker = APIWorker(self._api.search_users, query, 10)
        worker.finished.connect(self._on_user_search_results)
        worker.start()

    def _on_user_search_results(self, result: dict):
        """Handle user search results."""
        users = result.get("users", [])
        if users:
            user_id = users[0].get("id")
            self._load_user_vehicles(user_id)

    def _load_user_vehicles(self, user_id: int):
        """Load vehicles for user."""
        worker = APIWorker(self._api.get_user_vehicles, user_id)
        worker.finished.connect(self._on_vehicles_loaded)
        worker.start()

    def _on_vehicles_loaded(self, result: dict):
        """Handle vehicles loaded."""
        vehicles = result.get("vehicles", [])

        self._vehicle_combo.clear()
        for v in vehicles:
            name = f"{v.get('make', '')} {v.get('model', '')} ({v.get('year', '')})"
            self._vehicle_combo.addItem(name, v.get("id"))

    def _on_vehicle_selected(self, index: int):
        """Handle vehicle selection."""
        vehicle_id = self._vehicle_combo.itemData(index)
        if vehicle_id and self._charts_available:
            self._load_vehicle_data(vehicle_id)

    def _load_vehicle_data(self, vehicle_id: int):
        """Load vehicle data for charts."""
        worker = APIWorker(self._api.get_vehicle_data_history, vehicle_id, 500)
        worker.finished.connect(self._on_vehicle_data_received)
        worker.start()

    def _on_vehicle_data_received(self, result: dict):
        """Handle vehicle data received."""
        data = result.get("data", [])
        if not data or not self._charts_available:
            return

        # Extract data series
        timestamps = [d.get("timestamp", 0) for d in data]
        coolant = [d.get("coolant_temp", 0) for d in data]
        battery = [d.get("battery_voltage", 0) for d in data]
        load = [d.get("engine_load", 0) for d in data]
        rpm = [d.get("rpm", 0) for d in data]

        # Normalize timestamps
        if timestamps:
            base = timestamps[0]
            timestamps = [t - base for t in timestamps]

        # Update charts
        self._chart_coolant.clear()
        self._chart_coolant.plot(timestamps, coolant, pen=pg.mkPen(PredictTheme.PRIMARY, width=2))

        self._chart_battery.clear()
        self._chart_battery.plot(timestamps, battery, pen=pg.mkPen(PredictTheme.PRIMARY, width=2))

        self._chart_load.clear()
        self._chart_load.plot(timestamps, load, pen=pg.mkPen(PredictTheme.PRIMARY, width=2))

        self._chart_rpm.clear()
        self._chart_rpm.plot(timestamps, rpm, pen=pg.mkPen(PredictTheme.PRIMARY, width=2))

    def _create_fleet_health_tab(self) -> QWidget:
        """Create fleet health tab with heatmap."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)

        # Controls
        controls_layout = QHBoxLayout()
        refresh_btn = QPushButton("Refresh Fleet Health")
        refresh_btn.clicked.connect(self._load_fleet_health)
        controls_layout.addWidget(refresh_btn)

        self._fleet_status_label = QLabel("Click Refresh to load fleet health data")
        self._fleet_status_label.setStyleSheet(f"color: {PredictTheme.TEXT_SECONDARY};")
        controls_layout.addWidget(self._fleet_status_label)
        controls_layout.addStretch()

        layout.addLayout(controls_layout)

        # Matplotlib notice
        if not HAS_MATPLOTLIB:
            notice = QLabel("Install matplotlib for heatmap: pip install matplotlib numpy")
            notice.setStyleSheet(f"color: {PredictTheme.WARNING}; padding: 8px;")
            layout.addWidget(notice)

        # Heatmap container
        self._heatmap_container = QWidget()
        self._heatmap_layout = QVBoxLayout(self._heatmap_container)
        layout.addWidget(self._heatmap_container)

        # Worst components section
        worst_group = QGroupBox("Worst Components")
        worst_layout = QVBoxLayout(worst_group)

        self._worst_table = QTableWidget()
        self._worst_table.setColumnCount(4)
        self._worst_table.setHorizontalHeaderLabels(["Component", "Avg Health %", "Worst Vehicle", "Action Needed"])
        self._worst_table.setStyleSheet(get_table_stylesheet())
        self._worst_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        worst_layout.addWidget(self._worst_table)
        layout.addWidget(worst_group)

        # Store data for rendering
        self._fleet_health_results = []
        self._fleet_health_pending = 0

        layout.addStretch()
        return tab

    def _load_fleet_health(self):
        """Fetch health assessment for all vehicles."""
        self._fleet_status_label.setText("Loading fleet health data...")
        self._fleet_status_label.setStyleSheet(f"color: {PredictTheme.INFO};")

        worker = APIWorker(self._api.get_ai_dashboard)
        worker.finished.connect(self._on_fleet_vehicles_received)
        worker.error.connect(self._on_fleet_health_error)
        worker.start()

    def _on_fleet_vehicles_received(self, data: dict):
        """Handle fleet vehicles received."""
        vehicles = data.get("vehicles", [])
        if not vehicles:
            self._fleet_status_label.setText("No vehicles in fleet")
            self._fleet_status_label.setStyleSheet(f"color: {PredictTheme.WARNING};")
            return

        self._fleet_health_results = []
        self._fleet_health_pending = len(vehicles)
        self._fleet_status_label.setText(f"Loading health data for {len(vehicles)} vehicles...")

        for v in vehicles:
            vid = v.get("vehicle_id")
            name = v.get("vehicle_name", f"Vehicle {vid}")
            worker = APIWorker(self._api.get_health_assessment, vid)
            worker.finished.connect(lambda result, n=name: self._on_one_health(n, result))
            worker.error.connect(lambda e, n=name: self._on_one_health_error(n))
            worker.start()

    def _on_one_health(self, name: str, result: dict):
        """Handle health data for one vehicle."""
        components = result.get("components", {})
        self._fleet_health_results.append((name, components))
        self._fleet_health_pending -= 1

        if self._fleet_health_pending <= 0:
            self._render_fleet_health()

    def _on_one_health_error(self, name: str):
        """Handle error loading health for one vehicle."""
        logger.error(f"Failed to load health for {name}")
        self._fleet_health_pending -= 1
        if self._fleet_health_pending <= 0:
            self._render_fleet_health()

    def _on_fleet_health_error(self, error: str):
        """Handle fleet health loading error."""
        self._fleet_status_label.setText(f"Error: {error}")
        self._fleet_status_label.setStyleSheet(f"color: {PredictTheme.DANGER};")

    def _render_fleet_health(self):
        """Render fleet health heatmap and worst components."""
        if not self._fleet_health_results:
            self._fleet_status_label.setText("No health data available")
            self._fleet_status_label.setStyleSheet(f"color: {PredictTheme.WARNING};")
            return

        self._fleet_status_label.setText(f"Loaded health data for {len(self._fleet_health_results)} vehicles")
        self._fleet_status_label.setStyleSheet(f"color: {PredictTheme.SUCCESS};")

        # Clear old heatmap
        while self._heatmap_layout.count():
            item = self._heatmap_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Create heatmap
        if HAS_MATPLOTLIB:
            heatmap = self._create_health_heatmap(self._fleet_health_results)
            if heatmap:
                self._heatmap_layout.addWidget(heatmap)

        # Update worst components table
        self._update_worst_components()

    def _create_health_heatmap(self, health_data_list: list):
        """Create fleet health heatmap from list of (vehicle_name, components_dict)."""
        if not health_data_list:
            return None

        component_names = [
            "Engine Oil", "Coolant", "Battery", "Brakes", "Trans Fluid",
            "Spark Plugs", "Cat Conv", "O2 Sensors", "Air Filter", "Fuel System"
        ]
        component_ids = [
            "engine_oil", "coolant_system", "battery", "brakes", "transmission_fluid",
            "spark_plugs", "catalytic_converter", "o2_sensors", "air_filter", "fuel_system"
        ]

        vehicle_names = [name for name, _ in health_data_list]
        scores = []
        for _, components in health_data_list:
            row = [components.get(cid, {}).get("health_pct", 0) for cid in component_ids]
            scores.append(row)

        data = np.array(scores)
        fig, ax = plt.subplots(figsize=(12, max(3, len(vehicle_names) * 0.8)))
        fig.patch.set_facecolor('#1A1A2E')
        ax.set_facecolor('#1A1A2E')

        im = ax.imshow(data, cmap='RdYlGn', vmin=0, vmax=100, aspect='auto')
        ax.set_xticks(range(len(component_names)))
        ax.set_xticklabels(component_names, rotation=45, ha='right', color='white', fontsize=9)
        ax.set_yticks(range(len(vehicle_names)))
        ax.set_yticklabels(vehicle_names, color='white', fontsize=10)
        ax.tick_params(colors='white')

        # Add score text in each cell
        for i in range(len(vehicle_names)):
            for j in range(len(component_ids)):
                val = data[i, j]
                text_color = 'white' if val < 50 else 'black'
                ax.text(j, i, f"{int(val)}", ha='center', va='center', color=text_color, fontsize=9)

        cbar = fig.colorbar(im, ax=ax, label='Health Score', pad=0.02)
        cbar.ax.yaxis.label.set_color('white')
        cbar.ax.tick_params(colors='white')
        fig.tight_layout()

        canvas = FigureCanvasQTAgg(fig)
        plt.close(fig)  # Prevent memory leak on repeated refreshes
        return canvas

    def _update_worst_components(self):
        """Update worst components table."""
        if not self._fleet_health_results:
            return

        component_ids = [
            "engine_oil", "coolant_system", "battery", "brakes", "transmission_fluid",
            "spark_plugs", "catalytic_converter", "o2_sensors", "air_filter", "fuel_system"
        ]
        component_names = [
            "Engine Oil", "Coolant", "Battery", "Brakes", "Trans Fluid",
            "Spark Plugs", "Cat Conv", "O2 Sensors", "Air Filter", "Fuel System"
        ]

        # Calculate average scores and find worst vehicle for each component
        component_stats = []
        for i, cid in enumerate(component_ids):
            scores = []
            worst_vehicle = None
            worst_score = 100
            for name, components in self._fleet_health_results:
                score = components.get(cid, {}).get("health_pct", 0)
                scores.append(score)
                if score < worst_score:
                    worst_score = score
                    worst_vehicle = name

            avg_score = sum(scores) / len(scores) if scores else 0
            action = "Replace soon" if avg_score < 50 else "Monitor" if avg_score < 70 else "OK"
            component_stats.append((component_names[i], avg_score, worst_vehicle, action))

        # Sort by average score (worst first)
        component_stats.sort(key=lambda x: x[1])

        # Update table
        self._worst_table.setRowCount(len(component_stats))
        for i, (comp, avg, worst, action) in enumerate(component_stats):
            self._worst_table.setItem(i, 0, QTableWidgetItem(comp))
            self._worst_table.setItem(i, 1, QTableWidgetItem(f"{avg:.0f}"))
            self._worst_table.setItem(i, 2, QTableWidgetItem(worst or "N/A"))
            self._worst_table.setItem(i, 3, QTableWidgetItem(action))

    def _create_maintenance_tab(self) -> QWidget:
        """Create maintenance forecast tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)

        # Filter controls
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Priority:"))
        self._priority_filter = QComboBox()
        self._priority_filter.addItems(["All", "Critical", "High+", "Medium+"])
        self._priority_filter.currentTextChanged.connect(self._apply_maint_filter)
        filter_layout.addWidget(self._priority_filter)
        filter_layout.addStretch()

        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._load_maintenance_forecast)
        filter_layout.addWidget(refresh_btn)

        # Export CSV button
        export_btn = QPushButton("Export CSV")
        export_btn.clicked.connect(self._export_maintenance_csv)
        filter_layout.addWidget(export_btn)

        layout.addLayout(filter_layout)

        # Maintenance table
        self._maint_table = QTableWidget()
        self._maint_table.setColumnCount(7)
        self._maint_table.setHorizontalHeaderLabels([
            "Vehicle", "Component", "Due Date", "Days Left", "Priority", "Est. Cost (QAR)", "Survival %"
        ])
        self._maint_table.setStyleSheet(get_table_stylesheet())
        self._maint_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._maint_table.horizontalHeader().setStretchLastSection(True)
        self._maint_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._maint_table.setSortingEnabled(True)
        layout.addWidget(self._maint_table)

        # Total cost summary
        self._total_cost_label = QLabel("Total Estimated Cost: 0 QAR")
        self._total_cost_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {PredictTheme.PRIMARY};")
        layout.addWidget(self._total_cost_label)

        # Storage for maintenance events
        self._maint_events = []
        self._maint_pending = 0

        return tab

    def _load_maintenance_forecast(self):
        """Fetch maintenance events for all vehicles."""
        self._maint_events = []
        worker = APIWorker(self._api.get_ai_dashboard)
        worker.finished.connect(self._on_maint_vehicles)
        worker.error.connect(lambda e: logger.error(f"Maint forecast error: {e}"))
        worker.start()

    def _on_maint_vehicles(self, data: dict):
        """Handle fleet vehicles for maintenance."""
        vehicles = data.get("vehicles", [])
        self._maint_events = []
        self._maint_pending = len(vehicles)

        if not vehicles:
            self._render_maintenance()
            return

        for v in vehicles:
            vid = v.get("vehicle_id")
            name = v.get("vehicle_name", f"Vehicle {vid}")
            worker = APIWorker(self._api.get_health_assessment, vid)
            worker.finished.connect(lambda r, n=name: self._on_one_maint(n, r))
            worker.error.connect(lambda e: self._on_one_maint_err())
            worker.start()

    def _on_one_maint(self, vehicle_name: str, result: dict):
        """Handle maintenance data for one vehicle."""
        events = result.get("maintenance_events", [])
        for ev in events:
            self._maint_events.append({
                "vehicle": vehicle_name,
                "component": ev.get("component", ""),
                "due_date": ev.get("due_date", ""),
                "due_in_days": ev.get("due_in_days", 999),
                "priority": ev.get("priority", "low"),
                "cost": ev.get("estimated_cost", {}).get("total", 0) if isinstance(ev.get("estimated_cost"), dict) else 0,
                "survival": ev.get("survival_probability", 1.0),
            })
        self._maint_pending -= 1
        if self._maint_pending <= 0:
            self._render_maintenance()

    def _on_one_maint_err(self):
        """Handle error loading maintenance for one vehicle."""
        self._maint_pending -= 1
        if self._maint_pending <= 0:
            self._render_maintenance()

    def _render_maintenance(self):
        """Render maintenance table."""
        # Sort by days left (most urgent first)
        self._maint_events.sort(key=lambda x: x.get("due_in_days", 999))

        # Update table
        self._maint_table.setRowCount(len(self._maint_events))
        total_cost = 0

        for i, ev in enumerate(self._maint_events):
            self._maint_table.setItem(i, 0, QTableWidgetItem(ev["vehicle"]))
            self._maint_table.setItem(i, 1, QTableWidgetItem(ev["component"].replace("_", " ").title()))
            self._maint_table.setItem(i, 2, QTableWidgetItem(str(ev["due_date"])))
            self._maint_table.setItem(i, 3, QTableWidgetItem(str(ev["due_in_days"])))

            priority_item = QTableWidgetItem(ev["priority"].capitalize())
            priority_color = {
                "critical": PredictTheme.DANGER,
                "high": PredictTheme.WARNING,
                "medium": PredictTheme.INFO,
                "low": PredictTheme.TEXT_MUTED,
            }.get(ev["priority"], PredictTheme.TEXT_MUTED)
            priority_item.setForeground(QColor(priority_color))
            self._maint_table.setItem(i, 4, priority_item)

            self._maint_table.setItem(i, 5, QTableWidgetItem(f"{ev['cost']:.0f}"))
            self._maint_table.setItem(i, 6, QTableWidgetItem(f"{ev['survival'] * 100:.0f}%"))

            total_cost += ev["cost"]

        self._total_cost_label.setText(f"Total Estimated Cost: {total_cost:.0f} QAR")
        self._apply_maint_filter()

    def _apply_maint_filter(self):
        """Apply priority filter to maintenance table."""
        filt = self._priority_filter.currentText()
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

        for row in range(self._maint_table.rowCount()):
            priority_item = self._maint_table.item(row, 4)
            if not priority_item:
                continue
            priority = priority_item.text().lower()
            show = True

            if filt == "Critical":
                show = priority == "critical"
            elif filt == "High+":
                show = priority_order.get(priority, 3) <= 1
            elif filt == "Medium+":
                show = priority_order.get(priority, 3) <= 2

            self._maint_table.setRowHidden(row, not show)

    def _export_maintenance_csv(self):
        """Export maintenance data to CSV file."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Maintenance Forecast", "maintenance_forecast.csv", "CSV Files (*.csv)"
        )
        if not path:
            return

        try:
            with open(path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Vehicle", "Component", "Due Date", "Days Left", "Priority", "Cost (QAR)", "Survival %"])

                # Write visible/filtered rows
                for row in range(self._maint_table.rowCount()):
                    if not self._maint_table.isRowHidden(row):
                        vehicle = self._maint_table.item(row, 0).text()
                        component = self._maint_table.item(row, 1).text()
                        due_date = self._maint_table.item(row, 2).text()
                        days_left = self._maint_table.item(row, 3).text()
                        priority = self._maint_table.item(row, 4).text()
                        cost = self._maint_table.item(row, 5).text()
                        survival = self._maint_table.item(row, 6).text()

                        writer.writerow([vehicle, component, due_date, days_left, priority, cost, survival])

            QMessageBox.information(self, "Export Complete", f"Saved to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export: {e}")

    def cleanup(self):
        """Stop all background workers."""
        if self._stats_worker:
            self._stats_worker.stop()
            self._stats_worker.wait(2000)

    def closeEvent(self, event):
        """Clean up on close."""
        self.cleanup()
        event.accept()
