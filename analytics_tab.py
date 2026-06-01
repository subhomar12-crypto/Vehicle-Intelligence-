"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Analytics Tab

Analytics Tab with Real-Time Charts
=====================================

Provides comprehensive vehicle analytics with interactive charts:
- Fuel efficiency trends (MPG over time)
- Maintenance costs (monthly breakdown)
- DTC frequency (category distribution)
- Driving score trends (area chart)
- Temperature history
- RPM distribution

Features:
- Real-time data updates
- Interactive charts with zoom/pan
- Export chart data to CSV
- Time range filtering
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import deque

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QGridLayout, QFileDialog,
    QSpinBox, QCheckBox, QTabWidget, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QTimer, QDate
from PySide6.QtGui import QFont, QColor

import pyqtgraph as pg
import numpy as np

from ui_common import show_error, show_info, ProfessionalTheme

logger = logging.getLogger(__name__)


class AnalyticsChartWidget(QWidget):
    """Base widget for analytics charts with common controls"""
    
    data_exported = Signal(str)  # chart_name
    
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header with title and export button
        header = QHBoxLayout()
        
        title_label = QLabel(self.title)
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title_label.setStyleSheet(f"color: {ProfessionalTheme.TEXT_PRIMARY};")
        header.addWidget(title_label)
        
        header.addStretch()
        
        self.export_btn = QPushButton("📊 Export Data")
        self.export_btn.setStyleSheet(self._get_button_style('secondary'))
        self.export_btn.clicked.connect(self._export_data)
        header.addWidget(self.export_btn)
        
        layout.addLayout(header)
        
        # Chart area
        self.chart_container = QWidget()
        self.chart_layout = QVBoxLayout(self.chart_container)
        self.chart_layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self.chart_container)
    
    def _get_button_style(self, style_type: str) -> str:
        """Get consistent button style"""
        styles = {
            'primary': """
                QPushButton {
                    background-color: #C40000;
                    color: #F0F6FC;
                    border: none;
                    padding: 8px 16px;
                    font-size: 12px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover { background-color: #E53935; }
                QPushButton:pressed { background-color: #B71C1C; }
            """,
            'secondary': """
                QPushButton {
                    background-color: #21262D;
                    color: #F0F6FC;
                    border: 1px solid #30363D;
                    padding: 6px 14px;
                    font-size: 11px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover { background-color: #30363D; }
                QPushButton:pressed { background-color: #161B22; }
            """,
            'success': """
                QPushButton {
                    background-color: #4CAF50;
                    color: #F0F6FC;
                    border: none;
                    padding: 8px 16px;
                    font-size: 12px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover { background-color: #66BB6A; }
                QPushButton:pressed { background-color: #388E3C; }
            """
        }
        return styles.get(style_type, styles['secondary'])
    
    def _export_data(self):
        """Export chart data to CSV"""
        self.data_exported.emit(self.title)
    
    def update_data(self, data: Dict[str, Any]):
        """Update chart with new data - to be overridden by subclasses"""
        pass


