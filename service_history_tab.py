"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Service History Tab

Service History & Component Tracking Tab
Integrated with vehicle profiles to track actual service events and component lifecycles
Helps AI learn component degradation patterns for better predictions

Enhanced with:
- Integration with EnhancedPredictionEngine for feedback learning
- LSTM training data collection
- Prediction confirmation workflow
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QFormLayout,
    QDateEdit, QSpinBox, QDoubleSpinBox, QTextEdit, QGroupBox, QLineEdit,
    QMessageBox, QTabWidget, QScrollArea, QProgressBar, QCheckBox, QFileDialog
)
from PySide6.QtCore import Qt, QDate, Signal, QTimer
from PySide6.QtGui import QColor, QFont
import sqlite3
import json
import csv
from datetime import datetime, timedelta
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Try to import enhanced prediction engine
try:
    from enhanced_prediction_engine import EnhancedPredictionEngine
    ENHANCED_ENGINE_AVAILABLE = True
except ImportError:
    ENHANCED_ENGINE_AVAILABLE = False


class ServiceHistoryTab(QWidget):
    """
    Service History & Component Tracking Tab
    Tracks actual service events for selected vehicle profile
    Integrates with EnhancedPredictionEngine for feedback learning
    """

    service_logged = Signal(dict)  # Emits when new service is logged

    def __init__(self, profile_db_path='./data/vehicle_profiles.db'):
        super().__init__()
        self.profile_db_path = profile_db_path
        self.current_profile = None
        self.current_vehicle_id = None
        self.service_db_path = './data/service_history.db'

        # Reference to enhanced prediction engine (set externally)
        self.enhanced_engine = None

        self._init_service_database()
        self.init_ui()

    def set_enhanced_engine(self, engine):
        """Set reference to EnhancedPredictionEngine for feedback integration."""
        self.enhanced_engine = engine
        logger.info("Enhanced prediction engine connected to ServiceHistoryTab")

    def _init_service_database(self):
        """Initialize service history database"""
        Path(self.service_db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.service_db_path)
        c = conn.cursor()

        # Service records table
        c.execute('''
            CREATE TABLE IF NOT EXISTS service_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_name TEXT NOT NULL,
                component_type TEXT NOT NULL,
                service_date TEXT NOT NULL,
                service_km INTEGER NOT NULL,
                service_type TEXT NOT NULL,
                part_brand TEXT,
                part_spec TEXT,
                expected_lifespan_km INTEGER,
                expected_lifespan_months INTEGER,
                actual_usage_km INTEGER,
                actual_usage_months INTEGER,
                condition_at_replacement TEXT,
                cost REAL,
                notes TEXT,
                technician TEXT,
                confirmed_fix INTEGER DEFAULT 0,
                resolution_status TEXT DEFAULT 'N/A - Not a fix',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Add new columns if they don't exist (for existing databases)
        try:
            c.execute("ALTER TABLE service_records ADD COLUMN confirmed_fix INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            c.execute("ALTER TABLE service_records ADD COLUMN resolution_status TEXT DEFAULT 'N/A - Not a fix'")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Component lifecycle tracking
        c.execute('''
            CREATE TABLE IF NOT EXISTS component_lifecycle (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_name TEXT NOT NULL,
                component_type TEXT NOT NULL,
                install_date TEXT NOT NULL,
                install_km INTEGER NOT NULL,
                current_km INTEGER,
                current_condition TEXT,
                degradation_rate REAL,
                predicted_failure_km INTEGER,
                last_inspection_date TEXT,
                last_inspection_km INTEGER,
                status TEXT DEFAULT 'active',
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()
        logger.info("Service history database initialized")

    def init_ui(self):
        """Initialize user interface"""
        logger.info("init_ui: Starting...")
        layout = QVBoxLayout(self)
        logger.info("init_ui: QVBoxLayout created")
        layout.setSpacing(10)

        # Header
        header_layout = QHBoxLayout()
        logger.info("init_ui: QHBoxLayout created")

        title = QLabel("<h2>Service History & Component Tracking</h2>")
        logger.info("init_ui: Title QLabel created")
        title.setStyleSheet("color: #1976D2;")
        logger.info("init_ui: Title setStyleSheet done")
        header_layout.addWidget(title)
        logger.info("init_ui: Title added to layout")

        header_layout.addStretch()
        logger.info("init_ui: addStretch done")

        # Current profile display (read-only, set from Profiles tab)
        profile_label = QLabel("Current Profile:")
        logger.info("init_ui: profile_label created")
        profile_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(profile_label)
        logger.info("init_ui: profile_label added")

        self.current_profile_label = QLabel("No profile loaded")
        logger.info("init_ui: current_profile_label created")
        self.current_profile_label.setStyleSheet("""
            background: #FFF9C4;
            border: 1px solid #FBC02D;
            border-radius: 5px;
            padding: 5px 15px;
            color: #F57F17;
            font-weight: bold;
        """)
        logger.info("init_ui: current_profile_label setStyleSheet done")
        header_layout.addWidget(self.current_profile_label)
        logger.info("init_ui: current_profile_label added to header_layout")

        layout.addLayout(header_layout)
        logger.info("init_ui: header_layout added to main layout")

        # Info panel
        self.info_label = QLabel("Select a vehicle profile to view/add service history")
        logger.info("init_ui: info_label created")
        self.info_label.setStyleSheet("""
            background: #E3F2FD;
            border: 1px solid #2196F3;
            border-radius: 5px;
            padding: 10px;
            color: #1565C0;
        """)
        logger.info("init_ui: info_label setStyleSheet done")
        layout.addWidget(self.info_label)
        logger.info("init_ui: info_label added")

        # Main content tabs
        self.content_tabs = QTabWidget()
        logger.info("init_ui: QTabWidget created")

        # Tab 1: Log New Service
        logger.info("init_ui: Creating Log Service tab...")
        self.content_tabs.addTab(self._create_log_service_tab(), "Log New Service")
        logger.info("init_ui: Log Service tab added")

        # Tab 2: Service History
        logger.info("init_ui: Creating History tab...")
        self.content_tabs.addTab(self._create_history_tab(), "Service History")
        logger.info("init_ui: History tab added")

        # Tab 3: Component Lifecycle
        logger.info("init_ui: Creating Lifecycle tab...")
        self.content_tabs.addTab(self._create_lifecycle_tab(), "Component Status")
        logger.info("init_ui: Lifecycle tab added")

        # Tab 4: AI Learning Insights
        logger.info("init_ui: Creating AI Insights tab...")
        self.content_tabs.addTab(self._create_ai_insights_tab(), "AI Learning Data")
        logger.info("init_ui: AI Insights tab added")

        # Tab 5: Pending Predictions (for feedback)
        logger.info("init_ui: Creating Predictions tab...")
        self.content_tabs.addTab(self._create_predictions_tab(), "Pending Predictions")
        logger.info("init_ui: Predictions tab added")

        # Tab 6: LSTM Training Status
        logger.info("init_ui: Creating LSTM tab...")
        self.content_tabs.addTab(self._create_lstm_tab(), "LSTM Training")
        logger.info("init_ui: LSTM tab added")

        layout.addWidget(self.content_tabs)
        logger.info("init_ui: Complete!")

    def _create_log_service_tab(self):
        """Create tab for logging new service"""
        logger.info("_create_log_service_tab: Starting...")
        widget = QWidget()
        logger.info("_create_log_service_tab: QWidget created")
        layout = QVBoxLayout(widget)
        logger.info("_create_log_service_tab: QVBoxLayout created")

        # Scroll area for form
        scroll = QScrollArea()
        logger.info("_create_log_service_tab: QScrollArea created")
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        logger.info("_create_log_service_tab: scroll_widget created")
        scroll_layout = QVBoxLayout(scroll_widget)
        logger.info("_create_log_service_tab: scroll_layout created")

        # Component selection
        component_group = QGroupBox("Component Information")
        logger.info("_create_log_service_tab: QGroupBox created")
        component_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        component_layout = QFormLayout()
        logger.info("_create_log_service_tab: QFormLayout created")

        logger.info("_create_log_service_tab: Creating component_type QComboBox...")
        self.component_type = QComboBox()
        logger.info("_create_log_service_tab: QComboBox created")
        self.component_type.addItems([
            'Brake Pads (Front)',
            'Brake Pads (Rear)',
            'Brake Discs (Front)',
            'Brake Discs (Rear)',
            'Engine Oil',
            'Oil Filter',
            'Air Filter',
            'Cabin Filter',
            'Fuel Filter',
            'Battery',
            'Spark Plugs',
            'Coolant',
            'Transmission Fluid',
            'Differential Oil',
            'Tires (Set)',
            'Tire (Individual)',
            'Serpentine Belt',
            'Timing Belt',
            'Water Pump',
            'Alternator',
            'Starter Motor',
            'Suspension Components',
            'Other'
        ])
        logger.info("_create_log_service_tab: items added")
        component_layout.addRow("Component Type:", self.component_type)
        logger.info("_create_log_service_tab: component_type added to form")

        logger.info("_create_log_service_tab: Creating service_type...")
        self.service_type = QComboBox()
        self.service_type.addItems([
            'Replacement (New)',
            'Replacement (Refurbished)',
            'Inspection',
            'Cleaning',
            'Adjustment',
            'Repair',
            'Other'
        ])
        component_layout.addRow("Service Type:", self.service_type)
        logger.info("_create_log_service_tab: service_type done")

        component_group.setLayout(component_layout)
        scroll_layout.addWidget(component_group)
        logger.info("_create_log_service_tab: Component group done")

        # Service details
        service_group = QGroupBox("Service Details")
        logger.info("_create_log_service_tab: Service details group created")
        service_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        logger.info("_create_log_service_tab: service_group styled")
        service_layout = QFormLayout()
        logger.info("_create_log_service_tab: service_layout created")

        logger.info("_create_log_service_tab: Creating QDateEdit...")
        self.service_date = QDateEdit()
        logger.info("_create_log_service_tab: QDateEdit created")
        self.service_date.setDate(QDate.currentDate())
        logger.info("_create_log_service_tab: setDate done")
        self.service_date.setCalendarPopup(True)
        logger.info("_create_log_service_tab: setCalendarPopup done")
        service_layout.addRow("Service Date:", self.service_date)
        logger.info("_create_log_service_tab: service_date added")

        logger.info("_create_log_service_tab: Creating service_km...")
        self.service_km = QSpinBox()
        self.service_km.setRange(0, 9999999)
        self.service_km.setSuffix(" km")
        service_layout.addRow("Odometer at Service:", self.service_km)
        logger.info("_create_log_service_tab: service_km done")

        self.part_brand = QLineEdit()
        self.part_brand.setPlaceholderText("e.g., Bosch, Brembo, OEM")
        service_layout.addRow("Part Brand:", self.part_brand)
        logger.info("_create_log_service_tab: part_brand done")

        self.part_spec = QLineEdit()
        self.part_spec.setPlaceholderText("e.g., Ceramic, Semi-Metallic, 5W-30")
        service_layout.addRow("Part Specification:", self.part_spec)
        logger.info("_create_log_service_tab: part_spec done")

        service_group.setLayout(service_layout)
        scroll_layout.addWidget(service_group)
        logger.info("_create_log_service_tab: service_group complete")

        # Expected lifespan (for AI learning)
        logger.info("_create_log_service_tab: Creating lifespan group...")
        lifespan_group = QGroupBox("Expected Lifespan (For AI Learning)")
        logger.info("_create_log_service_tab: lifespan_group created")
        lifespan_group.setStyleSheet("QGroupBox { font-weight: bold; color: #F57C00; }")
        logger.info("_create_log_service_tab: lifespan_group styled")
        lifespan_layout = QFormLayout()

        self.expected_km = QSpinBox()
        self.expected_km.setRange(0, 500000)
        self.expected_km.setSuffix(" km")
        self.expected_km.setValue(50000)
        lifespan_layout.addRow("Expected Lifespan (km):", self.expected_km)

        self.expected_months = QSpinBox()
        self.expected_months.setRange(0, 120)
        self.expected_months.setSuffix(" months")
        self.expected_months.setValue(24)
        lifespan_layout.addRow("Expected Lifespan (months):", self.expected_months)

        lifespan_info = QLabel(
            "💡 AI will learn from this data to predict component failures.\n"
            "Enter the manufacturer's expected lifespan or your experience."
        )
        lifespan_info.setStyleSheet("color: #666; font-size: 11px;")
        lifespan_info.setWordWrap(True)
        lifespan_layout.addRow(lifespan_info)

        lifespan_group.setLayout(lifespan_layout)
        scroll_layout.addWidget(lifespan_group)

        # Replaced component info (if replacement)
        replaced_group = QGroupBox("Previous Component Info (If Replacement)")
        replaced_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        replaced_layout = QFormLayout()

        self.actual_usage_km = QSpinBox()
        self.actual_usage_km.setRange(0, 500000)
        self.actual_usage_km.setSuffix(" km")
        replaced_layout.addRow("Actual Usage (km):", self.actual_usage_km)

        self.actual_usage_months = QSpinBox()
        self.actual_usage_months.setRange(0, 120)
        self.actual_usage_months.setSuffix(" months")
        replaced_layout.addRow("Actual Usage (months):", self.actual_usage_months)

        self.condition_at_replacement = QComboBox()
        self.condition_at_replacement.addItems([
            'N/A (New Installation)',
            'Worn Out (100%)',
            'Severely Worn (80-99%)',
            'Moderately Worn (50-79%)',
            'Lightly Worn (20-49%)',
            'Good Condition (<20%)',
            'Failed/Broken',
            'Preventive Replacement'
        ])
        replaced_layout.addRow("Condition:", self.condition_at_replacement)

        replaced_group.setLayout(replaced_layout)
        scroll_layout.addWidget(replaced_group)

        # Additional info
        additional_group = QGroupBox("Additional Information")
        additional_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        additional_layout = QFormLayout()

        self.service_cost = QDoubleSpinBox()
        self.service_cost.setRange(0, 99999)
        self.service_cost.setPrefix("$ ")
        self.service_cost.setDecimals(2)
        additional_layout.addRow("Service Cost:", self.service_cost)

        self.technician = QLineEdit()
        self.technician.setPlaceholderText("e.g., Self, Dealer, ABC Garage")
        additional_layout.addRow("Technician/Location:", self.technician)

        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Any additional notes, observations, or recommendations...")
        self.notes.setMaximumHeight(100)
        additional_layout.addRow("Notes:", self.notes)

        additional_group.setLayout(additional_layout)
        scroll_layout.addWidget(additional_group)

        # AI Learning & Resolution Tracking (NEW)
        ai_learning_group = QGroupBox("🤖 AI Learning & Fix Confirmation")
        ai_learning_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #0D47A1;
                border: 2px solid #1976D2;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        ai_learning_layout = QFormLayout()

        # Educational text
        ai_help_text = QLabel(
            "💡 <b>Help the AI Learn!</b><br>"
            "Confirming fixes helps the AI learn to predict failures more accurately. "
            "Your feedback directly improves future predictions for this vehicle and similar ones in the fleet."
        )
        ai_help_text.setStyleSheet("""
            background: #E3F2FD;
            border: 1px solid #2196F3;
            border-radius: 3px;
            padding: 8px;
            color: #0D47A1;
            font-size: 11px;
        """)
        ai_help_text.setWordWrap(True)
        ai_learning_layout.addRow(ai_help_text)

        # Confirmed Fix checkbox
        self.confirmed_fix = QCheckBox("This service fixed a predicted or diagnosed issue")
        self.confirmed_fix.setStyleSheet("font-weight: bold; color: #0D47A1; padding: 5px;")
        ai_learning_layout.addRow(self.confirmed_fix)

        # Resolution status (enabled when confirmed_fix is checked)
        self.resolution_status = QComboBox()
        self.resolution_status.addItems([
            'N/A - Not a fix',
            'Resolved - Issue completely fixed',
            'Partially Resolved - Issue improved but not fully fixed',
            'Not Resolved - Issue persists'
        ])
        self.resolution_status.setEnabled(False)
        ai_learning_layout.addRow("Resolution Status:", self.resolution_status)

        # Connect checkbox to enable/disable resolution status
        self.confirmed_fix.toggled.connect(lambda checked: self.resolution_status.setEnabled(checked))

        ai_learning_group.setLayout(ai_learning_layout)
        scroll_layout.addWidget(ai_learning_group)

        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # Buttons
        button_layout = QHBoxLayout()

        save_btn = QPushButton("💾 Save Service Record")
        save_btn.setStyleSheet(self._get_button_style('success'))
        save_btn.clicked.connect(self.save_service_record)
        button_layout.addWidget(save_btn)

        clear_btn = QPushButton("Clear Form")
        clear_btn.setStyleSheet(self._get_button_style('secondary'))
        clear_btn.clicked.connect(self.clear_form)
        button_layout.addWidget(clear_btn)

        layout.addLayout(button_layout)

        return widget

    def _create_history_tab(self):
        """Create service history table tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Filter controls
        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("Component:"))
        self.history_filter_component = QComboBox()
        self.history_filter_component.addItem("All Components")
        self.history_filter_component.currentTextChanged.connect(self.refresh_history)
        filter_layout.addWidget(self.history_filter_component)

        filter_layout.addStretch()

        export_btn = QPushButton("Export to CSV")
        export_btn.setStyleSheet(self._get_button_style('secondary'))
        export_btn.clicked.connect(self.export_history)
        filter_layout.addWidget(export_btn)

        layout.addLayout(filter_layout)

        # History table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(10)
        self.history_table.setHorizontalHeaderLabels([
            'Date', 'Odometer', 'Component', 'Service Type', 'Brand',
            'Expected Life', 'Actual Usage', 'Condition', 'Cost', 'Notes'
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._apply_table_styling(self.history_table)

        layout.addWidget(self.history_table)

        return widget

    def _create_lifecycle_tab(self):
        """Create component lifecycle status tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info = QLabel(
            "This shows the current status of all active components.\n"
            "AI uses this data to predict when components will need replacement."
        )
        info.setStyleSheet("color: #666; padding: 10px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Lifecycle table
        self.lifecycle_table = QTableWidget()
        self.lifecycle_table.setColumnCount(8)
        self.lifecycle_table.setHorizontalHeaderLabels([
            'Component', 'Install Date', 'Install KM', 'Current Age (km)',
            'Current Age (months)', 'Condition', 'Predicted Failure', 'Status'
        ])
        self.lifecycle_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.lifecycle_table.setAlternatingRowColors(True)
        self._apply_table_styling(self.lifecycle_table)

        layout.addWidget(self.lifecycle_table)

        return widget

    def _create_ai_insights_tab(self):
        """Create AI learning insights tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info = QLabel(
            "<h3>AI Learning Data</h3>"
            "This shows what the AI has learned from your service history."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.ai_insights_text = QTextEdit()
        self.ai_insights_text.setReadOnly(True)
        layout.addWidget(self.ai_insights_text)

        analyze_btn = QPushButton("Generate AI Analysis")
        analyze_btn.setStyleSheet(self._get_button_style('info'))
        analyze_btn.clicked.connect(self.generate_ai_insights)
        layout.addWidget(analyze_btn)

        return widget

    def set_profile(self, profile_name):
        """Set the current profile from the Profiles tab"""
        if not profile_name:
            self.current_profile = None
            self.current_profile_label.setText("No profile loaded")
            self.current_profile_label.setStyleSheet("""
                background: #FFF9C4;
                border: 1px solid #FBC02D;
                border-radius: 5px;
                padding: 5px 15px;
                color: #F57F17;
                font-weight: bold;
            """)
            self.info_label.setText("Please load a vehicle profile from the Profiles tab")
            return

        self.current_profile = profile_name
        self.current_profile_label.setText(profile_name)
        self.current_profile_label.setStyleSheet("""
            background: #C8E6C9;
            border: 1px solid #4CAF50;
            border-radius: 5px;
            padding: 5px 15px;
            color: #2E7D32;
            font-weight: bold;
        """)
        self.info_label.setText(f"Service history for: {profile_name}")
        self.info_label.setStyleSheet("""
            background: #C8E6C9;
            border: 1px solid #4CAF50;
            border-radius: 5px;
            padding: 10px;
            color: #2E7D32;
            font-weight: bold;
        """)

        # Refresh all tabs
        self.refresh_history()
        self.refresh_lifecycle()
        self.update_component_filter()

        logger.info(f"Profile set to: {profile_name}")

    def on_profile_changed(self, profile_name):
        """Handle profile selection change"""
        if not profile_name:
            return

        self.current_profile = profile_name
        self.info_label.setText(f"Selected Profile: {profile_name}")
        self.info_label.setStyleSheet("""
            background: #C8E6C9;
            border: 1px solid #4CAF50;
            border-radius: 5px;
            padding: 10px;
            color: #2E7D32;
            font-weight: bold;
        """)

        # Refresh all tabs
        self.refresh_history()
        self.refresh_lifecycle()
        self.update_component_filter()

    def update_component_filter(self):
        """Update component filter in history tab"""
        if not self.current_profile:
            return

        conn = sqlite3.connect(self.service_db_path)
        c = conn.cursor()
        c.execute('''
            SELECT DISTINCT component_type
            FROM service_records
            WHERE profile_name = ?
            ORDER BY component_type
        ''', (self.current_profile,))

        components = [row[0] for row in c.fetchall()]
        conn.close()

        current = self.history_filter_component.currentText()
        self.history_filter_component.clear()
        self.history_filter_component.addItem("All Components")
        self.history_filter_component.addItems(components)

        if current in components:
            self.history_filter_component.setCurrentText(current)

    def save_service_record(self):
        """Save new service record"""
        if not self.current_profile:
            QMessageBox.warning(self, "No Profile", "Please select a vehicle profile first.")
            return

        try:
            conn = sqlite3.connect(self.service_db_path)
            c = conn.cursor()

            # Insert service record
            c.execute('''
                INSERT INTO service_records (
                    profile_name, component_type, service_date, service_km,
                    service_type, part_brand, part_spec, expected_lifespan_km,
                    expected_lifespan_months, actual_usage_km, actual_usage_months,
                    condition_at_replacement, cost, notes, technician,
                    confirmed_fix, resolution_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.current_profile,
                self.component_type.currentText(),
                self.service_date.date().toString('yyyy-MM-dd'),
                self.service_km.value(),
                self.service_type.currentText(),
                self.part_brand.text(),
                self.part_spec.text(),
                self.expected_km.value(),
                self.expected_months.value(),
                self.actual_usage_km.value(),
                self.actual_usage_months.value(),
                self.condition_at_replacement.currentText(),
                self.service_cost.value(),
                self.notes.toPlainText(),
                self.technician.text(),
                1 if self.confirmed_fix.isChecked() else 0,
                self.resolution_status.currentText()
            ))

            # Update component lifecycle if replacement
            if 'Replacement' in self.service_type.currentText():
                self._update_component_lifecycle(
                    self.current_profile,
                    self.component_type.currentText(),
                    self.service_date.date().toString('yyyy-MM-dd'),
                    self.service_km.value()
                )

            conn.commit()
            conn.close()

            # Emit signal
            self.service_logged.emit({
                'profile': self.current_profile,
                'component': self.component_type.currentText(),
                'date': self.service_date.date().toString('yyyy-MM-dd'),
                'km': self.service_km.value()
            })

            QMessageBox.information(self, "Success", "Service record saved successfully!")

            # Refresh displays
            self.refresh_history()
            self.refresh_lifecycle()
            self.clear_form()

            logger.info(f"Service record saved for {self.current_profile}")

            # Sync to remote server in background
            self._sync_to_server()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save service record:\n{e}")
            logger.error(f"Save service record error: {e}")

    def _sync_to_server(self):
        """
        Sync service records to remote server.
        This makes service history available to mobile apps (PredictOBD, Guardian).
        """
        if not self.current_profile:
            return

        try:
            # Get profile_id from profile name
            profile_id = self._get_profile_id(self.current_profile)
            if not profile_id:
                logger.warning(f"Could not find profile_id for {self.current_profile}")
                return

            # Get the latest service record for this profile
            conn = sqlite3.connect(self.service_db_path)
            c = conn.cursor()
            c.execute('''
                SELECT id, component_type, service_date, service_km, service_type,
                       part_brand, part_spec, expected_lifespan_km, expected_lifespan_months,
                       actual_usage_km, actual_usage_months, condition_at_replacement,
                       cost, notes, technician, confirmed_fix, resolution_status
                FROM service_records
                WHERE profile_name = ?
                ORDER BY id DESC
                LIMIT 1
            ''', (self.current_profile,))
            record = c.fetchone()
            conn.close()

            if not record:
                return

            # Prepare record data for server
            record_data = {
                'profile_id': profile_id,
                'component_type': record[1],
                'service_date': record[2],
                'service_km': record[3],
                'service_type': record[4],
                'part_brand': record[5] or None,
                'part_spec': record[6] or None,
                'expected_lifespan_km': record[7] or None,
                'expected_lifespan_months': record[8] or None,
                'actual_usage_km': record[9] or None,
                'actual_usage_months': record[10] or None,
                'condition_at_replacement': record[11] or None,
                'cost': record[12] or None,
                'notes': record[13] or None,
                'technician': record[14] or None,
                'confirmed_fix': bool(record[15]),
                'resolution_status': record[16] or None
            }

            # Try to sync using remote_server_client
            try:
                from remote_server_client import RemoteServerClient
                client = RemoteServerClient()

                if client.is_connected():
                    response = client.post('/api/service-records', json=record_data)
                    if response and response.status_code == 200:
                        result = response.json()
                        if result.get('success'):
                            logger.info(f"Service record synced to server: {record_data['component_type']}")
                        else:
                            logger.warning(f"Server rejected service record: {result.get('error')}")
                    else:
                        logger.warning(f"Failed to sync service record: HTTP {response.status_code if response else 'N/A'}")
                else:
                    logger.debug("Remote server not connected, skipping sync")
            except ImportError:
                logger.debug("remote_server_client not available, skipping sync")
            except Exception as e:
                logger.warning(f"Error syncing to server: {e}")

        except Exception as e:
            logger.error(f"Error preparing service record for sync: {e}")

    def _get_profile_id(self, profile_name: str) -> int:
        """Get profile_id from profile name by querying the vehicle profiles database."""
        try:
            conn = sqlite3.connect(self.profile_db_path)
            c = conn.cursor()

            # Try to find profile by name or plate
            c.execute('''
                SELECT id FROM vehicle_profiles
                WHERE profile_name = ? OR car_plate = ?
                LIMIT 1
            ''', (profile_name, profile_name))

            result = c.fetchone()
            conn.close()

            if result:
                return result[0]

            logger.warning(f"Profile not found: {profile_name}")
            return None

        except Exception as e:
            logger.error(f"Error getting profile_id: {e}")
            return None

    def _update_component_lifecycle(self, profile, component, install_date, install_km):
        """Update component lifecycle tracking"""
        try:
            conn = sqlite3.connect(self.service_db_path)
            c = conn.cursor()

            # Mark old component as replaced
            c.execute('''
                UPDATE component_lifecycle
                SET status = 'replaced', updated_at = CURRENT_TIMESTAMP
                WHERE profile_name = ? AND component_type = ? AND status = 'active'
            ''', (profile, component))

            # Add new component
            c.execute('''
                INSERT INTO component_lifecycle (
                    profile_name, component_type, install_date, install_km,
                    current_km, current_condition, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (profile, component, install_date, install_km, install_km, 'New', 'active'))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Lifecycle update error: {e}")

    def refresh_history(self):
        """Refresh service history table"""
        if not self.current_profile:
            return

        try:
            conn = sqlite3.connect(self.service_db_path)
            c = conn.cursor()

            component_filter = self.history_filter_component.currentText()

            if component_filter == "All Components":
                c.execute('''
                    SELECT service_date, service_km, component_type, service_type,
                           part_brand, expected_lifespan_km, actual_usage_km,
                           condition_at_replacement, cost, notes
                    FROM service_records
                    WHERE profile_name = ?
                    ORDER BY service_date DESC, service_km DESC
                ''', (self.current_profile,))
            else:
                c.execute('''
                    SELECT service_date, service_km, component_type, service_type,
                           part_brand, expected_lifespan_km, actual_usage_km,
                           condition_at_replacement, cost, notes
                    FROM service_records
                    WHERE profile_name = ? AND component_type = ?
                    ORDER BY service_date DESC, service_km DESC
                ''', (self.current_profile, component_filter))

            records = c.fetchall()
            conn.close()

            self.history_table.setRowCount(len(records))

            for i, record in enumerate(records):
                for j, value in enumerate(record):
                    item = QTableWidgetItem(str(value) if value is not None else '')
                    self.history_table.setItem(i, j, item)

        except Exception as e:
            logger.error(f"Refresh history error: {e}")

    def refresh_lifecycle(self):
        """Refresh component lifecycle table"""
        if not self.current_profile:
            return

        try:
            conn = sqlite3.connect(self.service_db_path)
            c = conn.cursor()

            c.execute('''
                SELECT component_type, install_date, install_km, current_km,
                       current_condition, predicted_failure_km, status
                FROM component_lifecycle
                WHERE profile_name = ? AND status = 'active'
                ORDER BY component_type
            ''', (self.current_profile,))

            records = c.fetchall()
            conn.close()

            self.lifecycle_table.setRowCount(len(records))

            for i, record in enumerate(records):
                component, install_date, install_km, current_km, condition, predicted, status = record

                # Calculate ages
                age_km = (current_km or install_km) - install_km

                try:
                    install_dt = datetime.strptime(install_date, '%Y-%m-%d')
                    age_months = (datetime.now() - install_dt).days / 30
                except (ValueError, TypeError):
                    age_months = 0

                self.lifecycle_table.setItem(i, 0, QTableWidgetItem(component))
                self.lifecycle_table.setItem(i, 1, QTableWidgetItem(install_date))
                self.lifecycle_table.setItem(i, 2, QTableWidgetItem(str(install_km)))
                self.lifecycle_table.setItem(i, 3, QTableWidgetItem(str(age_km)))
                self.lifecycle_table.setItem(i, 4, QTableWidgetItem(f"{age_months:.1f}"))
                self.lifecycle_table.setItem(i, 5, QTableWidgetItem(condition or 'Unknown'))
                self.lifecycle_table.setItem(i, 6, QTableWidgetItem(str(predicted) if predicted else 'N/A'))
                self.lifecycle_table.setItem(i, 7, QTableWidgetItem(status))

        except Exception as e:
            logger.error(f"Refresh lifecycle error: {e}")

    def generate_ai_insights(self):
        """Generate AI learning insights from service history"""
        if not self.current_profile:
            return

        try:
            conn = sqlite3.connect(self.service_db_path)
            c = conn.cursor()

            # Get all service records for this profile
            c.execute('''
                SELECT component_type, expected_lifespan_km, actual_usage_km,
                       condition_at_replacement
                FROM service_records
                WHERE profile_name = ? AND actual_usage_km > 0
            ''', (self.current_profile,))

            records = c.fetchall()
            conn.close()

            if not records:
                self.ai_insights_text.setPlainText("No service data available for AI analysis yet.")
                return

            # Analyze by component type
            insights = []
            insights.append(f"AI Learning Analysis for: {self.current_profile}\n")
            insights.append("=" * 60 + "\n\n")

            component_data = {}
            for component, expected, actual, condition in records:
                if component not in component_data:
                    component_data[component] = []
                component_data[component].append((expected, actual, condition))

            for component, data in component_data.items():
                insights.append(f"Component: {component}\n")
                insights.append(f"  Total replacements logged: {len(data)}\n")

                avg_expected = sum(d[0] for d in data) / len(data)
                avg_actual = sum(d[1] for d in data if d[1]) / len([d for d in data if d[1]]) if any(d[1] for d in data) else 0

                insights.append(f"  Average expected lifespan: {avg_expected:.0f} km\n")
                insights.append(f"  Average actual usage: {avg_actual:.0f} km\n")

                if avg_actual > 0:
                    accuracy = (avg_actual / avg_expected) * 100
                    insights.append(f"  Lifespan accuracy: {accuracy:.1f}%\n")

                    if accuracy < 80:
                        insights.append(f"  ⚠️ AI learned: Component fails earlier than expected\n")
                    elif accuracy > 120:
                        insights.append(f"  ✅ AI learned: Component lasts longer than expected\n")
                    else:
                        insights.append(f"  ✅ AI learned: Component lifespan matches expectations\n")

                insights.append("\n")

            self.ai_insights_text.setPlainText("".join(insights))

        except Exception as e:
            logger.error(f"AI insights error: {e}")
            self.ai_insights_text.setPlainText(f"Error generating insights: {e}")

    def clear_form(self):
        """Clear the service entry form"""
        self.service_date.setDate(QDate.currentDate())
        self.service_km.setValue(0)
        self.part_brand.clear()
        self.part_spec.clear()
        self.expected_km.setValue(50000)
        self.expected_months.setValue(24)
        self.actual_usage_km.setValue(0)
        self.actual_usage_months.setValue(0)
        self.condition_at_replacement.setCurrentIndex(0)
        self.service_cost.setValue(0)
        self.technician.clear()
        self.notes.clear()
        # Clear AI learning fields
        self.confirmed_fix.setChecked(False)
        self.resolution_status.setCurrentIndex(0)
        self.resolution_status.setEnabled(False)

    def export_history(self):
        """Export service history to CSV"""
        if not self.current_profile:
            QMessageBox.warning(self, "No Profile", "Please select a vehicle profile first.")
            return

        try:
            conn = sqlite3.connect(self.service_db_path)
            c = conn.cursor()

            # Get all service records for current profile
            component_filter = self.history_filter_component.currentText()
            if component_filter == "All Components":
                c.execute('''
                    SELECT service_date, service_km, component_type, service_type,
                           part_brand, expected_lifespan_km, actual_usage_km,
                           condition_at_replacement, cost, notes, technician
                    FROM service_records
                    WHERE profile_name = ?
                    ORDER BY service_date DESC, service_km DESC
                    ''', (self.current_profile,))
            else:
                c.execute('''
                    SELECT service_date, service_km, component_type, service_type,
                           part_brand, expected_lifespan_km, actual_usage_km,
                           condition_at_replacement, cost, notes, technician
                    FROM service_records
                    WHERE profile_name = ? AND component_type = ?
                    ORDER BY service_date DESC, service_km DESC
                    ''', (self.current_profile, component_filter))

            records = c.fetchall()
            conn.close()

            if not records:
                QMessageBox.information(self, "No Data", "No service history records found for this profile.")
                return

            # Ask user for file location
            filename, _ = QFileDialog.getSaveFileName(
                self,
                f"service_history_{self.current_profile}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "CSV Files (*.csv)"
            )

            if not filename:
                return

            # Write CSV file
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow([
                    'Date', 'Odometer (km)', 'Component Type', 'Service Type',
                    'Part Brand', 'Part Specification', 'Expected Lifespan (km)',
                    'Expected Lifespan (months)', 'Actual Usage (km)', 'Actual Usage (months)',
                    'Condition at Replacement', 'Cost', 'Technician', 'Notes'
                ])

                # Write data rows
                for record in records:
                    writer.writerow([
                        record[0],  # service_date
                        record[1],  # service_km
                        record[2],  # component_type
                        record[3],  # service_type
                        record[4],  # part_brand
                        record[5],  # part_spec
                        record[6],  # expected_lifespan_km
                        record[7],  # expected_lifespan_months
                        record[8],  # actual_usage_km
                        record[9],  # actual_usage_months
                        record[10],  # condition_at_replacement
                        record[11],  # cost
                        record[12],  # technician
                        record[13] if len(record) > 13 else ''  # notes
                    ])

            QMessageBox.information(
                self,
                "Export Complete",
                f"Successfully exported {len(records)} service records to:\n{filename}"
            )
            logger.info(f"Service history exported to {filename}")

        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export service history:\n{e}"
            )
            logger.error(f"Export error: {e}")

    def _create_predictions_tab(self):
        """Create pending predictions tab for feedback confirmation."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Info
        info = QLabel(
            "<b>Pending Predictions</b><br>"
            "These AI predictions are awaiting confirmation. "
            "Confirming whether predictions were correct helps train the LSTM model for better accuracy."
        )
        info.setWordWrap(True)
        info.setStyleSheet("""
            background: #E3F2FD;
            border: 1px solid #2196F3;
            border-radius: 5px;
            padding: 10px;
            color: #1565C0;
        """)
        layout.addWidget(info)

        # Predictions table
        self.predictions_table = QTableWidget()
        self.predictions_table.setColumnCount(6)
        self.predictions_table.setHorizontalHeaderLabels([
            'Prediction Date', 'Component', 'Predicted Failure', 'Confidence', 'Status', 'Action'
        ])
        self.predictions_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.predictions_table.setAlternatingRowColors(True)
        self._apply_table_styling(self.predictions_table)
        layout.addWidget(self.predictions_table)

        # Buttons
        btn_layout = QHBoxLayout()

        refresh_btn = QPushButton("Refresh Predictions")
        refresh_btn.setStyleSheet(self._get_button_style('secondary'))
        refresh_btn.clicked.connect(self._refresh_predictions)
        btn_layout.addWidget(refresh_btn)

        expire_btn = QPushButton("Mark Old as No-Failure")
        expire_btn.setToolTip("Mark predictions older than 30 days as 'no failure occurred'")
        expire_btn.setStyleSheet(self._get_button_style('warning'))
        expire_btn.clicked.connect(self._expire_old_predictions)
        btn_layout.addWidget(expire_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return widget

    def _create_lstm_tab(self):
        """Create LSTM training status tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # LSTM Status
        status_group = QGroupBox("LSTM Model Status")
        status_layout = QFormLayout(status_group)

        self.lstm_status_label = QLabel("Checking...")
        status_layout.addRow("Status:", self.lstm_status_label)

        self.lstm_version_label = QLabel("-")
        status_layout.addRow("Model Version:", self.lstm_version_label)

        self.lstm_samples_label = QLabel("-")
        status_layout.addRow("Training Samples:", self.lstm_samples_label)

        self.lstm_last_trained = QLabel("-")
        status_layout.addRow("Last Trained:", self.lstm_last_trained)

        layout.addWidget(status_group)

        # Training Data
        data_group = QGroupBox("Training Data Collection")
        data_layout = QFormLayout(data_group)

        self.labeled_sequences_label = QLabel("-")
        data_layout.addRow("Labeled Sequences:", self.labeled_sequences_label)

        self.positive_samples_label = QLabel("-")
        data_layout.addRow("Positive (failures):", self.positive_samples_label)

        self.negative_samples_label = QLabel("-")
        data_layout.addRow("Negative (no failure):", self.negative_samples_label)

        self.lstm_ready_label = QLabel("-")
        data_layout.addRow("Ready for Training:", self.lstm_ready_label)

        layout.addWidget(data_group)

        # Training Actions
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions_group)

        self.train_lstm_btn = QPushButton("Train LSTM Model")
        self.train_lstm_btn.setStyleSheet(self._get_button_style('primary'))
        self.train_lstm_btn.clicked.connect(self._train_lstm)
        actions_layout.addWidget(self.train_lstm_btn)

        self.training_progress = QProgressBar()
        self.training_progress.setVisible(False)
        actions_layout.addWidget(self.training_progress)

        self.training_status_label = QLabel("")
        self.training_status_label.setWordWrap(True)
        actions_layout.addWidget(self.training_status_label)

        refresh_btn = QPushButton("Refresh Status")
        refresh_btn.setStyleSheet(self._get_button_style('secondary'))
        refresh_btn.clicked.connect(self._refresh_lstm_status)
        actions_layout.addWidget(refresh_btn)

        layout.addWidget(actions_group)
        layout.addStretch()

        # Initial refresh
        QTimer.singleShot(1000, self._refresh_lstm_status)

        return widget

    def _refresh_predictions(self):
        """Refresh pending predictions from enhanced engine."""
        if not self.enhanced_engine:
            self.predictions_table.setRowCount(0)
            return

        predictions = self.enhanced_engine.get_pending_predictions(self.current_vehicle_id)
        self.predictions_table.setRowCount(len(predictions))

        for i, pred in enumerate(predictions):
            self.predictions_table.setItem(i, 0, QTableWidgetItem(
                pred.get('predicted_date', '')[:10]
            ))
            self.predictions_table.setItem(i, 1, QTableWidgetItem(
                pred.get('predicted_component', '')
            ))
            self.predictions_table.setItem(i, 2, QTableWidgetItem(
                pred.get('predicted_failure_date', '')[:10]
            ))

            conf = pred.get('confidence_score', 0)
            conf_item = QTableWidgetItem(f"{conf * 100:.0f}%")
            if conf > 0.7:
                conf_item.setBackground(QColor(200, 255, 200))
            elif conf > 0.4:
                conf_item.setBackground(QColor(255, 255, 200))
            else:
                conf_item.setBackground(QColor(255, 200, 200))
            self.predictions_table.setItem(i, 3, conf_item)

            self.predictions_table.setItem(i, 4, QTableWidgetItem(
                pred.get('status', 'pending')
            ))

            # Confirm button
            confirm_btn = QPushButton("Confirm")
            confirm_btn.setStyleSheet(self._get_button_style('primary'))
            confirm_btn.clicked.connect(lambda _, p=pred: self._confirm_prediction(p))
            self.predictions_table.setCellWidget(i, 5, confirm_btn)

    def _confirm_prediction(self, prediction: dict):
        """Show dialog to confirm a prediction."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Confirm Prediction")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)

        # Prediction info
        info = QLabel(
            f"<b>Component:</b> {prediction.get('predicted_component', 'Unknown')}<br>"
            f"<b>Predicted Failure:</b> {prediction.get('predicted_failure_date', '')[:10]}<br>"
            f"<b>Confidence:</b> {prediction.get('confidence_score', 0) * 100:.0f}%"
        )
        layout.addWidget(info)

        # Feedback form
        form = QFormLayout()

        correct_combo = QComboBox()
        correct_combo.addItems([
            "Yes - Failure occurred as predicted",
            "Partially - Similar issue occurred",
            "No - No failure occurred",
            "No - Different issue occurred"
        ])
        form.addRow("Was prediction correct?", correct_combo)

        outcome_combo = QComboBox()
        outcome_combo.addItems(['failed', 'no_failure', 'partial', 'different_failure'])
        form.addRow("Actual Outcome:", outcome_combo)

        failure_date = QDateEdit()
        failure_date.setCalendarPopup(True)
        failure_date.setDate(QDate.currentDate())
        form.addRow("Failure Date (if applicable):", failure_date)

        notes = QTextEdit()
        notes.setMaximumHeight(60)
        form.addRow("Notes:", notes)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save Feedback")
        save_btn.setStyleSheet(self._get_button_style('success'))
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(self._get_button_style('secondary'))
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        def save_feedback():
            if self.enhanced_engine:
                was_correct = correct_combo.currentText().startswith("Yes")
                result = self.enhanced_engine.confirm_prediction(
                    prediction_id=prediction.get('prediction_id'),
                    was_correct=was_correct,
                    actual_outcome=outcome_combo.currentText(),
                    actual_failure_date=failure_date.date().toString(Qt.ISODate),
                    user_notes=notes.toPlainText()
                )
                if result.get('success'):
                    QMessageBox.information(dialog, "Success", "Feedback recorded!")
                    dialog.accept()
                    self._refresh_predictions()
                    self._refresh_lstm_status()
                else:
                    QMessageBox.warning(dialog, "Error", result.get('error', 'Unknown error'))
            else:
                QMessageBox.warning(dialog, "Error", "Enhanced engine not connected")

        save_btn.clicked.connect(save_feedback)
        cancel_btn.clicked.connect(dialog.reject)

        dialog.exec()

    def _expire_old_predictions(self):
        """Mark old predictions as no-failure (negative samples)."""
        if not self.enhanced_engine:
            return

        if hasattr(self.enhanced_engine, 'feedback_collector') and self.enhanced_engine.feedback_collector:
            expired = self.enhanced_engine.feedback_collector.expire_old_predictions(30)
            QMessageBox.information(
                self, "Expired",
                f"Marked {len(expired)} old predictions as 'no failure' (negative training samples)"
            )
            self._refresh_predictions()
            self._refresh_lstm_status()

    def _refresh_lstm_status(self):
        """Refresh LSTM training status display."""
        if not self.enhanced_engine:
            self.lstm_status_label.setText("Not connected")
            self.lstm_status_label.setStyleSheet("color: orange;")
            self.train_lstm_btn.setEnabled(False)
            return

        # Get LSTM status
        lstm_status = self.enhanced_engine.get_lstm_status()

        if lstm_status.get('available'):
            self.lstm_status_label.setText("Available")
            self.lstm_status_label.setStyleSheet("color: green; font-weight: bold;")
            self.lstm_version_label.setText(lstm_status.get('version', '-'))
            self.lstm_samples_label.setText(str(lstm_status.get('training_samples', 0)))

            last_trained = lstm_status.get('last_trained')
            if last_trained:
                self.lstm_last_trained.setText(last_trained[:19])
            else:
                self.lstm_last_trained.setText("Never")

            self.train_lstm_btn.setEnabled(True)
        else:
            reason = lstm_status.get('reason', 'Unknown')
            self.lstm_status_label.setText(f"Not available: {reason}")
            self.lstm_status_label.setStyleSheet("color: orange;")
            self.train_lstm_btn.setEnabled(False)

        # Get feedback statistics
        feedback_stats = self.enhanced_engine.get_feedback_statistics()

        if feedback_stats.get('available'):
            training_data = feedback_stats.get('training_data', {})
            self.labeled_sequences_label.setText(str(training_data.get('total_sequences', 0)))
            self.positive_samples_label.setText(str(training_data.get('positive_samples', 0)))
            self.negative_samples_label.setText(str(training_data.get('negative_samples', 0)))

            if training_data.get('lstm_ready'):
                self.lstm_ready_label.setText("Yes - Sufficient data")
                self.lstm_ready_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                total = training_data.get('total_sequences', 0)
                self.lstm_ready_label.setText(f"No - Need {100 - total} more samples")
                self.lstm_ready_label.setStyleSheet("color: orange;")

    def _train_lstm(self):
        """Start LSTM model training."""
        if not self.enhanced_engine:
            return

        self.train_lstm_btn.setEnabled(False)
        self.training_progress.setVisible(True)
        self.training_progress.setRange(0, 0)  # Indeterminate
        self.training_status_label.setText("Training in progress...")
        self.training_status_label.setStyleSheet("color: blue;")

        # Train the model
        result = self.enhanced_engine.train_lstm_model()

        self.training_progress.setVisible(False)
        self.train_lstm_btn.setEnabled(True)

        if result.get('success'):
            self.training_status_label.setText(
                f"Training complete!\n"
                f"Version: {result.get('version')}\n"
                f"Epochs: {result.get('epochs')}\n"
                f"Accuracy: {result.get('accuracy', 0) * 100:.1f}%"
            )
            self.training_status_label.setStyleSheet("color: green;")
        else:
            self.training_status_label.setText(f"Training failed: {result.get('error')}")
            self.training_status_label.setStyleSheet("color: red;")

        self._refresh_lstm_status()
    
    def _get_button_style(self, style_type: str = 'primary') -> str:
        """Get consistent button stylesheet based on style type."""
        styles = {
            'primary': """
                QPushButton {
                        background-color: #C40000;
                        color: #FFFFFF;
                        border: none;
                        padding: 12px 24px;
                        font-size: 14px;
                        font-weight: 600;
                        border-radius: 6px;
                    }
                    QPushButton:hover {
                        background-color: #E53935;
                    }
                    QPushButton:pressed {
                        background-color: #A00000;
                    }
                    QPushButton:disabled {
                        background-color: #30363D;
                        color: #8B949E;
                    }
            """,
            'secondary': """
                QPushButton {
                        background-color: #21262D;
                        color: #F0F6FC;
                        border: 1px solid #30363D;
                        padding: 10px 20px;
                        font-size: 14px;
                        font-weight: 600;
                        border-radius: 6px;
                    }
                    QPushButton:hover {
                        background-color: #30363D;
                    }
                    QPushButton:disabled {
                        background-color: #161B22;
                        color: #8B949E;
                    }
            """,
            'danger': """
                QPushButton {
                        background-color: #C40000;
                        color: #FFFFFF;
                        border: none;
                        padding: 10px 20px;
                        font-size: 14px;
                        font-weight: 600;
                        border-radius: 6px;
                    }
                    QPushButton:hover {
                        background-color: #E53935;
                    }
                    QPushButton:pressed {
                        background-color: #A00000;
                    }
                    QPushButton:disabled {
                        background-color: #30363D;
                        color: #8B949E;
                    }
            """,
            'success': """
                QPushButton {
                        background-color: #4CAF50;
                        color: #FFFFFF;
                        border: none;
                        padding: 10px 20px;
                        font-size: 14px;
                        font-weight: 600;
                        border-radius: 6px;
                    }
                    QPushButton:hover {
                        background-color: #45a049;
                    }
                    QPushButton:pressed {
                        background-color: #388E3C;
                    }
                    QPushButton:disabled {
                        background-color: #30363D;
                        color: #8B949E;
                    }
            """,
            'warning': """
                QPushButton {
                        background-color: #FFC107;
                        color: #FFFFFF;
                        border: none;
                        padding: 10px 20px;
                        font-size: 14px;
                        font-weight: 600;
                        border-radius: 6px;
                    }
                    QPushButton:hover {
                        background-color: #FFD54F;
                    }
                    QPushButton:pressed {
                        background-color: #FFA000;
                    }
                    QPushButton:disabled {
                        background-color: #30363D;
                        color: #8B949E;
                    }
            """,
            'info': """
                QPushButton {
                        background-color: #2196F3;
                        color: #FFFFFF;
                        border: none;
                        padding: 10px 20px;
                        font-size: 14px;
                        font-weight: 600;
                        border-radius: 6px;
                    }
                    QPushButton:hover {
                        background-color: #1976D2;
                    }
                    QPushButton:pressed {
                        background-color: #0D47A1;
                    }
                    QPushButton:disabled {
                        background-color: #30363D;
                        color: #8B949E;
                    }
            """
        }
        return styles.get(style_type, styles['primary'])
    
    def _apply_table_styling(self, table_widget):
        """Apply consistent table styling to a QTableWidget"""
        table_widget.setStyleSheet("""
            QTableWidget {
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 8px;
                gridline-color: #30363D;
            }
            QTableWidget::item {
                padding: 10px;
                border-bottom: 1px solid #30363D;
            }
            QTableWidget::item:selected {
                background-color: #C40000;
                color: #FFFFFF;
            }
            QTableWidget::item:hover {
                background-color: #30363D;
            }
            QHeaderView::section {
                background-color: #161B22;
                color: #F0F6FC;
                padding: 12px;
                border: none;
                border-bottom: 2px solid #C40000;
                font-weight: 600;
            }
            QScrollBar:vertical {
                background-color: #161B22;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #484F58;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #6E7681;
            }
        """)
