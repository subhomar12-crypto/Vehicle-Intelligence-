"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Settings Tab

Settings Tab - Comprehensive Application Settings
Created: 2025-12-16
Refactored: 2026-01-10 - Enhanced with General, OBD, Notification, and AI settings

Provides user controls for:
- General settings (language, units, auto-connect)
- OBD settings (port, baud rate, protocol)
- Notification settings (email, SMS, push preferences)
- AI behavior mode (Conservative / Balanced / Early-warning)
- Learning scope (Vehicle only / Fleet assisted)
- Advanced settings (thresholds, baseline requirements)
"""

import json
import os
from typing import Dict, Any
from config import get_config
CONFIG = get_config()
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QGroupBox, QRadioButton, QButtonGroup, QSlider, QSpinBox,
    QCheckBox, QPushButton, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QScrollArea, QFrame, QGridLayout, QTabWidget,
    QLineEdit, QSpinBox, QDoubleSpinBox, QFileDialog, QFormLayout
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class SettingsTab(QWidget):
    """
    Comprehensive Settings Tab
    
    Provides user controls for:
    - General settings (language, units, auto-connect)
    - OBD settings (port, baud rate, protocol)
    - Notification settings (email, SMS, push preferences)
    - AI behavior and learning configuration
    """

    # Signal emitted when settings are saved
    settings_saved = Signal(dict)
    theme_changed = Signal(str)  # Emitted when theme is changed

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_file = "./data/settings.json"
        self.obd_settings_file = "./data/obd_settings.json"
        self.notification_settings_file = "./data/notification_settings.json"
        self._setup_ui()
        self._load_all_settings()

    def _setup_ui(self):
        """Build the settings UI with tabbed interface"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ==================== HEADER ====================
        header = QFrame()
        header.setStyleSheet("background-color: #161B22; border-bottom: 1px solid #30363D;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 15, 20, 15)
        header_layout.setSpacing(15)

        title = QLabel("⚙️ Settings")
        title.setFont(QFont("Segoe UI", 24, QFont.Bold))
        title.setStyleSheet("color: #F0F6FC;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Theme selector
        theme_label = QLabel("Theme:")
        theme_label.setStyleSheet("color: #8B949E; font-size: 13px;")
        header_layout.addWidget(theme_label)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light"])
        self.theme_combo.setStyleSheet("""
            QComboBox {
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 13px;
            }
        """)
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        header_layout.addWidget(self.theme_combo)

        main_layout.addWidget(header)

        # ==================== TAB WIDGET ====================
        self.settings_tabs = QTabWidget()
        self.settings_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #0D1117;
            }
            QTabBar::tab {
                background-color: #161B22;
                color: #8B949E;
                padding: 12px 24px;
                border: none;
                border-bottom: 2px solid transparent;
                font-size: 13px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background-color: #0D1117;
                color: #F0F6FC;
                border-bottom: 2px solid #C40000;
            }
            QTabBar::tab:hover {
                color: #F0F6FC;
            }
        """)

        # Create tabs
        self.general_tab = self._create_general_tab()
        self.settings_tabs.addTab(self.general_tab, "🌐 General")

        self.obd_tab = self._create_obd_tab()
        self.settings_tabs.addTab(self.obd_tab, "🔌 OBD")

        self.notification_tab = self._create_notification_tab()
        self.settings_tabs.addTab(self.notification_tab, "🔔 Notifications")

        self.ai_tab = self._create_ai_tab()
        self.settings_tabs.addTab(self.ai_tab, "🤖 AI")

        main_layout.addWidget(self.settings_tabs)

        # ==================== ACTION BUTTONS ====================
        footer = QFrame()
        footer.setStyleSheet("background-color: #161B22; border-top: 1px solid #30363D;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 15, 20, 15)
        footer_layout.setSpacing(12)

        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.setStyleSheet(self._get_button_style('secondary'))
        self.reset_btn.clicked.connect(self._reset_defaults)
        footer_layout.addWidget(self.reset_btn)

        footer_layout.addStretch()

        self.save_btn = QPushButton("💾 Save Settings")
        self.save_btn.setStyleSheet(self._get_button_style('primary'))
        self.save_btn.clicked.connect(self._save_all_settings)
        footer_layout.addWidget(self.save_btn)

        main_layout.addWidget(footer)

    def _create_general_tab(self) -> QWidget:
        """Create General settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(25)

        # Language
        lang_card = self._create_card("🌍 Language & Region", "#0DCAF0")
        lang_content = QVBoxLayout(lang_card)
        lang_content.setSpacing(15)

        lang_row = QHBoxLayout()
        lang_label = QLabel("Language:")
        lang_label.setStyleSheet("color: #E0E0E0; font-size: 13px;")
        self.language_combo = QComboBox()
        self.language_combo.addItems(["English", "Arabic", "Spanish", "French", "German"])
        self.language_combo.setStyleSheet(self._get_combo_style())
        lang_row.addWidget(lang_label)
        lang_row.addWidget(self.language_combo, 1)
        lang_content.addLayout(lang_row)

        # Units
        units_row = QHBoxLayout()
        units_label = QLabel("Units:")
        units_label.setStyleSheet("color: #E0E0E0; font-size: 13px;")
        self.units_combo = QComboBox()
        self.units_combo.addItems(["Metric (km, °C, L)", "Imperial (mi, °F, gal)"])
        self.units_combo.setStyleSheet(self._get_combo_style())
        units_row.addWidget(units_label)
        units_row.addWidget(self.units_combo, 1)
        lang_content.addLayout(units_row)

        layout.addWidget(lang_card)

        # Connection
        conn_card = self._create_card("🔗 Connection Settings", "#4CAF50")
        conn_content = QVBoxLayout(conn_card)
        conn_content.setSpacing(15)

        self.auto_connect = QCheckBox("Auto-connect to last vehicle on startup")
        self.auto_connect.setStyleSheet(self._get_checkbox_style())
        conn_content.addWidget(self.auto_connect)

        self.reconnect_on_disconnect = QCheckBox("Automatically reconnect if connection lost")
        self.reconnect_on_disconnect.setStyleSheet(self._get_checkbox_style())
        conn_content.addWidget(self.reconnect_on_disconnect)

        conn_timeout_row = QHBoxLayout()
        conn_timeout_label = QLabel("Connection Timeout (seconds):")
        conn_timeout_label.setStyleSheet("color: #E0E0E0; font-size: 13px;")
        self.conn_timeout = QSpinBox()
        self.conn_timeout.setMinimum(5)
        self.conn_timeout.setMaximum(60)
        self.conn_timeout.setValue(15)
        self.conn_timeout.setStyleSheet(self._get_spinbox_style())
        conn_timeout_row.addWidget(conn_timeout_label)
        conn_timeout_row.addWidget(self.conn_timeout, 1)
        conn_timeout_row.addStretch()
        conn_content.addLayout(conn_timeout_row)

        layout.addWidget(conn_card)

        # Data
        data_card = self._create_card("💾 Data Settings", "#FFC107")
        data_content = QVBoxLayout(data_card)
        data_content.setSpacing(15)

        data_retention_row = QHBoxLayout()
        data_retention_label = QLabel("Data Retention (days):")
        data_retention_label.setStyleSheet("color: #E0E0E0; font-size: 13px;")
        self.data_retention = QSpinBox()
        self.data_retention.setMinimum(7)
        self.data_retention.setMaximum(365)
        self.data_retention.setValue(90)
        self.data_retention.setSuffix(" days")
        self.data_retention.setStyleSheet(self._get_spinbox_style())
        data_retention_row.addWidget(data_retention_label)
        data_retention_row.addWidget(self.data_retention, 1)
        data_retention_row.addStretch()
        data_content.addLayout(data_retention_row)

        self.auto_backup = QCheckBox("Enable automatic data backup")
        self.auto_backup.setStyleSheet(self._get_checkbox_style())
        data_content.addWidget(self.auto_backup)

        layout.addWidget(data_card)

        layout.addStretch()
        return widget

    def _create_obd_tab(self) -> QWidget:
        """Create OBD settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(25)

        # Connection
        conn_card = self._create_card("🔌 OBD Connection", "#0DCAF0")
        conn_content = QVBoxLayout(conn_card)
        conn_content.setSpacing(15)

        port_row = QHBoxLayout()
        port_label = QLabel("Serial Port:")
        port_label.setStyleSheet("color: #E0E0E0; font-size: 13px;")
        self.obd_port = QLineEdit()
        self.obd_port.setPlaceholderText("e.g., COM3, /dev/ttyUSB0")
        self.obd_port.setStyleSheet(self._get_lineedit_style())
        port_row.addWidget(port_label)
        port_row.addWidget(self.obd_port, 1)
        conn_content.addLayout(port_row)

        baud_row = QHBoxLayout()
        baud_label = QLabel("Baud Rate:")
        baud_label.setStyleSheet("color: #E0E0E0; font-size: 13px;")
        self.baud_rate = QComboBox()
        self.baud_rate.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baud_rate.setCurrentText("38400")
        self.baud_rate.setStyleSheet(self._get_combo_style())
        baud_row.addWidget(baud_label)
        baud_row.addWidget(self.baud_rate, 1)
        conn_content.addLayout(baud_row)

        protocol_row = QHBoxLayout()
        protocol_label = QLabel("Protocol:")
        protocol_label.setStyleSheet("color: #E0E0E0; font-size: 13px;")
        self.protocol = QComboBox()
        self.protocol.addItems(["Auto", "ISO 15765-4 CAN", "ISO 14230-4 KWP", "ISO 9141-2", "J1850 PWM", "J1850 VPW"])
        self.protocol.setCurrentText("Auto")
        self.protocol.setStyleSheet(self._get_combo_style())
        protocol_row.addWidget(protocol_label)
        protocol_row.addWidget(self.protocol, 1)
        conn_content.addLayout(protocol_row)

        layout.addWidget(conn_card)

        # Data Collection
        data_card = self._create_card("📊 Data Collection", "#4CAF50")
        data_content = QVBoxLayout(data_card)
        data_content.setSpacing(15)

        polling_row = QHBoxLayout()
        polling_label = QLabel("Polling Interval (ms):")
        polling_label.setStyleSheet("color: #E0E0E0; font-size: 13px;")
        self.polling_interval = QSpinBox()
        self.polling_interval.setMinimum(100)
        self.polling_interval.setMaximum(5000)
        self.polling_interval.setValue(1000)
        self.polling_interval.setSuffix(" ms")
        self.polling_interval.setStyleSheet(self._get_spinbox_style())
        polling_row.addWidget(polling_label)
        polling_row.addWidget(self.polling_interval, 1)
        polling_row.addStretch()
        data_content.addLayout(polling_row)

        self.log_all_pids = QCheckBox("Log all available PIDs")
        self.log_all_pids.setStyleSheet(self._get_checkbox_style())
        data_content.addWidget(self.log_all_pids)

        self.enable_fast_init = QCheckBox("Enable fast initialization")
        self.enable_fast_init.setStyleSheet(self._get_checkbox_style())
        data_content.addWidget(self.enable_fast_init)

        layout.addWidget(data_card)

        layout.addStretch()
        return widget

    def _create_notification_tab(self) -> QWidget:
        """Create Notification settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(25)

        # In-App
        app_card = self._create_card("💻 In-App Notifications", "#0DCAF0")
        app_content = QVBoxLayout(app_card)
        app_content.setSpacing(15)

        self.enable_app_notifications = QCheckBox("Enable in-app notifications")
        self.enable_app_notifications.setChecked(True)
        self.enable_app_notifications.setStyleSheet(self._get_checkbox_style())
        app_content.addWidget(self.enable_app_notifications)

        self.show_notifications_on_screen = QCheckBox("Show notifications on screen")
        self.show_notifications_on_screen.setChecked(True)
        self.show_notifications_on_screen.setStyleSheet(self._get_checkbox_style())
        app_content.addWidget(self.show_notifications_on_screen)

        self.play_sound_on_alert = QCheckBox("Play sound on critical alerts")
        self.play_sound_on_alert.setChecked(True)
        self.play_sound_on_alert.setStyleSheet(self._get_checkbox_style())
        app_content.addWidget(self.play_sound_on_alert)

        layout.addWidget(app_card)

        # Email
        email_card = self._create_card("📧 Email Notifications", "#4CAF50")
        email_content = QVBoxLayout(email_card)
        email_content.setSpacing(15)

        self.enable_email = QCheckBox("Enable email notifications")
        self.enable_email.setStyleSheet(self._get_checkbox_style())
        email_content.addWidget(self.enable_email)

        email_row = QHBoxLayout()
        email_label = QLabel("Email Address:")
        email_label.setStyleSheet("color: #E0E0E0; font-size: 13px;")
        self.email_address = QLineEdit()
        self.email_address.setPlaceholderText("your@email.com")
        self.email_address.setStyleSheet(self._get_lineedit_style())
        email_row.addWidget(email_label)
        email_row.addWidget(self.email_address, 1)
        email_content.addLayout(email_row)

        # Email preferences
        email_prefs = QLabel("Notify me for:")
        email_prefs.setStyleSheet("color: #E0E0E0; font-size: 13px; font-weight: 600;")
        email_content.addWidget(email_prefs)

        self.email_critical = QCheckBox("Critical alerts only")
        self.email_critical.setChecked(True)
        self.email_critical.setStyleSheet(self._get_checkbox_style())
        email_content.addWidget(self.email_critical)

        self.email_all = QCheckBox("All alerts and predictions")
        self.email_all.setStyleSheet(self._get_checkbox_style())
        email_content.addWidget(self.email_all)

        layout.addWidget(email_card)

        # SMS
        sms_card = self._create_card("📱 SMS Notifications", "#FFC107")
        sms_content = QVBoxLayout(sms_card)
        sms_content.setSpacing(15)

        self.enable_sms = QCheckBox("Enable SMS notifications")
        self.enable_sms.setStyleSheet(self._get_checkbox_style())
        sms_content.addWidget(self.enable_sms)

        sms_row = QHBoxLayout()
        sms_label = QLabel("Phone Number:")
        sms_label.setStyleSheet("color: #E0E0E0; font-size: 13px;")
        self.sms_number = QLineEdit()
        self.sms_number.setPlaceholderText("+1234567890")
        self.sms_number.setStyleSheet(self._get_lineedit_style())
        sms_row.addWidget(sms_label)
        sms_row.addWidget(self.sms_number, 1)
        sms_content.addLayout(sms_row)

        self.sms_critical_only = QCheckBox("SMS for critical alerts only")
        self.sms_critical_only.setChecked(True)
        self.sms_critical_only.setStyleSheet(self._get_checkbox_style())
        sms_content.addWidget(self.sms_critical_only)

        layout.addWidget(sms_card)

        # Push
        push_card = self._create_card("🔔 Push Notifications", "#FFC107")
        push_content = QVBoxLayout(push_card)
        push_content.setSpacing(15)

        self.enable_push = QCheckBox("Enable push notifications")
        self.enable_push.setStyleSheet(self._get_checkbox_style())
        push_content.addWidget(self.enable_push)

        self.push_background = QCheckBox("Receive notifications when app is in background")
        self.push_background.setStyleSheet(self._get_checkbox_style())
        push_content.addWidget(self.push_background)

        layout.addWidget(push_card)

        layout.addStretch()
        return widget

    def _create_ai_tab(self) -> QWidget:
        """Create AI settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(25)

        # AI Behavior Card
        behavior_card = self._create_card("🎯 AI Behavior Mode", "#0DCAF0")
        behavior_content = QVBoxLayout(behavior_card)
        behavior_content.setSpacing(12)

        behavior_help = QLabel(
            "Choose how sensitive the AI should be when making predictions:"
        )
        behavior_help.setWordWrap(True)
        behavior_help.setStyleSheet(self._get_help_text_style())
        behavior_content.addWidget(behavior_help)

        # Radio buttons
        self.behavior_group_buttons = QButtonGroup(self)

        self.conservative_radio = QRadioButton("Conservative - High confidence only (70%+)")
        self.balanced_radio = QRadioButton("Balanced - Standard sensitivity (50%+) [Recommended]")
        self.early_warning_radio = QRadioButton("Early Warning - More sensitive (30%+)")
        self.balanced_radio.setChecked(True)

        for radio in [self.conservative_radio, self.balanced_radio, self.early_warning_radio]:
            radio.setStyleSheet(self._get_radio_style())
            self.behavior_group_buttons.addButton(radio)
            behavior_content.addWidget(radio)

        layout.addWidget(behavior_card)

        # Learning Scope Card
        scope_card = self._create_card("📚 Learning Scope", "#4CAF50")
        scope_content = QVBoxLayout(scope_card)
        scope_content.setSpacing(12)

        scope_help = QLabel(
            "Choose how the AI learns from vehicle data:"
        )
        scope_help.setWordWrap(True)
        scope_help.setStyleSheet(self._get_help_text_style())
        scope_content.addWidget(scope_help)

        self.scope_group_buttons = QButtonGroup(self)

        self.vehicle_only_radio = QRadioButton("Vehicle Only - Personalized learning")
        self.fleet_assisted_radio = QRadioButton("Fleet Assisted - Learn from similar vehicles [Recommended]")
        self.fleet_assisted_radio.setChecked(True)

        for radio in [self.vehicle_only_radio, self.fleet_assisted_radio]:
            radio.setStyleSheet(self._get_radio_style())
            self.scope_group_buttons.addButton(radio)
            scope_content.addWidget(radio)

        layout.addWidget(scope_card)

        # Advanced Settings Card
        advanced_card = self._create_card("🔬 Advanced Settings", "#FFC107")
        advanced_content = QVBoxLayout(advanced_card)
        advanced_content.setSpacing(15)

        # Confidence Threshold
        threshold_row = QVBoxLayout()
        threshold_label = QLabel("Prediction Confidence Threshold")
        threshold_label.setStyleSheet("color: #E0E0E0; font-size: 13px; font-weight: 600;")
        threshold_row.addWidget(threshold_label)

        threshold_slider_row = QHBoxLayout()
        self.confidence_threshold = QSlider(Qt.Horizontal)
        self.confidence_threshold.setMinimum(10)
        self.confidence_threshold.setMaximum(90)
        self.confidence_threshold.setValue(50)
        self.confidence_threshold.setTickPosition(QSlider.TicksBelow)
        self.confidence_threshold.setTickInterval(10)
        self.confidence_threshold.setStyleSheet(self._get_slider_style())

        self.confidence_value_label = QLabel("50%")
        self.confidence_value_label.setStyleSheet("font-weight: bold; color: #0DCAF0; font-size: 14px;")
        self.confidence_value_label.setFixedWidth(40)

        self.confidence_threshold.valueChanged.connect(
            lambda val: self.confidence_value_label.setText(f"{val}%")
        )

        threshold_slider_row.addWidget(self.confidence_threshold, 1)
        threshold_slider_row.addWidget(self.confidence_value_label)
        threshold_row.addLayout(threshold_slider_row)
        advanced_content.addLayout(threshold_row)

        # Baseline Days
        baseline_row = QHBoxLayout()
        baseline_label = QLabel("Minimum Baseline Days:")
        baseline_label.setStyleSheet("color: #E0E0E0; font-size: 13px;")
        self.baseline_days = QSpinBox()
        self.baseline_days.setMinimum(1)
        self.baseline_days.setMaximum(30)
        self.baseline_days.setValue(7)
        self.baseline_days.setSuffix(" days")
        self.baseline_days.setStyleSheet(self._get_spinbox_style())
        baseline_row.addWidget(baseline_label)
        baseline_row.addWidget(self.baseline_days, 1)
        baseline_row.addStretch()
        advanced_content.addLayout(baseline_row)

        # Shadow Mode
        self.shadow_mode = QCheckBox("Enable Shadow Evaluation Mode")
        self.shadow_mode.setStyleSheet(self._get_checkbox_style())
        self.shadow_mode.setToolTip("AI predicts without alerting until accuracy is verified")
        advanced_content.addWidget(self.shadow_mode)

        layout.addWidget(advanced_card)

        # PDF History Card
        pdf_card = self._create_card("📄 Recent PDF Reports", "#FFC107")
        pdf_content = QVBoxLayout(pdf_card)
        pdf_content.setSpacing(10)

        self.pdf_history_table = QTableWidget()
        self.pdf_history_table.setColumnCount(4)
        self.pdf_history_table.setHorizontalHeaderLabels(["Profile", "Type", "Status", "Date"])
        self.pdf_history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.pdf_history_table.setMaximumHeight(150)
        self.pdf_history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.pdf_history_table.setStyleSheet(self._get_table_style())
        pdf_content.addWidget(self.pdf_history_table)

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setStyleSheet(self._get_button_style('secondary'))
        refresh_btn.clicked.connect(self._load_pdf_history)
        pdf_content.addWidget(refresh_btn)

        layout.addWidget(pdf_card)

        layout.addStretch()
        return widget

    def _create_card(self, title: str, color: str) -> QFrame:
        """Create a consistent card/frame for settings sections"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #161B22;
                border: 1px solid {color};
                border-radius: 12px;
                padding: 20px;
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Card title
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title_label.setStyleSheet(f"color: {color};")
        layout.addWidget(title_label)

        return card

    def _add_divider(self, layout: QVBoxLayout):
        """Add a visual divider line"""
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #30363D;")
        layout.addWidget(divider)

    def _get_help_text_style(self) -> str:
        """Get consistent help text style"""
        return """
            color: #8B949E;
            font-size: 12px;
            padding: 12px;
            background-color: #21262D;
            border-radius: 6px;
        """

    def _get_radio_style(self) -> str:
        """Get consistent radio button style"""
        return """
            QRadioButton {
                color: #F0F6FC;
                font-size: 13px;
                spacing: 10px;
                padding: 6px 0;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
            }
            QRadioButton::indicator:unchecked {
                border: 2px solid #484F58;
                border-radius: 9px;
                background: #161B22;
            }
            QRadioButton::indicator:checked {
                border: 2px solid #C40000;
                border-radius: 9px;
                background: #C40000;
            }
        """

    def _get_slider_style(self) -> str:
        """Get slider style"""
        return """
            QSlider::groove:horizontal {
                height: 6px;
                background: #30363D;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #C40000;
                border: none;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QSlider::sub-page:horizontal {
                background: #C40000;
                border-radius: 3px;
            }
        """

    def _get_spinbox_style(self) -> str:
        """Get spinbox style"""
        return """
            QSpinBox {
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }
            QSpinBox:focus {
                border: 1px solid #C40000;
            }
        """

    def _get_checkbox_style(self) -> str:
        """Get checkbox style"""
        return """
            QCheckBox {
                color: #F0F6FC;
                font-size: 13px;
                spacing: 10px;
                padding: 6px 0;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #484F58;
                border-radius: 4px;
                background: #161B22;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #C40000;
                border-radius: 4px;
                background: #C40000;
            }
        """

    def _get_table_style(self) -> str:
        """Get table style"""
        return """
            QTableWidget {
                background-color: #21262D;
                color: #F0F6FC;
                border: none;
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
            QHeaderView::section {
                background-color: #0D1117;
                color: #F0F6FC;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #C40000;
                font-weight: 600;
                font-size: 12px;
            }
        """

    def _get_button_style(self, style_type: str = 'primary') -> str:
        """Get consistent button stylesheet"""
        styles = {
            'primary': """
                QPushButton {
                    background-color: #C40000;
                    color: #FFFFFF;
                    border: none;
                    padding: 12px 28px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #E53935;
                }
                QPushButton:pressed {
                    background-color: #A00000;
                }
            """,
            'secondary': """
                QPushButton {
                    background-color: #21262D;
                    color: #F0F6FC;
                    border: 1px solid #30363D;
                    padding: 12px 24px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #30363D;
                    border-color: #8B949E;
                }
            """
        }
        return styles.get(style_type, styles['primary'])

    def _get_combo_style(self) -> str:
        """Get combobox style"""
        return """
            QComboBox {
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QComboBox:focus {
                border: 1px solid #C40000;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border: 4px solid transparent;
                border-top: 6px solid #8B949E;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                selection-background-color: #C40000;
                selection-color: #FFFFFF;
            }
        """

    def _get_lineedit_style(self) -> str:
        """Get lineedit style"""
        return """
            QLineEdit {
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #C40000;
            }
            QLineEdit:placeholder {
                color: #8B949E;
            }
        """

    def _get_current_settings(self) -> Dict[str, Any]:
        """Get all current settings as dictionary"""
        return {
            "general": self._get_general_settings(),
            "obd": self._get_obd_settings(),
            "notifications": self._get_notification_settings(),
            "ai": self._get_ai_settings()
        }

    def _get_general_settings(self) -> Dict[str, Any]:
        """Get general settings"""
        return {
            "language": self.language_combo.currentText(),
            "units": self.units_combo.currentText(),
            "auto_connect": self.auto_connect.isChecked(),
            "reconnect_on_disconnect": self.reconnect_on_disconnect.isChecked(),
            "connection_timeout": self.conn_timeout.value(),
            "data_retention_days": self.data_retention.value(),
            "auto_backup": self.auto_backup.isChecked()
        }

    def _get_obd_settings(self) -> Dict[str, Any]:
        """Get OBD settings"""
        return {
            "port": self.obd_port.text(),
            "baud_rate": int(self.baud_rate.currentText()),
            "protocol": self.protocol.currentText(),
            "polling_interval_ms": self.polling_interval.value(),
            "log_all_pids": self.log_all_pids.isChecked(),
            "enable_fast_init": self.enable_fast_init.isChecked()
        }

    def _get_notification_settings(self) -> Dict[str, Any]:
        """Get notification settings"""
        return {
            "in_app": {
                "enabled": self.enable_app_notifications.isChecked(),
                "show_on_screen": self.show_notifications_on_screen.isChecked(),
                "play_sound": self.play_sound_on_alert.isChecked()
            },
            "email": {
                "enabled": self.enable_email.isChecked(),
                "address": self.email_address.text(),
                "critical_only": self.email_critical.isChecked(),
                "all_alerts": self.email_all.isChecked()
            },
            "sms": {
                "enabled": self.enable_sms.isChecked(),
                "phone": self.sms_number.text(),
                "critical_only": self.sms_critical_only.isChecked()
            },
            "push": {
                "enabled": self.enable_push.isChecked(),
                "background": self.push_background.isChecked()
            }
        }

    def _get_ai_settings(self) -> Dict[str, Any]:
        """Get AI settings"""
        if self.conservative_radio.isChecked():
            behavior_mode = "conservative"
        elif self.balanced_radio.isChecked():
            behavior_mode = "balanced"
        else:
            behavior_mode = "early_warning"

        learning_scope = "fleet_assisted" if self.fleet_assisted_radio.isChecked() else "vehicle_only"

        return {
            "ai_behavior_mode": behavior_mode,
            "learning_scope": learning_scope,
            "confidence_threshold": self.confidence_threshold.value(),
            "minimum_baseline_days": self.baseline_days.value(),
            "shadow_evaluation_mode": self.shadow_mode.isChecked()
        }

    def _save_all_settings(self):
        """Save all settings to files and emit signal"""
        settings = self._get_current_settings()
        
        # Save main settings
        self._save_general_settings(settings["general"])
        self._save_obd_settings(settings["obd"])
        self._save_notification_settings(settings["notifications"])
        self._save_ai_settings(settings["ai"])

        self.settings_saved.emit(settings)
        QMessageBox.information(self, "Settings Saved", "All settings saved successfully!")

    def _save_general_settings(self, settings: Dict[str, Any]):
        """Save general settings to file"""
        os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
        
        # Load existing settings and update general section
        existing = {}
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    existing = json.load(f)
            except:
                pass
        
        existing["general"] = settings
        
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(existing, f, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save general settings:\n{e}")

    def _save_obd_settings(self, settings: Dict[str, Any]):
        """Save OBD settings to file"""
        os.makedirs(os.path.dirname(self.obd_settings_file), exist_ok=True)
        
        try:
            with open(self.obd_settings_file, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save OBD settings:\n{e}")

    def _save_notification_settings(self, settings: Dict[str, Any]):
        """Save notification settings to file"""
        os.makedirs(os.path.dirname(self.notification_settings_file), exist_ok=True)
        
        try:
            with open(self.notification_settings_file, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save notification settings:\n{e}")

    def _save_ai_settings(self, settings: Dict[str, Any]):
        """Save AI settings to file"""
        ai_settings_file = "./data/ai_settings.json"
        os.makedirs(os.path.dirname(ai_settings_file), exist_ok=True)
        
        try:
            with open(ai_settings_file, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save AI settings:\n{e}")

    def _load_all_settings(self):
        """Load all settings from files"""
        self._load_general_settings()
        self._load_obd_settings()
        self._load_notification_settings()
        self._load_ai_settings()
        self._load_pdf_history()

    def _load_general_settings(self):
        """Load general settings from file"""
        if not os.path.exists(self.settings_file):
            return

        try:
            with open(self.settings_file, 'r') as f:
                settings = json.load(f)
            
            general = settings.get("general", {})
            
            language = general.get("language", "English")
            index = self.language_combo.findText(language)
            if index >= 0:
                self.language_combo.setCurrentIndex(index)
            
            units = general.get("units", "Metric (km, °C, L)")
            index = self.units_combo.findText(units)
            if index >= 0:
                self.units_combo.setCurrentIndex(index)
            
            self.auto_connect.setChecked(general.get("auto_connect", False))
            self.reconnect_on_disconnect.setChecked(general.get("reconnect_on_disconnect", False))
            self.conn_timeout.setValue(general.get("connection_timeout", 15))
            self.data_retention.setValue(general.get("data_retention_days", 90))
            self.auto_backup.setChecked(general.get("auto_backup", False))
            
        except Exception as e:
            print(f"Failed to load general settings: {e}")

    def _load_obd_settings(self):
        """Load OBD settings from file"""
        if not os.path.exists(self.obd_settings_file):
            return

        try:
            with open(self.obd_settings_file, 'r') as f:
                settings = json.load(f)
            
            self.obd_port.setText(settings.get("port", ""))
            
            baud = str(settings.get("baud_rate", 38400))
            index = self.baud_rate.findText(baud)
            if index >= 0:
                self.baud_rate.setCurrentIndex(index)
            
            protocol = settings.get("protocol", "Auto")
            index = self.protocol.findText(protocol)
            if index >= 0:
                self.protocol.setCurrentIndex(index)
            
            self.polling_interval.setValue(settings.get("polling_interval_ms", 1000))
            self.log_all_pids.setChecked(settings.get("log_all_pids", False))
            self.enable_fast_init.setChecked(settings.get("enable_fast_init", False))
            
        except Exception as e:
            print(f"Failed to load OBD settings: {e}")

    def _load_notification_settings(self):
        """Load notification settings from file"""
        if not os.path.exists(self.notification_settings_file):
            return

        try:
            with open(self.notification_settings_file, 'r') as f:
                settings = json.load(f)
            
            # In-app
            in_app = settings.get("in_app", {})
            self.enable_app_notifications.setChecked(in_app.get("enabled", True))
            self.show_notifications_on_screen.setChecked(in_app.get("show_on_screen", True))
            self.play_sound_on_alert.setChecked(in_app.get("play_sound", True))
            
            # Email
            email = settings.get("email", {})
            self.enable_email.setChecked(email.get("enabled", False))
            self.email_address.setText(email.get("address", ""))
            self.email_critical.setChecked(email.get("critical_only", True))
            self.email_all.setChecked(email.get("all_alerts", False))
            
            # SMS
            sms = settings.get("sms", {})
            self.enable_sms.setChecked(sms.get("enabled", False))
            self.sms_number.setText(sms.get("phone", ""))
            self.sms_critical_only.setChecked(sms.get("critical_only", True))
            
            # Push
            push = settings.get("push", {})
            self.enable_push.setChecked(push.get("enabled", False))
            self.push_background.setChecked(push.get("background", False))
            
        except Exception as e:
            print(f"Failed to load notification settings: {e}")

    def _load_ai_settings(self):
        """Load AI settings from file"""
        ai_settings_file = "./data/ai_settings.json"
        if not os.path.exists(ai_settings_file):
            return

        try:
            with open(ai_settings_file, 'r') as f:
                settings = json.load(f)

            behavior_mode = settings.get("ai_behavior_mode", "balanced")
            if behavior_mode == "conservative":
                self.conservative_radio.setChecked(True)
            elif behavior_mode == "balanced":
                self.balanced_radio.setChecked(True)
            else:
                self.early_warning_radio.setChecked(True)

            learning_scope = settings.get("learning_scope", "fleet_assisted")
            if learning_scope == "vehicle_only":
                self.vehicle_only_radio.setChecked(True)
            else:
                self.fleet_assisted_radio.setChecked(True)

            self.confidence_threshold.setValue(settings.get("confidence_threshold", 50))
            self.baseline_days.setValue(settings.get("minimum_baseline_days", 7))
            self.shadow_mode.setChecked(settings.get("shadow_evaluation_mode", False))

        except Exception as e:
            print(f"Failed to load AI settings: {e}")

    def _reset_defaults(self):
        """Reset all settings to defaults"""
        reply = QMessageBox.question(
            self, "Reset Settings",
            "Reset all settings to defaults?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Reset General
            self.language_combo.setCurrentText("English")
            self.units_combo.setCurrentText("Metric (km, °C, L)")
            self.auto_connect.setChecked(False)
            self.reconnect_on_disconnect.setChecked(False)
            self.conn_timeout.setValue(15)
            self.data_retention.setValue(90)
            self.auto_backup.setChecked(False)
            
            # Reset OBD
            self.obd_port.setText("")
            self.baud_rate.setCurrentText("38400")
            self.protocol.setCurrentText("Auto")
            self.polling_interval.setValue(1000)
            self.log_all_pids.setChecked(False)
            self.enable_fast_init.setChecked(False)
            
            # Reset Notifications
            self.enable_app_notifications.setChecked(True)
            self.show_notifications_on_screen.setChecked(True)
            self.play_sound_on_alert.setChecked(True)
            self.enable_email.setChecked(False)
            self.email_address.setText("")
            self.email_critical.setChecked(True)
            self.email_all.setChecked(False)
            self.enable_sms.setChecked(False)
            self.sms_number.setText("")
            self.sms_critical_only.setChecked(True)
            self.enable_push.setChecked(False)
            self.push_background.setChecked(False)
            
            # Reset AI
            self.balanced_radio.setChecked(True)
            self.fleet_assisted_radio.setChecked(True)
            self.confidence_threshold.setValue(50)
            self.baseline_days.setValue(7)
            self.shadow_mode.setChecked(False)

            QMessageBox.information(self, "Reset Complete", "Settings reset to defaults.")

    def get_settings(self) -> Dict[str, Any]:
        """Get current settings (public API)"""
        return self._get_current_settings()

    def _on_theme_changed(self, theme: str):
        """Handle theme change"""
        self.theme_changed.emit(theme.lower())

    def _load_pdf_history(self):
        """Load PDF generation history from queue file"""
        pdf_queue_file = str(CONFIG.DATA_DIR / "pdf_queue.json")

        try:
            if not os.path.exists(pdf_queue_file):
                self.pdf_history_table.setRowCount(0)
                return

            with open(pdf_queue_file, 'r') as f:
                queue_data = json.load(f)

            all_requests = []

            for req in queue_data.get("pending", []):
                all_requests.append({
                    "profile": req.get("profile_name", "Unknown"),
                    "type": req.get("report_type", ""),
                    "status": "⏳ Pending",
                    "date": req.get("created_at", "")[:16] if req.get("created_at") else ""
                })

            for req_id, req in queue_data.get("completed", {}).items():
                status = "✅ Complete" if req.get("status") == "completed" else "❌ Failed"
                all_requests.append({
                    "profile": req.get("profile_name", "Unknown"),
                    "type": req.get("report_type", ""),
                    "status": status,
                    "date": req.get("completed_at", req.get("created_at", ""))[:16]
                })

            all_requests.sort(key=lambda x: x.get("date", ""), reverse=True)
            all_requests = all_requests[:10]

            self.pdf_history_table.setRowCount(len(all_requests))
            for row, req in enumerate(all_requests):
                self.pdf_history_table.setItem(row, 0, QTableWidgetItem(req["profile"]))
                self.pdf_history_table.setItem(row, 1, QTableWidgetItem(req["type"].replace("_", " ").title()))
                self.pdf_history_table.setItem(row, 2, QTableWidgetItem(req["status"]))
                self.pdf_history_table.setItem(row, 3, QTableWidgetItem(req["date"].replace("T", " ")))

        except Exception as e:
            print(f"Failed to load PDF history: {e}")