class FuelEfficiencyChart(AnalyticsChartWidget):
    """Fuel efficiency (MPG) trend chart"""
    
    def __init__(self, parent=None):
        super().__init__("Fuel Efficiency Trend", parent)
        self.data_buffer = deque(maxlen=100)
        self._setup_chart()
    
    def _setup_chart(self):
        """Setup pyqtgraph plot widget"""
        # Create plot widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(ProfessionalTheme.CARD_BG)
        self.plot_widget.setTitle("MPG Over Time", color=ProfessionalTheme.TEXT_PRIMARY, size="12pt")
        
        # Configure axes
        self.plot_widget.setLabel('left', 'MPG', color=ProfessionalTheme.TEXT_SECONDARY)
        self.plot_widget.setLabel('bottom', 'Date', color=ProfessionalTheme.TEXT_SECONDARY)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # Create curve with Predict Red color
        self.curve = self.plot_widget.plot(
            pen=pg.mkPen(color=QColor(ProfessionalTheme.PRIMARY), width=2),
            symbol='o',
            symbolSize=8,
            symbolBrush=pg.mkBrush(QColor(ProfessionalTheme.PRIMARY))
        )
        
        # Add average line
        self.avg_line = self.plot_widget.plot(
            pen=pg.mkPen(color=QColor(ProfessionalTheme.SUCCESS), width=1, style=Qt.DashLine)
        )
        
        self.chart_layout.addWidget(self.plot_widget)
    
    def update_data(self, data: Dict[str, Any]):
        """Update chart with fuel data"""
        mpg = data.get('mpg')
        if mpg is not None:
            self.data_buffer.append({
                'timestamp': datetime.now(),
                'mpg': float(mpg)
            })
            
            # Update plot
            timestamps = [d['timestamp'] for d in self.data_buffer]
            mpg_values = [d['mpg'] for d in self.data_buffer]
            
            if len(timestamps) > 1:
                # Convert timestamps to numeric for plotting
                base_time = timestamps[0]
                x_values = [(t - base_time).total_seconds() / 3600 for t in timestamps]  # Hours from start
                
                self.curve.setData(x_values, mpg_values)
                
                # Calculate and show average
                avg_mpg = sum(mpg_values) / len(mpg_values)
                self.avg_line.setData([0, x_values[-1]], [avg_mpg, avg_mpg])
        
        # Update title with current value
        if mpg:
            self.plot_widget.setTitle(f"MPG Over Time (Current: {mpg:.1f})", 
                                  color=ProfessionalTheme.TEXT_PRIMARY, size="12pt")
    
    def get_export_data(self) -> str:
        """Get data for export"""
        lines = ["Timestamp,MPG"]
        for d in self.data_buffer:
            lines.append(f"{d['timestamp'].isoformat()},{d['mpg']:.2f}")
        return "\n".join(lines)


class MaintenanceCostChart(AnalyticsChartWidget):
    """Monthly maintenance costs bar chart"""
    
    def __init__(self, parent=None):
        super().__init__("Monthly Maintenance Costs", parent)
        self.monthly_data = {}
        self._setup_chart()
    
    def _setup_chart(self):
        """Setup bar chart for monthly costs"""
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(ProfessionalTheme.CARD_BG)
        self.plot_widget.setTitle("Maintenance Costs by Month", color=ProfessionalTheme.TEXT_PRIMARY, size="12pt")
        
        # Configure axes
        self.plot_widget.setLabel('left', 'Cost ($)', color=ProfessionalTheme.TEXT_SECONDARY)
        self.plot_widget.setLabel('bottom', 'Month', color=ProfessionalTheme.TEXT_SECONDARY)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # Create bar graph item
        self.bar_graph = pg.BarGraphItem(x=[0], height=[0], width=0.8, brush=pg.mkBrush(QColor(ProfessionalTheme.PRIMARY)))
        self.plot_widget.addItem(self.bar_graph)
        
        self.chart_layout.addWidget(self.plot_widget)
    
    def update_data(self, data: Dict[str, Any]):
        """Update chart with maintenance data"""
        cost = data.get('cost')
        if cost is not None:
            month_key = datetime.now().strftime("%Y-%m")
            if month_key not in self.monthly_data:
                self.monthly_data[month_key] = 0.0
            self.monthly_data[month_key] += float(cost)
            
            # Update bar chart
            months = sorted(self.monthly_data.keys())
            costs = [self.monthly_data[m] for m in months]
            
            # Create x positions (0, 1, 2, ...)
            x_positions = list(range(len(months)))
            
            self.bar_graph.setOpts(x=x_positions, height=costs, width=0.7)
            
            # Update x-axis labels
            ax = self.plot_widget.getAxis('bottom')
            ax.setTicks([[(i, m[-2:]) for i, m in enumerate(months)]])
            
            # Update title with total
            total = sum(costs)
            self.plot_widget.setTitle(f"Monthly Maintenance Costs (Total: ${total:.2f})", 
                                  color=ProfessionalTheme.TEXT_PRIMARY, size="12pt")
    
    def get_export_data(self) -> str:
        """Get data for export"""
        lines = ["Month,Cost"]
        for month, cost in sorted(self.monthly_data.items()):
            lines.append(f"{month},{cost:.2f}")
        return "\n".join(lines)


class DTCCategoryChart(AnalyticsChartWidget):
    """DTC codes by category (pie chart)"""
    
    def __init__(self, parent=None):
        super().__init__("DTC Code Categories", parent)
        self.dtc_data = {}
        self._setup_chart()
    
    def _setup_chart(self):
        """Setup pie chart for DTC categories"""
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(ProfessionalTheme.CARD_BG)
        self.plot_widget.setTitle("DTC Codes by Category", color=ProfessionalTheme.TEXT_PRIMARY, size="12pt")
        self.plot_widget.hideAxis('left')
        self.plot_widget.hideAxis('bottom')
        
        # Create pie chart using PlotDataItem
        self.pie_item = pg.PlotDataItem()
        self.plot_widget.addItem(self.pie_item)
        
        # Legend
        self.legend_label = QLabel("No DTC data available")
        self.legend_label.setStyleSheet(f"color: {ProfessionalTheme.TEXT_SECONDARY}; font-size: 11px;")
        self.legend_label.setWordWrap(True)
        self.chart_layout.addWidget(self.legend_label)
        self.chart_layout.addWidget(self.plot_widget)
    
    def update_data(self, data: Dict[str, Any]):
        """Update chart with DTC data"""
        dtc_code = data.get('dtc_code')
        if dtc_code:
            # Categorize DTC
            category = self._categorize_dtc(dtc_code)
            if category not in self.dtc_data:
                self.dtc_data[category] = 0
            self.dtc_data[category] += 1
            
            # Update pie chart
            if self.dtc_data:
                categories = list(self.dtc_data.keys())
                counts = list(self.dtc_data.values())
                total = sum(counts)
                
                # Calculate angles for pie slices
                angles = []
                start_angle = 0
                colors = [
                    QColor(ProfessionalTheme.PRIMARY),      # Powertrain
                    QColor(ProfessionalTheme.SUCCESS),      # Body
                    QColor(ProfessionalTheme.WARNING),      # Chassis
                    QColor(ProfessionalTheme.INFO),         # Network
                    QColor(ProfessionalTheme.DANGER),       # Other
                ]
                
                # Create pie slices using PlotDataItem
                self.pie_item.clear()
                
                for i, (cat, count) in enumerate(zip(categories, counts)):
                    slice_angle = (count / total) * 360
                    end_angle = start_angle + slice_angle
                    
                    # Create pie slice data
                    theta = np.linspace(np.radians(start_angle), np.radians(end_angle), 50)
                    radius = 1.0
                    x = radius * np.cos(theta)
                    y = radius * np.sin(theta)
                    
                    self.pie_item.setData(x, y, 
                                         pen=pg.mkPen(colors[i % len(colors)], width=2),
                                         symbol='o',
                                         symbolSize=10,
                                         symbolBrush=pg.mkBrush(colors[i % len(colors)]))
                    
                    start_angle = end_angle
                
                # Update legend
                legend_text = "\n".join([f"{cat}: {count}" for cat, count in self.dtc_data.items()])
                self.legend_label.setText(legend_text)
                
                # Update title
                self.plot_widget.setTitle(f"DTC Codes by Category (Total: {total})", 
                                      color=ProfessionalTheme.TEXT_PRIMARY, size="12pt")
    
    def _categorize_dtc(self, code: str) -> str:
        """Categorize DTC code by prefix"""
        if not code:
            return "Unknown"
        
        code_upper = code.upper()
        if code_upper.startswith('P'):
            return "Powertrain"
        elif code_upper.startswith('B'):
            return "Body"
        elif code_upper.startswith('C'):
            return "Chassis"
        elif code_upper.startswith('U'):
            return "Network"
        else:
            return "Other"
    
    def get_export_data(self) -> str:
        """Get data for export"""
        lines = ["Category,Count"]
        for category, count in self.dtc_data.items():
            lines.append(f"{category},{count}")
        return "\n".join(lines)


class DrivingScoreChart(AnalyticsChartWidget):
    """Driving score trend area chart"""
    
    def __init__(self, parent=None):
        super().__init__("Driving Score Trend", parent)
        self.score_buffer = deque(maxlen=50)
        self._setup_chart()
    
    def _setup_chart(self):
        """Setup area chart for driving scores"""
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(ProfessionalTheme.CARD_BG)
        self.plot_widget.setTitle("Driving Score Over Time", color=ProfessionalTheme.TEXT_PRIMARY, size="12pt")
        
        # Configure axes
        self.plot_widget.setLabel('left', 'Score', color=ProfessionalTheme.TEXT_SECONDARY)
        self.plot_widget.setLabel('bottom', 'Time', color=ProfessionalTheme.TEXT_SECONDARY)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setYRange(0, 100)
        
        # Create area curve
        self.curve = self.plot_widget.plot(
            pen=pg.mkPen(color=QColor(ProfessionalTheme.PRIMARY), width=2),
            fillLevel=0,
            brush=pg.mkBrush(QColor(ProfessionalTheme.PRIMARY_LIGHT))
        )
        
        # Add threshold lines
        self.good_threshold = self.plot_widget.plot(
            pen=pg.mkPen(color=QColor(ProfessionalTheme.SUCCESS), width=1, style=Qt.DashLine)
        )
        self.warning_threshold = self.plot_widget.plot(
            pen=pg.mkPen(color=QColor(ProfessionalTheme.WARNING), width=1, style=Qt.DashLine)
        )
        
        self.chart_layout.addWidget(self.plot_widget)
    
    def update_data(self, data: Dict[str, Any]):
        """Update chart with driving score"""
        score = data.get('driving_score')
        if score is not None:
            self.score_buffer.append({
                'timestamp': datetime.now(),
                'score': float(score)
            })
            
            # Update plot
            timestamps = [d['timestamp'] for d in self.score_buffer]
            scores = [d['score'] for d in self.score_buffer]
            
            if len(timestamps) > 1:
                base_time = timestamps[0]
                x_values = [(t - base_time).total_seconds() / 60 for t in timestamps]  # Minutes from start
                
                self.curve.setData(x_values, scores)
                
                # Update threshold lines
                self.good_threshold.setData([0, x_values[-1]], [80, 80])
                self.warning_threshold.setData([0, x_values[-1]], [60, 60])
            
            # Update title with current score
            self.plot_widget.setTitle(f"Driving Score Over Time (Current: {score:.0f})", 
                                  color=ProfessionalTheme.TEXT_PRIMARY, size="12pt")
    
    def get_export_data(self) -> str:
        """Get data for export"""
        lines = ["Timestamp,Score"]
        for d in self.score_buffer:
            lines.append(f"{d['timestamp'].isoformat()},{d['score']:.1f}")
        return "\n".join(lines)


class TemperatureHistoryChart(AnalyticsChartWidget):
    """Temperature history line chart"""
    
    def __init__(self, parent=None):
        super().__init__("Temperature History", parent)
        self.temp_buffer = deque(maxlen=200)
        self._setup_chart()
    
    def _setup_chart(self):
        """Setup temperature chart"""
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(ProfessionalTheme.CARD_BG)
        self.plot_widget.setTitle("Temperature History", color=ProfessionalTheme.TEXT_PRIMARY, size="12pt")
        
        # Configure axes
        self.plot_widget.setLabel('left', 'Temperature (°C)', color=ProfessionalTheme.TEXT_SECONDARY)
        self.plot_widget.setLabel('bottom', 'Time', color=ProfessionalTheme.TEXT_SECONDARY)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # Create curves for coolant and intake
        self.coolant_curve = self.plot_widget.plot(
            name="Coolant",
            pen=pg.mkPen(color=QColor(ProfessionalTheme.PRIMARY), width=2),
            symbol='o',
            symbolSize=6
        )
        self.intake_curve = self.plot_widget.plot(
            name="Intake",
            pen=pg.mkPen(color=QColor(ProfessionalTheme.INFO), width=2),
            symbol='s',
            symbolSize=6
        )
        
        # Add legend
        self.plot_widget.addLegend()
        
        self.chart_layout.addWidget(self.plot_widget)
    
    def update_data(self, data: Dict[str, Any]):
        """Update chart with temperature data"""
        coolant = data.get('coolant_temp')
        intake = data.get('intake_temp')
        
        if coolant is not None or intake is not None:
            self.temp_buffer.append({
                'timestamp': datetime.now(),
                'coolant': float(coolant) if coolant is not None else None,
                'intake': float(intake) if intake is not None else None
            })
            
            # Update plots
            timestamps = [d['timestamp'] for d in self.temp_buffer]
            coolant_temps = [d['coolant'] for d in self.temp_buffer if d['coolant'] is not None]
            intake_temps = [d['intake'] for d in self.temp_buffer if d['intake'] is not None]
            
            if len(timestamps) > 1:
                base_time = timestamps[0]
                x_values = [(t - base_time).total_seconds() / 60 for t in timestamps]
                
                # Update coolant curve
                if coolant_temps:
                    coolant_x = [x_values[i] for i, d in enumerate(self.temp_buffer) if d['coolant'] is not None]
                    self.coolant_curve.setData(coolant_x, coolant_temps)
                
                # Update intake curve
                if intake_temps:
                    intake_x = [x_values[i] for i, d in enumerate(self.temp_buffer) if d['intake'] is not None]
                    self.intake_curve.setData(intake_x, intake_temps)
    
    def get_export_data(self) -> str:
        """Get data for export"""
        lines = ["Timestamp,Coolant Temp,Intake Temp"]
        for d in self.temp_buffer:
            coolant = f"{d['coolant']:.1f}" if d['coolant'] is not None else ""
            intake = f"{d['intake']:.1f}" if d['intake'] is not None else ""
            lines.append(f"{d['timestamp'].isoformat()},{coolant},{intake}")
        return "\n".join(lines)


class RPMHistogramChart(AnalyticsChartWidget):
    """RPM distribution histogram"""
    
    def __init__(self, parent=None):
        super().__init__("RPM Distribution", parent)
        self.rpm_buffer = deque(maxlen=1000)
        self._setup_chart()
    
    def _setup_chart(self):
        """Setup histogram for RPM distribution"""
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(ProfessionalTheme.CARD_BG)
        self.plot_widget.setTitle("RPM Distribution", color=ProfessionalTheme.TEXT_PRIMARY, size="12pt")
        
        # Configure axes
        self.plot_widget.setLabel('left', 'Frequency', color=ProfessionalTheme.TEXT_SECONDARY)
        self.plot_widget.setLabel('bottom', 'RPM', color=ProfessionalTheme.TEXT_SECONDARY)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # Create bar graph for histogram
        self.bar_graph = pg.BarGraphItem(x=[0], height=[0], width=0.8, brush=pg.mkBrush(QColor(ProfessionalTheme.PRIMARY)))
        self.plot_widget.addItem(self.bar_graph)
        
        self.chart_layout.addWidget(self.plot_widget)
    
    def update_data(self, data: Dict[str, Any]):
        """Update chart with RPM data"""
        rpm = data.get('rpm')
        if rpm is not None:
            self.rpm_buffer.append(float(rpm))
            
            # Calculate histogram
            if len(self.rpm_buffer) > 10:
                values = list(self.rpm_buffer)
                hist, bin_edges = np.histogram(values, bins=20)
                bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
                
                self.bar_graph.setOpts(x=bin_centers, height=hist, width=bin_centers[1] - bin_centers[0])
                
                # Update title
                avg_rpm = sum(values) / len(values)
                self.plot_widget.setTitle(f"RPM Distribution (Avg: {avg_rpm:.0f} RPM)", 
                                      color=ProfessionalTheme.TEXT_PRIMARY, size="12pt")
    
    def get_export_data(self) -> str:
        """Get data for export"""
        lines = ["RPM"]
        for rpm in self.rpm_buffer:
            lines.append(f"{rpm:.0f}")
        return "\n".join(lines)


class AnalyticsTab(QWidget):
    """
    PREDICT - Analytics Tab with Real-Time Charts
    
    Provides comprehensive vehicle analytics with interactive charts.
    """
    
    def __init__(self, get_historical_data=None, parent=None):
        super().__init__(parent)
        self.get_historical_data = get_historical_data or (lambda: [])
        
        self._setup_ui()
        self._setup_charts()
        self._start_update_timer()
    
    def _setup_ui(self):
        """Setup main UI layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # Header
        header = QHBoxLayout()
        
        title = QLabel("Vehicle Analytics")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title.setStyleSheet(f"color: {ProfessionalTheme.TEXT_PRIMARY};")
        header.addWidget(title)
        
        header.addStretch()
        
        # Time range selector
        time_label = QLabel("Time Range:")
        time_label.setStyleSheet(f"color: {ProfessionalTheme.TEXT_SECONDARY}; font-size: 12px;")
        header.addWidget(time_label)
        
        self.time_range = QComboBox()
        self.time_range.addItems(["Last Hour", "Last 6 Hours", "Last 24 Hours", "Last 7 Days", "All Data"])
        self.time_range.setCurrentIndex(2)  # Default: Last 24 Hours
        self.time_range.setStyleSheet(f"""
            QComboBox {{
                background-color: {ProfessionalTheme.CARD_BG};
                color: {ProfessionalTheme.TEXT_PRIMARY};
                border: 1px solid {ProfessionalTheme.BORDER};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {ProfessionalTheme.CARD_BG};
                color: {ProfessionalTheme.TEXT_PRIMARY};
                selection-background-color: {ProfessionalTheme.PRIMARY};
                border: 1px solid {ProfessionalTheme.BORDER};
            }}
        """)
        header.addWidget(self.time_range)
        
        # Refresh button
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.setStyleSheet(self._get_button_style('primary'))
        self.refresh_btn.clicked.connect(self._refresh_charts)
        header.addWidget(self.refresh_btn)
        
        layout.addLayout(header)
        
        # Chart tabs
        self.chart_tabs = QTabWidget()
        self.chart_tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {ProfessionalTheme.BORDER};
                border-radius: 8px;
                background-color: {ProfessionalTheme.BACKGROUND_SECONDARY};
                padding: 5px;
            }}
            QTabBar::tab {{
                background-color: {ProfessionalTheme.CARD_BG};
                color: {ProfessionalTheme.TEXT_SECONDARY};
                padding: 10px 18px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                border: 1px solid {ProfessionalTheme.BORDER};
                border-bottom: none;
                font-weight: 500;
            }}
            QTabBar::tab:selected {{
                background-color: {ProfessionalTheme.PRIMARY};
                color: {ProfessionalTheme.TEXT_PRIMARY};
                font-weight: 600;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {ProfessionalTheme.CARD_BG_HOVER};
                color: {ProfessionalTheme.TEXT_PRIMARY};
            }}
        """)
        layout.addWidget(self.chart_tabs)
        
        # Status bar
        self.status_label = QLabel("Ready - Waiting for data...")
        self.status_label.setStyleSheet(f"color: {ProfessionalTheme.TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(self.status_label)
    
    def _setup_charts(self):
        """Setup all chart widgets"""
        # Fuel Efficiency Chart
        self.fuel_chart = FuelEfficiencyChart()
        self.fuel_chart.data_exported.connect(self._export_chart_data)
        self.chart_tabs.addTab(self.fuel_chart, "📈 Fuel Efficiency")
        
        # Maintenance Cost Chart
        self.cost_chart = MaintenanceCostChart()
        self.cost_chart.data_exported.connect(self._export_chart_data)
        self.chart_tabs.addTab(self.cost_chart, "💰 Maintenance Costs")
        
        # DTC Category Chart
        self.dtc_chart = DTCCategoryChart()
        self.dtc_chart.data_exported.connect(self._export_chart_data)
        self.chart_tabs.addTab(self.dtc_chart, "⚠️ DTC Categories")
        
        # Driving Score Chart
        self.score_chart = DrivingScoreChart()
        self.score_chart.data_exported.connect(self._export_chart_data)
        self.chart_tabs.addTab(self.score_chart, "🎯 Driving Score")
        
        # Temperature History Chart
        self.temp_chart = TemperatureHistoryChart()
        self.temp_chart.data_exported.connect(self._export_chart_data)
        self.chart_tabs.addTab(self.temp_chart, "🌡️ Temperature")
        
        # RPM Distribution Chart
        self.rpm_chart = RPMHistogramChart()
        self.rpm_chart.data_exported.connect(self._export_chart_data)
        self.chart_tabs.addTab(self.rpm_chart, "📊 RPM Distribution")
    
    def _start_update_timer(self):
        """Start timer for periodic data updates"""
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update_charts)
        self.update_timer.start(2000)  # Update every 2 seconds
    
    def _update_charts(self):
        """Update all charts with latest data"""
        try:
            data = self.get_historical_data()
            
            if data:
                # Get most recent data point
                latest = data[-1] if isinstance(data, list) else data
                
                # Update each chart
                self.fuel_chart.update_data(latest)
                self.cost_chart.update_data(latest)
                self.dtc_chart.update_data(latest)
                self.score_chart.update_data(latest)
                self.temp_chart.update_data(latest)
                self.rpm_chart.update_data(latest)
                
                # Update status
                self.status_label.setText(f"Last update: {datetime.now().strftime('%H:%M:%S')}")
            else:
                self.status_label.setText("No data available - Connect to vehicle to see analytics")
        
        except Exception as e:
            logger.error(f"Error updating charts: {e}")
            self.status_label.setText(f"Error: {str(e)}")
    
    def _refresh_charts(self):
        """Force refresh of all charts"""
        self._update_charts()
        show_info(self, "Refreshed", "All charts have been refreshed with latest data.")
    
    def _export_chart_data(self, chart_name: str):
        """Export chart data to CSV file"""
        try:
            # Get data from active chart
            current_widget = self.chart_tabs.currentWidget()
            
            if hasattr(current_widget, 'get_export_data'):
                csv_data = current_widget.get_export_data()
                
                # Generate filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"analytics_{chart_name.replace(' ', '_').lower()}_{timestamp}.csv"
                
                # Save file
                filepath, _ = QFileDialog.getSaveFileName(
                    self, "Export Chart Data", filename, "CSV Files (*.csv)"
                )
                
                if filepath:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(csv_data)
                    
                    show_info(self, "Export Successful", f"Chart data exported to:\n{filepath}")
            else:
                show_error(self, "Export Error", "Current chart does not support data export.")
        
        except Exception as e:
            show_error(self, "Export Error", f"Failed to export data:\n{str(e)}")
    
    def _get_button_style(self, style_type: str) -> str:
        """Get consistent button style"""
        styles = {
            'primary': """
                QPushButton {
                    background-color: #C40000;
                    color: #F0F6FC;
                    border: none;
                    padding: 8px 16px;
                    font-size: 12px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover { background-color: #E53935; }
                QPushButton:pressed { background-color: #B71C1C; }
            """,
            'secondary': """
                QPushButton {
                    background-color: #21262D;
                    color: #F0F6FC;
                    border: 1px solid #30363D;
                    padding: 6px 14px;
                    font-size: 11px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover { background-color: #30363D; }
                QPushButton:pressed { background-color: #161B22; }
            """,
            'success': """
                QPushButton {
                    background-color: #4CAF50;
                    color: #F0F6FC;
                    border: none;
                    padding: 8px 16px;
                    font-size: 12px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover { background-color: #66BB6A; }
                QPushButton:pressed { background-color: #388E3C; }
            """
        }
        return styles.get(style_type, styles['primary'])
    
    def update_live_data(self, data: Dict[str, Any]):
        """Update charts with live OBD data"""
        # This allows external components to push data directly
        # Get current chart widget and update it
        current_widget = self.chart_tabs.currentWidget()
        if current_widget and hasattr(current_widget, 'update_data'):
            current_widget.update_data(data)
    
    def set_data_source(self, get_data_func):
        """Set custom data source function"""
        self.get_historical_data = get_data_func


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Mock data source
    def mock_data_source():
        return [{
            'mpg': 28.5,
            'cost': 45.50,
            'dtc_code': 'P0300',
            'driving_score': 85,
            'coolant_temp': 90.5,
            'intake_temp': 35.2,
            'rpm': 2500
        }]
    
    tab = AnalyticsTab(get_historical_data=mock_data_source)
    tab.setWindowTitle("PREDICT - Analytics Tab (Test)")
    tab.resize(1200, 800)
    tab.show()
    
    sys.exit(app.exec())
