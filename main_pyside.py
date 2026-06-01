"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Main Desktop Application Entry Point

Main PySide Application with Enhanced UI and Full Integration
Features:
- Professional dark theme with modern design
- Enhanced circular and linear gauges
- Full AI integration (UnifiedAIModule + PredictiveFailureEngine)
- Real-time vehicle monitoring
- Comprehensive failure prediction
- Secure data handling
"""

from __future__ import annotations  # PEP 563: Postponed evaluation of annotations

import sys
import os

# CRITICAL: Ensure desktop modules take priority over server modules
# This prevents the server's data_export.py from being imported instead of desktop's
_desktop_path = os.path.dirname(os.path.abspath(__file__))
if _desktop_path not in sys.path:
    sys.path.insert(0, _desktop_path)

# Configure UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'ignore')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'ignore')

# TensorFlow is now loaded lazily when first needed by AI modules
# This improves startup time significantly (TensorFlow import takes 2-5 seconds)
# Individual AI model modules (attention_lstm_model.py, cnn_lstm_model.py, etc.)
# handle their own TensorFlow imports when they're actually used
TENSORFLOW_PRELOADED = False  # Will be set True by modules that need it
_tensorflow_module = None

def get_tensorflow():
    """Lazy load TensorFlow only when actually needed"""
    global _tensorflow_module, TENSORFLOW_PRELOADED
    if _tensorflow_module is None:
        try:
            import tensorflow as tf
            _tensorflow_module = tf
            TENSORFLOW_PRELOADED = True
            print(f"TensorFlow {tf.__version__} loaded on demand")
        except ImportError:
            print("TensorFlow not installed - LSTM predictions will use fallback heuristics")
        except Exception as e:
            print(f"TensorFlow initialization issue: {e}")
    return _tensorflow_module

import json
import time
import csv
import math
import hashlib
import logging
import re
from datetime import datetime, timedelta
from typing import Callable, Optional, Dict, Any, List, Tuple
from pathlib import Path
import asyncio
from collections import deque
from enum import Enum

# Import centralized configuration
try:
    from config import get_config
    CONFIG = get_config()
except ImportError:
    CONFIG = None

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QSplitter,
    QPlainTextEdit, QComboBox, QGroupBox, QGridLayout, QHeaderView,
    QMessageBox, QDialog, QFormLayout, QLineEdit, QSpinBox, QProgressBar,
    QFileDialog, QInputDialog, QListWidget, QListWidgetItem, QCheckBox,
    QSlider, QToolButton, QMenu, QSizePolicy, QScrollArea, QTextEdit,
    QFrame, QGraphicsDropShadowEffect, QStackedWidget, QStatusBar, QSplashScreen
)
from PySide6.QtCore import (
    Qt, QTimer, QThread, Signal, QPropertyAnimation, QEasingCurve,
    QRect, QPoint, QSize, Property, QParallelAnimationGroup, QEventLoop
)
from PySide6.QtGui import (
    QIcon, QFont, QColor, QPalette, QPainter, QLinearGradient, QPen,
    QBrush, QCursor, QRadialGradient, QPainterPath, QConicalGradient, QPixmap, QAction
)

# Global app variable - will be created in main()
app = None

# Import version early (no Qt dependency)
from version import APP_VERSION

# Flags for optional modules - will be set during import_modules()
DATA_MANAGEMENT_TAB_AVAILABLE = False
DEVICES_TAB_AVAILABLE = False
NOTIFICATIONS_TAB_AVAILABLE = False
USER_MANAGEMENT_TAB_AVAILABLE = False
MOBILE_SERVER_AVAILABLE = False

# Phase 2 tab availability flags
FUEL_TRACKING_TAB_AVAILABLE = False
DRIVING_SCORE_TAB_AVAILABLE = False
GEOFENCING_TAB_AVAILABLE = False
ESP32_SENSORS_TAB_AVAILABLE = False
MAINTENANCE_REMINDERS_TAB_AVAILABLE = False
RECALL_ALERTS_TAB_AVAILABLE = False

# Phase 4 & 5 tab availability flags
ANALYTICS_TAB_AVAILABLE = False
HELP_TAB_AVAILABLE = False


class PredictSplashScreen(QSplashScreen):
    """
    Professional splash screen with progress indicator.
    Shows loading status during application startup.
    """

    def __init__(self):
        # Create a pixmap for the splash screen
        pixmap = QPixmap(500, 300)
        pixmap.fill(QColor("#1A1A2E"))

        super().__init__(pixmap)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)

        self._progress = 0
        self._status_text = "Starting PREDICT..."
        self._draw_splash()

    def _draw_splash(self):
        """Draw the splash screen content"""
        pixmap = QPixmap(500, 300)
        pixmap.fill(QColor("#1A1A2E"))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw gradient background
        gradient = QLinearGradient(0, 0, 0, 300)
        gradient.setColorAt(0, QColor("#1A1A2E"))
        gradient.setColorAt(1, QColor("#0D0D1A"))
        painter.fillRect(0, 0, 500, 300, gradient)

        # Draw border
        painter.setPen(QPen(QColor("#D4AF37"), 2))
        painter.drawRect(1, 1, 497, 297)

        # Draw title
        title_font = QFont("Segoe UI", 32, QFont.Bold)
        painter.setFont(title_font)
        painter.setPen(QColor("#D4AF37"))
        painter.drawText(0, 60, 500, 50, Qt.AlignCenter, "PREDICT")

        # Draw subtitle
        subtitle_font = QFont("Segoe UI", 12)
        painter.setFont(subtitle_font)
        painter.setPen(QColor("#888888"))
        painter.drawText(0, 100, 500, 30, Qt.AlignCenter, "Vehicle Intelligence Platform")

        # Draw version
        version_font = QFont("Segoe UI", 10)
        painter.setFont(version_font)
        painter.setPen(QColor("#666666"))
        painter.drawText(0, 125, 500, 20, Qt.AlignCenter, f"v{APP_VERSION}")

        # Draw progress bar background
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#2A2A3E"))
        painter.drawRoundedRect(50, 200, 400, 10, 5, 5)

        # Draw progress bar fill
        if self._progress > 0:
            progress_gradient = QLinearGradient(50, 0, 450, 0)
            progress_gradient.setColorAt(0, QColor("#D4AF37"))
            progress_gradient.setColorAt(1, QColor("#F0C14B"))
            painter.setBrush(progress_gradient)
            progress_width = int(400 * (self._progress / 100))
            painter.drawRoundedRect(50, 200, progress_width, 10, 5, 5)

        # Draw status text
        status_font = QFont("Segoe UI", 10)
        painter.setFont(status_font)
        painter.setPen(QColor("#AAAAAA"))
        painter.drawText(0, 225, 500, 30, Qt.AlignCenter, self._status_text)

        # Draw copyright
        copyright_font = QFont("Segoe UI", 8)
        painter.setFont(copyright_font)
        painter.setPen(QColor("#555555"))
        painter.drawText(0, 270, 500, 20, Qt.AlignCenter, "© 2026 PREDICT - All Rights Reserved")

        painter.end()
        self.setPixmap(pixmap)

    def set_progress(self, value: int, status: str = None):
        """Update progress bar and status text"""
        self._progress = min(100, max(0, value))
        if status:
            self._status_text = status
        self._draw_splash()
        QApplication.processEvents()


def import_modules():
    """Import all Qt-dependent modules after QApplication is created."""
    global DATA_MANAGEMENT_TAB_AVAILABLE, DEVICES_TAB_AVAILABLE
    global NOTIFICATIONS_TAB_AVAILABLE, USER_MANAGEMENT_TAB_AVAILABLE
    global MOBILE_SERVER_AVAILABLE
    # Phase 2 tab availability flags
    global FUEL_TRACKING_TAB_AVAILABLE, DRIVING_SCORE_TAB_AVAILABLE
    global GEOFENCING_TAB_AVAILABLE, ESP32_SENSORS_TAB_AVAILABLE
    global MAINTENANCE_REMINDERS_TAB_AVAILABLE, RECALL_ALERTS_TAB_AVAILABLE
    # Phase 4 & 5 tab availability flags
    global ANALYTICS_TAB_AVAILABLE, HELP_TAB_AVAILABLE

    # Import modules
    global ConnectionTab, ProfessionalConnectivityManager, VehicleProfileManager
    global UnifiedAIModule, ProfileManager, PDFExporter, CloudSyncManager
    global VINDecoder, PredictiveFailureEngine, ComponentPredictor, DTCManager, DTCTab

    from connection_tab import ConnectionTab
    from connectivity_module import ProfessionalConnectivityManager
    from vehicle_module import VehicleProfileManager
    from unified_ai_module import UnifiedAIModule
    from profile_manager import ProfileManager
    from pdf_exporter import PDFExporter
    from cloud_sync import CloudSyncManager
    from vin_decoder import VINDecoder
    from predictive_failure_engine import PredictiveFailureEngine
    try:
        from component_prediction_models import ComponentPredictor
    except ImportError as e:
        print(f"Note: ComponentPredictor not available: {e}")
        ComponentPredictor = None
    from dtc_module import DTCManager
    from dtc_tab import DTCTab

    # Import LLM Assistant modules
    global get_llm_assistant, StartupScreen, ChatTab, start_llm_api_server
    from llm_assistant import get_llm_assistant
    from startup_screen import StartupScreen
    from chat_tab import ChatTab
    from llm_api_server import start_llm_api_server

    # Import modular tabs
    global AITrainingTab, PIDLearningTab, PIDLearningManager, ReportsTab
    global ServerTab, HistoricalDataManager, BackupManager
    global EnhancedAILearning, AIAutoRetrainingScheduler

    from ai_training_tab import AITrainingTab
    from pid_learning_tab import PIDLearningTab, PIDLearningManager
    from reports_tab import ReportsTab
    from server_tab_v2 import ServerTab
    from historical_data_manager import HistoricalDataManager
    from backup_manager import BackupManager
    from enhanced_ai_learning import EnhancedAILearning
    from ai_auto_retraining import AIAutoRetrainingScheduler

    # Import Info Panel Widget for (!) buttons
    global InfoPanelWidget
    try:
        from info_panel_widget import InfoPanelWidget
    except ImportError as e:
        InfoPanelWidget = None
        print(f"Note: InfoPanelWidget not available: {e}")

    # Import Tier Upgrade Dialog
    global TierUpgradeDialog
    try:
        from tier_upgrade_dialog import TierUpgradeDialog
    except ImportError as e:
        TierUpgradeDialog = None
        print(f"Note: TierUpgradeDialog not available: {e}")

    # Import new tabs
    global DataManagementTab, DevicesTab, NotificationsTab, UserManagementTab
    global FuelTrackingTab, DrivingScoreTab, GeofencingTab, ESP32SensorsTab, MaintenanceRemindersTab, RecallAlertsTab
    global AnalyticsTab, HelpTab

    try:
        from data_management_tab import DataManagementTab
        DATA_MANAGEMENT_TAB_AVAILABLE = True
    except ImportError as e:
        DATA_MANAGEMENT_TAB_AVAILABLE = False
        print(f"Note: Data Management Tab not available: {e}")

    try:
        from devices_tab import DevicesTab
        DEVICES_TAB_AVAILABLE = True
    except ImportError as e:
        DEVICES_TAB_AVAILABLE = False
        print(f"Note: Devices Tab not available: {e}")

    try:
        from notifications_tab import NotificationsTab
        NOTIFICATIONS_TAB_AVAILABLE = True
    except ImportError as e:
        NOTIFICATIONS_TAB_AVAILABLE = False
        print(f"Note: Notifications Tab not available: {e}")

    try:
        from user_management_tab import UserManagementTab
        USER_MANAGEMENT_TAB_AVAILABLE = True
    except ImportError as e:
        USER_MANAGEMENT_TAB_AVAILABLE = False
        print(f"Note: User Management Tab not available: {e}")

    # Import Phase 2 tabs
    try:
        from fuel_tracking_tab import FuelTrackingTab
        FUEL_TRACKING_TAB_AVAILABLE = True
    except ImportError as e:
        FUEL_TRACKING_TAB_AVAILABLE = False
        print(f"Note: Fuel Tracking Tab not available: {e}")

    try:
        from driving_score_tab import DrivingScoreTab
        DRIVING_SCORE_TAB_AVAILABLE = True
    except ImportError as e:
        DRIVING_SCORE_TAB_AVAILABLE = False
        print(f"Note: Driving Score Tab not available: {e}")

    try:
        from geofencing_tab import GeofencingTab
        GEOFENCING_TAB_AVAILABLE = True
    except ImportError as e:
        GEOFENCING_TAB_AVAILABLE = False
        print(f"Note: Geofencing Tab not available: {e}")

    try:
        from esp32_sensors_tab import ESP32SensorsTab
        ESP32_SENSORS_TAB_AVAILABLE = True
    except ImportError as e:
        ESP32_SENSORS_TAB_AVAILABLE = False
        print(f"Note: ESP32 Sensors Tab not available: {e}")

    try:
        from maintenance_reminders_tab import MaintenanceRemindersTab
        MAINTENANCE_REMINDERS_TAB_AVAILABLE = True
    except ImportError as e:
        MAINTENANCE_REMINDERS_TAB_AVAILABLE = False
        print(f"Note: Maintenance Reminders Tab not available: {e}")

    try:
        from recall_alerts_tab import RecallAlertsTab
        RECALL_ALERTS_TAB_AVAILABLE = True
    except ImportError as e:
        RECALL_ALERTS_TAB_AVAILABLE = False
        print(f"Note: Recall Alerts Tab not available: {e}")

    # Phase 4 & 5 tabs
    try:
        from analytics_tab import AnalyticsTab
        ANALYTICS_TAB_AVAILABLE = True
    except ImportError as e:
        ANALYTICS_TAB_AVAILABLE = False
        print(f"Note: Analytics Tab not available: {e}")

    try:
        from help_tab import HelpTab
        HELP_TAB_AVAILABLE = True
    except ImportError as e:
        HELP_TAB_AVAILABLE = False
        print(f"Note: Help Tab not available: {e}")

    # Import the fixed Live Data tab
    global FixedLiveDataTab
    from live_data_tab import LiveDataTab as FixedLiveDataTab

    # Import new UI components for sidebar navigation
    global DashboardWidget, SidebarNavigation
    from dashboard_widget import DashboardWidget
    from sidebar_navigation import SidebarNavigation

    # Import enhanced dashboard widgets for AI status, predictions, notifications, export
    global EnhancedDashboard, AIStatusWidget, PredictionsSummaryWidget
    global NotificationsCenterWidget, DataExportWidget
    try:
        from dashboard_widgets import (
            EnhancedDashboard, AIStatusWidget, PredictionsSummaryWidget,
            NotificationsCenterWidget, DataExportWidget
        )
        ENHANCED_DASHBOARD_AVAILABLE = True
    except ImportError as e:
        ENHANCED_DASHBOARD_AVAILABLE = False
        print(f"Note: Enhanced Dashboard widgets not available: {e}")

    # Import mobile server components
    global MobileServerWrapper, DirectReportServer, LiveDataWebSocketClient, MobileDataBridge
    try:
        from mobile_server_wrapper import MobileServerWrapper, DirectReportServer, LiveDataWebSocketClient
        from mobile_data_bridge import MobileDataBridge
        MOBILE_SERVER_AVAILABLE = True
    except ImportError:
        MOBILE_SERVER_AVAILABLE = False
        print("Note: Mobile server modules not available")

# Additional module availability flags - set during import_modules()
PID_PROFILE_AVAILABLE = False
HEARTBEAT_MANAGER_AVAILABLE = False
ACCURACY_TRACKER_AVAILABLE = False
ALERT_NOTIFICATION_MANAGER_AVAILABLE = False
CATALOG_EDITOR_AVAILABLE = False
PRODUCTION_SYSTEMS_AVAILABLE = False
MANAGEMENT_TABS_AVAILABLE = False
ENHANCED_ENGINE_AVAILABLE = False
ENHANCED_DASHBOARD_AVAILABLE = False

def import_additional_modules():
    """Import additional Qt-dependent modules after QApplication is created."""
    global PID_PROFILE_AVAILABLE, HEARTBEAT_MANAGER_AVAILABLE, ACCURACY_TRACKER_AVAILABLE
    global ALERT_NOTIFICATION_MANAGER_AVAILABLE, CATALOG_EDITOR_AVAILABLE
    global PRODUCTION_SYSTEMS_AVAILABLE, MANAGEMENT_TABS_AVAILABLE, ENHANCED_ENGINE_AVAILABLE

    # Import new modules
    global PIDProfileResolver, VehicleCatalog, VehicleProfile
    try:
        from pid_profiles import PIDProfileResolver, VehicleCatalog, VehicleProfile
        PID_PROFILE_AVAILABLE = True
    except ImportError:
        PID_PROFILE_AVAILABLE = False

    # Import Device Heartbeat Manager
    global get_heartbeat_manager, DeviceHeartbeatManager, DeviceStatus
    try:
        from device_heartbeat import get_heartbeat_manager, DeviceHeartbeatManager, DeviceStatus
        HEARTBEAT_MANAGER_AVAILABLE = True
    except ImportError as e:
        HEARTBEAT_MANAGER_AVAILABLE = False
        print(f"Note: Device Heartbeat Manager not available: {e}")

    # Import prediction accuracy tracker
    global get_accuracy_tracker
    try:
        from prediction_accuracy_tracker import get_accuracy_tracker
        ACCURACY_TRACKER_AVAILABLE = True
    except ImportError:
        ACCURACY_TRACKER_AVAILABLE = False

    # Import Alert Notification Manager
    global get_notification_manager, AlertNotificationManager, NotificationChannel, NotificationPriority
    try:
        from alert_notifications import get_notification_manager, AlertNotificationManager, NotificationChannel, NotificationPriority
        ALERT_NOTIFICATION_MANAGER_AVAILABLE = True
    except ImportError as e:
        ALERT_NOTIFICATION_MANAGER_AVAILABLE = False
        print(f"Note: Alert Notification Manager not available: {e}")

    global VehicleCatalogEditor
    try:
        from vehicle_catalog_editor import VehicleCatalogEditor
        CATALOG_EDITOR_AVAILABLE = True
    except ImportError:
        CATALOG_EDITOR_AVAILABLE = False

    # Import production systems (integrity, monitoring, backup)
    global run_startup_integrity_check, start_monitoring, start_scheduled_backups
    try:
        from system_integrity import run_startup_integrity_check
        from monitoring_alerts import start_monitoring
        from enterprise_backup import start_scheduled_backups
        PRODUCTION_SYSTEMS_AVAILABLE = True
    except ImportError as e:
        PRODUCTION_SYSTEMS_AVAILABLE = False
        print(f"Note: Production systems not available: {e}")

    # Import subscription and admin dashboard tabs (Customer Management merged into Profile tab)
    global SubscriptionTab, AdminDashboard
    try:
        from subscription_tab import SubscriptionTab
        from admin_dashboard import AdminDashboard
        MANAGEMENT_TABS_AVAILABLE = True
    except ImportError as e:
        MANAGEMENT_TABS_AVAILABLE = False
        print(f"Note: Management tabs not available: {e}")

    # Import tier management tab (FREE/PRO/PREMIUM system)
    global SubscriptionManagementTab, TIER_MANAGEMENT_AVAILABLE
    try:
        from subscription_management_tab import SubscriptionManagementTab
        TIER_MANAGEMENT_AVAILABLE = True
    except ImportError as e:
        TIER_MANAGEMENT_AVAILABLE = False
        SubscriptionManagementTab = None
        print(f"Note: Tier management tab not available: {e}")

    # Import Enhanced Prediction Engine (LSTM, ESP32, Feedback)
    global EnhancedPredictionEngine, create_enhanced_engine
    try:
        from enhanced_prediction_engine import EnhancedPredictionEngine, create_enhanced_engine
        ENHANCED_ENGINE_AVAILABLE = True
    except ImportError as e:
        ENHANCED_ENGINE_AVAILABLE = False
        print(f"Note: Enhanced prediction engine not available: {e}")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
#   ENHANCED PROFESSIONAL THEME - UPDATED WITH PREDICT RED THEME
# =============================================================================

class ProfessionalTheme:
    """Professional dark theme with PREDICT RED color palette"""
    
    # Primary Colors - PREDICT RED
    PRIMARY = "#C40000"
    PRIMARY_DARK = "#A00000"
    PRIMARY_LIGHT = "#E57373"  # Softer accent color for section headers
    
    # Secondary Colors
    SECONDARY = "#1A1A1A"
    SECONDARY_DARK = "#0D0D0D"
    
    # Status Colors
    SUCCESS = "#4CAF50"
    SUCCESS_LIGHT = "#20C997"
    WARNING = "#FFC107"
    WARNING_DARK = "#E0A800"
    DANGER = "#C40000"  # Updated to Predict Red
    DANGER_DARK = "#A00000"
    INFO = "#0DCAF0"
    
    # Background Colors
    BACKGROUND = "#0D1117"
    BACKGROUND_SECONDARY = "#161B22"
    CARD_BG = "#21262D"
    CARD_BG_HOVER = "#30363D"
    
    # Text Colors
    TEXT_PRIMARY = "#F0F6FC"
    TEXT_SECONDARY = "#8B949E"
    TEXT_MUTED = "#6E7681"
    
    # Border Colors
    BORDER = "#30363D"
    BORDER_LIGHT = "#484F58"
    BORDER_FOCUS = "#388BFD"
    
    # Connection Colors
    BLUE_CONNECTION = "#0D6EFD"
    GREEN_CONNECTION = "#198754"
    WIFI_CONNECTION = "#6610F2"
    
    # Gauge Colors - Updated with Predict Red
    GAUGE_BG = "#1A1F25"
    GAUGE_RING = "#2D333B"
    GAUGE_NORMAL = "#4CAF50"
    GAUGE_WARNING = "#FFC107"
    GAUGE_CRITICAL = "#C40000"  # Predict Red
    GAUGE_GLOW = "#C40000"      # Predict Red
    GAUGE_NEEDLE = "#C40000"    # Predict Red
    
    @classmethod
    def apply_theme(cls, app: QApplication):
        """Apply professional dark theme to the application"""
        app.setStyle("Fusion")
        
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(cls.BACKGROUND))
        palette.setColor(QPalette.WindowText, QColor(cls.TEXT_PRIMARY))
        palette.setColor(QPalette.Base, QColor(cls.CARD_BG))
        palette.setColor(QPalette.AlternateBase, QColor(cls.BACKGROUND_SECONDARY))
        palette.setColor(QPalette.ToolTipBase, QColor(cls.CARD_BG))
        palette.setColor(QPalette.ToolTipText, QColor(cls.TEXT_PRIMARY))
        palette.setColor(QPalette.Text, QColor(cls.TEXT_PRIMARY))
        palette.setColor(QPalette.PlaceholderText, QColor(cls.TEXT_MUTED))
        palette.setColor(QPalette.Button, QColor(cls.CARD_BG))
        palette.setColor(QPalette.ButtonText, QColor(cls.TEXT_PRIMARY))
        palette.setColor(QPalette.BrightText, QColor(cls.DANGER))
        palette.setColor(QPalette.Highlight, QColor(cls.PRIMARY))
        palette.setColor(QPalette.HighlightedText, QColor(cls.TEXT_PRIMARY))
        palette.setColor(QPalette.Link, QColor(cls.PRIMARY))
        palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(cls.TEXT_MUTED))
        palette.setColor(QPalette.Disabled, QPalette.Text, QColor(cls.TEXT_MUTED))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(cls.TEXT_MUTED))
        
        app.setPalette(palette)
        app.setStyleSheet(cls._get_stylesheet())
    
    @classmethod
    def _get_stylesheet(cls) -> str:
        """Get complete application stylesheet"""
        return f"""
            QWidget {{
                font-family: 'Segoe UI', 'SF Pro Display', -apple-system, sans-serif;
                font-size: 13px;
            }}
            
            QMainWindow {{
                background-color: {cls.BACKGROUND};
            }}
            
            QTabWidget::pane {{
                border: 1px solid {cls.BORDER};
                border-radius: 8px;
                background-color: {cls.BACKGROUND_SECONDARY};
                padding: 5px;
            }}
            
            QTabBar::tab {{
                background-color: {cls.CARD_BG};
                color: {cls.TEXT_SECONDARY};
                padding: 10px 18px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                border: 1px solid {cls.BORDER};
                border-bottom: none;
                font-weight: 500;
            }}
            
            QTabBar::tab:selected {{
                background-color: {cls.PRIMARY};
                color: {cls.TEXT_PRIMARY};
                font-weight: 600;
            }}
            
            QTabBar::tab:hover:!selected {{
                background-color: {cls.CARD_BG_HOVER};
                color: {cls.TEXT_PRIMARY};
            }}
            
            QGroupBox {{
                font-weight: 600;
                font-size: 14px;
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 10px;
                margin-top: 14px;
                padding: 15px 10px 10px 10px;
                background-color: {cls.CARD_BG};
            }}
            
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
                color: {cls.PRIMARY_LIGHT};
            }}
            
            QPushButton {{
                background-color: {cls.CARD_BG};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
                min-height: 20px;
            }}
            
            QPushButton:hover {{
                background-color: {cls.CARD_BG_HOVER};
                border-color: {cls.BORDER_LIGHT};
            }}
            
            QPushButton:pressed {{
                background-color: {cls.PRIMARY_DARK};
            }}
            
            QPushButton:disabled {{
                background-color: {cls.BACKGROUND_SECONDARY};
                color: {cls.TEXT_MUTED};
            }}
            
            QLineEdit, QSpinBox, QDoubleSpinBox {{
                background-color: {cls.BACKGROUND_SECONDARY};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 6px;
                padding: 8px 12px;
            }}
            
            QLineEdit:focus, QSpinBox:focus {{
                border-color: {cls.BORDER_FOCUS};
            }}
            
            QComboBox {{
                background-color: {cls.CARD_BG};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 6px;
                padding: 8px 12px;
                min-width: 100px;
            }}
            
            QComboBox QAbstractItemView {{
                background-color: {cls.CARD_BG};
                color: {cls.TEXT_PRIMARY};
                selection-background-color: {cls.PRIMARY};
                border: 1px solid {cls.BORDER};
            }}
            
            QTableWidget {{
                background-color: {cls.CARD_BG};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 8px;
                gridline-color: {cls.BORDER};
            }}
            
            QTableWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {cls.BORDER};
            }}
            
            QTableWidget::item:selected {{
                background-color: {cls.PRIMARY};
            }}
            
            QHeaderView::section {{
                background-color: {cls.BACKGROUND_SECONDARY};
                color: {cls.TEXT_PRIMARY};
                padding: 10px;
                border: none;
                border-bottom: 2px solid {cls.PRIMARY};
                font-weight: 600;
            }}
            
            QScrollBar:vertical {{
                background-color: {cls.BACKGROUND_SECONDARY};
                width: 10px;
                border-radius: 5px;
            }}
            
            QScrollBar::handle:vertical {{
                background-color: {cls.BORDER_LIGHT};
                border-radius: 5px;
                min-height: 30px;
            }}
            
            QScrollBar::handle:vertical:hover {{
                background-color: {cls.TEXT_MUTED};
            }}
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            
            QPlainTextEdit, QTextEdit {{
                background-color: {cls.BACKGROUND_SECONDARY};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 8px;
                padding: 10px;
                font-family: 'Consolas', 'Monaco', monospace;
            }}
            
            QProgressBar {{
                background-color: {cls.BACKGROUND_SECONDARY};
                border: 1px solid {cls.BORDER};
                border-radius: 6px;
                text-align: center;
                color: {cls.TEXT_PRIMARY};
                height: 22px;
            }}
            
            QProgressBar::chunk {{
                background-color: {cls.PRIMARY};
                border-radius: 5px;
            }}
            
            QSlider::groove:horizontal {{
                background-color: {cls.BORDER};
                height: 6px;
                border-radius: 3px;
            }}
            
            QSlider::handle:horizontal {{
                background-color: {cls.PRIMARY};
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }}
            
            QSlider::handle:horizontal:hover {{
                background-color: {cls.PRIMARY_LIGHT};
            }}
            
            QCheckBox {{
                color: {cls.TEXT_PRIMARY};
                spacing: 8px;
            }}
            
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {cls.BORDER};
                border-radius: 4px;
                background-color: {cls.CARD_BG};
            }}
            
            QCheckBox::indicator:checked {{
                background-color: {cls.PRIMARY};
                border-color: {cls.PRIMARY};
            }}
            
            QSplitter::handle {{
                background-color: {cls.BORDER};
            }}
            
            QToolTip {{
                background-color: {cls.CARD_BG};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 6px;
                padding: 8px;
            }}
            
            QStatusBar {{
                background-color: {cls.BACKGROUND_SECONDARY};
                color: {cls.TEXT_SECONDARY};
                border-top: 1px solid {cls.BORDER};
                padding: 5px;
            }}
        """


def show_error(parent: QWidget, title: str, message: str):
    """Display error message box"""
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(message)
    msg.setIcon(QMessageBox.Critical)
    msg.exec()


def show_info(parent: QWidget, title: str, message: str):
    """Display info message box"""
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(message)
    msg.setIcon(QMessageBox.Information)
    msg.exec()


# =============================================================================
#   ENHANCED PROFESSIONAL GAUGES - UPDATED WITH RED NEEDLE
# =============================================================================

class ModernCircularGauge(QWidget):
    """Modern circular gauge with glow effects and smooth animations"""
    
    def __init__(self, title="", min_val=0, max_val=100, unit="", 
                 warning_threshold=70, critical_threshold=90, parent=None):
        super().__init__(parent)
        self.title = title
        self.min_val = min_val
        self.max_val = max_val
        self.unit = unit
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        
        self._current_value = 0
        self._display_value = 0
        self._target_value = 0
        self._is_valid = False
        
        # Animation
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._animate_value)
        self._animation_timer.setInterval(16)  # ~60 FPS
        
        self.setFixedSize(200, 240)
        self.setToolTip(f"{title}\nRange: {min_val}-{max_val}{unit}")
    
    def set_value(self, value, is_valid=True):
        """Set gauge value with smooth animation"""
        self._is_valid = is_valid
        if is_valid:
            self._target_value = max(self.min_val, min(self.max_val, value))
            if not self._animation_timer.isActive():
                self._animation_timer.start()
        else:
            self._target_value = self.min_val
            self._display_value = self.min_val
            self._animation_timer.stop()
        self.update()
    
    def _animate_value(self):
        """Smooth animation for value changes"""
        diff = self._target_value - self._display_value
        if abs(diff) < 0.5:
            self._display_value = self._target_value
            self._animation_timer.stop()
        else:
            self._display_value += diff * 0.15
        self.update()
    
    def _get_value_color(self) -> QColor:
        """Get color based on current value percentage"""
        if not self._is_valid:
            return QColor(ProfessionalTheme.TEXT_MUTED)
        
        percentage = (self._display_value - self.min_val) / (self.max_val - self.min_val) * 100
        
        if percentage >= self.critical_threshold:
            return QColor(ProfessionalTheme.GAUGE_CRITICAL)  # Predict Red
        elif percentage >= self.warning_threshold:
            return QColor(ProfessionalTheme.WARNING)
        else:
            return QColor(ProfessionalTheme.SUCCESS)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        center_x = width // 2
        center_y = (height - 40) // 2
        radius = min(center_x, center_y) - 20
        
        # Draw outer glow ring
        if self._is_valid:
            glow_color = self._get_value_color()
            glow_color.setAlpha(30)
            glow_gradient = QRadialGradient(center_x, center_y, radius + 15)
            glow_gradient.setColorAt(0.7, glow_color)
            glow_gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setBrush(glow_gradient)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(center_x - radius - 15, center_y - radius - 15, 
                              (radius + 15) * 2, (radius + 15) * 2)
        
        # Draw background ring
        painter.setPen(QPen(QColor(ProfessionalTheme.GAUGE_RING), 12, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(Qt.NoBrush)
        arc_rect = QRect(center_x - radius, center_y - radius, radius * 2, radius * 2)
        painter.drawArc(arc_rect, 225 * 16, -270 * 16)
        
        # Draw value arc
        if self._is_valid and self._display_value > self.min_val:
            value_color = self._get_value_color()
            
            # Create gradient for value arc with Predict Red
            gradient = QConicalGradient(center_x, center_y, 225)
            if value_color == QColor(ProfessionalTheme.GAUGE_CRITICAL):
                # Use red gradient for critical
                gradient.setColorAt(0, QColor(ProfessionalTheme.PRIMARY_LIGHT))
                gradient.setColorAt(1, QColor(ProfessionalTheme.PRIMARY_DARK))
            else:
                gradient.setColorAt(0, value_color)
                gradient.setColorAt(1, value_color.darker(120))
            
            pen = QPen(QBrush(gradient), 10, Qt.SolidLine, Qt.RoundCap)
            painter.setPen(pen)
            
            # Calculate arc span
            percentage = (self._display_value - self.min_val) / (self.max_val - self.min_val)
            span_angle = int(-270 * percentage * 16)
            painter.drawArc(arc_rect, 225 * 16, span_angle)
        
        # Draw center background
        painter.setPen(Qt.NoPen)
        center_gradient = QRadialGradient(center_x, center_y, radius - 15)
        center_gradient.setColorAt(0, QColor(ProfessionalTheme.CARD_BG))
        center_gradient.setColorAt(1, QColor(ProfessionalTheme.GAUGE_BG))
        painter.setBrush(center_gradient)
        painter.drawEllipse(center_x - radius + 20, center_y - radius + 20,
                          (radius - 20) * 2, (radius - 20) * 2)
        
        # Draw value text
        painter.setPen(QColor(ProfessionalTheme.TEXT_PRIMARY))
        value_font = QFont()
        value_font.setPointSize(24)
        value_font.setBold(True)
        painter.setFont(value_font)
        
        if self._is_valid:
            value_text = f"{self._display_value:.0f}"
        else:
            value_text = "---"
        
        text_rect = QRect(center_x - 50, center_y - 20, 100, 40)
        painter.drawText(text_rect, Qt.AlignCenter, value_text)
        
        # Draw unit
        unit_font = QFont()
        unit_font.setPointSize(11)
        painter.setFont(unit_font)
        painter.setPen(QColor(ProfessionalTheme.TEXT_SECONDARY))
        unit_rect = QRect(center_x - 30, center_y + 15, 60, 20)
        painter.drawText(unit_rect, Qt.AlignCenter, self.unit)
        
        # Draw title
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QColor(ProfessionalTheme.TEXT_PRIMARY))
        title_rect = QRect(0, height - 35, width, 30)
        painter.drawText(title_rect, Qt.AlignCenter, self.title)
        
        # Draw min/max labels
        label_font = QFont()
        label_font.setPointSize(8)
        painter.setFont(label_font)
        painter.setPen(QColor(ProfessionalTheme.TEXT_MUTED))
        
        # Min label (bottom left of arc)
        painter.drawText(center_x - radius - 5, center_y + radius - 10, f"{self.min_val}")
        # Max label (bottom right of arc)
        painter.drawText(center_x + radius - 20, center_y + radius - 10, f"{self.max_val}")


class ModernLinearGauge(QWidget):
    """Modern linear gauge with gradient fill and animations"""
    
    def __init__(self, title="", min_val=0, max_val=100, unit="",
                 warning_threshold=70, critical_threshold=90, parent=None):
        super().__init__(parent)
        self.title = title
        self.min_val = min_val
        self.max_val = max_val
        self.unit = unit
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        
        self._current_value = 0
        self._display_value = 0
        self._target_value = 0
        self._is_valid = False
        
        # Animation
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._animate_value)
        self._animation_timer.setInterval(16)
        
        self.setFixedHeight(70)
        self.setMinimumWidth(200)
    
    def set_value(self, value, is_valid=True):
        """Set gauge value with animation"""
        self._is_valid = is_valid
        if is_valid:
            self._target_value = max(self.min_val, min(self.max_val, value))
            if not self._animation_timer.isActive():
                self._animation_timer.start()
        else:
            self._target_value = self.min_val
            self._display_value = self.min_val
            self._animation_timer.stop()
        self.update()
    
    def _animate_value(self):
        """Smooth animation"""
        diff = self._target_value - self._display_value
        if abs(diff) < 0.5:
            self._display_value = self._target_value
            self._animation_timer.stop()
        else:
            self._display_value += diff * 0.15
        self.update()
    
    def _get_value_color(self) -> QColor:
        """Get color based on value percentage"""
        if not self._is_valid:
            return QColor(ProfessionalTheme.TEXT_MUTED)
        
        percentage = (self._display_value - self.min_val) / (self.max_val - self.min_val) * 100
        
        if percentage >= self.critical_threshold:
            return QColor(ProfessionalTheme.GAUGE_CRITICAL)  # Predict Red
        elif percentage >= self.warning_threshold:
            return QColor(ProfessionalTheme.WARNING)
        else:
            return QColor(ProfessionalTheme.SUCCESS)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        bar_height = 14
        bar_y = 30
        bar_radius = 7
        
        # Draw title and value
        painter.setPen(QColor(ProfessionalTheme.TEXT_PRIMARY))
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(0, 0, width, 25, Qt.AlignLeft, self.title)
        
        # Draw value
        value_font = QFont()
        value_font.setPointSize(11)
        painter.setFont(value_font)
        
        if self._is_valid:
            value_text = f"{self._display_value:.1f}{self.unit}"
            painter.setPen(self._get_value_color())
        else:
            value_text = "---"
            painter.setPen(QColor(ProfessionalTheme.TEXT_MUTED))
        
        painter.drawText(0, 0, width, 25, Qt.AlignRight, value_text)
        
        # Draw background bar
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(ProfessionalTheme.GAUGE_RING))
        painter.drawRoundedRect(0, bar_y, width, bar_height, bar_radius, bar_radius)
        
        # Draw value bar
        if self._is_valid and self._display_value > self.min_val:
            percentage = (self._display_value - self.min_val) / (self.max_val - self.min_val)
            fill_width = int(width * percentage)
            
            if fill_width > 0:
                # Gradient fill
                value_color = self._get_value_color()
                gradient = QLinearGradient(0, bar_y, fill_width, bar_y)
                if value_color == QColor(ProfessionalTheme.GAUGE_CRITICAL):
                    # Red gradient for critical
                    gradient.setColorAt(0, QColor(ProfessionalTheme.PRIMARY_LIGHT))
                    gradient.setColorAt(1, QColor(ProfessionalTheme.PRIMARY))
                else:
                    gradient.setColorAt(0, value_color.lighter(110))
                    gradient.setColorAt(1, value_color)
                
                painter.setBrush(gradient)
                painter.drawRoundedRect(0, bar_y, fill_width, bar_height, bar_radius, bar_radius)
        
        # Draw min/max labels
        label_font = QFont()
        label_font.setPointSize(8)
        painter.setFont(label_font)
        painter.setPen(QColor(ProfessionalTheme.TEXT_MUTED))
        painter.drawText(0, bar_y + bar_height + 2, 40, 20, Qt.AlignLeft, f"{self.min_val}")
        painter.drawText(width - 40, bar_y + bar_height + 2, 40, 20, Qt.AlignRight, f"{self.max_val}")


class ModernSparkline(QWidget):
    """Modern sparkline chart with gradient fill and hover effects"""
    
    def __init__(self, color=None, parent=None):
        super().__init__(parent)
        self._values = deque(maxlen=100)
        self._timestamps = deque(maxlen=100)
        self._color = QColor(color) if color else QColor(ProfessionalTheme.PRIMARY)  # Predict Red
        self._hover_index = -1
        
        self.setFixedHeight(50)
        self.setMouseTracking(True)
    
    def add_value(self, value):
        """Add new value to sparkline"""
        self._values.append(value)
        self._timestamps.append(datetime.now())
        self.update()
    
    def clear(self):
        """Clear all values"""
        self._values.clear()
        self._timestamps.clear()
        self.update()
    
    def mouseMoveEvent(self, event):
        if len(self._values) < 2:
            return
        
        x_pos = event.pos().x()
        index = int(x_pos * len(self._values) / self.width())
        index = max(0, min(len(self._values) - 1, index))
        
        if index != self._hover_index:
            self._hover_index = index
            self.update()
    
    def leaveEvent(self, event):
        self._hover_index = -1
        self.update()
    
    def paintEvent(self, event):
        if len(self._values) < 2:
            painter = QPainter(self)
            painter.setPen(QColor(ProfessionalTheme.TEXT_MUTED))
            painter.drawText(self.rect(), Qt.AlignCenter, "No data")
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        min_val = min(self._values)
        max_val = max(self._values)
        value_range = max_val - min_val if max_val > min_val else 1
        
        # Calculate points
        points = []
        for i, value in enumerate(self._values):
            x = int(i * width / (len(self._values) - 1))
            y = int(height - 5 - (value - min_val) * (height - 10) / value_range)
            points.append(QPoint(x, y))
        
        # Draw filled area
        fill_path = QPainterPath()
        fill_path.moveTo(0, height)
        for point in points:
            fill_path.lineTo(point)
        fill_path.lineTo(width, height)
        fill_path.closeSubpath()
        
        fill_gradient = QLinearGradient(0, 0, 0, height)
        fill_color = QColor(self._color)
        fill_color.setAlpha(60)
        fill_gradient.setColorAt(0, fill_color)
        fill_gradient.setColorAt(1, QColor(0, 0, 0, 0))
        
        painter.fillPath(fill_path, fill_gradient)
        
        # Draw line
        painter.setPen(QPen(self._color, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        for i in range(len(points) - 1):
            painter.drawLine(points[i], points[i + 1])
        
        # Draw hover point
        if 0 <= self._hover_index < len(points):
            point = points[self._hover_index]
            value = self._values[self._hover_index]
            
            # Draw point
            painter.setBrush(self._color)
            painter.setPen(QPen(QColor(ProfessionalTheme.TEXT_PRIMARY), 2))
            painter.drawEllipse(point, 5, 5)
            
            # Draw tooltip
            tooltip_text = f"{value:.1f}"
            tooltip_rect = painter.fontMetrics().boundingRect(tooltip_text)
            tooltip_x = min(point.x(), width - tooltip_rect.width() - 15)
            tooltip_y = max(5, point.y() - 25)
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(ProfessionalTheme.CARD_BG))
            painter.drawRoundedRect(tooltip_x - 5, tooltip_y, 
                                   tooltip_rect.width() + 10, tooltip_rect.height() + 6, 4, 4)
            
            painter.setPen(QColor(ProfessionalTheme.TEXT_PRIMARY))
            painter.drawText(tooltip_x, tooltip_y + tooltip_rect.height(), tooltip_text)


# =============================================================================
#   CONNECTION INDICATOR
# =============================================================================

class ConnectionIndicator(QWidget):
    """Animated connection status indicator"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(28, 28)
        self._status = "disconnected"
        self._connection_type = "unknown"
        self._pulse_opacity = 1.0
        self._pulse_direction = -1
        
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._update_pulse)
    
    def set_status(self, status: str, connection_type: str = "unknown"):
        """Set status: 'connected', 'connecting', 'disconnected'"""
        self._status = status
        self._connection_type = connection_type
        
        if status == "connecting":
            self._pulse_timer.start(50)
        else:
            self._pulse_timer.stop()
            self._pulse_opacity = 1.0
        
        self.update()
    
    def _update_pulse(self):
        self._pulse_opacity += self._pulse_direction * 0.05
        if self._pulse_opacity <= 0.3:
            self._pulse_direction = 1
        elif self._pulse_opacity >= 1.0:
            self._pulse_direction = -1
        self.update()
    
    def _get_color(self) -> QColor:
        if self._status == "connected":
            if self._connection_type == "bluetooth":
                return QColor(ProfessionalTheme.BLUE_CONNECTION)
            elif self._connection_type == "usb":
                return QColor(ProfessionalTheme.GREEN_CONNECTION)
            return QColor(ProfessionalTheme.SUCCESS)
        elif self._status == "connecting":
            return QColor(ProfessionalTheme.WARNING)
        return QColor(ProfessionalTheme.DANGER)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        color = self._get_color()
        
        # Draw outer glow
        if self._status in ["connected", "connecting"]:
            glow = QColor(color)
            glow.setAlphaF(0.3 * self._pulse_opacity)
            painter.setBrush(glow)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(2, 2, 24, 24)
        
        # Draw main indicator
        main_color = QColor(color)
        if self._status == "connecting":
            main_color.setAlphaF(self._pulse_opacity)
        
        painter.setBrush(main_color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(6, 6, 16, 16)
        
        # Draw inner highlight
        if self._status == "connected":
            painter.setBrush(QColor(255, 255, 255, 80))
            painter.drawEllipse(9, 9, 6, 6)


# =============================================================================
#   DATA LOGGER WITH SECURITY
# =====================================================================

class SecureDataLogger:
    """Secure data logger with integrity checking"""

    def __init__(self, log_directory=None):
        # Use CONFIG.LOGS_DIR if available, otherwise fallback
        if log_directory is None:
            if CONFIG:
                log_directory = str(CONFIG.LOGS_DIR)
            else:
                log_directory = "./data/logs"
        self.log_directory = log_directory
        # For backward compatibility, keep the original attribute name
        self.current_session_file = None
        # Alias for clarity in other parts of the app (per-vehicle log file)
        self.current_vehicle_log_file = None
        self._session_hash = None
        self._ensure_directory()

    def _ensure_directory(self):
        """Create log directory if needed"""
        if not os.path.exists(self.log_directory):
            os.makedirs(self.log_directory, exist_ok=True)

    def _clean_filename_component(self, text: str) -> str:
        """
        Clean a string so it is safe for use in filenames:
        - Uppercase
        - Remove emojis and special characters
        - Replace spaces with underscores
        - Collapse multiple underscores
        """
        if not text:
            return "UNKNOWN"
        # Uppercase for consistency
        text = text.upper()
        # Remove anything that is not a word char, space, or hyphen
        text = re.sub(r"[^\w\s-]", "", text)
        # Replace spaces with underscores
        text = text.replace(" ", "_")
        # Collapse multiple underscores
        text = re.sub(r"_+", "_", text)
        # Strip leading/trailing underscores
        text = text.strip("_")
        return text or "UNKNOWN"

    def _build_vehicle_log_path(self, vehicle_profile: Optional[Dict[str, Any]]) -> str:
        """
        Build a deterministic per-vehicle log file path based on
        profile name + license plate.
        """
        profile = vehicle_profile or {}
        profile_name = profile.get("name") or "UNKNOWN"
        plate = profile.get("license_plate") or profile.get("plate") or "UNKNOWN"

        clean_name = self._clean_filename_component(profile_name)
        clean_plate = self._clean_filename_component(plate)

        filename = f"{clean_name}_{clean_plate}.jsonl"
        return os.path.join(self.log_directory, filename)

    def start_session(self, vehicle_profile=None) -> str:
        """Start (or continue) logging for a vehicle with integrity tracking.

        Instead of creating a new per-session file, we now create one
        merged log file per vehicle, and append a new session header/footer
        segment each time.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Build / reuse per-vehicle log file path
        self.current_session_file = self._build_vehicle_log_path(vehicle_profile)
        # Keep alias in sync
        self.current_vehicle_log_file = self.current_session_file

        # Initialize session hash for this connection
        self._session_hash = hashlib.sha256()

        header = {
            "type": "session_header",
            "session_start": timestamp,
            "vehicle_profile": vehicle_profile,
            "app_version": APP_VERSION,
        }
        self._append_entry(header)

        return self.current_session_file

    def log_data(self, data: Dict[str, Any]):
        """Log data point with timestamp"""
        if self.current_session_file and data:
            entry = {
                "type": "data_point",
                "timestamp": datetime.now().isoformat(),
                "data": data,
            }
            self._append_entry(entry)

    def _append_entry(self, entry: Dict[str, Any]):
        """Append entry to log file with integrity tracking"""
        try:
            if not self.current_session_file:
                return

            line = json.dumps(entry) + "\n"

            # Update session hash
            if self._session_hash:
                self._session_hash.update(line.encode())

            with open(self.current_session_file, "a", encoding="utf-8") as f:
                f.write(line)

        except Exception as e:
            logger.error(f"Logging error: {e}")

    def end_session(self) -> Optional[str]:
        """End session and return integrity hash"""
        if self.current_session_file and self._session_hash:
            footer = {
                "type": "session_footer",
                "session_end": datetime.now().isoformat(),
                "integrity_hash": self._session_hash.hexdigest(),
            }
            self._append_entry(footer)

            hash_value = self._session_hash.hexdigest()
            # Reset only in-memory state; file itself remains and is reused
            self.current_session_file = None
            self.current_vehicle_log_file = None
            self._session_hash = None
            return hash_value
        return None

    def get_session_data(self, session_file: str) -> List[Dict[str, Any]]:
        """Read data from a log file, returning only data_point entries."""
        data: List[Dict[str, Any]] = []
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if entry.get("type") == "data_point":
                            data.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Error reading session: {e}")
        return data

    def list_sessions(self) -> List[str]:
        """List available log files.

        Previously this only returned files starting with 'session_'.
        Now we return all .jsonl files in the log directory so that:
        - Old session_* files are still visible
        - New per-vehicle files (PROFILE_PLATE.jsonl) are also visible
        """
        sessions: List[str] = []
        try:
            if os.path.exists(self.log_directory):
                for f in os.listdir(self.log_directory):
                    if f.endswith(".jsonl"):
                        sessions.append(f)
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
        return sorted(sessions, reverse=True)


# =============================================================================
#   PID LEARNING MANAGER
# =============================================================================

class PIDLearningManager:
    """Manages custom OBD PID definitions"""
    
    def __init__(self, directory="./learned_pids"):
        self.directory = directory
        self.learned_pids_directory = directory  # Alias for compatibility
        self.learned_pids = {}
        self._ensure_directory()
        self._load_pids()
    
    def _ensure_directory(self):
        if not os.path.exists(self.directory):
            os.makedirs(self.directory, exist_ok=True)
    
    def _load_pids(self):
        """Load all learned PIDs"""
        self.learned_pids = {}
        try:
            for filename in os.listdir(self.directory):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.directory, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        pid_data = json.load(f)
                        hex_code = pid_data.get('hex_code', '').upper()
                        if hex_code:
                            self.learned_pids[hex_code] = pid_data
            logger.info(f"Loaded {len(self.learned_pids)} learned PIDs")
        except Exception as e:
            logger.error(f"Error loading PIDs: {e}")
    
    def save_pid(self, pid_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Save a PID definition"""
        try:
            hex_code = pid_data.get('hex_code', '').upper()
            if not hex_code:
                return False, "Invalid hex code"
            
            filename = f"pid_{hex_code}.json"
            filepath = os.path.join(self.directory, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(pid_data, f, indent=2)
            
            self.learned_pids[hex_code] = pid_data
            return True, f"PID {hex_code} saved"
        except Exception as e:
            return False, f"Error: {e}"
    
    def delete_pid(self, hex_code: str) -> Tuple[bool, str]:
        """Delete a PID definition"""
        try:
            hex_code = hex_code.upper()
            filename = f"pid_{hex_code}.json"
            filepath = os.path.join(self.directory, filename)
            
            if os.path.exists(filepath):
                os.remove(filepath)
                self.learned_pids.pop(hex_code, None)
                return True, f"PID {hex_code} deleted"
            return False, "PID not found"
        except Exception as e:
            return False, f"Error: {e}"
    
    def get_all_pids(self) -> Dict[str, Dict[str, Any]]:
        return self.learned_pids.copy()
    
    def get_pid(self, hex_code: str) -> Optional[Dict[str, Any]]:
        """Get a specific PID by hex code"""
        return self.learned_pids.get(hex_code.upper())
    
    def load_learned_pids(self):
        """Reload PIDs from directory"""
        self._load_pids()


# =============================================================================
#   HEADER DASHBOARD - UPDATED WITH LOGO
# =============================================================================

class HeaderDashboard(QFrame):
    """Professional header dashboard with status indicators and logo"""

    # Signal emitted when vehicle is changed
    vehicle_changed = Signal(str)  # profile_id

    # Signal emitted when voice command button is clicked
    voice_command_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HeaderDashboard")
        self.setFixedHeight(80)
        self._setup_ui()
        self._apply_style()
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(20)
        
        # App title with logo
        title_widget = QWidget()
        title_layout = QVBoxLayout(title_widget)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)
        
        # Try to load logo image
        logo_paths = [
            "predict_logo.png",
            "./predict_logo.png",
            os.path.join(os.path.dirname(__file__), "predict_logo.png"),
        ]
        
        logo_loaded = False
        for logo_path in logo_paths:
            if os.path.exists(logo_path):
                logo_pixmap = QPixmap(logo_path)
                if not logo_pixmap.isNull():
                    # Scale logo to appropriate height (40px)
                    logo_pixmap = logo_pixmap.scaledToHeight(40, Qt.SmoothTransformation)
                    
                    logo_label = QLabel()
                    logo_label.setPixmap(logo_pixmap)
                    title_layout.addWidget(logo_label)
                    logo_loaded = True
                    break
        
        # Fallback to text if logo not found
        if not logo_loaded:
            app_title = QLabel("PREDICT")
            app_title.setStyleSheet(f"""
                font-size: 24px;
                font-weight: 700;
                color: {ProfessionalTheme.PRIMARY};
                letter-spacing: 2px;
            """)
            title_layout.addWidget(app_title)
        
        # Add subtitle
        app_subtitle = QLabel("Professional Car AI")
        app_subtitle.setStyleSheet(f"""
            font-size: 11px;
            color: {ProfessionalTheme.TEXT_SECONDARY};
        """)
        title_layout.addWidget(app_subtitle)
        
        layout.addWidget(title_widget)
        
        layout.addStretch(1)
        
        # Connection status
        conn_widget = QWidget()
        conn_layout = QHBoxLayout(conn_widget)
        conn_layout.setContentsMargins(0, 0, 0, 0)
        conn_layout.setSpacing(10)
        
        self.connection_indicator = ConnectionIndicator()
        self.connection_label = QLabel("Disconnected")
        self.connection_label.setStyleSheet(f"color: {ProfessionalTheme.DANGER}; font-weight: 600;")
        
        conn_layout.addWidget(self.connection_indicator)
        conn_layout.addWidget(self.connection_label)
        layout.addWidget(conn_widget)
        
        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setStyleSheet(f"background-color: {ProfessionalTheme.BORDER};")
        layout.addWidget(sep1)
        
        # Active profile
        profile_widget = QWidget()
        profile_layout = QVBoxLayout(profile_widget)
        profile_layout.setContentsMargins(0, 0, 0, 0)
        profile_layout.setSpacing(2)
        
        profile_title = QLabel("Active Profile")
        profile_title.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 11px;
                padding: 0 5px;
            }
        """)
        
        self.profile_label = QLabel("None")
        self.profile_label.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                font-size: 13px;
                font-weight: bold;
                padding: 0 10px;
            }
        """)
        
        profile_layout.addWidget(profile_title)
        profile_layout.addWidget(self.profile_label)
        layout.addWidget(profile_widget)
        
        # Separator
        sep_profile = QFrame()
        sep_profile.setFrameShape(QFrame.VLine)
        sep_profile.setStyleSheet(f"background-color: {ProfessionalTheme.BORDER};")
        layout.addWidget(sep_profile)
        
        # Vehicle Switcher
        vehicle_widget = QWidget()
        vehicle_layout = QVBoxLayout(vehicle_widget)
        vehicle_layout.setContentsMargins(0, 0, 0, 0)
        vehicle_layout.setSpacing(2)
        
        vehicle_title = QLabel("Vehicle")
        vehicle_title.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 11px;
                padding: 0 5px;
            }
        """)
        
        self.vehicle_combo = QComboBox()
        self.vehicle_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {ProfessionalTheme.CARD_BG};
                color: {ProfessionalTheme.TEXT_PRIMARY};
                border: 1px solid {ProfessionalTheme.BORDER};
                border-radius: 4px;
                padding: 4px 8px;
                min-width: 150px;
                font-size: 12px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border: none;
                width: 10px;
                height: 10px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {ProfessionalTheme.CARD_BG};
                color: {ProfessionalTheme.TEXT_PRIMARY};
                selection-background-color: {ProfessionalTheme.PRIMARY};
                border: 1px solid {ProfessionalTheme.BORDER};
            }}
        """)
        self.vehicle_combo.addItem("No Vehicles")
        self.vehicle_combo.currentIndexChanged.connect(self._on_vehicle_changed)
        
        vehicle_layout.addWidget(vehicle_title)
        vehicle_layout.addWidget(self.vehicle_combo)
        layout.addWidget(vehicle_widget)
        
        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setStyleSheet(f"background-color: {ProfessionalTheme.BORDER};")
        layout.addWidget(sep2)
        
        # Data quality
        quality_widget = QWidget()
        quality_layout = QVBoxLayout(quality_widget)
        quality_layout.setContentsMargins(0, 0, 0, 0)
        quality_layout.setSpacing(2)
        
        quality_title = QLabel("Data Quality")
        quality_title.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 11px;
                padding: 0 5px;
            }
        """)
        
        self.quality_label = QLabel("---")
        self.quality_label.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                font-size: 13px;
                font-weight: bold;
                padding: 0 10px;
            }
        """)
        
        quality_layout.addWidget(quality_title)
        quality_layout.addWidget(self.quality_label)
        layout.addWidget(quality_widget)
        
        # Separator
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.VLine)
        sep3.setStyleSheet(f"background-color: {ProfessionalTheme.BORDER};")
        layout.addWidget(sep3)
        
        # AI Status
        ai_widget = QWidget()
        ai_layout = QVBoxLayout(ai_widget)
        ai_layout.setContentsMargins(0, 0, 0, 0)
        ai_layout.setSpacing(2)
        
        ai_title = QLabel("AI Engine")
        ai_title.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 11px;
                padding: 0 5px;
            }
        """)
        
        self.ai_label = QLabel("Ready")
        self.ai_label.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                font-size: 13px;
                font-weight: bold;
                padding: 0 10px;
            }
        """)
        
        ai_layout.addWidget(ai_title)
        ai_layout.addWidget(self.ai_label)
        layout.addWidget(ai_widget)
        
        # Separator
        sep_sync = QFrame()
        sep_sync.setFrameShape(QFrame.VLine)
        sep_sync.setStyleSheet(f"background-color: {ProfessionalTheme.BORDER};")
        layout.addWidget(sep_sync)
        
        # Sync Status
        sync_widget = QWidget()
        sync_layout = QVBoxLayout(sync_widget)
        sync_layout.setContentsMargins(0, 0, 0, 0)
        sync_layout.setSpacing(2)
        
        sync_title = QLabel("Sync Status")
        sync_title.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 11px;
                padding: 0 5px;
            }
        """)
        
        self.sync_label = QLabel("Not Syncing")
        self.sync_label.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                font-size: 13px;
                font-weight: bold;
                padding: 0 10px;
            }
        """)
        
        sync_layout.addWidget(sync_title)
        sync_layout.addWidget(self.sync_label)
        layout.addWidget(sync_widget)
        
        # Voice Command
        voice_widget = QWidget()
        voice_layout = QVBoxLayout(voice_widget)
        voice_layout.setContentsMargins(0, 0, 0, 0)
        voice_layout.setSpacing(2)
        
        voice_title = QLabel("Voice Command")
        voice_title.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 11px;
                padding: 0 5px;
            }
        """)
        
        # Voice button with microphone icon
        self.voice_btn = QToolButton()
        self.voice_btn.setFixedSize(40, 40)
        self.voice_btn.setStyleSheet(f"""
            QToolButton {{
                background-color: {ProfessionalTheme.CARD_BG};
                color: {ProfessionalTheme.TEXT_PRIMARY};
                border: 1px solid {ProfessionalTheme.BORDER};
                border-radius: 8px;
                font-size: 18px;
            }}
            QToolButton:hover {{
                background-color: {ProfessionalTheme.CARD_BG_HOVER};
                border-color: {ProfessionalTheme.BORDER_LIGHT};
            }}
            QToolButton:pressed {{
                background-color: {ProfessionalTheme.PRIMARY};
            }}
        """)
        self.voice_btn.setToolTip("Click to issue voice command")
        self.voice_btn.clicked.connect(self._emit_voice_command)
        
        # Voice status label
        self.voice_status_label = QLabel("Ready")
        self.voice_status_label.setStyleSheet("""
            QLabel {
                color: #4CAF50;
                font-size: 12px;
                font-weight: bold;
                padding: 0 10px;
            }
        """)
        
        voice_layout.addWidget(voice_title)
        voice_btn_layout = QHBoxLayout()
        voice_btn_layout.setContentsMargins(0, 0, 0, 0)
        voice_btn_layout.setSpacing(5)
        voice_btn_layout.addWidget(self.voice_btn)
        voice_btn_layout.addWidget(self.voice_status_label)
        voice_btn_layout.addStretch()
        voice_layout.addLayout(voice_btn_layout)
        layout.addWidget(voice_widget)
        
        # Voice separator
        sep_voice = QFrame()
        sep_voice.setFrameShape(QFrame.VLine)
        sep_voice.setStyleSheet(f"background-color: {ProfessionalTheme.BORDER};")
        layout.addWidget(sep_voice)
    
    def _apply_style(self):
        """Apply premium gradient style to header"""
        self.setStyleSheet(f"""
            #HeaderDashboard {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #21262D,
                    stop:1 #161B22
                );
                border-bottom: 2px solid {ProfessionalTheme.PRIMARY};
            }}
        """)
    
    def update_connection(self, status: str, label: str, conn_type: str = "unknown"):
        """Update connection status display"""
        # Convert ConnectionType enum to string if needed
        if hasattr(conn_type, 'value'):
            conn_type = conn_type.value
        elif hasattr(conn_type, 'name'):
            conn_type = conn_type.name
        
        self.connection_indicator.set_status(status, conn_type)
        self.connection_label.setText(label)
        
        if status == "connected":
            self.connection_label.setStyleSheet(f"color: {ProfessionalTheme.SUCCESS}; font-weight: 600;")
        elif status == "connecting":
            self.connection_label.setStyleSheet(f"color: {ProfessionalTheme.WARNING}; font-weight: 600;")
        else:
            self.connection_label.setStyleSheet(f"color: {ProfessionalTheme.DANGER}; font-weight: 600;")
    
    def update_profile(self, name: str):
        """Update active profile display"""
        self.profile_label.setText(name if name else "None")
        if name:
            self.profile_label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {ProfessionalTheme.PRIMARY};")
        else:
            self.profile_label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {ProfessionalTheme.TEXT_SECONDARY};")
    
    def update_quality(self, quality: int):
        """Update data quality indicator"""
        self.quality_label.setText(f"{quality}%")
        if quality >= 90:
            self.quality_label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {ProfessionalTheme.SUCCESS};")
        elif quality >= 70:
            self.quality_label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {ProfessionalTheme.WARNING};")
        else:
            self.quality_label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {ProfessionalTheme.DANGER};")
    
    def update_ai_status(self, status: str):
        """Update AI engine status"""
        self.ai_label.setText(status)
        if status.lower() in ["ready", "active", "analyzing"]:
            self.ai_label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {ProfessionalTheme.SUCCESS};")
        elif status.lower() in ["training", "loading"]:
            self.ai_label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {ProfessionalTheme.WARNING};")
        else:
            self.ai_label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {ProfessionalTheme.TEXT_SECONDARY};")



    def populate_vehicles(self, profiles: List[Dict[str, Any]]):
        """Populate vehicle switcher with available profiles"""
        self.vehicle_combo.blockSignals(True)
        self.vehicle_combo.clear()
        
        if not profiles:
            self.vehicle_combo.addItem("No Vehicles")
        else:
            self.vehicle_combo.addItem("Select Vehicle", None)
            for profile in profiles:
                profile_id = profile.get('profile_id', '')
                name = profile.get('name', 'Unknown')
                make = profile.get('make', '')
                model = profile.get('model', '')
                year = profile.get('year', '')
                
                # Format display text
                if make and model:
                    display_text = f"{name} ({year} {make} {model})"
                else:
                    display_text = name
                
                self.vehicle_combo.addItem(display_text, profile_id)
        
        self.vehicle_combo.blockSignals(False)
    
    def set_current_vehicle(self, profile_id: str):
        """Set currently selected vehicle"""
        self.vehicle_combo.blockSignals(True)
        for i in range(self.vehicle_combo.count()):
            if self.vehicle_combo.itemData(i) == profile_id:
                self.vehicle_combo.setCurrentIndex(i)
                break
        else:
            # Profile not found, select first item
            self.vehicle_combo.setCurrentIndex(0)
        self.vehicle_combo.blockSignals(False)
    
    def _on_vehicle_changed(self, index: int):
        """Handle vehicle selection change"""
        profile_id = self.vehicle_combo.itemData(index)
        if profile_id:
            self.vehicle_changed.emit(profile_id)

    def _emit_voice_command(self):
        """Emit voice command signal when button clicked"""
        self.voice_command_requested.emit()

    def update_sync_status(self, status: str, last_sync: str = None):
        """Update sync status indicator
        
        Args:
            status: Sync state - 'syncing', 'synced', 'error', 'disabled'
            last_sync: Last sync timestamp string (optional)
        """
        if status == 'syncing':
            self.sync_label.setText("Syncing...")
            self.sync_label.setStyleSheet(f"""
                QLabel {{
                    color: {ProfessionalTheme.WARNING};
                    font-size: 13px;
                    font-weight: bold;
                    padding: 0 10px;
                }}
            """)
        elif status == 'synced':
            if last_sync:
                time_str = last_sync
            else:
                time_str = "Just now"
            self.sync_label.setText(f"Synced {time_str}")
            self.sync_label.setStyleSheet(f"""
                QLabel {{
                    color: {ProfessionalTheme.SUCCESS};
                    font-size: 13px;
                    font-weight: bold;
                    padding: 0 10px;
                }}
            """)
        elif status == 'error':
            self.sync_label.setText("Sync Error")
            self.sync_label.setStyleSheet(f"""
                QLabel {{
                    color: {ProfessionalTheme.DANGER};
                    font-size: 13px;
                    font-weight: bold;
                    padding: 0 10px;
                }}
            """)
        else:  # disabled
            self.sync_label.setText("Not Syncing")
            self.sync_label.setStyleSheet(f"""
                QLabel {{
                    color: {ProfessionalTheme.TEXT_SECONDARY};
                    font-size: 13px;
                    font-weight: bold;
                    padding: 0 10px;
                }}
            """)


# =============================================================================
#   FAILURE FORECAST TAB - ENHANCED
# =============================================================================

class CollapsiblePanel(QWidget):
    """Collapsible panel for expandable UI sections"""

    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.is_expanded = False
        self._setup_ui(title)

    def _setup_ui(self, title):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header button
        self.header_btn = QPushButton(f"▶ {title}")
        self.header_btn.setStyleSheet(self._get_button_style('secondary'))
        self.header_btn.clicked.connect(self._toggle)
        layout.addWidget(self.header_btn)

        # Content area (hidden by default)
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(15, 10, 15, 10)
        self.content_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {ProfessionalTheme.BACKGROUND_SECONDARY};
                border: 1px solid {ProfessionalTheme.BORDER};
                border-top: none;
                border-bottom-left-radius: 5px;
                border-bottom-right-radius: 5px;
            }}
        """)
        self.content_widget.setVisible(False)
        layout.addWidget(self.content_widget)

    def _toggle(self):
        """Toggle panel expansion"""
        self.is_expanded = not self.is_expanded
        self.content_widget.setVisible(self.is_expanded)

        # Update arrow icon
        title_text = self.header_btn.text()[2:]  # Remove arrow
        icon = "▼" if self.is_expanded else "▶"
        self.header_btn.setText(f"{icon} {title_text}")

    def add_widget(self, widget):
        """Add a widget to the content area"""
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        """Add a layout to the content area"""
        self.content_layout.addLayout(layout)

    def _get_button_style(self, style_type: str = 'primary') -> str:
        """Get consistent button style based on type."""
        styles = {
            'primary': """
                QPushButton {
                    background-color: #C40000;
                    color: #F0F6FC;
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
                    background-color: #B71C1C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
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
                QPushButton:pressed {
                    background-color: #161B22;
                }
            """,
            'danger': """
                QPushButton {
                    background-color: #DA3633;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #F85149;
                }
                QPushButton:pressed {
                    background-color: #B62324;
                }
            """,
            'success': """
                QPushButton {
                    background-color: #238636;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #2EA043;
                }
                QPushButton:pressed {
                    background-color: #196C2E;
                }
            """
        }
        return styles.get(style_type, styles['primary'])


class FailureForecastTab(QWidget):
    """Enhanced Failure Forecast dashboard with AI integration"""

    def __init__(self, predictive_engine: PredictiveFailureEngine,
                 unified_ai: UnifiedAIModule,
                 get_active_profile: Callable,
                 get_latest_snapshot: Callable,
                 get_recent_history: Callable,
                 parent=None):
        super().__init__(parent)
        self.engine = predictive_engine
        self.unified_ai = unified_ai
        self.get_active_profile = get_active_profile
        self.get_latest_snapshot = get_latest_snapshot
        self.get_recent_history = get_recent_history

        # Component predictor for brake/oil/battery predictions
        if ComponentPredictor is not None:
            self.component_predictor = ComponentPredictor()
        else:
            self.component_predictor = None

        self.history_buffer = deque(maxlen=200)
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # Header
        header = QHBoxLayout()
        
        title = QLabel("Failure Forecast (3-7 Days)")
        title.setStyleSheet(f"""
            font-size: 18px;
            font-weight: 700;
            color: {ProfessionalTheme.TEXT_PRIMARY};
        """)
        
        self.vehicle_label = QLabel("Vehicle: None")
        self.vehicle_label.setStyleSheet(f"color: {ProfessionalTheme.TEXT_SECONDARY};")
        
        self.refresh_btn = QPushButton("⟳ Refresh Forecast")
        self.refresh_btn.setStyleSheet(self._get_button_style('primary'))
        self.refresh_btn.clicked.connect(self.refresh_forecast)
        
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.vehicle_label)
        header.addSpacing(20)
        header.addWidget(self.refresh_btn)
        layout.addLayout(header)
        
        # Overall Risk Card
        risk_card = QFrame()
        risk_card.setStyleSheet(f"""
            QFrame {{
                background-color: {ProfessionalTheme.CARD_BG};
                border: 1px solid {ProfessionalTheme.BORDER};
                border-radius: 12px;
                padding: 20px;
            }}
        """)
        risk_layout = QHBoxLayout(risk_card)
        
        # Risk indicator
        risk_left = QVBoxLayout()
        self.risk_status = QLabel("NORMAL")
        self.risk_status.setStyleSheet(f"""
            font-size: 24px;
            font-weight: 700;
            color: {ProfessionalTheme.SUCCESS};
        """)
        self.risk_desc = QLabel("All systems operating within normal parameters")
        self.risk_desc.setStyleSheet(f"color: {ProfessionalTheme.TEXT_SECONDARY};")
        risk_left.addWidget(self.risk_status)
        risk_left.addWidget(self.risk_desc)
        
        risk_right = QHBoxLayout()
        risk_right.setSpacing(30)
        
        # Score
        score_box = QVBoxLayout()
        self.score_value = QLabel("--")
        self.score_value.setStyleSheet(f"font-size: 28px; font-weight: 700; color: {ProfessionalTheme.TEXT_PRIMARY};")
        score_label = QLabel("Risk Score")
        score_label.setStyleSheet(f"color: {ProfessionalTheme.TEXT_MUTED}; font-size: 11px;")
        score_box.addWidget(self.score_value, 0, Qt.AlignCenter)
        score_box.addWidget(score_label, 0, Qt.AlignCenter)
        
        # Probability
        prob_box = QVBoxLayout()
        self.prob_value = QLabel("--%")
        self.prob_value.setStyleSheet(f"font-size: 28px; font-weight: 700; color: {ProfessionalTheme.TEXT_PRIMARY};")
        prob_label = QLabel("Probability")
        prob_label.setStyleSheet(f"color: {ProfessionalTheme.TEXT_MUTED}; font-size: 11px;")
        prob_box.addWidget(self.prob_value, 0, Qt.AlignCenter)
        prob_box.addWidget(prob_label, 0, Qt.AlignCenter)
        
        # Horizon
        horizon_box = QVBoxLayout()
        self.horizon_value = QLabel("3-7")
        self.horizon_value.setStyleSheet(f"font-size: 28px; font-weight: 700; color: {ProfessionalTheme.TEXT_PRIMARY};")
        horizon_label = QLabel("Days Horizon")
        horizon_label.setStyleSheet(f"color: {ProfessionalTheme.TEXT_MUTED}; font-size: 11px;")
        horizon_box.addWidget(self.horizon_value, 0, Qt.AlignCenter)
        horizon_box.addWidget(horizon_label, 0, Qt.AlignCenter)
        
        risk_right.addLayout(score_box)
        risk_right.addLayout(prob_box)
        risk_right.addLayout(horizon_box)
        
        risk_layout.addLayout(risk_left, 2)
        risk_layout.addLayout(risk_right, 1)
        layout.addWidget(risk_card)
        
        # Main content splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Left: Component table
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        table_group = QGroupBox("Component Risk Analysis")
        table_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 13px;
                color: {ProfessionalTheme.PRIMARY};
                background-color: {ProfessionalTheme.CARD_BG};
                border: 1px solid {ProfessionalTheme.BORDER};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 8px;
                background-color: {ProfessionalTheme.CARD_BG};
            }}
        """)
        table_layout = QVBoxLayout(table_group)
        
        self.component_table = QTableWidget()
        self.component_table.setColumnCount(5)
        self.component_table.setHorizontalHeaderLabels([
            "Component", "Risk Level", "Probability", "Horizon", "Key Signal"
        ])
        self.component_table.horizontalHeader().setStretchLastSection(True)
        self.component_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.component_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.component_table.setAlternatingRowColors(True)
        self.component_table.verticalHeader().setVisible(False)
        # Apply consistent table styling
        self._apply_table_styling(self.component_table)
        
        table_layout.addWidget(self.component_table)
        left_layout.addWidget(table_group)
        splitter.addWidget(left)
        
        # Right: 3-Layer Predictions Display
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # LAYER 1: Driver Summary (Always Visible)
        layer1_group = QGroupBox("Prediction Summary (Driver-Friendly)")
        layer1_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 13px;
                color: {ProfessionalTheme.SUCCESS};
                background-color: {ProfessionalTheme.CARD_BG};
                border: 1px solid {ProfessionalTheme.BORDER};
                border-radius: 8px;
                padding: 12px;
                margin-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 8px;
                background-color: {ProfessionalTheme.CARD_BG};
            }}
        """)
        layer1_layout = QVBoxLayout(layer1_group)

        # Issue
        self.layer1_issue = QLabel("Issue: Waiting for data...")
        self.layer1_issue.setWordWrap(True)
        self.layer1_issue.setStyleSheet(f"font-size: 13px; color: {ProfessionalTheme.TEXT_PRIMARY};")
        layer1_layout.addWidget(self.layer1_issue)

        # Risk Level
        self.layer1_risk = QLabel("Risk Level: -")
        self.layer1_risk.setStyleSheet(f"font-size: 12px; color: {ProfessionalTheme.TEXT_SECONDARY};")
        layer1_layout.addWidget(self.layer1_risk)

        # Confidence
        self.layer1_confidence = QLabel("Confidence: --%")
        self.layer1_confidence.setStyleSheet(f"font-size: 12px; color: {ProfessionalTheme.TEXT_SECONDARY};")
        layer1_layout.addWidget(self.layer1_confidence)

        # Recommendation
        self.layer1_recommendation = QLabel("Recommendation: -")
        self.layer1_recommendation.setWordWrap(True)
        self.layer1_recommendation.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {ProfessionalTheme.SUCCESS};")
        layer1_layout.addWidget(self.layer1_recommendation)

        right_layout.addWidget(layer1_group)

        # LAYER 2: Technical Summary (Collapsible)
        self.layer2_panel = CollapsiblePanel("🔧 Technical Details (Mechanic View)")

        # Sensor Deviations
        self.layer2_deviations = QLabel("Sensor Deviations: None detected")
        self.layer2_deviations.setWordWrap(True)
        self.layer2_deviations.setStyleSheet(f"font-size: 12px; color: {ProfessionalTheme.TEXT_PRIMARY}; margin-bottom: 10px;")
        self.layer2_panel.add_widget(self.layer2_deviations)

        # Trend Explanation
        self.layer2_trends = QLabel("Trend: No significant trends")
        self.layer2_trends.setWordWrap(True)
        self.layer2_trends.setStyleSheet(f"font-size: 12px; color: {ProfessionalTheme.TEXT_SECONDARY}; margin-bottom: 10px;")
        self.layer2_panel.add_widget(self.layer2_trends)

        # Fleet Cases
        self.layer2_fleet = QLabel("Fleet Cases: No similar cases found")
        self.layer2_fleet.setWordWrap(True)
        self.layer2_fleet.setStyleSheet(f"font-size: 12px; color: {ProfessionalTheme.TEXT_SECONDARY};")
        self.layer2_panel.add_widget(self.layer2_fleet)

        right_layout.addWidget(self.layer2_panel)

        # LAYER 3: Deep AI Detail (Collapsible)
        self.layer3_panel = CollapsiblePanel("🧠 Deep AI Reasoning (Advanced)")

        # Signals Involved
        self.layer3_signals = QLabel("Signals: None analyzed")
        self.layer3_signals.setWordWrap(True)
        self.layer3_signals.setStyleSheet(f"font-size: 11px; color: {ProfessionalTheme.TEXT_MUTED}; margin-bottom: 10px;")
        self.layer3_panel.add_widget(self.layer3_signals)

        # Correlation Logic
        self.layer3_correlations = QLabel("Correlations: No correlations detected")
        self.layer3_correlations.setWordWrap(True)
        self.layer3_correlations.setStyleSheet(f"font-size: 11px; color: {ProfessionalTheme.TEXT_MUTED}; margin-bottom: 10px;")
        self.layer3_panel.add_widget(self.layer3_correlations)

        # Data Limitations
        self.layer3_limitations = QLabel("⚠️ Data Limitations: Limited baseline (need 7+ days of driving data)")
        self.layer3_limitations.setWordWrap(True)
        self.layer3_limitations.setStyleSheet(f"font-size: 11px; color: {ProfessionalTheme.WARNING}; font-weight: bold;")
        self.layer3_panel.add_widget(self.layer3_limitations)

        right_layout.addWidget(self.layer3_panel)
        right_layout.addStretch()
        
        splitter.addWidget(right)
        splitter.setSizes([550, 450])
        layout.addWidget(splitter, 1)
    
    def refresh_forecast(self):
        """Refresh failure forecast analysis"""
        try:
            profile = self.get_active_profile() or {}
            latest = self.get_latest_snapshot() or {}
            
            # Update history buffer
            if latest:
                self.history_buffer.append({
                    'timestamp': datetime.now(),
                    'data': latest
                })
            
            history = [e['data'] for e in self.history_buffer]
            
            # Update vehicle label
            name = profile.get('name', 'Unknown') if profile else 'No Profile'
            self.vehicle_label.setText(f"Vehicle: {name}")
            
            if not latest:
                self._show_no_data()
                return
            
            # Get prediction from engine
            result = self.engine.analyze_failure_risk(
                vehicle_profile=profile,
                latest_data=latest,
                history=history,
                horizon_days=(3, 7)
            )

            # Get component-specific predictions (brake, oil, battery)
            component_results = {}
            try:
                if self.component_predictor is not None:
                    component_results = self.component_predictor.predict_all(history)
            except Exception as comp_err:
                logger.warning(f"Component predictions failed: {comp_err}")

            # Also get unified AI insights
            try:
                ai_dashboard = self.unified_ai.get_dashboard_summary(
                    vehicle_profile=profile,
                    latest_data=latest,
                    history=history
                )
                ai_insights = self.unified_ai.generate_comprehensive_insights(ai_dashboard)
            except Exception:
                ai_insights = {}

            self._update_display(result, ai_insights, component_results)
            
        except Exception as e:
            logger.error(f"Forecast error: {e}")
            show_error(self, "Forecast Error", f"Failed to generate forecast:\n{e}")
    
    def _show_no_data(self):
        """Show no data message"""
        self.risk_status.setText("NO DATA")
        self.risk_status.setStyleSheet(f"font-size: 24px; font-weight: 700; color: {ProfessionalTheme.TEXT_MUTED};")
        self.risk_desc.setText("Connect to vehicle and start live data to generate forecast")
        self.score_value.setText("--")
        self.prob_value.setText("--%")
        self.component_table.setRowCount(0)
        self.actions_text.setPlainText("No data available for analysis.")
        self.insights_text.setPlainText("Connect to vehicle to generate AI insights.")
    
    def _update_display(self, result: Dict, ai_insights: Dict, component_results: Dict = None):
        """Update UI with forecast results"""
        risk_assessment = result.get('risk_assessment', {})
        predictions = result.get('failure_predictions', {})
        expert_insights = result.get('expert_insights', [])

        # Merge component predictions (brake, oil, battery) into display
        if component_results and component_results.get('components'):
            for comp_name, comp_data in component_results['components'].items():
                # Convert to the format expected by the table
                severity = comp_data.get('severity', 'normal')
                risk_level = {'critical': 'CRITICAL', 'warning': 'HIGH', 'normal': 'LOW'}.get(severity, 'LOW')

                # Calculate probability from remaining life
                remaining = comp_data.get('remaining_life_percent', comp_data.get('state_of_health', 100))
                probability = max(0, min(1, (100 - remaining) / 100))

                # Get failure window
                window = comp_data.get('failure_window_days', comp_data.get('days_until_change', comp_data.get('remaining_months', (30, 60))))
                if isinstance(window, tuple):
                    horizon = list(window)
                else:
                    horizon = [30, 60]

                predictions[comp_name] = {
                    'risk_level': risk_level,
                    'probability': probability,
                    'horizon_days': horizon,
                    'signals': [comp_data.get('recommendation', 'Monitor condition')],
                    'recommended_actions': [comp_data.get('recommendation', '')]
                }
        
        # Update overall risk
        overall = risk_assessment.get('overall_risk', 'NORMAL')
        score = risk_assessment.get('score', 0)
        probability = risk_assessment.get('probability', 0.0)
        
        self.risk_status.setText(overall)
        self.score_value.setText(str(score))
        self.prob_value.setText(f"{probability:.0%}")
        
        # Set colors based on risk level
        if 'CRITICAL' in overall.upper():
            color = ProfessionalTheme.GAUGE_CRITICAL  # Predict Red
            self.risk_desc.setText("Critical issues detected - immediate attention required")
        elif 'HIGH' in overall.upper() or 'WARNING' in overall.upper():
            color = ProfessionalTheme.WARNING
            self.risk_desc.setText("High risk indicators detected - schedule service soon")
        elif 'MEDIUM' in overall.upper() or 'ALERT' in overall.upper():
            color = ProfessionalTheme.WARNING
            self.risk_desc.setText("Moderate risk - monitor closely")
        else:
            color = ProfessionalTheme.SUCCESS
            self.risk_desc.setText("All systems operating within normal parameters")
        
        self.risk_status.setStyleSheet(f"font-size: 24px; font-weight: 700; color: {color};")
        
        # Update component table
        self.component_table.setRowCount(len(predictions))
        row = 0
        for component, data in predictions.items():
            name = component.replace('_', ' ').title()
            risk_level = data.get('risk_level', 'LOW')
            prob = data.get('probability', 0.0)
            horizon = data.get('horizon_days', [3, 7])
            signals = data.get('signals', [])
            key_signal = signals[0] if signals else "No significant signals"
            
            self.component_table.setItem(row, 0, QTableWidgetItem(name))
            
            risk_item = QTableWidgetItem(risk_level)
            if risk_level == 'CRITICAL':
                risk_item.setBackground(QColor(ProfessionalTheme.GAUGE_CRITICAL))
            elif risk_level == 'HIGH':
                risk_item.setBackground(QColor(ProfessionalTheme.WARNING))
            elif risk_level == 'MEDIUM':
                risk_item.setBackground(QColor("#665000"))
            else:
                risk_item.setBackground(QColor(ProfessionalTheme.SUCCESS))
            self.component_table.setItem(row, 1, risk_item)
            
            self.component_table.setItem(row, 2, QTableWidgetItem(f"{prob:.0%}"))
            self.component_table.setItem(row, 3, QTableWidgetItem(f"{horizon[0]}-{horizon[1]} days"))
            self.component_table.setItem(row, 4, QTableWidgetItem(key_signal[:60] + "..." if len(key_signal) > 60 else key_signal))
            
            row += 1
        
        self.component_table.resizeColumnsToContents()
        
        # Update actions
        all_actions = set()
        for data in predictions.values():
            all_actions.update(data.get('recommended_actions', []))
        
        if all_actions:
            actions = "Recommended Actions:\n\n" + "\n".join(f"• {a}" for a in sorted(all_actions))
        else:
            actions = "No specific actions recommended.\nContinue regular maintenance schedule."
        self.actions_text.setPlainText(actions)
        
        # Update insights (combine engine insights with unified AI)
        insights_lines = []
        if expert_insights:
            insights_lines.extend([f"• {i}" for i in expert_insights])
        
        if ai_insights:
            if ai_insights.get('health_overview'):
                insights_lines.append(f"\nHealth: {ai_insights['health_overview']}")
            if ai_insights.get('maintenance_priority'):
                insights_lines.append(f"\nPriority: {ai_insights['maintenance_priority']}")
        
        self.insights_text.setPlainText("\n".join(insights_lines) if insights_lines else "No specific insights available.")

        # UPDATE 3-LAYER PREDICTIONS DISPLAY
        self._update_3layer_display(result, ai_insights, predictions)

    def _update_3layer_display(self, result: Dict, ai_insights: Dict, predictions: Dict):
        """Update the 3-layer predictions display"""
        risk_assessment = result.get('risk_assessment', {})
        overall_risk = risk_assessment.get('overall_risk', 'NORMAL')
        probability = risk_assessment.get('probability', 0.0)

        # LAYER 1: Driver Summary
        if overall_risk == 'CRITICAL' or 'CRITICAL' in overall_risk:
            issue_text = "⚠️ Critical Issue Detected - Immediate attention required"
            risk_color = ProfessionalTheme.DANGER
        elif overall_risk == 'HIGH' or 'HIGH' in overall_risk:
            issue_text = "⚠️ High Risk Detected - Schedule service soon"
            risk_color = ProfessionalTheme.WARNING
        elif overall_risk == 'MEDIUM' or 'MEDIUM' in overall_risk:
            issue_text = "🔔 Moderate Risk - Monitor vehicle closely"
            risk_color = ProfessionalTheme.WARNING
        else:
            issue_text = "✅ All Systems Normal - Vehicle is healthy"
            risk_color = ProfessionalTheme.SUCCESS

        self.layer1_issue.setText(f"Issue: {issue_text}")
        self.layer1_issue.setStyleSheet(f"font-size: 13px; color: {risk_color}; font-weight: bold;")

        self.layer1_risk.setText(f"Risk Level: {overall_risk}")
        self.layer1_risk.setStyleSheet(f"font-size: 12px; color: {ProfessionalTheme.TEXT_SECONDARY};")

        # Calculate confidence (inverse of uncertainty)
        confidence = int(probability * 100) if probability > 0 else 0
        self.layer1_confidence.setText(f"Confidence: {confidence}% (based on {len(self.history_buffer)} data points)")
        self.layer1_confidence.setStyleSheet(f"font-size: 12px; color: {ProfessionalTheme.TEXT_SECONDARY};")

        # Recommendation
        if overall_risk == 'CRITICAL' or 'CRITICAL' in overall_risk:
            recommendation = "🔴 Stop driving and seek immediate service"
        elif overall_risk == 'HIGH' or 'HIGH' in overall_risk:
            recommendation = "🟡 Schedule service within 1-2 days"
        elif overall_risk == 'MEDIUM' or 'MEDIUM' in overall_risk:
            recommendation = "🟢 Monitor and schedule service within a week"
        else:
            recommendation = "✅ Continue normal driving, follow regular maintenance"

        self.layer1_recommendation.setText(f"Recommendation: {recommendation}")

        # LAYER 2: Technical Summary
        # Sensor Deviations
        deviations = []
        for component, data in predictions.items():
            signals = data.get('signals', [])
            if signals:
                deviations.extend(signals[:2])  # Top 2 signals per component

        if deviations:
            deviations_text = f"🔧 Sensor Deviations:\n" + "\n".join(f"  • {dev}" for dev in deviations[:5])
        else:
            deviations_text = "✅ No significant sensor deviations detected"

        self.layer2_deviations.setText(deviations_text)

        # Trend Explanation
        if len(self.history_buffer) > 20:
            trend_text = f"📈 Trend: Based on {len(self.history_buffer)} data points over recent driving sessions, "
            if overall_risk == 'CRITICAL' or 'CRITICAL' in overall_risk:
                trend_text += "critical degradation detected in key systems"
            elif overall_risk == 'HIGH' or 'HIGH' in overall_risk:
                trend_text += "progressive degradation detected"
            else:
                trend_text += "systems are stable with normal variations"
        else:
            trend_text = f"⏳ Limited trend data ({len(self.history_buffer)} points) - need 20+ for accurate trending"

        self.layer2_trends.setText(trend_text)

        # Fleet Cases
        fleet_text = "🚗 Fleet Cases: Fleet learning not yet available (future feature)"
        self.layer2_fleet.setText(fleet_text)

        # LAYER 3: Deep AI Detail
        # Signals Involved
        all_signals = set()
        for data in predictions.values():
            all_signals.update(data.get('signals', []))

        if all_signals:
            signals_text = f"📊 Signals Analyzed:\n" + "\n".join(f"  • {sig}" for sig in list(all_signals)[:8])
        else:
            signals_text = "📊 Signals: No specific signals flagged"

        self.layer3_signals.setText(signals_text)

        # Correlation Logic
        correlations_text = f"🔗 Correlations: Analyzing {len(predictions)} component(s) with {len(all_signals)} signal(s)"
        self.layer3_correlations.setText(correlations_text)

        # Data Limitations
        baseline_days = len(self.history_buffer) / 10  # Rough estimate (10 samples per day)
        if baseline_days < 7:
            limitations_text = f"⚠️ Data Limitations: Limited baseline ({baseline_days:.1f} days of data, need 7+ days for full accuracy)"
            limitations_color = ProfessionalTheme.WARNING
        elif baseline_days < 14:
            limitations_text = f"📊 Data Quality: Moderate baseline ({baseline_days:.1f} days of data, 14+ days recommended)"
            limitations_color = ProfessionalTheme.INFO
        else:
            limitations_text = f"✅ Data Quality: Strong baseline ({baseline_days:.1f} days of data)"
            limitations_color = ProfessionalTheme.SUCCESS

        self.layer3_limitations.setText(limitations_text)
        self.layer3_limitations.setStyleSheet(f"font-size: 11px; color: {limitations_color}; font-weight: bold;")

    def update_live_data(self, snapshot: Dict):
        """Update with new live data"""
        if snapshot:
            self.history_buffer.append({
                'timestamp': datetime.now(),
                'data': snapshot
            })

    def _get_button_style(self, style_type: str = 'primary') -> str:
        """Get consistent button style based on type."""
        styles = {
            'primary': """
                QPushButton {
                    background-color: #C40000;
                    color: #F0F6FC;
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
                    background-color: #B71C1C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
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
                QPushButton:pressed {
                    background-color: #161B22;
                }
            """,
            'danger': """
                QPushButton {
                    background-color: #DA3633;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #F85149;
                }
                QPushButton:pressed {
                    background-color: #B62324;
                }
            """,
            'success': """
                QPushButton {
                    background-color: #238636;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #2EA043;
                }
                QPushButton:pressed {
                    background-color: #196C2E;
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


# =============================================================================
#   EDIT VEHICLE DIALOG - COMPREHENSIVE VEHICLE PROFILE EDITING
# =============================================================================

class EditVehicleDialog(QDialog):
    """Comprehensive vehicle profile edit dialog with all fields."""

    def __init__(self, vehicle_data: dict, parent=None):
        super().__init__(parent)
        self.vehicle_data = vehicle_data
        self.setWindowTitle("Edit Vehicle Profile")
        self.setMinimumWidth(450)
        self.setMinimumHeight(500)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setSpacing(8)

        # Vehicle Name
        self.name_edit = QLineEdit(self.vehicle_data.get('name', ''))
        form_layout.addRow("Name:", self.name_edit)

        # Make
        self.make_edit = QLineEdit(self.vehicle_data.get('make', ''))
        form_layout.addRow("Make:", self.make_edit)

        # Model
        self.model_edit = QLineEdit(self.vehicle_data.get('model', ''))
        form_layout.addRow("Model:", self.model_edit)

        # Year
        self.year_spin = QSpinBox()
        self.year_spin.setRange(1900, 2030)
        self.year_spin.setValue(int(self.vehicle_data.get('year', 0)) if self.vehicle_data.get('year') else 2024)
        form_layout.addRow("Year:", self.year_spin)

        # VIN
        self.vin_edit = QLineEdit(self.vehicle_data.get('vin', ''))
        form_layout.addRow("VIN:", self.vin_edit)

        # License Plate
        self.plate_edit = QLineEdit(self.vehicle_data.get('license_plate', ''))
        form_layout.addRow("License Plate:", self.plate_edit)

        # Separator
        separator = QLabel("— Engine & Drivetrain —")
        separator.setStyleSheet(f"color: {ProfessionalTheme.TEXT_SECONDARY}; font-weight: bold; padding: 8px 0 4px 0;")
        form_layout.addRow(separator)

        # Engine Type
        self.engine_type_combo = QComboBox()
        self.engine_type_combo.addItems(["", "I3", "I4", "V6", "V8", "V10", "V12", "Electric", "Hybrid", "Rotary"])
        current_engine = self.vehicle_data.get('engine_type', '')
        idx = self.engine_type_combo.findText(current_engine)
        if idx >= 0:
            self.engine_type_combo.setCurrentIndex(idx)
        form_layout.addRow("Engine Type:", self.engine_type_combo)

        # Cylinders
        self.cylinders_spin = QSpinBox()
        self.cylinders_spin.setRange(0, 16)
        self.cylinders_spin.setSpecialValueText("—")
        cyl = self.vehicle_data.get('cylinders')
        if cyl:
            self.cylinders_spin.setValue(int(cyl))
        form_layout.addRow("Cylinders:", self.cylinders_spin)

        # Displacement
        self.displacement_combo = QComboBox()
        self.displacement_combo.addItems(["", "1.0L", "1.2L", "1.4L", "1.5L", "1.6L", "1.8L",
            "2.0L", "2.4L", "2.5L", "2.7L", "3.0L", "3.5L", "3.8L", "4.0L", "4.7L",
            "5.0L", "5.6L", "5.7L", "6.0L", "6.2L", "6.7L"])
        current_disp = self.vehicle_data.get('displacement', '')
        idx = self.displacement_combo.findText(current_disp)
        if idx >= 0:
            self.displacement_combo.setCurrentIndex(idx)
        form_layout.addRow("Displacement:", self.displacement_combo)

        # Fuel Type
        self.fuel_type_combo = QComboBox()
        self.fuel_type_combo.addItems(["", "Gasoline", "Diesel", "Electric", "Hybrid", "Plug-in Hybrid", "LPG/CNG"])
        current_fuel = self.vehicle_data.get('fuel_type', '')
        idx = self.fuel_type_combo.findText(current_fuel)
        if idx >= 0:
            self.fuel_type_combo.setCurrentIndex(idx)
        form_layout.addRow("Fuel Type:", self.fuel_type_combo)

        # Transmission
        self.transmission_combo = QComboBox()
        self.transmission_combo.addItems(["", "Automatic", "Manual", "CVT", "DCT (Dual Clutch)"])
        current_trans = self.vehicle_data.get('transmission', '')
        idx = self.transmission_combo.findText(current_trans)
        if idx >= 0:
            self.transmission_combo.setCurrentIndex(idx)
        form_layout.addRow("Transmission:", self.transmission_combo)

        # Drivetrain
        self.drivetrain_combo = QComboBox()
        self.drivetrain_combo.addItems(["", "FWD", "RWD", "AWD", "4WD"])
        current_drive = self.vehicle_data.get('drivetrain', '')
        idx = self.drivetrain_combo.findText(current_drive)
        if idx >= 0:
            self.drivetrain_combo.setCurrentIndex(idx)
        form_layout.addRow("Drivetrain:", self.drivetrain_combo)

        # Separator
        separator2 = QLabel("— Other —")
        separator2.setStyleSheet(f"color: {ProfessionalTheme.TEXT_SECONDARY}; font-weight: bold; padding: 8px 0 4px 0;")
        form_layout.addRow(separator2)

        # Color
        self.color_edit = QLineEdit(self.vehicle_data.get('color', ''))
        form_layout.addRow("Color:", self.color_edit)

        # Category
        self.category_combo = QComboBox()
        self.category_combo.addItems(["Personal", "Work", "Fleet", "Rental", "Other"])
        current_cat = self.vehicle_data.get('category', 'Personal')
        idx = self.category_combo.findText(current_cat)
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)
        form_layout.addRow("Category:", self.category_combo)

        scroll.setWidget(form_widget)
        layout.addWidget(scroll, 1)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save Changes")
        save_btn.setStyleSheet(f"background-color: {ProfessionalTheme.PRIMARY}; color: white; font-weight: bold;")
        save_btn.clicked.connect(self.accept)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

    def get_updated_data(self) -> dict:
        """Return updated profile data dict."""
        data = dict(self.vehicle_data)  # Start with existing data
        data['name'] = self.name_edit.text().strip()
        data['make'] = self.make_edit.text().strip()
        data['model'] = self.model_edit.text().strip()
        data['year'] = self.year_spin.value()
        data['vin'] = self.vin_edit.text().strip().upper()
        data['license_plate'] = self.plate_edit.text().strip().upper()
        data['engine_type'] = self.engine_type_combo.currentText()
        data['cylinders'] = self.cylinders_spin.value() if self.cylinders_spin.value() > 0 else None
        data['displacement'] = self.displacement_combo.currentText()
        data['fuel_type'] = self.fuel_type_combo.currentText()
        data['transmission'] = self.transmission_combo.currentText()
        data['drivetrain'] = self.drivetrain_combo.currentText()
        data['color'] = self.color_edit.text().strip()
        data['category'] = self.category_combo.currentText()
        return data


# =============================================================================
#   ADD PROFILE DIALOG - COMPREHENSIVE VEHICLE PROFILE CREATION
# =============================================================================

class AddProfileDialog(QDialog):
    """
    Comprehensive dialog for adding a new vehicle profile.
    Uses the vehicle catalog for brand/model/year selection.
    """
    
    def __init__(self, vehicle_catalog=None, connectivity_manager=None, vehicle_manager=None, parent=None):
        super().__init__(parent)
        self.vehicle_catalog = vehicle_catalog
        self.connectivity_manager = connectivity_manager
        self.vehicle_manager = vehicle_manager
        self.profile_data = None

        self.setWindowTitle("Add New Vehicle Profile")
        self.setMinimumWidth(500)
        self.setMinimumHeight(600)

        self._setup_ui()
        self._load_catalog_data()
        self._load_owners()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Create New Vehicle Profile")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {ProfessionalTheme.PRIMARY};")
        layout.addWidget(title)
        
        # Form scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(Qt.AlignRight)
        
        # Owner Selection Section
        owner_group = QGroupBox("Owner Assignment")
        owner_layout = QFormLayout(owner_group)

        self.owner_combo = QComboBox()
        self.owner_combo.addItem("-- No Owner --", None)
        self.owner_combo.addItem("+ Create New Owner...", "new")
        owner_layout.addRow("Assign to Owner:", self.owner_combo)

        form_layout.addRow(owner_group)

        # Customer Information Section
        customer_group = QGroupBox("Customer Information")
        customer_layout = QFormLayout(customer_group)

        self.customer_name_edit = QLineEdit()
        self.customer_name_edit.setPlaceholderText("Enter customer name")
        customer_layout.addRow("Customer Name:", self.customer_name_edit)

        self.profile_name_edit = QLineEdit()
        self.profile_name_edit.setPlaceholderText("Enter profile name (e.g., John's Altima)")
        customer_layout.addRow("Profile Name:", self.profile_name_edit)

        # Customer contact info (for registration system)
        self.customer_phone_edit = QLineEdit()
        self.customer_phone_edit.setPlaceholderText("Phone number (e.g., +971501234567)")
        customer_layout.addRow("Phone:", self.customer_phone_edit)

        self.customer_email_edit = QLineEdit()
        self.customer_email_edit.setPlaceholderText("Email address (optional)")
        customer_layout.addRow("Email:", self.customer_email_edit)

        form_layout.addRow(customer_group)
        
        # Vehicle Information Section
        vehicle_group = QGroupBox("Vehicle Information")
        vehicle_layout = QFormLayout(vehicle_group)
        
        # Brand/Manufacturer dropdown
        self.brand_combo = QComboBox()
        self.brand_combo.setEditable(True)
        self.brand_combo.addItem("-- Select Manufacturer --")
        self.brand_combo.currentTextChanged.connect(self._on_brand_changed)
        vehicle_layout.addRow("Manufacturer:", self.brand_combo)
        
        # Model dropdown
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.addItem("-- Select Model --")
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        self.model_combo.setEnabled(False)
        vehicle_layout.addRow("Model:", self.model_combo)
        
        # Year dropdown
        self.year_combo = QComboBox()
        self.year_combo.setEditable(True)
        self.year_combo.addItem("-- Select Year --")
        self.year_combo.setEnabled(False)
        vehicle_layout.addRow("Year:", self.year_combo)
        
        # Submodel/Variant (optional)
        self.submodel_combo = QComboBox()
        self.submodel_combo.setEditable(True)
        self.submodel_combo.addItem("-- Select Submodel (Optional) --")
        self.submodel_combo.setEnabled(False)
        vehicle_layout.addRow("Submodel/Variant:", self.submodel_combo)
        
        form_layout.addRow(vehicle_group)
        
        # Identification Section
        id_group = QGroupBox("Vehicle Identification")
        id_layout = QFormLayout(id_group)
        
        # VIN with read button
        vin_row = QHBoxLayout()
        self.vin_edit = QLineEdit()
        self.vin_edit.setPlaceholderText("17-character VIN")
        self.vin_edit.setMaxLength(17)
        vin_row.addWidget(self.vin_edit)
        
        self.read_vin_btn = QPushButton("Read from OBD")
        self.read_vin_btn.setStyleSheet(self._get_button_style('secondary'))
        self.read_vin_btn.setToolTip("Read VIN from connected OBD adapter")
        self.read_vin_btn.clicked.connect(self._read_vin_from_obd)
        self.read_vin_btn.setEnabled(False)  # Enable only when connected
        vin_row.addWidget(self.read_vin_btn)
        
        vin_widget = QWidget()
        vin_widget.setLayout(vin_row)
        id_layout.addRow("VIN Number:", vin_widget)
        
        # License Plate
        self.plate_edit = QLineEdit()
        self.plate_edit.setPlaceholderText("License plate number")
        id_layout.addRow("License Plate:", self.plate_edit)
        
        form_layout.addRow(id_group)
        
        # Additional Information Section (optional)
        optional_group = QGroupBox("Additional Information (Optional)")
        optional_group.setCheckable(True)
        optional_group.setChecked(False)
        optional_layout = QFormLayout(optional_group)
        
        self.color_edit = QLineEdit()
        self.color_edit.setPlaceholderText("Vehicle color")
        optional_layout.addRow("Color:", self.color_edit)
        
        self.engine_type_combo = QComboBox()
        self.engine_type_combo.addItems(["", "I3", "I4", "V6", "V8", "V10", "V12", "Electric", "Hybrid", "Rotary"])
        optional_layout.addRow("Engine Type:", self.engine_type_combo)

        self.cylinders_spin = QSpinBox()
        self.cylinders_spin.setRange(0, 16)
        self.cylinders_spin.setSpecialValueText("—")
        optional_layout.addRow("Cylinders:", self.cylinders_spin)

        self.displacement_combo = QComboBox()
        self.displacement_combo.addItems(["", "1.0L", "1.2L", "1.4L", "1.5L", "1.6L", "1.8L",
            "2.0L", "2.4L", "2.5L", "2.7L", "3.0L", "3.5L", "3.8L", "4.0L", "4.7L",
            "5.0L", "5.6L", "5.7L", "6.0L", "6.2L", "6.7L"])
        optional_layout.addRow("Displacement:", self.displacement_combo)

        self.fuel_type_combo = QComboBox()
        self.fuel_type_combo.addItems(["", "Gasoline", "Diesel", "Electric", "Hybrid", "Plug-in Hybrid", "LPG/CNG"])
        optional_layout.addRow("Fuel Type:", self.fuel_type_combo)

        self.transmission_combo = QComboBox()
        self.transmission_combo.addItems(["", "Automatic", "Manual", "CVT", "DCT (Dual Clutch)"])
        optional_layout.addRow("Transmission:", self.transmission_combo)

        self.drivetrain_combo = QComboBox()
        self.drivetrain_combo.addItems(["", "FWD", "RWD", "AWD", "4WD"])
        optional_layout.addRow("Drivetrain:", self.drivetrain_combo)
        
        form_layout.addRow(optional_group)
        
        scroll.setWidget(form_widget)
        layout.addWidget(scroll, 1)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        create_btn = QPushButton("Create Profile")
        create_btn.setStyleSheet(f"background-color: {ProfessionalTheme.PRIMARY}; color: white; font-weight: bold;")
        create_btn.clicked.connect(self._create_profile)
        button_layout.addWidget(create_btn)
        
        layout.addLayout(button_layout)
        
        # Update OBD read button state
        self._update_obd_button_state()
    
    def _load_catalog_data(self):
        """Load vehicle catalog data into brand dropdown"""
        if not self.vehicle_catalog:
            # Try to create catalog
            try:
                if PID_PROFILE_AVAILABLE:
                    self.vehicle_catalog = VehicleCatalog()
            except Exception as e:
                logger.warning(f"Could not load vehicle catalog: {e}")
                return
        
        if self.vehicle_catalog:
            brands = self.vehicle_catalog.get_brand_names()
            self.brand_combo.clear()
            self.brand_combo.addItem("-- Select Manufacturer --")
            for brand in sorted(brands):
                if brand:
                    self.brand_combo.addItem(brand)

    def _load_owners(self):
        """Load owners into the owner dropdown"""
        if not self.vehicle_manager:
            return

        try:
            owners = self.vehicle_manager.get_all_owners()
            # Clear and re-add default items
            self.owner_combo.clear()
            self.owner_combo.addItem("-- No Owner --", None)
            self.owner_combo.addItem("+ Create New Owner...", "new")
            # Add existing owners
            for owner in owners:
                name = owner.get('name', '')
                owner_id = owner.get('owner_id')
                vehicle_count = owner.get('vehicle_count', 0)
                display_text = f"{name} ({vehicle_count} vehicles)" if vehicle_count else name
                self.owner_combo.addItem(display_text, owner_id)
        except Exception as e:
            logger.warning(f"Could not load owners: {e}")

    def _on_brand_changed(self, brand_name):
        """Handle brand selection change"""
        self.model_combo.clear()
        self.model_combo.addItem("-- Select Model --")
        self.year_combo.clear()
        self.year_combo.addItem("-- Select Year --")
        self.submodel_combo.clear()
        self.submodel_combo.addItem("-- Select Submodel (Optional) --")
        
        if brand_name and brand_name != "-- Select Manufacturer --" and self.vehicle_catalog:
            models = self.vehicle_catalog.get_model_names_for_brand(brand_name)
            for model in sorted(models):
                if model:
                    self.model_combo.addItem(model)
            self.model_combo.setEnabled(True)
        else:
            self.model_combo.setEnabled(False)
            self.year_combo.setEnabled(False)
            self.submodel_combo.setEnabled(False)
    
    def _on_model_changed(self, model_name):
        """Handle model selection change"""
        self.year_combo.clear()
        self.year_combo.addItem("-- Select Year --")
        self.submodel_combo.clear()
        self.submodel_combo.addItem("-- Select Submodel (Optional) --")
        
        brand_name = self.brand_combo.currentText()
        if model_name and model_name != "-- Select Model --" and self.vehicle_catalog:
            years = self.vehicle_catalog.get_years_for_model(brand_name, model_name)
            for year in sorted(years, reverse=True):
                self.year_combo.addItem(str(year))
            
            submodels = self.vehicle_catalog.get_submodels_for_model(brand_name, model_name)
            for submodel in submodels:
                if submodel:
                    self.submodel_combo.addItem(submodel)
            
            self.year_combo.setEnabled(True)
            self.submodel_combo.setEnabled(len(submodels) > 0)
        else:
            self.year_combo.setEnabled(False)
            self.submodel_combo.setEnabled(False)
    
    def _update_obd_button_state(self):
        """Update the OBD read button enabled state"""
        if self.connectivity_manager and getattr(self.connectivity_manager, 'connected', False):
            self.read_vin_btn.setEnabled(True)
            self.read_vin_btn.setToolTip("Read VIN from connected OBD adapter")
        else:
            self.read_vin_btn.setEnabled(False)
            self.read_vin_btn.setToolTip("Connect to OBD adapter first to read VIN")
    
    def _read_vin_from_obd(self):
        """Read VIN from connected OBD adapter using Mode 09 PID 02"""
        if not self.connectivity_manager:
            show_error(self, "Error", "No connectivity manager available")
            return
        
        if not getattr(self.connectivity_manager, 'connected', False):
            show_error(self, "Not Connected", "Please connect to OBD adapter first")
            return
        
        try:
            # Try to read VIN using Mode 09 PID 02
            import obd
            if hasattr(self.connectivity_manager, 'obd_connection') and self.connectivity_manager.obd_connection:
                response = self.connectivity_manager.obd_connection.query(obd.commands.VIN)
                if response and not response.is_null():
                    vin = str(response.value)
                    if vin and len(vin) >= 17:
                        self.vin_edit.setText(vin[:17])
                        show_info(self, "VIN Read", f"VIN successfully read: {vin[:17]}")
                        return
            
            show_info(self, "VIN Not Available", "Could not read VIN from vehicle. Please enter manually.")
        except Exception as e:
            logger.error(f"Error reading VIN: {e}")
            show_error(self, "Error", f"Failed to read VIN: {str(e)}")
    
    def _validate_inputs(self):
        """Validate required inputs"""
        errors = []
        
        profile_name = self.profile_name_edit.text().strip()
        if not profile_name:
            errors.append("Profile Name is required")
        
        brand = self.brand_combo.currentText()
        if not brand or brand == "-- Select Manufacturer --":
            errors.append("Please select a Manufacturer")
        
        model = self.model_combo.currentText()
        if not model or model == "-- Select Model --":
            errors.append("Please select a Model")
        
        year = self.year_combo.currentText()
        if not year or year == "-- Select Year --":
            errors.append("Please select a Year")
        
        # VIN validation (optional but if provided, should be valid)
        vin = self.vin_edit.text().strip().upper()
        if vin and len(vin) != 17:
            errors.append("VIN must be exactly 17 characters")
        
        return errors
    
    def _create_profile(self):
        """Create the profile from form data"""
        errors = self._validate_inputs()
        if errors:
            show_error(self, "Validation Error", "\n".join(errors))
            return

        # Handle owner selection
        owner_id = self.owner_combo.currentData() if hasattr(self, 'owner_combo') else None
        if owner_id == "new":
            # Create new owner via parent's method
            if hasattr(self.parent(), '_add_owner_dialog'):
                owner_id = self.parent()._add_owner_dialog()
                if not owner_id:
                    return  # Cancelled
            else:
                owner_id = None

        # Build profile data
        year_text = self.year_combo.currentText()
        try:
            year = int(year_text)
        except ValueError:
            year = 0

        submodel = self.submodel_combo.currentText()
        if submodel == "-- Select Submodel (Optional) --":
            submodel = ""

        self.profile_data = {
            'name': self.profile_name_edit.text().strip(),
            'customer_name': self.customer_name_edit.text().strip(),
            'customer_phone': self.customer_phone_edit.text().strip() if hasattr(self, 'customer_phone_edit') else '',
            'customer_email': self.customer_email_edit.text().strip().lower() if hasattr(self, 'customer_email_edit') else '',
            'make': self.brand_combo.currentText(),
            'brand': self.brand_combo.currentText(),  # Alias
            'model': self.model_combo.currentText(),
            'submodel': submodel,
            'year': year,
            'vin': self.vin_edit.text().strip().upper(),
            'license_plate': self.plate_edit.text().strip().upper(),
            'plate': self.plate_edit.text().strip().upper(),  # Alias
            'color': self.color_edit.text().strip() if hasattr(self, 'color_edit') else '',
            'engine_type': self.engine_type_combo.currentText() if hasattr(self, 'engine_type_combo') else '',
            'cylinders': self.cylinders_spin.value() if hasattr(self, 'cylinders_spin') and self.cylinders_spin.value() > 0 else None,
            'displacement': self.displacement_combo.currentText() if hasattr(self, 'displacement_combo') else '',
            'fuel_type': self.fuel_type_combo.currentText() if hasattr(self, 'fuel_type_combo') else '',
            'transmission': self.transmission_combo.currentText() if hasattr(self, 'transmission_combo') else '',
            'drivetrain': self.drivetrain_combo.currentText() if hasattr(self, 'drivetrain_combo') else '',
            'owner_id': owner_id,
        }

        self.accept()
    
    def get_profile_data(self):
        """Return the profile data if dialog was accepted"""
        return self.profile_data

    def _get_button_style(self, style_type: str = 'primary') -> str:
        """Get consistent button style based on type."""
        styles = {
            'primary': """
                QPushButton {
                    background-color: #C40000;
                    color: #F0F6FC;
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
                    background-color: #B71C1C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
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
                QPushButton:pressed {
                    background-color: #161B22;
                }
            """,
            'danger': """
                QPushButton {
                    background-color: #DA3633;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #F85149;
                }
                QPushButton:pressed {
                    background-color: #B62324;
                }
            """,
            'success': """
                QPushButton {
                    background-color: #238636;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #2EA043;
                }
                QPushButton:pressed {
                    background-color: #196C2E;
                }
            """
        }
        return styles.get(style_type, styles['primary'])


# =============================================================================
#   VEHICLE RESEARCH WORKER
# =============================================================================

class VehicleResearchFetchWorker(QThread):
    """Background QThread to fetch vehicle research + Mode 06 data from the local API."""

    research_ready = Signal(dict)   # emitted with research dict on success
    mode06_ready = Signal(dict)     # emitted with Mode 06 test results
    fetch_failed = Signal(str)      # emitted with error message on failure

    def __init__(self, vehicle_id: int, parent=None):
        super().__init__(parent)
        self.vehicle_id = vehicle_id

    def run(self):
        try:
            from predict.desktop.api_client import PredictAPIClient
            client = PredictAPIClient()
            result = client.get_vehicle_research(self.vehicle_id)
            # Server returns {success, research: {...}, status}
            research = result.get('research') or {}
            if research:
                self.research_ready.emit(research)
            else:
                # No research data yet — emit status only
                self.research_ready.emit({'research_status': result.get('status', 'pending')})
        except Exception as e:
            self.fetch_failed.emit(str(e))

        # Also fetch Mode 06 ECU test results (non-blocking)
        try:
            from predict.desktop.api_client import PredictAPIClient
            client = PredictAPIClient()
            mode06 = client.get(f"/api/vehicle/{self.vehicle_id}/mode06")
            if mode06 and mode06.get('success'):
                self.mode06_ready.emit(mode06)
        except Exception:
            pass  # Mode 06 fetch failure is non-fatal


# =============================================================================
#   PROFILES TAB
# =============================================================================

class ProfilesTab(QWidget):
    """Vehicle Profiles Management Tab"""
    
    def __init__(self, vehicle_manager, on_profile_loaded, vin_decoder=None, data_logger=None, parent=None):
        super().__init__(parent)
        self.vehicle_manager = vehicle_manager
        self.on_profile_loaded = on_profile_loaded
        self.vin_decoder = vin_decoder
        self.data_logger = data_logger or SecureDataLogger()
        
        # Initialize vehicle catalog for the add dialog
        self.vehicle_catalog = None
        try:
            if PID_PROFILE_AVAILABLE:
                self.vehicle_catalog = VehicleCatalog()
        except Exception as e:
            logger.warning(f"Could not load vehicle catalog: {e}")
        
        # Reference to connectivity manager (set by main window)
        self.connectivity_manager = None

        self._profiles = []
        self._active_id = None
        self.online_profiles = set()

        # Connection status tracking with timeout
        self._last_connection_time = None
        self._connection_timeout_seconds = 15  # Mark as disconnected if no data for 15 seconds
        self._connection_timer = QTimer(self)
        self._connection_timer.timeout.connect(self._check_connection_timeout)
        self._connection_timer.start(15000)  # Check every 15 seconds (reduced for performance)
        self._is_connected = False
        self._last_device_id = None

        self._setup_ui()
        self.refresh_profiles()

        # Auto-refresh timer - refresh profiles every 5 seconds to pick up new users/edits
        self._auto_refresh_timer = QTimer(self)
        self._auto_refresh_timer.timeout.connect(self._auto_refresh_profiles)
        self._auto_refresh_timer.start(5000)  # 5 seconds
    
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

    def _get_button_style(self, style_type: str = 'primary') -> str:
        """Get consistent button style based on type."""
        styles = {
            'primary': """
                QPushButton {
                    background-color: #C40000;
                    color: #F0F6FC;
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
                    background-color: #B71C1C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
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
                    border-color: #8B949E;
                }
                QPushButton:pressed {
                    background-color: #161B22;
                }
                QPushButton:disabled {
                    background-color: #161B22;
                    color: #484F58;
                    border-color: #30363D;
                }
            """,
            'danger': """
                QPushButton {
                    background-color: #C40000;
                    color: #F0F6FC;
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
                    background-color: #B71C1C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """,
            'success': """
                QPushButton {
                    background-color: #4CAF50;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #66BB6A;
                }
                QPushButton:pressed {
                    background-color: #388E3C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """
        }
        return styles.get(style_type, styles['primary'])

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Left panel container for auto-adjustable layout
        left_widget = QWidget()
        left_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left = QVBoxLayout(left_widget)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(8)

        # Header
        header = QHBoxLayout()
        title = QLabel("Vehicle Profiles")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {ProfessionalTheme.TEXT_PRIMARY};")

        # Connection Status Indicator
        self.connection_indicator = QLabel("●")
        self.connection_indicator.setStyleSheet("color: #888888; font-size: 20px;")  # Gray = unknown
        self.connection_indicator.setToolTip("Mobile app connection status")
        self.connection_status_label = QLabel("Not Connected")
        self.connection_status_label.setStyleSheet(f"color: #888888; font-size: 11px;")

        self.add_btn = QPushButton("+ Add")
        self.add_btn.setStyleSheet(self._get_button_style('secondary'))
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setStyleSheet(self._get_button_style('secondary'))
        self.info_btn = QPushButton("ℹ️ Info")
        self.info_btn.setStyleSheet(self._get_button_style('secondary'))
        self.info_btn.setToolTip("View customer details (email, phone, etc.)")
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setStyleSheet(self._get_button_style('danger'))
        self.load_btn = QPushButton("Load")
        self.load_btn.setStyleSheet(self._get_button_style('primary'))
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setStyleSheet(self._get_button_style('secondary'))

        self.add_btn.clicked.connect(self._add_profile)
        self.edit_btn.clicked.connect(self._edit_profile)
        self.info_btn.clicked.connect(self._show_profile_info_dialog)
        self.delete_btn.clicked.connect(self._delete_profile)
        self.load_btn.clicked.connect(self._load_profile)
        self.refresh_btn.clicked.connect(self.refresh_profiles)

        header.addWidget(title)
        header.addSpacing(15)
        header.addWidget(self.connection_indicator)
        header.addWidget(self.connection_status_label)
        header.addStretch()
        for btn in [self.add_btn, self.edit_btn, self.info_btn, self.delete_btn, self.load_btn, self.refresh_btn]:
            header.addWidget(btn)
        left.addLayout(header)

        # Search bar
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        search_label.setStyleSheet(f"font-size: 12px; color: {ProfessionalTheme.TEXT_PRIMARY};")
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search by name or license plate...")
        self.search_box.textChanged.connect(self._filter_profiles)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_box)
        left.addLayout(search_layout)
        
        # Tree View - Hierarchical profile display with expand/collapse
        from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
        self.tree = QTreeWidget()
        self.tree.setColumnCount(8)
        self.tree.setHeaderLabels(["#", "Name", "Make", "Model", "Year", "VIN", "★", "ℹ️"])
        self.tree.setSelectionMode(QTreeWidget.SingleSelection)
        self.tree.setIndentation(20)
        self.tree.setRootIsDecorated(True)  # Show expand/collapse arrows
        self.tree.setAnimated(True)  # Smooth expand/collapse animation
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tree.itemClicked.connect(self._on_item_clicked)

        # Context menu for adding child profiles
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_tree_context_menu)

        # Apply tree styling
        self.tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {ProfessionalTheme.BACKGROUND_SECONDARY};
                color: {ProfessionalTheme.TEXT_PRIMARY};
                border: 1px solid {ProfessionalTheme.BORDER};
                border-radius: 8px;
                font-size: 12px;
            }}
            QTreeWidget::item {{
                padding: 8px 4px;
                border-bottom: 1px solid {ProfessionalTheme.BORDER};
            }}
            QTreeWidget::item:selected {{
                background-color: {ProfessionalTheme.PRIMARY};
                color: white;
            }}
            QTreeWidget::item:hover {{
                background-color: {ProfessionalTheme.CARD_BG_HOVER};
            }}
            QHeaderView::section {{
                background-color: {ProfessionalTheme.CARD_BG};
                color: {ProfessionalTheme.TEXT_PRIMARY};
                padding: 8px;
                border: none;
                border-bottom: 2px solid {ProfessionalTheme.PRIMARY};
                font-weight: bold;
            }}
        """)

        # Set column widths
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # #
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Name
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Make
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Model
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Year
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # VIN
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # ★
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # ℹ️ Info

        # Keep reference as self.table for compatibility
        self.table = self.tree

        left.addWidget(self.tree)
        layout.addWidget(left_widget, 3)
        
        # Right: Details - Wrapped in scroll area for responsive layout
        # Create scroll area for right panel (stored as instance var for info panel toggle)
        self.right_scroll = QScrollArea()
        self.right_scroll.setWidgetResizable(True)
        self.right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.right_scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {ProfessionalTheme.BACKGROUND_SECONDARY};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {ProfessionalTheme.BORDER};
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: #555;
            }}
        """)

        # Content widget for scroll area
        right_content = QWidget()
        right = QVBoxLayout(right_content)
        right.setContentsMargins(5, 5, 5, 5)
        right.setSpacing(10)

        # Profile info - adaptive sizing
        info_group = QGroupBox("Profile Details")
        info_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        info_layout = QVBoxLayout(info_group)

        # Placeholder text when no profile selected
        self.profile_details_placeholder = QLabel("👤 Select a vehicle profile from the table above to view details")
        self.profile_details_placeholder.setAlignment(Qt.AlignCenter)
        self.profile_details_placeholder.setMinimumHeight(120)
        self.profile_details_placeholder.setStyleSheet("""
            QLabel {
                color: #8B949E;
                font-style: italic;
                padding: 30px 15px;
                background-color: #161B22;
                border-radius: 6px;
                border: 1px dashed #30363D;
            }
        """)
        info_layout.addWidget(self.profile_details_placeholder)

        # Form layout for actual details (initially hidden)
        self.profile_details_form = QWidget()
        profile_form_layout = QFormLayout(self.profile_details_form)
        profile_form_layout.setContentsMargins(5, 5, 5, 5)
        profile_form_layout.setSpacing(5)

        self.info_labels = {}
        fields = [("Name", "name"), ("Make", "make"), ("Model", "model"), ("Year", "year"),
                  ("VIN", "vin"), ("License Plate", "license_plate"), ("Engine", "engine_type"),
                  ("Cylinders", "cylinders"), ("Displacement", "displacement"),
                  ("Transmission", "transmission"), ("Fuel Type", "fuel_type"),
                  ("Drivetrain", "drivetrain")]

        for label, key in fields:
            lbl = QLabel("-")
            lbl.setStyleSheet("font-weight: 600; font-size: 12px;")
            profile_form_layout.addRow(f"{label}:", lbl)
            self.info_labels[key] = lbl

        self.profile_details_form.setVisible(False)
        info_layout.addWidget(self.profile_details_form)

        # API Key section
        api_key_layout = QHBoxLayout()
        api_key_label = QLabel("API Key:")
        api_key_label.setStyleSheet(f"color: {ProfessionalTheme.TEXT_SECONDARY}; font-size: 11px;")
        self.api_key_display = QLineEdit()
        self.api_key_display.setReadOnly(True)
        self.api_key_display.setEchoMode(QLineEdit.Password)  # Hide by default
        self.api_key_display.setPlaceholderText("No API key for this profile")
        self.api_key_display.setStyleSheet("""
            QLineEdit {
                background-color: #161B22;
                border: 1px solid #30363D;
                border-radius: 3px;
                padding: 4px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10px;
            }
        """)

        # Show/Hide toggle button
        self.api_key_toggle_btn = QPushButton("👁️")
        self.api_key_toggle_btn.setMaximumWidth(60)
        self.api_key_toggle_btn.setStyleSheet(self._get_button_style('secondary'))
        self.api_key_toggle_btn.clicked.connect(self._toggle_api_key_visibility)
        self.api_key_visible = False

        # Copy button
        self.api_key_copy_btn = QPushButton("📋")
        self.api_key_copy_btn.setMaximumWidth(60)
        self.api_key_copy_btn.setStyleSheet(self._get_button_style('secondary'))
        self.api_key_copy_btn.clicked.connect(self._copy_api_key_to_clipboard)

        api_key_layout.addWidget(api_key_label)
        api_key_layout.addWidget(self.api_key_display, 1)
        api_key_layout.addWidget(self.api_key_toggle_btn)
        api_key_layout.addWidget(self.api_key_copy_btn)
        info_layout.addLayout(api_key_layout)

        right.addWidget(info_group)

        # AI Status Panel - compact
        ai_status_group = QGroupBox("🤖 AI Learning Status")
        ai_status_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        ai_status_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                color: {ProfessionalTheme.INFO};
                border: 2px solid {ProfessionalTheme.INFO};
                border-radius: 5px;
                padding: 8px;
                margin-top: 5px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                font-size: 11px;
            }}
        """)
        ai_status_layout = QVBoxLayout(ai_status_group)
        ai_status_layout.setSpacing(5)

        # Learning State
        state_layout = QHBoxLayout()
        state_label = QLabel("State:")
        state_label.setStyleSheet(f"color: {ProfessionalTheme.TEXT_SECONDARY}; font-size: 10px;")
        self.ai_learning_state = QLabel("⏳ Limited")
        self.ai_learning_state.setStyleSheet(f"color: {ProfessionalTheme.WARNING}; font-weight: bold; font-size: 10px;")
        state_layout.addWidget(state_label)
        state_layout.addWidget(self.ai_learning_state)
        state_layout.addStretch()
        ai_status_layout.addLayout(state_layout)

        # Baseline Progress
        baseline_layout = QHBoxLayout()
        baseline_label = QLabel("Progress:")
        baseline_label.setStyleSheet(f"color: {ProfessionalTheme.TEXT_SECONDARY}; font-size: 10px;")
        self.ai_baseline_progress = QProgressBar()
        self.ai_baseline_progress.setMaximum(100)
        self.ai_baseline_progress.setValue(0)
        self.ai_baseline_progress.setTextVisible(True)
        self.ai_baseline_progress.setFormat("%p%")
        self.ai_baseline_progress.setMaximumHeight(16)
        self.ai_baseline_progress.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {ProfessionalTheme.BORDER};
                border-radius: 3px;
                background-color: {ProfessionalTheme.BACKGROUND_SECONDARY};
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {ProfessionalTheme.SUCCESS};
            }}
        """)
        baseline_layout.addWidget(baseline_label)
        baseline_layout.addWidget(self.ai_baseline_progress, 1)
        ai_status_layout.addLayout(baseline_layout)

        # Fleet Knowledge Status
        fleet_layout = QHBoxLayout()
        fleet_label = QLabel("Fleet:")
        fleet_label.setStyleSheet(f"color: {ProfessionalTheme.TEXT_SECONDARY}; font-size: 10px;")
        self.ai_fleet_status = QLabel("⚪ N/A")
        self.ai_fleet_status.setStyleSheet(f"color: {ProfessionalTheme.TEXT_MUTED}; font-weight: bold; font-size: 10px;")
        fleet_layout.addWidget(fleet_label)
        fleet_layout.addWidget(self.ai_fleet_status)
        fleet_layout.addStretch()
        ai_status_layout.addLayout(fleet_layout)

        # Last Learning Update
        update_layout = QHBoxLayout()
        update_label = QLabel("Update:")
        update_label.setStyleSheet(f"color: {ProfessionalTheme.TEXT_SECONDARY}; font-size: 10px;")
        self.ai_last_update = QLabel("Never")
        self.ai_last_update.setStyleSheet(f"color: {ProfessionalTheme.TEXT_MUTED}; font-size: 9px;")
        update_layout.addWidget(update_label)
        update_layout.addWidget(self.ai_last_update)
        update_layout.addStretch()
        ai_status_layout.addLayout(update_layout)

        right.addWidget(ai_status_group)

        # Live snapshot - compact
        live_group = QGroupBox("Latest Snapshot")
        live_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        live_layout = QFormLayout(live_group)
        live_layout.setContentsMargins(5, 5, 5, 5)
        live_layout.setSpacing(3)

        self.live_labels = {}
        live_fields = [("RPM", "rpm"), ("Speed", "speed"), ("Coolant", "coolant_temp"),
                       ("Battery", "battery_voltage"), ("Load", "engine_load")]

        for label, key in live_fields:
            lbl = QLabel("-")
            lbl.setStyleSheet("font-weight: 600; font-size: 11px;")
            live_layout.addRow(f"{label}:", lbl)
            self.live_labels[key] = lbl

        right.addWidget(live_group)

        # Service History box
        service_group = QGroupBox("Service History")
        service_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        service_layout = QVBoxLayout(service_group)

        self.service_history_list = QListWidget()
        self.service_history_list.setMaximumHeight(120)
        self.service_history_list.setStyleSheet("font-size: 10px;")
        service_layout.addWidget(self.service_history_list)

        right.addWidget(service_group)
        right.addStretch()

        # Set the scroll area content
        self.right_scroll.setWidget(right_content)

        # Add scroll area to main layout with responsive sizing
        layout.addWidget(self.right_scroll, 2)

        # === INFO PANEL (slides in when clicking ℹ️) ===
        self.info_panel = None
        if InfoPanelWidget is not None:
            self.info_panel = InfoPanelWidget()
            self.info_panel.setVisible(False)  # Hidden by default
            self.info_panel.closed.connect(self._on_info_panel_closed)
            self.info_panel.pdf_requested.connect(self._on_pdf_requested)
            self.info_panel.action_requested.connect(self._on_action_requested)
            layout.addWidget(self.info_panel)

    def update_online_status(self, online_ids):
        """Update the list of online profiles and refresh table"""
        new_set = set(str(x) for x in online_ids)
        if new_set != self.online_profiles:
            self.online_profiles = new_set
            self.refresh_profiles()

    def _get_status_icon(self, status):
        """Create status circle icon (green/red/grey)"""
        cache_key = f'_{status}_icon'
        if not hasattr(self, cache_key):
            pixmap = QPixmap(12, 12)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)

            # Status colors
            colors = {
                'online': "#4CAF50",    # Green - Live data streaming
                'offline': "#F44336",   # Red - Disconnected
                'never': "#9E9E9E"      # Grey - Never connected
            }

            painter.setBrush(QColor(colors.get(status, "#9E9E9E")))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(1, 1, 10, 10)
            painter.end()
            setattr(self, cache_key, QIcon(pixmap))
        return getattr(self, cache_key)

    def _fetch_server_owners(self):
        """Fetch all users from server and convert to owner format for tree display."""
        try:
            from server_api_client import ServerAPIClient
            client = ServerAPIClient()
            response = client._make_request("GET", "/api/admin/all-users")

            if response.success and response.data:
                server_owners = []
                for user in response.data.get('users', []):
                    # Skip deleted users
                    if user.get('status') == 'deleted':
                        continue

                    # Get vehicle data if present
                    vehicle = user.get('vehicle')
                    has_vehicle = vehicle and vehicle.get('make')

                    # Convert server user to owner format that tree expects
                    owner = {
                        'owner_id': f"server_{user.get('user_id', 0)}",
                        'name': user.get('name', 'Unknown'),
                        'email': user.get('email', ''),
                        'phone': user.get('phone', ''),
                        'tier': user.get('tier', 'free'),
                        'status': user.get('status', 'active'),
                        'source': user.get('source', 'android'),
                        'api_key': user.get('api_key', ''),
                        'created_at': user.get('created_at', ''),
                        'last_used_at': user.get('last_used_at', ''),
                        'online_status': user.get('online_status', 'Unknown'),
                        'is_server': True,  # Flag to identify server users
                        'server_user_id': user.get('user_id'),  # Keep original ID for saving
                        'vehicle': vehicle,  # Include vehicle data from server
                        'vehicle_count': 1 if has_vehicle else 0,
                        'driver_count': 0,
                    }
                    server_owners.append(owner)
                return server_owners
            else:
                logger.warning(f"Could not fetch server owners: {getattr(response, 'message', 'Unknown error')}")
        except Exception as e:
            logger.warning(f"Could not fetch server owners: {e}")
        return []

    def _merge_owners(self, server_owners, local_owners):
        """Merge server owners with local owners, avoiding duplicates by email."""
        merged = []

        # Get set of local emails (lowercase for comparison)
        local_emails = set()
        for o in local_owners:
            email = o.get('email', '')
            if email:
                local_emails.add(email.lower())

        # Add server owners that don't exist locally
        for so in server_owners:
            email = so.get('email', '').lower()
            if email and email not in local_emails:
                merged.append(so)

        # Add all local owners
        merged.extend(local_owners)

        return merged

    def _auto_refresh_profiles(self):
        """Auto-refresh profiles silently (no error dialogs), preserving current selection."""
        try:
            # Save current selection path so we can restore it after refresh
            selected_path = self._get_selected_item_path()
            self._refresh_profiles_internal()
            # Restore selection
            if selected_path:
                self._restore_selected_item(selected_path)
        except Exception as e:
            profiles_logger.debug(f"Auto-refresh skipped: {e}")

    def _get_selected_item_path(self):
        """Get a path identifier for the currently selected tree item."""
        item = self.tree.currentItem()
        if not item:
            return None
        # Build a path from the item's stored data
        data = item.data(0, Qt.UserRole)
        if not data:
            return None
        item_type = data.get('type', '')
        item_data = data.get('data', {})
        if item_type == 'owner':
            return ('owner', item_data.get('owner_id'))
        elif item_type == 'vehicle':
            return ('vehicle', item_data.get('profile_id'))
        elif item_type == 'driver':
            return ('driver', item_data.get('driver_id'))
        return None

    def _restore_selected_item(self, path):
        """Restore tree selection by matching the saved path."""
        item_type, item_id = path
        for i in range(self.tree.topLevelItemCount()):
            owner_item = self.tree.topLevelItem(i)
            if self._match_tree_item(owner_item, item_type, item_id):
                self.tree.setCurrentItem(owner_item)
                return
            # Check children (vehicles)
            for j in range(owner_item.childCount()):
                vehicle_item = owner_item.child(j)
                if self._match_tree_item(vehicle_item, item_type, item_id):
                    self.tree.setCurrentItem(vehicle_item)
                    return
                # Check grandchildren (drivers)
                for k in range(vehicle_item.childCount()):
                    driver_item = vehicle_item.child(k)
                    if self._match_tree_item(driver_item, item_type, item_id):
                        self.tree.setCurrentItem(driver_item)
                        return

    def _match_tree_item(self, item, target_type, target_id):
        """Check if a tree item matches the target type and ID."""
        data = item.data(0, Qt.UserRole)
        if not data:
            return False
        if data.get('type') != target_type:
            return False
        item_data = data.get('data', {})
        if target_type == 'owner':
            return item_data.get('owner_id') == target_id
        elif target_type == 'vehicle':
            return item_data.get('profile_id') == target_id
        elif target_type == 'driver':
            return item_data.get('driver_id') == target_id
        return False

    def refresh_profiles(self):
        """Refresh profiles list as 3-level hierarchy: Owner → Vehicle → Driver"""
        try:
            self._refresh_profiles_internal()
        except Exception as e:
            profiles_logger.error(f"Error refreshing profiles: {e}")
            import traceback
            traceback.print_exc()
            try:
                from utils import show_error
                show_error(self, "Refresh Error", f"Failed to refresh profiles:\n{e}")
            except:
                pass

    def _refresh_profiles_internal(self):
        """Internal refresh logic - called by refresh_profiles() with error handling"""
        from PySide6.QtWidgets import QTreeWidgetItem
        from PySide6.QtGui import QFont, QBrush

        self._profiles = self.vehicle_manager.get_all_profiles() or []
        self.tree.clear()

        # Get local owners from database
        local_owners = self.vehicle_manager.get_all_owners() or []

        # Fetch server-registered owners (Android registrations)
        server_owners = self._fetch_server_owners()

        # Merge: server owners that don't exist locally + all local owners
        owners = self._merge_owners(server_owners, local_owners)

        row_num = 1

        # === LEVEL 0: OWNERS ===
        for owner in owners:
            owner_id = owner.get('owner_id')
            owner_name = owner.get('name', 'Unknown Owner')
            vehicle_count = owner.get('vehicle_count', 0)
            driver_count = owner.get('driver_count', 0)
            is_server = owner.get('is_server', False)  # Server-registered user

            # Build owner display name
            count_info = []
            if vehicle_count > 0:
                count_info.append(f"{vehicle_count} vehicle{'s' if vehicle_count != 1 else ''}")
            if driver_count > 0:
                count_info.append(f"{driver_count} driver{'s' if driver_count != 1 else ''}")

            # Add source badge for server users
            if is_server:
                source = owner.get('source', 'android').upper()
                tier = owner.get('tier', 'free').upper()
                owner_display = f"{owner_name} [{source}] ({tier})"
            else:
                owner_display = f"{owner_name} ({', '.join(count_info)})" if count_info else owner_name

            owner_item = QTreeWidgetItem([
                str(row_num),
                owner_display,
                "",  # Make
                "",  # Model
                "",  # Year
                "",  # VIN
                "",  # Favorite
                "ℹ️"  # Info button
            ])
            row_num += 1

            # Store owner data
            owner_item.setData(0, Qt.UserRole, {'type': 'owner', 'data': owner})

            # Style owner row (bold)
            owner_font = owner_item.font(1)
            owner_font.setBold(True)
            owner_item.setFont(1, owner_font)

            # Use different color for server users (green for Android, blue for Desktop)
            if is_server:
                source = owner.get('source', 'android')
                if source == 'android':
                    color = QColor("#4CAF50")  # Green for Android users
                else:
                    color = QColor("#2196F3")  # Blue for Desktop users
                for col in range(8):
                    owner_item.setForeground(col, color)
            else:
                for col in range(8):
                    owner_item.setForeground(col, QColor(ProfessionalTheme.TEXT_PRIMARY))

            self.tree.addTopLevelItem(owner_item)

            # === LEVEL 1: VEHICLES under this owner ===
            if is_server:
                # Server users have vehicle data from API response
                server_vehicle = owner.get('vehicle')
                if server_vehicle and server_vehicle.get('make'):
                    # Create a vehicle dict in the format expected by the tree
                    vehicles = [{
                        'profile_id': server_vehicle.get('profile_id'),
                        'name': f"{server_vehicle.get('make', '')} {server_vehicle.get('model', '')}".strip() or 'Vehicle',
                        'make': server_vehicle.get('make', ''),
                        'model': server_vehicle.get('model', ''),
                        'year': server_vehicle.get('year', ''),
                        'plate': server_vehicle.get('plate', ''),
                        'vin': '',
                        'is_favorite': False,
                        'driver_count': 0,
                        'is_server_vehicle': True  # Flag for server vehicle
                    }]
                else:
                    vehicles = []
            else:
                vehicles = self.vehicle_manager.get_vehicles_for_owner(owner_id) or []
            for vehicle in vehicles:
                profile_id = vehicle.get('profile_id')
                vehicle_name = vehicle.get('name', '')
                make = vehicle.get('make', '')
                model = vehicle.get('model', '')
                year = vehicle.get('year', '')
                vin = vehicle.get('vin', '')
                is_favorite = vehicle.get('is_favorite', False)
                veh_driver_count = vehicle.get('driver_count', 0)

                # Get connection status
                status = self._get_profile_status(vehicle)

                # Build vehicle display name (Phase 7 fix)
                # Priority: "Year Make Model" > "Make Model" > stored name > fallback
                if make and model:
                    if year:
                        veh_display = f"{year} {make} {model}"
                    else:
                        veh_display = f"{make} {model}"
                elif vehicle_name and vehicle_name.strip():
                    veh_display = vehicle_name
                else:
                    veh_display = "Unknown Vehicle"

                if veh_driver_count > 0:
                    veh_display += f" ({veh_driver_count} driver{'s' if veh_driver_count != 1 else ''})"

                vehicle_item = QTreeWidgetItem([
                    "",
                    f"  {veh_display}",
                    str(make),
                    str(model),
                    str(year) if year else "",
                    str(vin) if vin else "",
                    "★" if is_favorite else "",
                    "ℹ️"  # Info button
                ])

                # Store vehicle/profile data
                vehicle_item.setData(0, Qt.UserRole, {'type': 'profile', 'data': vehicle, 'owner_id': owner_id})
                vehicle_item.setIcon(1, self._get_status_icon(status))

                # Style vehicle row
                for col in range(8):
                    vehicle_item.setForeground(col, QColor(ProfessionalTheme.TEXT_PRIMARY))

                owner_item.addChild(vehicle_item)

                # === LEVEL 2: DRIVERS under this vehicle ===
                drivers = self.vehicle_manager.get_drivers_for_profile(profile_id) or []
                for driver in drivers:
                    driver_name = driver.get('name', 'Unknown')
                    relationship = driver.get('relationship', 'driver')
                    is_primary = driver.get('is_primary', False)
                    age = driver.get('age', '')
                    license_num = driver.get('license_number', '')

                    # Build driver display name with role badge
                    guardian_role = driver.get('guardian_role', 'driver')
                    role_icon = ""
                    if guardian_role == 'owner':
                        role_icon = "👑 "
                    elif guardian_role == 'co_guardian':
                        role_icon = "🛡 "

                    driver_display = f"    {role_icon}{driver_name}"
                    if is_primary:
                        driver_display += " (Primary)"
                    if guardian_role and guardian_role != 'driver':
                        role_label = guardian_role.replace('_', '-').title()
                        driver_display += f" [{role_label}]"
                    elif relationship and relationship != 'driver':
                        driver_display += f" - {relationship.title()}"

                    driver_item = QTreeWidgetItem([
                        "",
                        driver_display,
                        "",
                        "",
                        str(age) if age else "",
                        license_num or "",
                        "",
                        "ℹ️"  # Info button
                    ])

                    # Store driver data
                    driver_item.setData(0, Qt.UserRole, {
                        'type': 'driver',
                        'data': driver,
                        'profile_id': profile_id,
                        'owner_id': owner_id
                    })

                    # Style driver row with role-based color
                    if guardian_role == 'owner':
                        driver_color = QColor("#FFB300")  # Gold for owner
                    elif guardian_role == 'co_guardian':
                        driver_color = QColor("#AB47BC")  # Purple for co-guardian
                    else:
                        driver_color = QColor("#58A6FF")  # Blue for regular driver
                    for col in range(8):
                        driver_item.setForeground(col, driver_color)

                    driver_font = driver_item.font(1)
                    driver_font.setPointSize(driver_font.pointSize() - 1)
                    driver_item.setFont(1, driver_font)

                    vehicle_item.addChild(driver_item)

                # Add "+ Add Driver" under vehicle
                add_driver_item = QTreeWidgetItem([
                    "", "    + Add Driver", "", "", "", "", "", ""
                ])
                add_driver_item.setData(0, Qt.UserRole, {
                    'type': 'add_driver',
                    'profile_id': profile_id,
                    'owner_id': owner_id
                })
                add_color = QColor("#4CAF50")
                for col in range(8):
                    add_driver_item.setForeground(col, add_color)
                add_font = add_driver_item.font(1)
                add_font.setItalic(True)
                add_driver_item.setFont(1, add_font)
                vehicle_item.addChild(add_driver_item)

                # Auto-expand vehicles with drivers
                if drivers:
                    vehicle_item.setExpanded(True)

            # Add "+ Add Vehicle" under owner
            add_vehicle_item = QTreeWidgetItem([
                "", "  + Add Vehicle", "", "", "", "", "", ""
            ])
            add_vehicle_item.setData(0, Qt.UserRole, {
                'type': 'add_vehicle',
                'owner_id': owner_id
            })
            add_color = QColor("#4CAF50")
            for col in range(8):
                add_vehicle_item.setForeground(col, add_color)
            add_font = add_vehicle_item.font(1)
            add_font.setItalic(True)
            add_vehicle_item.setFont(1, add_font)
            owner_item.addChild(add_vehicle_item)

            # Auto-expand owners
            owner_item.setExpanded(True)

        # === STANDALONE VEHICLES (no owner) ===
        unassigned = self.vehicle_manager.get_unassigned_vehicles() or []
        if unassigned:
            standalone_item = QTreeWidgetItem([
                str(row_num),
                "Standalone Vehicles (No Owner)",
                "", "", "", "", "", ""
            ])
            standalone_item.setData(0, Qt.UserRole, {'type': 'standalone_group'})

            # Style standalone header (gray, italic)
            standalone_font = standalone_item.font(1)
            standalone_font.setItalic(True)
            standalone_item.setFont(1, standalone_font)
            for col in range(8):
                standalone_item.setForeground(col, QColor(ProfessionalTheme.TEXT_SECONDARY))

            self.tree.addTopLevelItem(standalone_item)

            for vehicle in unassigned:
                profile_id = vehicle.get('profile_id')
                vehicle_name = vehicle.get('name', '')
                make = vehicle.get('make', '')
                model = vehicle.get('model', '')
                year = vehicle.get('year', '')
                vin = vehicle.get('vin', '')
                is_favorite = vehicle.get('is_favorite', False)
                veh_driver_count = vehicle.get('driver_count', 0)

                status = self._get_profile_status(vehicle)

                veh_display = vehicle_name
                if veh_driver_count > 0:
                    veh_display += f" ({veh_driver_count} driver{'s' if veh_driver_count != 1 else ''})"

                vehicle_item = QTreeWidgetItem([
                    "",
                    f"  {veh_display}",
                    str(make),
                    str(model),
                    str(year) if year else "",
                    str(vin) if vin else "",
                    "★" if is_favorite else "",
                    "ℹ️"  # Info button
                ])

                vehicle_item.setData(0, Qt.UserRole, {'type': 'profile', 'data': vehicle, 'owner_id': None})
                vehicle_item.setIcon(1, self._get_status_icon(status))

                for col in range(8):
                    vehicle_item.setForeground(col, QColor(ProfessionalTheme.TEXT_PRIMARY))

                standalone_item.addChild(vehicle_item)

                # Drivers under standalone vehicle
                drivers = self.vehicle_manager.get_drivers_for_profile(profile_id) or []
                for driver in drivers:
                    driver_name = driver.get('name', 'Unknown')
                    relationship = driver.get('relationship', 'driver')
                    is_primary = driver.get('is_primary', False)
                    guardian_role = driver.get('guardian_role', 'driver')

                    role_icon = ""
                    if guardian_role == 'owner':
                        role_icon = "👑 "
                    elif guardian_role == 'co_guardian':
                        role_icon = "🛡 "

                    driver_display = f"    {role_icon}{driver_name}"
                    if is_primary:
                        driver_display += " (Primary)"
                    if guardian_role and guardian_role != 'driver':
                        role_label = guardian_role.replace('_', '-').title()
                        driver_display += f" [{role_label}]"
                    elif relationship and relationship != 'driver':
                        driver_display += f" - {relationship.title()}"

                    driver_item = QTreeWidgetItem([
                        "", driver_display, "", "", "", "", "", "ℹ️"
                    ])
                    driver_item.setData(0, Qt.UserRole, {
                        'type': 'driver',
                        'data': driver,
                        'profile_id': profile_id,
                        'owner_id': None
                    })

                    # Role-based color coding
                    if guardian_role == 'owner':
                        driver_color = QColor("#FFB300")  # Gold for owner
                    elif guardian_role == 'co_guardian':
                        driver_color = QColor("#AB47BC")  # Purple for co-guardian
                    else:
                        driver_color = QColor("#58A6FF")  # Blue for regular driver
                    for col in range(8):
                        driver_item.setForeground(col, driver_color)

                    vehicle_item.addChild(driver_item)

                # Add Driver placeholder
                add_driver_item = QTreeWidgetItem([
                    "", "    + Add Driver", "", "", "", "", "", ""
                ])
                add_driver_item.setData(0, Qt.UserRole, {
                    'type': 'add_driver',
                    'profile_id': profile_id,
                    'owner_id': None
                })
                for col in range(8):
                    add_driver_item.setForeground(col, QColor("#4CAF50"))
                add_font = add_driver_item.font(1)
                add_font.setItalic(True)
                add_driver_item.setFont(1, add_font)
                vehicle_item.addChild(add_driver_item)

                if drivers:
                    vehicle_item.setExpanded(True)

            standalone_item.setExpanded(True)

    def _show_tree_context_menu(self, position):
        """Show context menu for tree items (right-click) - handles profiles and drivers"""
        from PySide6.QtWidgets import QMenu

        item = self.tree.itemAt(position)
        if not item:
            return

        item_data = item.data(0, Qt.UserRole)
        if not item_data:
            return

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 5px;
            }}
            QMenu::item {{
                padding: 8px 20px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: #C40000;
            }}
        """)

        item_type = item_data.get('type', 'profile')

        # Owner context menu
        if item_type == 'owner':
            owner = item_data.get('data', {})
            owner_id = owner.get('owner_id')
            print(f"[DEBUG] Owner context menu: owner_id={owner_id}")

            add_vehicle = menu.addAction("+ Add Vehicle")
            add_vehicle.triggered.connect(lambda checked=False, oid=owner_id: self._add_vehicle_for_owner(oid))

            menu.addSeparator()

            edit_owner = menu.addAction("Edit Owner")
            edit_owner.triggered.connect(lambda checked=False, o=owner: self._edit_owner_dialog(o))

            gen_key = menu.addAction("Generate API Key")
            gen_key.triggered.connect(lambda checked=False, o=owner: self._generate_owner_api_key(o))

            menu.addSeparator()

            delete_owner = menu.addAction("Delete Owner")
            delete_owner.triggered.connect(lambda checked=False, oid=owner_id: self._delete_owner(oid))

            menu.exec(self.tree.viewport().mapToGlobal(position))
            return

        # Add Vehicle placeholder context menu
        if item_type == 'add_vehicle':
            owner_id = item_data.get('owner_id')
            print(f"[DEBUG] Add Vehicle context menu: owner_id={owner_id}")
            add_action = menu.addAction("+ Add New Vehicle")
            add_action.triggered.connect(lambda checked=False, oid=owner_id: self._add_vehicle_for_owner(oid))
            menu.exec(self.tree.viewport().mapToGlobal(position))
            return

        if item_type == 'add_driver':
            # Clicked on "Add Driver" placeholder
            add_action = menu.addAction("+ Add New Driver")
            add_action.triggered.connect(lambda: self._add_driver_dialog(item_data.get('profile_id')))
            menu.exec(self.tree.viewport().mapToGlobal(position))
            return

        if item_type == 'driver':
            # Driver-specific context menu
            driver = item_data.get('data', {})
            profile_id = item_data.get('profile_id')

            edit_driver = menu.addAction("Edit Driver")
            edit_driver.triggered.connect(lambda: self._edit_driver_dialog(driver, profile_id))

            if not driver.get('is_primary'):
                set_primary = menu.addAction("Set as Primary Driver")
                set_primary.triggered.connect(lambda: self._set_primary_driver(driver.get('driver_id'), profile_id))

            gen_key = menu.addAction("Generate API Key")
            gen_key.triggered.connect(lambda: self._generate_driver_api_key(driver, profile_id))

            # Guardian role actions (admin-only)
            current_guardian_role = driver.get('guardian_role', 'driver')
            driver_name_for_role = driver.get('name', 'Unknown')
            menu.addSeparator()
            if current_guardian_role != 'co_guardian':
                promote_action = menu.addAction("Promote to Co-Guardian")
                promote_action.triggered.connect(
                    lambda checked=False, did=driver.get('driver_id'), dn=driver_name_for_role, pid=profile_id:
                        self._set_guardian_role(did, 'co_guardian', dn, pid))
            if current_guardian_role != 'driver':
                demote_action = menu.addAction("Demote to Driver")
                demote_action.triggered.connect(
                    lambda checked=False, did=driver.get('driver_id'), dn=driver_name_for_role, pid=profile_id:
                        self._set_guardian_role(did, 'driver', dn, pid))

            menu.addSeparator()

            remove_driver = menu.addAction("Remove Driver")
            remove_driver.triggered.connect(lambda: self._remove_driver(driver.get('driver_id')))

            menu.exec(self.tree.viewport().mapToGlobal(position))
            return

        # Profile (Vehicle) context menu
        profile = item_data.get('data', item_data)

        # Add driver option for vehicles
        add_driver = menu.addAction("+ Add Driver")
        add_driver.triggered.connect(lambda: self._add_driver_dialog(profile.get('profile_id')))

        menu.addSeparator()

        # Load profile
        load_action = menu.addAction("Load Profile")
        load_action.triggered.connect(self._load_profile)

        # Edit profile
        edit_action = menu.addAction("Edit Profile")
        edit_action.triggered.connect(self._edit_profile)

        # Assign to owner option (for vehicles)
        menu.addSeparator()
        assign_owner = menu.addAction("Assign to Owner...")
        assign_owner.triggered.connect(lambda: self._assign_vehicle_to_owner_dialog(profile))

        menu.addSeparator()

        # Delete profile
        delete_action = menu.addAction("Delete Profile")
        delete_action.triggered.connect(self._delete_profile)

        menu.exec(self.tree.viewport().mapToGlobal(position))

    def _get_profile_status(self, profile):
        """Determine profile status: online/offline/never"""
        from datetime import datetime, timedelta

        pid = str(profile.get('profile_id', ''))
        
        # Immediate check from mobile wrapper signals (via self.online_profiles)
        if hasattr(self, 'online_profiles') and pid in self.online_profiles:
            return 'online'

        last_seen = profile.get('last_seen')
        ever_connected = profile.get('ever_connected', False)

        # Never connected
        if not ever_connected or not last_seen:
            return 'never'

        # Parse last_seen timestamp
        try:
            if isinstance(last_seen, str):
                last_seen_dt = datetime.fromisoformat(last_seen)
            else:
                last_seen_dt = last_seen

            # Check if online (data received in last 30 seconds)
            time_diff = datetime.now() - last_seen_dt
            if time_diff < timedelta(seconds=30):
                return 'online'
            else:
                return 'offline'
        except Exception:
            return 'never'
    
    def _get_selected(self):
        """Get currently selected profile from tree widget"""
        items = self.tree.selectedItems()
        if items:
            # Return the profile dict stored in the item's data
            return items[0].data(0, Qt.UserRole)
        return None
    
    def _on_selection_changed(self):
        item_data = self._get_selected()
        if not item_data:
            # Show placeholder and hide details form
            self.profile_details_placeholder.setVisible(True)
            self.profile_details_form.setVisible(False)
            self.api_key_display.clear()
            self.api_key_display.setPlaceholderText("No API key for this profile")
            return

        item_type = item_data.get('type', 'profile')

        # Handle vehicle/profile items
        if item_type in ('profile', 'vehicle'):
            profile = item_data.get('data', item_data)

            # Hide placeholder and show details form
            self.profile_details_placeholder.setVisible(False)
            self.profile_details_form.setVisible(True)

            for key, label in self.info_labels.items():
                label.setText(str(profile.get(key, '-')))

            # Load API key for selected profile (also check by owner_id as fallback)
            self._load_api_key_for_profile(profile.get('profile_id'), profile.get('owner_id'))
            # Load service history for selected profile
            self._load_service_history(profile.get('name', ''))

        # Handle owner items - show owner details and API key
        elif item_type == 'owner':
            owner_data = item_data.get('data', item_data)
            owner_id = owner_data.get('owner_id') or item_data.get('owner_id')

            # Show details form for owner
            self.profile_details_placeholder.setVisible(False)
            self.profile_details_form.setVisible(True)

            # Update labels with owner info
            for key, label in self.info_labels.items():
                if key == 'name':
                    label.setText(str(owner_data.get('name', '-')))
                elif key == 'make':
                    label.setText(f"Owner ID: {owner_id}")
                elif key == 'model':
                    vehicles = owner_data.get('vehicles', [])
                    label.setText(f"{len(vehicles)} vehicle(s)")
                else:
                    label.setText('-')

            # Load API key for owner (check by owner_id)
            self._load_api_key_for_owner(owner_id)
            # Clear service history for owners
            self._load_service_history('')

        # Handle driver items
        elif item_type == 'driver':
            driver_data = item_data.get('data', item_data)
            driver_id = driver_data.get('driver_id')
            profile_id = item_data.get('profile_id')

            # Show details form for driver
            self.profile_details_placeholder.setVisible(False)
            self.profile_details_form.setVisible(True)

            # Update labels with driver info
            for key, label in self.info_labels.items():
                if key == 'name':
                    label.setText(str(driver_data.get('name', '-')))
                elif key == 'make':
                    label.setText(f"Driver")
                elif key == 'model':
                    label.setText(driver_data.get('relationship', '-'))
                elif key == 'year':
                    label.setText(driver_data.get('phone', '-') or '-')
                else:
                    label.setText('-')

            # Load API key for driver
            self._load_api_key_for_driver(driver_id)
            self._load_service_history('')

        else:
            # For placeholder items, clear details
            self.profile_details_placeholder.setVisible(True)
            self.profile_details_form.setVisible(False)
            self.api_key_display.clear()
            self.api_key_display.setPlaceholderText("Select a vehicle to view details")

    def _on_item_clicked(self, item, column):
        """Handle single-click on tree items - open dialogs for add placeholders or info panel"""
        item_data = item.data(0, Qt.UserRole)
        if not item_data:
            return

        item_type = item_data.get('type', 'profile')

        # Check if info button column (column 7) was clicked
        if column == 7 and item_type in ('owner', 'profile', 'driver'):
            self._show_info_panel(item_data)
            return

        # Single click opens add dialogs for placeholder items
        if item_type == 'add_driver':
            profile_id = item_data.get('profile_id')
            if profile_id:
                self._add_driver_dialog(profile_id)
        elif item_type == 'add_vehicle':
            owner_id = item_data.get('owner_id')
            print(f"[DEBUG] _on_item_clicked: add_vehicle clicked, owner_id={owner_id}, item_data={item_data}")
            if owner_id:
                self._add_vehicle_for_owner(owner_id)
            else:
                print("[ERROR] _on_item_clicked: owner_id is None for add_vehicle item")

    def _on_item_double_clicked(self, item, column):
        """Handle double-click on tree items - profiles, drivers, or add placeholders"""
        item_data = item.data(0, Qt.UserRole)
        if not item_data:
            return

        item_type = item_data.get('type', 'profile')

        if item_type == 'add_driver':
            # Double-clicked on "Add Driver" - open add dialog (also handled by single click)
            profile_id = item_data.get('profile_id')
            if profile_id:
                self._add_driver_dialog(profile_id)
        elif item_type == 'add_vehicle':
            # Double-clicked on "Add Vehicle" - open add vehicle dialog (also handled by single click)
            owner_id = item_data.get('owner_id')
            print(f"[DEBUG] _on_item_double_clicked: add_vehicle, owner_id={owner_id}")
            if owner_id:
                self._add_vehicle_for_owner(owner_id)
            else:
                print("[ERROR] _on_item_double_clicked: owner_id is None for add_vehicle item")
        elif item_type == 'driver':
            # Double-clicked on a driver - open edit dialog
            driver = item_data.get('data', {})
            profile_id = item_data.get('profile_id')
            self._edit_driver_dialog(driver, profile_id)
        elif item_type == 'owner':
            # Double-clicked on owner - just expand/collapse
            item.setExpanded(not item.isExpanded())
        elif item_type in ('standalone_group',):
            # Don't do anything for group headers
            item.setExpanded(not item.isExpanded())
        else:
            # Double-clicked on a profile - load it
            self._load_profile()

    # === INFO PANEL HANDLERS ===

    def _show_info_panel(self, item_data: dict):
        """Show the info panel with data for the clicked item"""
        if not self.info_panel:
            # Fallback if InfoPanelWidget not available
            QMessageBox.information(self, "Info", "Info panel not available")
            return

        item_type = item_data.get('type', '')
        data = item_data.get('data', {})

        if item_type == 'owner':
            # Fetch full owner data with vehicles and behavior
            owner_data = self._get_owner_info(data)
            self.info_panel.show_owner_info(owner_data)
        elif item_type == 'profile':
            # Fetch full vehicle data with drivers and predictions
            vehicle_data = self._get_vehicle_info(data)
            self.info_panel.show_vehicle_info(vehicle_data)
            # Kick off async research fetch
            profile_id = data.get('profile_id')
            if profile_id:
                self._fetch_vehicle_research_async(profile_id)
        elif item_type == 'driver':
            # Fetch full driver data with behavior
            driver_data = self._get_driver_info(data)
            self.info_panel.show_driver_info(driver_data)
        else:
            return

        # Hide Profile Details panel when showing info panel (prevents overlap)
        if hasattr(self, 'right_scroll'):
            self.right_scroll.setVisible(False)

        self.info_panel.setVisible(True)

    def _get_owner_info(self, owner: dict) -> dict:
        """Get complete owner information for the info panel including server data"""
        from datetime import datetime

        owner_id = owner.get('owner_id')
        # For server users, use numeric server_user_id for server lookups
        numeric_user_id = owner.get('server_user_id') or owner.get('user_id')

        # Get vehicles for owner - only for local (integer) owner_ids
        if owner_id and isinstance(owner_id, int):
            vehicles = self.vehicle_manager.get_vehicles_for_owner(owner_id) or []
        else:
            vehicles = []

        # Format created_at - handle both timestamps (float) and strings
        created_at = owner.get('created_at', 0)
        try:
            if isinstance(created_at, (int, float)) and created_at > 0:
                created_at_formatted = datetime.fromtimestamp(created_at).strftime('%b %d, %Y')
            elif isinstance(created_at, str) and created_at:
                # Already a formatted string (from server), use as-is
                created_at_formatted = created_at
            else:
                created_at_formatted = ''
        except Exception:
            created_at_formatted = str(created_at) if created_at else ''

        # Fetch user data from unified user server
        server_user_data = {}
        try:
            from server_api_client import get_unified_user_client
            client = get_unified_user_client()
            users_response = client.list_users()
            # ApiResponse is a dataclass with .success and .data attributes
            if users_response.success:
                data = users_response.data or {}
                users = data.get('users', [])
                # Try to match by server_user_id, email, api_key, or name
                owner_email = owner.get('email', '').lower()
                owner_name = owner.get('name', '').lower()
                owner_api_key = owner.get('api_key', '')
                for user in users:
                    user_email = user.get('email', '').lower()
                    user_name = user.get('name', '').lower()
                    user_api_key = user.get('api_key', '')
                    user_id = user.get('user_id')
                    # Match by numeric ID, email, api_key, or name
                    if (numeric_user_id and user_id == numeric_user_id) or \
                       (numeric_user_id and str(user_id) == str(numeric_user_id)) or \
                       (owner_email and user_email == owner_email) or \
                       (owner_api_key and user_api_key and owner_api_key == user_api_key) or \
                       (owner_name and user_name == owner_name):
                        server_user_data = {
                            'user_id': user.get('user_id'),
                            'tier': user.get('tier', 'free'),
                            'status': user.get('status', 'active'),
                            'features': user.get('features', []),
                            'limits': user.get('limits', {}),
                            'api_key': user.get('api_key', ''),
                            'last_used_at': user.get('last_used_at', ''),
                            'key_created_at': user.get('key_created_at', ''),
                            'online_status': user.get('online_status', 'Unknown'),
                        }
                        # Fetch usage stats
                        try:
                            usage_response = client.get_usage(user.get('user_id'))
                            if usage_response.success:
                                usage_data = usage_response.data or {}
                                server_user_data['usage'] = usage_data.get('usage', {})
                        except Exception:
                            pass  # Usage fetch is optional
                        break
        except Exception as e:
            print(f"[ProfilesTab] Could not fetch unified user data: {e}")

        # Driving behavior placeholder
        behavior = {
            'safety_score': 0,
            'total_trips': 0,
            'total_distance_km': 0,
            'violations': 0
        }

        return {
            **owner,
            **server_user_data,  # Merge server data (will override local data)
            'owner_id': owner_id,  # Keep owner_id
            'server_user_id': numeric_user_id,  # Preserve numeric ID for server operations
            'vehicles': vehicles,
            'created_at_formatted': created_at_formatted,
            'driving_behavior': behavior,
            'last_seen': 'N/A'
        }

    def _get_vehicle_info(self, vehicle: dict) -> dict:
        """Get complete vehicle information for the info panel"""
        from datetime import datetime

        profile_id = vehicle.get('profile_id')

        # Get drivers for vehicle
        drivers = self.vehicle_manager.get_drivers_for_profile(profile_id) or []

        # Add is_owner_driver flag to drivers
        for driver in drivers:
            driver['is_owner_driver'] = driver.get('relationship') == 'owner'

        # Get health data (from AI module if available)
        health = {
            'overall_score': 0,
            'components': {}
        }

        # Get predictions (placeholder - will be fetched from server)
        predictions = []

        # Get last seen info
        last_seen = vehicle.get('last_obd_connection', '')
        try:
            if last_seen:
                last_seen = datetime.fromisoformat(last_seen.replace('Z', '+00:00')).strftime('%b %d, %Y %I:%M %p')
        except:
            last_seen = 'Never'

        return {
            **vehicle,
            'drivers': drivers,
            'health': health,
            'predictions': predictions,
            'last_location': 'N/A',
            'last_seen': last_seen or 'Never'
        }

    def _get_driver_info(self, driver: dict) -> dict:
        """Get complete driver information for the info panel"""
        from datetime import datetime

        driver_id = driver.get('driver_id')

        # Get vehicles this driver is assigned to
        vehicles = []  # TODO: Implement vehicle lookup by driver

        # Format created_at
        created_at = driver.get('created_at', 0)
        try:
            created_at_formatted = datetime.fromtimestamp(created_at).strftime('%b %d, %Y') if created_at else ''
        except:
            created_at_formatted = ''

        # Driving behavior (placeholder - will be fetched from server)
        behavior = {
            'safety_score': 0,
            'total_trips': 0,
            'total_distance_km': 0,
            'violations': {'speeding': 0, 'harsh_braking': 0},
            'avg_speed': 0,
            'max_speed': 0,
            'harsh_braking_events': 0,
            'harsh_accel_events': 0
        }

        return {
            **driver,
            'vehicles': vehicles,
            'created_at_formatted': created_at_formatted,
            'behavior': behavior,
            'last_active': 'N/A'
        }

    def _on_info_panel_closed(self):
        """Handle info panel close"""
        # Restore Profile Details panel when info panel closes
        if hasattr(self, 'right_scroll'):
            self.right_scroll.setVisible(True)

    def _fetch_vehicle_research_async(self, profile_id: int):
        """Start a background thread to fetch vehicle research and update the info panel."""
        # Cancel any previous worker still running
        if hasattr(self, '_research_worker') and self._research_worker is not None:
            if self._research_worker.isRunning():
                self._research_worker.quit()
                self._research_worker.wait(500)

        worker = VehicleResearchFetchWorker(profile_id, parent=self)
        worker.research_ready.connect(self._on_research_fetched)
        worker.mode06_ready.connect(self._on_mode06_fetched)
        worker.fetch_failed.connect(self._on_research_fetch_failed)
        self._research_worker = worker
        worker.start()

    def _on_research_fetched(self, research_data: dict):
        """Called on GUI thread when research data arrives from the worker."""
        if hasattr(self, 'info_panel') and self.info_panel and self.info_panel.isVisible():
            self.info_panel.update_vehicle_intelligence(research_data)

    def _on_mode06_fetched(self, mode06_data: dict):
        """Called on GUI thread when Mode 06 ECU test data arrives from the worker."""
        if hasattr(self, 'info_panel') and self.info_panel and self.info_panel.isVisible():
            self.info_panel.update_mode06_data(mode06_data)

    def _on_research_fetch_failed(self, error_msg: str):
        """Called on GUI thread when research fetch fails."""
        import logging
        logging.getLogger(__name__).debug(f"Research fetch failed: {error_msg}")
        if hasattr(self, 'info_panel') and self.info_panel and self.info_panel.isVisible():
            self.info_panel.update_vehicle_intelligence({'research_status': 'failed'})

    def _on_pdf_requested(self, report_type: str, item_id):
        """Handle PDF generation request from info panel"""
        from PySide6.QtWidgets import QMessageBox, QFileDialog
        import os

        try:
            if not hasattr(self, 'pdf_exporter') or not self.pdf_exporter:
                QMessageBox.warning(self, "PDF Not Available",
                    "PDF generation is not available. Please ensure the PDF module is loaded.")
                return

            # Get data from the info panel
            panel_data = self.info_panel.current_data if self.info_panel else {}
            if not panel_data:
                QMessageBox.warning(self, "No Data", "No data available for report generation.")
                return

            # Determine file name based on report type
            name = panel_data.get('name', 'Unknown').replace(' ', '_')
            if report_type == 'owner':
                default_name = f"PREDICT_Customer_Report_{name}.pdf"
            elif report_type == 'vehicle':
                default_name = f"PREDICT_Vehicle_Report_{name}.pdf"
            else:
                default_name = f"PREDICT_Report_{name}.pdf"

            # Ask user for save location
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save Report", default_name, "PDF Files (*.pdf)"
            )
            if not file_path:
                return

            # Build vehicle profile for report
            if report_type == 'owner':
                vehicles = panel_data.get('vehicles', [])
                profile = vehicles[0] if vehicles else {
                    'name': panel_data.get('name', 'Unknown'),
                    'make': '', 'model': '', 'year': '',
                    'vin': '', 'license_plate': ''
                }
            else:
                profile = panel_data

            # Generate the report
            result = self.pdf_exporter.generate_master_report(
                profile=profile,
                snapshot=None,
                ai_module=None
            )

            if result.get('success') and self.pdf_exporter.save_pdf(file_path):
                QMessageBox.information(self, "Success",
                    f"Report saved successfully to:\n{file_path}")
                try:
                    os.startfile(file_path)
                except Exception:
                    pass  # May fail on non-Windows or if no PDF viewer
            else:
                QMessageBox.warning(self, "Error",
                    f"Failed to generate report: {result.get('error', 'Unknown error')}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate PDF: {e}")

    def _on_action_requested(self, action: str, data: dict):
        """Handle action requests from info panel"""
        from PySide6.QtWidgets import QMessageBox

        if action == 'upgrade_tier':
            owner_id = data.get('owner_id')
            if TierUpgradeDialog is not None:
                # Get full owner data for the dialog
                owner_data = self._get_owner_info({'owner_id': owner_id})
                dialog = TierUpgradeDialog(owner_data, self)
                dialog.upgrade_requested.connect(self._process_tier_upgrade_request)
                dialog.exec()
            else:
                QMessageBox.warning(
                    self,
                    "Feature Unavailable",
                    "Tier upgrade dialog is not available. Please check your installation."
                )
        elif action == 'view_api_key':
            owner_id = data.get('owner_id')
            # Try to get and show the API key
            owner = self.vehicle_manager.get_owner_by_id(owner_id)
            if owner and owner.get('api_key'):
                QMessageBox.information(
                    self,
                    "API Key",
                    f"API Key for {owner.get('name', 'Owner')}:\n\n{owner['api_key']}"
                )
            else:
                QMessageBox.warning(self, "No API Key", "No API key found for this owner.")
        elif action == 'view_trends':
            profile_id = data.get('profile_id')
            QMessageBox.information(
                self,
                "View Trends",
                f"View trends for vehicle ID: {profile_id}\n\nThis feature is being implemented."
            )
        elif action == 'add_driver':
            profile_id = data.get('profile_id')
            if profile_id:
                self._add_driver_dialog(profile_id)
        elif action == 'view_violations':
            driver_id = data.get('driver_id')
            QMessageBox.information(
                self,
                "View Violations",
                f"View violations for driver ID: {driver_id}\n\nThis feature is being implemented."
            )
        elif action == 'remove_driver':
            driver_id = data.get('driver_id')
            reply = QMessageBox.question(
                self,
                "Remove Driver",
                f"Are you sure you want to remove this driver?\n\nDriver ID: {driver_id}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                # TODO: Implement driver removal
                QMessageBox.information(self, "Removed", "Driver removal is being implemented.")
        elif action == 'check_recalls':
            # Check NHTSA recalls for this vehicle
            make = data.get('make', '')
            model = data.get('model', '')
            year = data.get('year', 0)
            profile_id = data.get('profile_id')

            if make and model and year:
                self._check_vehicle_recalls(make, model, year, profile_id)
            else:
                QMessageBox.warning(
                    self,
                    "Missing Data",
                    "Vehicle make, model, and year are required to check recalls."
                )
        elif action == 'refresh_research':
            # Refresh LLM research for this vehicle
            make = data.get('make', '')
            model = data.get('model', '')
            year = data.get('year', 0)
            profile_id = data.get('profile_id')

            if make and model and year:
                self._refresh_vehicle_research(make, model, year, profile_id)
            else:
                QMessageBox.warning(
                    self,
                    "Missing Data",
                    "Vehicle make, model, and year are required to refresh research."
                )
        elif action == 'user_deleted':
            # User was deleted from the info panel - refresh the tree
            user_id = data.get('user_id')
            print(f"[ProfilesTab] User {user_id} deleted, refreshing profiles")
            self.refresh_profiles()
        elif action == 'send_api_key_email':
            # Send API key email to user
            user_id = data.get('user_id')
            try:
                from server_api_client import get_unified_user_client
                client = get_unified_user_client()
                # This would trigger an email from the server
                # For now, just show a message
                QMessageBox.information(
                    self,
                    "Email Notification",
                    "Email notification will be sent from the server.\n\n"
                    "This feature requires server email configuration."
                )
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not send email: {e}")

    def _check_vehicle_recalls(self, make: str, model: str, year: int, profile_id: int):
        """Check NHTSA recalls for a vehicle and update info panel"""
        from PySide6.QtWidgets import QMessageBox, QProgressDialog
        from PySide6.QtCore import Qt

        try:
            # Import recall monitor
            from recall_monitor import check_recalls, get_recall_summary

            # Show progress
            progress = QProgressDialog(
                f"Checking recalls for {make} {model} {year}...",
                None, 0, 0, self
            )
            progress.setWindowTitle("Checking Recalls")
            progress.setWindowModality(Qt.WindowModal)
            progress.show()

            # Force check (not from cache)
            result = check_recalls(make, model, year, force=True)

            progress.close()

            if result.success:
                if result.total_recalls > 0:
                    msg = f"Found {result.total_recalls} recall(s) for {make} {model} {year}"
                    if result.critical_recalls > 0:
                        msg += f"\n\nCRITICAL: {result.critical_recalls} critical recall(s)!"
                    if result.has_new_recalls:
                        msg += f"\n\nNEW: {len(result.new_recalls)} new recall(s) since last check"

                    # Show recall details
                    for i, recall in enumerate(result.recalls[:3]):
                        msg += f"\n\n{i+1}. {recall.component}"
                        msg += f"\n   Severity: {recall.severity.upper()}"
                        if recall.summary:
                            short_summary = recall.summary[:100] + "..." if len(recall.summary) > 100 else recall.summary
                            msg += f"\n   {short_summary}"

                    QMessageBox.warning(self, "Recalls Found", msg)
                else:
                    QMessageBox.information(
                        self,
                        "No Recalls",
                        f"No active recalls found for {make} {model} {year}.\n\nYour vehicle is clear!"
                    )

                # Refresh the info panel to show updated recall data
                if hasattr(self, 'info_panel') and self.info_panel.isVisible():
                    self._refresh_current_info_panel()
            else:
                QMessageBox.warning(
                    self,
                    "Check Failed",
                    f"Failed to check recalls: {result.error_message}"
                )

        except ImportError:
            QMessageBox.warning(
                self,
                "Feature Unavailable",
                "Recall monitoring is not available. Please check your installation."
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to check recalls: {e}")

    def _refresh_vehicle_research(self, make: str, model: str, year: int, profile_id: int):
        """Refresh LLM research for a vehicle via the production API."""
        from PySide6.QtWidgets import QMessageBox

        if not profile_id:
            QMessageBox.warning(self, "Missing Data", "Vehicle profile ID is required to refresh research.")
            return

        try:
            from predict.desktop.api_client import PredictAPIClient
            client = PredictAPIClient()
            result = client.refresh_vehicle_research(profile_id)

            if result.get('success'):
                QMessageBox.information(
                    self,
                    "Research Queued",
                    f"Research refresh queued for {make} {model} {year}.\n\n"
                    f"The Vehicle Intelligence panel will update automatically\n"
                    f"when results are ready (30-60 seconds)."
                )
                # Update the panel to show "researching" state
                if hasattr(self, 'info_panel') and self.info_panel and self.info_panel.isVisible():
                    self.info_panel.update_vehicle_intelligence({'research_status': 'researching'})
            else:
                error = result.get('error') or result.get('message') or 'Unknown error'
                QMessageBox.warning(self, "Refresh Failed", f"Could not queue research: {error}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to refresh research: {e}")

    def _refresh_current_info_panel(self):
        """Refresh the currently displayed info panel with updated data"""
        if not hasattr(self, 'info_panel') or not self.info_panel.isVisible():
            return

        current_type = self.info_panel.current_type
        current_id = self.info_panel.current_id
        current_data = self.info_panel.current_data

        if current_type == 'vehicle' and current_id:
            # Reload vehicle data with updated recall/research info
            updated_data = self._get_vehicle_info(current_data)
            self.info_panel.show_vehicle_info(updated_data)

    def _process_tier_upgrade_request(self, owner_id: str, new_tier: str, request_data: dict):
        """Process a tier upgrade request from the dialog"""
        from PySide6.QtWidgets import QMessageBox
        import time
        import json

        try:
            # Save the upgrade request to the database
            # This will be reviewed by an admin
            conn = self.vehicle_manager.get_db_connection()
            if conn:
                cur = conn.cursor()

                # Check if tier_upgrade_requests table exists, create if not
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS tier_upgrade_requests (
                        request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        owner_id INTEGER NOT NULL,
                        customer_id TEXT,
                        current_tier TEXT NOT NULL,
                        requested_tier TEXT NOT NULL,
                        status TEXT DEFAULT 'pending',
                        requested_at REAL NOT NULL,
                        processed_at REAL,
                        processed_by TEXT,
                        notes TEXT,
                        new_api_key_hash TEXT,
                        owner_name TEXT,
                        owner_email TEXT,
                        tier_price TEXT,
                        tier_features TEXT
                    )
                """)

                # Insert the upgrade request
                cur.execute("""
                    INSERT INTO tier_upgrade_requests (
                        owner_id, current_tier, requested_tier, status,
                        requested_at, owner_name, owner_email, tier_price, tier_features
                    ) VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?)
                """, (
                    owner_id,
                    request_data.get('current_tier', 'free'),
                    new_tier,
                    time.time(),
                    request_data.get('owner_name', ''),
                    request_data.get('owner_email', ''),
                    request_data.get('tier_price', ''),
                    json.dumps(request_data.get('tier_features', []))
                ))

                conn.commit()
                conn.close()

                logger.info(f"Tier upgrade request saved: Owner {owner_id} requested {new_tier}")

        except Exception as e:
            logger.error(f"Failed to save tier upgrade request: {e}")
            QMessageBox.warning(
                self,
                "Error",
                f"Failed to save upgrade request: {e}"
            )

    def _filter_profiles(self):
        """Filter profiles based on search text in tree view"""
        search_text = self.search_box.text().lower()

        def filter_item(item):
            """Recursively filter tree items"""
            profile = item.data(0, Qt.UserRole)
            if not profile:
                item.setHidden(True)
                return False

            name = str(profile.get('name', '')).lower()
            license_plate = str(profile.get('license_plate', '')).lower()
            make = str(profile.get('make', '')).lower()
            model = str(profile.get('model', '')).lower()

            # Check if this item matches
            matches = (not search_text or
                       search_text in name or
                       search_text in license_plate or
                       search_text in make or
                       search_text in model)

            # Check children
            any_child_matches = False
            for i in range(item.childCount()):
                child = item.child(i)
                if filter_item(child):
                    any_child_matches = True

            # Show if this item or any child matches
            should_show = matches or any_child_matches
            item.setHidden(not should_show)

            # Expand if child matches
            if any_child_matches:
                item.setExpanded(True)

            return should_show

        # Filter all top-level items
        for i in range(self.tree.topLevelItemCount()):
            filter_item(self.tree.topLevelItem(i))

    def update_connection_status(self, device_id: str, status: str):
        """Update connection indicator based on mobile app connection status"""
        from datetime import datetime
        is_online = status.lower() in ['active', 'connected', 'online']

        if is_online:
            # Update last connection time and flag
            self._last_connection_time = datetime.now()
            self._is_connected = True
            self._last_device_id = device_id

            self.connection_indicator.setStyleSheet("color: #4CAF50; font-size: 20px;")  # Green
            self.connection_status_label.setText(f"Connected: {device_id}")
            self.connection_status_label.setStyleSheet("color: #4CAF50; font-size: 11px;")
            logger.debug(f"ProfilesTab: Connection indicator set to GREEN for {device_id}")
        else:
            self._is_connected = False
            self.connection_indicator.setStyleSheet("color: #F44336; font-size: 20px;")  # Red
            self.connection_status_label.setText("Disconnected")
            self.connection_status_label.setStyleSheet("color: #F44336; font-size: 11px;")
            logger.debug(f"ProfilesTab: Connection indicator set to RED for {device_id}")

    def _check_connection_timeout(self):
        """Check if connection has timed out (no data received)"""
        from datetime import datetime
        if self._is_connected and self._last_connection_time:
            elapsed = (datetime.now() - self._last_connection_time).total_seconds()
            if elapsed > self._connection_timeout_seconds:
                # Timeout - mark as disconnected
                self._is_connected = False
                self.connection_indicator.setStyleSheet("color: #888888; font-size: 20px;")  # Gray = timeout
                self.connection_status_label.setText("Connection timeout")
                self.connection_status_label.setStyleSheet("color: #888888; font-size: 11px;")
                logger.debug(f"ProfilesTab: Connection timed out after {elapsed:.1f}s")

    def update_heartbeat_status(self, device_id: str, old_status, new_status):
        """Update connection indicator based on heartbeat status"""
        from datetime import datetime
        # DeviceStatus enum: ONLINE, OFFLINE, DEGRADED, UNKNOWN
        status_name = new_status.name if hasattr(new_status, 'name') else str(new_status)
        if status_name == 'ONLINE':
            self._last_connection_time = datetime.now()
            self._is_connected = True
            self._last_device_id = device_id
            self.connection_indicator.setStyleSheet("color: #4CAF50; font-size: 20px;")  # Green
            self.connection_status_label.setText(f"Online: {device_id}")
            self.connection_status_label.setStyleSheet("color: #4CAF50; font-size: 11px;")
        elif status_name == 'DEGRADED':
            self._last_connection_time = datetime.now()
            self._is_connected = True
            self.connection_indicator.setStyleSheet("color: #FFC107; font-size: 20px;")  # Yellow/warning
            self.connection_status_label.setText(f"Degraded: {device_id}")
            self.connection_status_label.setStyleSheet("color: #FFC107; font-size: 11px;")
        else:
            self._is_connected = False
            self.connection_indicator.setStyleSheet("color: #F44336; font-size: 20px;")  # Red
            self.connection_status_label.setText("Offline")
            self.connection_status_label.setStyleSheet("color: #F44336; font-size: 11px;")

    def _load_api_key_for_profile(self, profile_id, owner_id=None):
        """Load API key from SERVER for the selected profile or owner"""
        if not profile_id and not owner_id:
            self.api_key_display.clear()
            self.api_key_display.setPlaceholderText("No API key for this profile")
            self._current_api_key = None
            return

        try:
            # Load from server API (source of truth)
            from server_api_client import get_server_client

            client = get_server_client()
            response = client.list_api_keys()

            if not response.success:
                self.api_key_display.clear()
                self.api_key_display.setPlaceholderText(f"Server error: {response.error}")
                self._current_api_key = None
                logger.error(f"Failed to load API keys from server: {response.error}")
                return

            api_keys = response.data.get('api_keys', [])

            # Find best matching key - prioritize admin tier, then by profile_id, then owner_id
            matching_keys = []
            for key_data in api_keys:
                # Handle both integer profile_id and nested object with profile_id
                stored_profile_id = key_data.get("profile_id")
                if isinstance(stored_profile_id, dict):
                    stored_profile_id = stored_profile_id.get("profile_id")
                stored_owner_id = key_data.get("owner_id")

                # Check for match by profile_id or owner_id
                match_type = None
                if profile_id and stored_profile_id == profile_id:
                    match_type = 'profile'
                elif owner_id and stored_owner_id == owner_id:
                    match_type = 'owner'

                if match_type:
                    tier = key_data.get('tier', 'free')
                    priority = 0 if tier == 'admin' else (1 if tier == 'premium' else 2)
                    matching_keys.append((priority, match_type, key_data))

            # Sort by priority (admin first) and prefer profile match over owner match
            matching_keys.sort(key=lambda x: (x[0], 0 if x[1] == 'profile' else 1))

            if matching_keys:
                _, match_type, key_data = matching_keys[0]
                key_name = key_data.get("name", "Unnamed Key")
                tier = key_data.get("tier", "free")
                status = key_data.get("status", "active")
                key_preview = key_data.get("key_preview", "****-****-****")
                created = key_data.get("created_at", "")

                if created:
                    try:
                        from datetime import datetime
                        if isinstance(created, (int, float)):
                            dt = datetime.fromtimestamp(created)
                        else:
                            dt = datetime.fromisoformat(str(created))
                        created = dt.strftime("%Y-%m-%d")
                    except:
                        created = ""

                # Display masked key preview (can't show actual key from server)
                self.api_key_display.setText(key_preview)
                self.api_key_display.setReadOnly(True)  # Server keys are read-only
                tooltip = f"Key: {key_name} | Tier: {tier.upper()} | Status: {status.upper()}"
                if match_type == 'owner':
                    tooltip += " (via Owner)"
                if created:
                    tooltip += f" | Created: {created}"
                tooltip += "\n(Server-managed key - preview only)"
                self.api_key_display.setToolTip(tooltip)
                self._current_api_key = None  # Can't store actual key from server
                self.api_key_visible = False
                self.api_key_toggle_btn.setText("👁️")
                if hasattr(self, 'api_key_toggle_btn'):
                    self.api_key_toggle_btn.setEnabled(False)  # Can't reveal server keys
                return

            # No key found for this profile
            self.api_key_display.clear()
            self.api_key_display.setPlaceholderText("No API key found for this profile")
            self._current_api_key = None

        except Exception as e:
            logger.error(f"Error loading API key from server: {e}")
            self.api_key_display.clear()
            self.api_key_display.setPlaceholderText(f"Error: {str(e)}")
            self._current_api_key = None

    def _load_api_key_for_owner(self, owner_id):
        """Load API key(s) associated with an owner"""
        if not owner_id:
            self.api_key_display.clear()
            self.api_key_display.setPlaceholderText("No owner selected")
            self._current_api_key = None
            return

        try:
            api_keys_file = CONFIG.API_KEYS_FILE if CONFIG else Path("config/api_keys.json")
            if not api_keys_file.exists():
                self.api_key_display.clear()
                self.api_key_display.setPlaceholderText("API keys file not found")
                self._current_api_key = None
                return

            with open(api_keys_file, 'r') as f:
                api_keys = json.load(f)

            # Find API key for this owner_id
            for key_id, key_data in api_keys.items():
                stored_owner_id = key_data.get("owner_id")

                if stored_owner_id == owner_id:
                    key_name = key_data.get("name", "Unnamed Key")
                    created = key_data.get("created", "")[:10] if key_data.get("created") else ""

                    # Try to decrypt the API key
                    key_encrypted = key_data.get("key_encrypted", "")
                    raw_key = None

                    if key_encrypted:
                        raw_key = self._decrypt_api_key(key_encrypted)

                    if raw_key:
                        self.api_key_display.setText(raw_key)
                        self.api_key_display.setEchoMode(QLineEdit.Password)
                        self.api_key_display.setToolTip(f"Owner Key: {key_name} (Created: {created})")
                        self._current_api_key = raw_key
                        self.api_key_visible = False
                        self.api_key_toggle_btn.setText("👁️")
                        return
                    else:
                        # Fallback: try backup file
                        raw_key = self._get_raw_api_key_from_backup(key_name, key_data.get("profile_name", ""))
                        if raw_key:
                            self.api_key_display.setText(raw_key)
                            self.api_key_display.setEchoMode(QLineEdit.Password)
                            self.api_key_display.setToolTip(f"Owner Key: {key_name} (from backup)")
                            self._current_api_key = raw_key
                            self.api_key_visible = False
                            self.api_key_toggle_btn.setText("👁️")
                            return
                        else:
                            self.api_key_display.setText(key_data.get("key_hidden", "***"))
                            self.api_key_display.setEchoMode(QLineEdit.Normal)
                            self.api_key_display.setToolTip(f"Owner Key: {key_name} (encrypted)")
                            self._current_api_key = None
                            return

            # No key found for this owner
            self.api_key_display.clear()
            self.api_key_display.setPlaceholderText("No API key found for this owner")
            self._current_api_key = None

        except Exception as e:
            logger.error(f"Error loading owner API key: {e}")
            self.api_key_display.clear()
            self.api_key_display.setPlaceholderText(f"Error: {str(e)}")
            self._current_api_key = None

    def _load_api_key_for_driver(self, driver_id):
        """Load API key(s) associated with a driver"""
        if not driver_id:
            self.api_key_display.clear()
            self.api_key_display.setPlaceholderText("No driver selected")
            self._current_api_key = None
            return

        try:
            api_keys_file = CONFIG.API_KEYS_FILE if CONFIG else Path("config/api_keys.json")
            if not api_keys_file.exists():
                self.api_key_display.clear()
                self.api_key_display.setPlaceholderText("API keys file not found")
                self._current_api_key = None
                return

            with open(api_keys_file, 'r') as f:
                api_keys = json.load(f)

            # Find API key for this driver_id
            for key_id, key_data in api_keys.items():
                stored_driver_id = key_data.get("driver_id")

                if stored_driver_id == driver_id:
                    key_name = key_data.get("name", "Unnamed Key")
                    created = key_data.get("created", "")[:10] if key_data.get("created") else ""

                    # Try to decrypt the API key
                    key_encrypted = key_data.get("key_encrypted", "")
                    raw_key = None

                    if key_encrypted:
                        raw_key = self._decrypt_api_key(key_encrypted)

                    if raw_key:
                        self.api_key_display.setText(raw_key)
                        self.api_key_display.setEchoMode(QLineEdit.Password)
                        self.api_key_display.setToolTip(f"Driver Key: {key_name} (Created: {created})")
                        self._current_api_key = raw_key
                        self.api_key_visible = False
                        self.api_key_toggle_btn.setText("👁️")
                        return
                    else:
                        # Fallback: try backup file
                        raw_key = self._get_raw_api_key_from_backup(key_name, key_data.get("profile_name", ""))
                        if raw_key:
                            self.api_key_display.setText(raw_key)
                            self.api_key_display.setEchoMode(QLineEdit.Password)
                            self.api_key_display.setToolTip(f"Driver Key: {key_name} (from backup)")
                            self._current_api_key = raw_key
                            self.api_key_visible = False
                            self.api_key_toggle_btn.setText("👁️")
                            return
                        else:
                            self.api_key_display.setText(key_data.get("key_hidden", "***"))
                            self.api_key_display.setEchoMode(QLineEdit.Normal)
                            self.api_key_display.setToolTip(f"Driver Key: {key_name} (encrypted)")
                            self._current_api_key = None
                            return

            # No key found for this driver
            self.api_key_display.clear()
            self.api_key_display.setPlaceholderText("No API key found for this driver")
            self._current_api_key = None

        except Exception as e:
            logger.error(f"Error loading driver API key: {e}")
            self.api_key_display.clear()
            self.api_key_display.setPlaceholderText(f"Error: {str(e)}")
            self._current_api_key = None

    def _decrypt_api_key(self, encrypted_text: str) -> Optional[str]:
        """Decrypt API key using XOR with admin password"""
        try:
            import base64
            # Admin password used for encryption
            password = "YOUR_ADMIN_PASSWORD"
            key = hashlib.sha256(password.encode()).digest()
            encrypted = base64.b64decode(encrypted_text.encode()).decode()
            decrypted = []
            for i, char in enumerate(encrypted):
                key_byte = key[i % len(key)]
                decrypted.append(chr(ord(char) ^ key_byte))
            return ''.join(decrypted)
        except Exception as e:
            logger.debug(f"Failed to decrypt API key: {e}")
            return None
    
    def _get_raw_api_key_from_backup(self, key_name: str, profile_name: str) -> Optional[str]:
        """Try to read the raw API key from backup text files"""
        try:
            # Use config path or fallback to legacy path
            if CONFIG:
                keys_folder = Path(CONFIG.get_customer_api_keys_dir("default"))
            else:
                keys_folder = Path("api_keys")

            # Also check legacy path if primary doesn't exist
            if not keys_folder.exists():
                keys_folder = Path("api_keys")

            if not keys_folder.exists():
                return None
            
            # Try different filename patterns
            possible_names = [
                f"{key_name}_apikey.txt",
                f"{profile_name}_apikey.txt",
                f"{key_name}_APIKEY.txt",
                f"{profile_name}_APIKEY.txt"
            ]
            
            for filename in possible_names:
                key_file = keys_folder / filename
                if key_file.exists():
                    with open(key_file, 'r') as f:
                        content = f.read()
                        # Look for "API KEY:" line followed by the key
                        lines = content.split('\n')
                        for i, line in enumerate(lines):
                            if 'API KEY:' in line.upper() and i + 1 < len(lines):
                                raw_key = lines[i + 1].strip()
                                if raw_key and len(raw_key) >= 8:  # Valid key length
                                    return raw_key
            return None
        except Exception as e:
            logger.debug(f"Could not read API key backup file: {e}")
            return None
    
    def _toggle_api_key_visibility(self):
        """Toggle API key visibility (show/hide)"""
        self.api_key_visible = not self.api_key_visible
        if self.api_key_visible:
            self.api_key_display.setEchoMode(QLineEdit.Normal)
            self.api_key_toggle_btn.setText("🙈 Hide")
        else:
            self.api_key_display.setEchoMode(QLineEdit.Password)
            self.api_key_toggle_btn.setText("👁️ Show")
    
    def _copy_api_key_to_clipboard(self):
        """Copy API key to clipboard"""
        if not hasattr(self, '_current_api_keys') or not self._current_api_keys:
            show_info(self, "No API Key", "No API key found for this profile.")
            return
        
        profile = self._get_selected()
        if not profile:
            return
        
        # Get the first key's raw value
        first_key = self._current_api_keys[0]
        raw_key = first_key.get('raw_key')
        
        if raw_key:
            # Copy the actual API key
            QApplication.clipboard().setText(raw_key)
            show_info(self, "Copied", f"API key '{first_key['name']}' copied to clipboard!")
        else:
            # Fallback: copy key info
            profile_name = profile.get('name', 'Unknown')
            key_info = []
            for key in self._current_api_keys:
                key_info.append(f"Key: {key['name']} (Created: {key['created'][:10]})")
            
            clipboard_text = f"Profile: {profile_name}\n" + "\n".join(key_info)
            keys_dir = str(CONFIG.get_customer_api_keys_dir("default")) if CONFIG else "C:/OBDserver/API_KEYS"
            clipboard_text += f"\n\nNote: Raw key not found. Check backup files in {keys_dir}/"
            
            QApplication.clipboard().setText(clipboard_text)
            show_info(self, "Copied", f"API key information copied. Raw key not found in backup files.")
    
    def _load_service_history(self, profile_name):
        """Load service history for the selected profile"""
        self.service_history_list.clear()

        if not profile_name:
            return

        try:
            import sqlite3
            db_path = "./data/service_history.db"
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Get recent service records for this profile
            cursor.execute("""
                SELECT service_date, component_type, service_type, service_km
                FROM service_records
                WHERE profile_name = ?
                ORDER BY service_date DESC
                LIMIT 10
            """, (profile_name,))

            records = cursor.fetchall()
            conn.close()

            if records:
                for date, component, svc_type, km in records:
                    item_text = f"{date} - {component}: {svc_type} ({km} km)"
                    self.service_history_list.addItem(item_text)
            else:
                self.service_history_list.addItem("No service history found")
        except Exception as e:
            self.service_history_list.addItem(f"Error loading history: {e}")

    def update_ai_status(self, learning_state=None, baseline_progress=None, fleet_status=None, last_update=None):
        """
        Update AI Learning Status panel

        Args:
            learning_state: str - One of: "Learning", "Limited Data", "Active Prediction"
            baseline_progress: int - Baseline completion percentage (0-100)
            fleet_status: str - One of: "Active", "Not Available"
            last_update: str - Last update timestamp (e.g., "2025-12-16 14:30")
        """
        if learning_state:
            # Map state to icon and color
            state_map = {
                "Learning": ("🧠 Learning", ProfessionalTheme.SUCCESS),
                "Limited Data": ("⏳ Limited Data", ProfessionalTheme.WARNING),
                "Active Prediction": ("✅ Active Prediction", ProfessionalTheme.SUCCESS_LIGHT)
            }
            icon_text, color = state_map.get(learning_state, ("⏳ Limited Data", ProfessionalTheme.WARNING))
            self.ai_learning_state.setText(icon_text)
            self.ai_learning_state.setStyleSheet(f"color: {color}; font-weight: bold;")

        if baseline_progress is not None:
            self.ai_baseline_progress.setValue(int(baseline_progress))

        if fleet_status:
            fleet_map = {
                "Active": ("✅ Active", ProfessionalTheme.SUCCESS),
                "Not Available": ("⚪ Not Available", ProfessionalTheme.TEXT_MUTED)
            }
            icon_text, color = fleet_map.get(fleet_status, ("⚪ Not Available", ProfessionalTheme.TEXT_MUTED))
            self.ai_fleet_status.setText(icon_text)
            self.ai_fleet_status.setStyleSheet(f"color: {color}; font-weight: bold;")

        if last_update:
            self.ai_last_update.setText(last_update)

    def _add_profile(self):
        """Open Add Owner dialog first, then Add Vehicle dialog"""
        from PySide6.QtWidgets import QMessageBox

        # Ask user what they want to add
        choice_dialog = QMessageBox(self)
        choice_dialog.setWindowTitle("Add New")
        choice_dialog.setText("What would you like to add?")
        choice_dialog.setIcon(QMessageBox.Question)

        owner_btn = choice_dialog.addButton("👤 New Owner + Vehicle", QMessageBox.AcceptRole)
        vehicle_btn = choice_dialog.addButton("🚗 Vehicle Only", QMessageBox.ActionRole)
        cancel_btn = choice_dialog.addButton(QMessageBox.Cancel)

        choice_dialog.setStyleSheet(f"""
            QMessageBox {{
                background-color: {ProfessionalTheme.BACKGROUND_SECONDARY};
                color: {ProfessionalTheme.TEXT_PRIMARY};
            }}
            QLabel {{
                color: {ProfessionalTheme.TEXT_PRIMARY};
                font-size: 13px;
            }}
            QPushButton {{
                background-color: {ProfessionalTheme.PRIMARY};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                min-width: 120px;
            }}
            QPushButton:hover {{
                background-color: {ProfessionalTheme.PRIMARY_LIGHT};
            }}
        """)

        choice_dialog.exec()
        clicked = choice_dialog.clickedButton()

        if clicked == owner_btn:
            # Flow: Add Owner → Add Vehicle
            self._add_owner_then_vehicle_flow()
        elif clicked == vehicle_btn:
            # Add vehicle only (can select existing owner)
            self._add_profile_with_owner(owner_id=None)

    def _add_owner_then_vehicle_flow(self):
        """Complete flow: Add Owner first, then automatically Add Vehicle"""
        from PySide6.QtWidgets import QMessageBox

        print("[DEBUG] _add_owner_then_vehicle_flow started")

        # Step 1: Add Owner
        owner_id = self._add_owner_dialog()
        print(f"[DEBUG] _add_owner_then_vehicle_flow: owner_id returned = {owner_id}")

        if owner_id:
            # Step 2: Ask if they want to add a vehicle now
            reply = QMessageBox.question(
                self,
                "Add Vehicle",
                f"Owner created successfully!\n\nWould you like to add a vehicle for this owner now?",
                QMessageBox.Yes | QMessageBox.No
            )
            print(f"[DEBUG] _add_owner_then_vehicle_flow: reply = {reply}, QMessageBox.Yes = {QMessageBox.Yes}")

            if reply == QMessageBox.Yes:
                print(f"[DEBUG] _add_owner_then_vehicle_flow: Calling _add_vehicle_dialog({owner_id})")
                # Open Add Vehicle dialog with the new owner pre-selected
                self._add_vehicle_dialog(owner_id)
            else:
                print("[DEBUG] _add_owner_then_vehicle_flow: User clicked No")
        else:
            print("[DEBUG] _add_owner_then_vehicle_flow: No owner_id returned, skipping vehicle dialog")

    def _add_vehicle_dialog(self, owner_id: int):
        """Open simplified Add Vehicle dialog (vehicle fields only, owner pre-selected)"""
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout,
                                       QLineEdit, QSpinBox, QComboBox,
                                       QDialogButtonBox, QLabel, QHBoxLayout,
                                       QPushButton, QMessageBox)

        try:
            print(f"[DEBUG] _add_vehicle_dialog called with owner_id={owner_id}")

            dialog = QDialog(self)
            dialog.setWindowTitle("Add Vehicle")
            dialog.setMinimumWidth(500)
            dialog.setStyleSheet(f"""
                QDialog {{
                    background-color: {ProfessionalTheme.BACKGROUND_SECONDARY};
                    color: {ProfessionalTheme.TEXT_PRIMARY};
                }}
                QLabel {{
                    color: {ProfessionalTheme.TEXT_PRIMARY};
                    font-size: 12px;
                }}
                QLineEdit, QSpinBox, QComboBox {{
                    background-color: {ProfessionalTheme.CARD_BG};
                    color: {ProfessionalTheme.TEXT_PRIMARY};
                    border: 1px solid {ProfessionalTheme.BORDER};
                    border-radius: 6px;
                    padding: 8px;
                    font-size: 12px;
                }}
                QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
                    border-color: {ProfessionalTheme.PRIMARY};
                }}
                QGroupBox {{
                    color: {ProfessionalTheme.TEXT_PRIMARY};
                    font-weight: bold;
                    border: 1px solid {ProfessionalTheme.BORDER};
                    border-radius: 6px;
                    margin-top: 10px;
                    padding-top: 10px;
                }}
            """)

            layout = QVBoxLayout(dialog)

            # Header with owner info
            owner = self.vehicle_manager.get_owner_by_id(owner_id) if owner_id else None
            owner_name = owner.get('name', 'Unknown') if owner else 'No Owner'

            header = QLabel(f"🚗 Add New Vehicle for {owner_name}")
            header.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {ProfessionalTheme.TEXT_PRIMARY}; margin-bottom: 15px;")
            layout.addWidget(header)

            # Form - Vehicle Information
            form = QFormLayout()
            form.setSpacing(10)

            # Make (required)
            make_input = QLineEdit()
            make_input.setPlaceholderText("e.g., Nissan, Toyota, BMW")
            form.addRow("Make *:", make_input)

            # Model (required)
            model_input = QLineEdit()
            model_input.setPlaceholderText("e.g., Patrol, Camry, X5")
            form.addRow("Model *:", model_input)

            # Year (required)
            year_input = QSpinBox()
            year_input.setRange(1900, 2030)
            year_input.setValue(2020)
            form.addRow("Year *:", year_input)

            # VIN (optional)
            vin_input = QLineEdit()
            vin_input.setPlaceholderText("17-character Vehicle Identification Number")
            vin_input.setMaxLength(17)
            form.addRow("VIN:", vin_input)

            # License Plate (optional)
            license_input = QLineEdit()
            license_input.setPlaceholderText("e.g., ABC 1234")
            form.addRow("License Plate:", license_input)

            # Category
            category_combo = QComboBox()
            category_combo.addItems(["Commercial", "Personal", "Fleet", "Rental"])
            form.addRow("Category:", category_combo)

            # Fuel Type
            fuel_combo = QComboBox()
            fuel_combo.addItems(["", "Gasoline", "Diesel", "Electric", "Hybrid", "LPG", "CNG"])
            form.addRow("Fuel Type:", fuel_combo)

            # Color (optional)
            color_input = QLineEdit()
            color_input.setPlaceholderText("e.g., White, Black, Silver")
            form.addRow("Color:", color_input)

            layout.addLayout(form)
            layout.addSpacing(15)

            # Buttons
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()

            cancel_btn = QPushButton("Cancel")
            cancel_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {ProfessionalTheme.CARD_BG};
                    color: {ProfessionalTheme.TEXT_PRIMARY};
                    border: 1px solid {ProfessionalTheme.BORDER};
                    padding: 10px 25px;
                    border-radius: 6px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {ProfessionalTheme.CARD_BG_HOVER};
                }}
            """)
            cancel_btn.clicked.connect(dialog.reject)
            btn_layout.addWidget(cancel_btn)

            save_btn = QPushButton("✓ Save Vehicle")
            save_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {ProfessionalTheme.PRIMARY};
                    color: white;
                    border: none;
                    padding: 10px 25px;
                    border-radius: 6px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {ProfessionalTheme.PRIMARY_LIGHT};
                }}
            """)
            save_btn.clicked.connect(dialog.accept)
            btn_layout.addWidget(save_btn)

            layout.addLayout(btn_layout)

            if dialog.exec() == QDialog.Accepted:
                make = make_input.text().strip()
                model = model_input.text().strip()
                year = year_input.value()

                if not make or not model:
                    show_error(self, "Error", "Make and Model are required")
                    return

                # Build profile name from make/model/year
                name = f"{make} {model} {year}"

                profile_data = {
                    'name': name,
                    'make': make,
                    'model': model,
                    'year': year,
                    'vin': vin_input.text().strip() or None,
                    'license_plate': license_input.text().strip() or None,
                    'category': category_combo.currentText(),
                    'fuel_type': fuel_combo.currentText() or None,
                    'color': color_input.text().strip() or None,
                    'owner_id': owner_id
                }

                try:
                    profile_id = self.vehicle_manager.create_profile(profile_data)
                    if profile_id:
                        show_info(self, "Success", f"Vehicle '{name}' added successfully!")
                        self.refresh_profiles()

                        # Ask if they want to add a driver
                        reply = QMessageBox.question(
                            self,
                            "Add Driver",
                            f"Would you like to add a driver for this vehicle?",
                            QMessageBox.Yes | QMessageBox.No
                        )
                        if reply == QMessageBox.Yes:
                            self._add_driver_dialog(profile_id)
                    else:
                        show_error(self, "Error", "Failed to add vehicle")
                except Exception as e:
                    show_error(self, "Error", f"Failed to add vehicle: {e}")

        except Exception as e:
            print(f"[ERROR] _add_vehicle_dialog failed: {e}")
            import traceback
            traceback.print_exc()
            show_error(self, "Error", f"Failed to open Add Vehicle dialog: {e}")
    
    def _edit_profile(self):
        """Edit selected item - handles owners, vehicles, and drivers"""
        item_data = self._get_selected()
        if not item_data:
            show_info(self, "Select Item", "Please select an item to edit")
            return

        item_type = item_data.get('type', 'profile')

        # Don't edit placeholder items
        if item_type in ('add_driver', 'add_vehicle', 'standalone_group'):
            return

        if item_type == 'owner':
            # Edit owner
            owner = item_data.get('data', {})
            owner_name = owner.get('name', '')
            owner_id = owner.get('owner_id')

            if not owner_id:
                show_error(self, "Error", "Cannot identify owner to edit")
                return

            name, ok = QInputDialog.getText(self, "Edit Owner", "Owner Name:", text=owner_name)
            if ok and name:
                try:
                    self.vehicle_manager.update_owner(owner_id, {'name': name})
                    self.refresh_profiles()
                except Exception as e:
                    show_error(self, "Error", f"Failed to update owner: {e}")

        elif item_type == 'driver':
            # Edit driver - open full edit dialog
            driver = item_data.get('data', {})
            profile_id = item_data.get('profile_id')
            self._edit_driver_dialog(driver, profile_id)

        else:
            # Edit vehicle/profile — open full edit dialog
            profile = item_data.get('data', item_data)
            profile_id = profile.get('profile_id')

            if not profile_id:
                show_error(self, "Error", "Cannot identify profile to edit")
                return

            dialog = EditVehicleDialog(profile, parent=self)
            if dialog.exec() == QDialog.Accepted:
                updated_data = dialog.get_updated_data()
                try:
                    self.vehicle_manager.update_profile(profile_id, updated_data)
                    self.refresh_profiles()
                except Exception as e:
                    show_error(self, "Error", f"Failed to update profile: {e}")
    
    def _delete_profile(self):
        """Delete selected item - handles owners, vehicles, and drivers"""
        item_data = self._get_selected()
        if not item_data:
            return

        item_type = item_data.get('type', 'profile')

        # Don't allow deleting placeholder items
        if item_type in ('add_driver', 'add_vehicle', 'standalone_group'):
            return

        if item_type == 'owner':
            # Deleting an owner
            owner = item_data.get('data', {})
            owner_name = owner.get('name', 'Unknown')
            owner_id = owner.get('owner_id')

            if not owner_id:
                show_error(self, "Error", "Cannot identify owner to delete")
                return

            reply = QMessageBox.question(
                self, "Delete Owner",
                f"Delete owner '{owner_name}'?\n\nThis will unlink all vehicles from this owner.",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                try:
                    self.vehicle_manager.delete_owner(owner_id)
                    self.refresh_profiles()
                    show_info(self, "Deleted", f"Owner '{owner_name}' deleted")
                except Exception as e:
                    show_error(self, "Error", f"Failed to delete owner: {e}")

        elif item_type == 'driver':
            # Deleting a driver
            driver = item_data.get('data', {})
            driver_name = driver.get('name', 'Unknown')
            driver_id = driver.get('driver_id')

            if not driver_id:
                show_error(self, "Error", "Cannot identify driver to delete")
                return

            reply = QMessageBox.question(
                self, "Delete Driver",
                f"Delete driver '{driver_name}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                try:
                    self.vehicle_manager.remove_driver(driver_id)
                    self.refresh_profiles()
                    show_info(self, "Deleted", f"Driver '{driver_name}' removed")
                except Exception as e:
                    show_error(self, "Error", f"Failed to delete driver: {e}")

        else:
            # Deleting a vehicle/profile
            profile = item_data.get('data', item_data)
            profile_name = profile.get('name', 'Unknown')
            profile_id = profile.get('profile_id')

            if not profile_id:
                show_error(self, "Error", "Cannot identify profile to delete")
                return

            reply = QMessageBox.question(
                self, "Delete Vehicle Profile",
                f"Delete vehicle profile '{profile_name}'?\n\nThis will also delete all drivers for this vehicle.",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                try:
                    self.vehicle_manager.delete_profile(profile_id)
                    self.refresh_profiles()
                    show_info(self, "Deleted", f"Profile '{profile_name}' deleted")
                except Exception as e:
                    show_error(self, "Error", f"Failed to delete profile: {e}")
    
    def _load_profile(self):
        """Load the selected vehicle profile"""
        item_data = self._get_selected()
        if not item_data:
            return

        item_type = item_data.get('type', 'profile')

        # Only allow loading vehicle/profile types
        if item_type not in ('profile', 'vehicle'):
            if item_type in ('owner', 'driver', 'add_driver', 'add_vehicle', 'standalone_group'):
                show_info(self, "Profile Loaded", "Loaded: None")
            return

        # Extract profile data
        profile = item_data.get('data', item_data)
        profile_id = profile.get('profile_id')

        if profile_id:
            self._active_id = profile_id
            if self.on_profile_loaded:
                self.on_profile_loaded(profile)
            show_info(self, "Profile Loaded", f"Loaded: {profile.get('name', 'Unknown')}")
        else:
            show_info(self, "Profile Loaded", "Loaded: None")

    # =============================================================================
    # CHILD PROFILE MANAGEMENT
    # =============================================================================

    def _show_child_profile_menu(self, parent_profile: dict):
        """Show dropdown menu for adding/viewing child profiles"""
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QCursor

        parent_id = parent_profile.get('profile_id')
        parent_name = parent_profile.get('name', 'Unknown')

        logger.debug(f"Showing child profile menu for: {parent_name} (ID: {parent_id})")

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 5px;
            }}
            QMenu::item {{
                padding: 8px 20px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: #C40000;
            }}
            QMenu::item:disabled {{
                color: #8B949E;
            }}
            QMenu::separator {{
                height: 1px;
                background-color: #30363D;
                margin: 5px 10px;
            }}
        """)

        # Get existing children first
        children = self._get_child_profiles(parent_id) if parent_id else []

        if children:
            # Show existing children
            for child in children:
                child_name = child.get('name', 'Unknown')
                child_action = menu.addAction(f"  {child_name}")
                child_action.triggered.connect(lambda checked, c=child: self._select_profile_in_table(c))
            menu.addSeparator()
        else:
            # Show "Empty" when no children
            empty_action = menu.addAction("  (Empty)")
            empty_action.setEnabled(False)
            menu.addSeparator()

        # Add new child option
        add_action = menu.addAction("+ Add Child Profile")
        add_action.triggered.connect(lambda: self._add_child_profile(parent_profile))

        # Show menu at cursor position
        menu.exec(QCursor.pos())

    def _add_child_profile(self, parent_profile: dict):
        """Open dialog to create new child profile"""
        parent_name = parent_profile.get('name', 'Unknown')

        # Simple input dialog for child profile
        name, ok = QInputDialog.getText(
            self,
            "Add Child Profile",
            f"Enter name for new profile under '{parent_name}':"
        )

        if ok and name:
            try:
                # Create child profile data
                child_data = {
                    'name': name,
                    'make': parent_profile.get('make', ''),
                    'model': parent_profile.get('model', ''),
                    'year': parent_profile.get('year', ''),
                    'parent_profile_id': parent_profile['profile_id'],
                    'profile_type': 'child'
                }

                # Create profile
                child_id = self.vehicle_manager.create_profile(child_data)

                if child_id:
                    # Auto-generate API key
                    api_key = self._generate_api_key_for_profile(child_id, name)

                    # Show success with API key
                    self._show_api_key_created_dialog(name, api_key)

                    # Refresh list
                    self.refresh_profiles()
                else:
                    show_error(self, "Error", "Failed to create child profile")

            except Exception as e:
                show_error(self, "Error", f"Failed to create child profile: {e}")

    def _link_existing_profile(self, parent_profile: dict):
        """Link an existing profile as a child of the selected profile"""
        parent_id = parent_profile['profile_id']
        parent_name = parent_profile.get('name', 'Unknown')

        # Get profiles that can be linked (not already children, not the parent itself)
        available_profiles = [
            p for p in self._profiles
            if p.get('profile_id') != parent_id
            and p.get('parent_profile_id') is None
        ]

        if not available_profiles:
            show_info(self, "No Profiles Available", "No standalone profiles available to link.")
            return

        # Create selection dialog
        profile_names = [f"{p.get('name')} ({p.get('make', '')} {p.get('model', '')})" for p in available_profiles]

        selected, ok = QInputDialog.getItem(
            self,
            "Link Existing Profile",
            f"Select profile to link under '{parent_name}':",
            profile_names,
            editable=False
        )

        if ok and selected:
            index = profile_names.index(selected)
            child_profile = available_profiles[index]

            try:
                # Update profile to be a child
                self.vehicle_manager.update_profile(child_profile['profile_id'], {
                    'parent_profile_id': parent_id,
                    'profile_type': 'child'
                })

                show_info(self, "Profile Linked",
                         f"'{child_profile.get('name')}' is now linked under '{parent_name}'")
                self.refresh_profiles()

            except Exception as e:
                show_error(self, "Error", f"Failed to link profile: {e}")

    # ==================== DRIVER MANAGEMENT METHODS ====================

    def _add_driver_dialog(self, profile_id: int):
        """Open dialog to add a new driver to a profile"""
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout,
                                       QLineEdit, QSpinBox, QComboBox,
                                       QDialogButtonBox, QLabel)

        dialog = QDialog(self)
        dialog.setWindowTitle("Add Driver")
        dialog.setMinimumWidth(400)
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {ProfessionalTheme.BACKGROUND_SECONDARY};
                color: {ProfessionalTheme.TEXT_PRIMARY};
            }}
            QLabel {{
                color: {ProfessionalTheme.TEXT_PRIMARY};
                font-size: 12px;
            }}
            QLineEdit, QSpinBox, QComboBox {{
                background-color: {ProfessionalTheme.CARD_BG};
                color: {ProfessionalTheme.TEXT_PRIMARY};
                border: 1px solid {ProfessionalTheme.BORDER};
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
            }}
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
                border-color: {ProfessionalTheme.PRIMARY};
            }}
        """)

        layout = QVBoxLayout(dialog)

        # Header
        header = QLabel("Add New Driver")
        header.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {ProfessionalTheme.TEXT_PRIMARY}; margin-bottom: 10px;")
        layout.addWidget(header)

        # Form
        form = QFormLayout()

        name_input = QLineEdit()
        name_input.setPlaceholderText("Enter driver name")
        form.addRow("Name *:", name_input)

        age_input = QSpinBox()
        age_input.setRange(16, 100)
        age_input.setValue(30)
        form.addRow("Age:", age_input)

        phone_input = QLineEdit()
        phone_input.setPlaceholderText("Enter phone number")
        form.addRow("Phone:", phone_input)

        email_input = QLineEdit()
        email_input.setPlaceholderText("Enter email address")
        form.addRow("Email:", email_input)

        license_input = QLineEdit()
        license_input.setPlaceholderText("Enter license number")
        form.addRow("License #:", license_input)

        relationship_combo = QComboBox()
        relationship_combo.addItems(["Driver", "Owner", "Spouse", "Child", "Employee", "Other"])
        form.addRow("Relationship:", relationship_combo)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        buttons.setStyleSheet(f"""
            QPushButton {{
                background-color: {ProfessionalTheme.PRIMARY};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {ProfessionalTheme.PRIMARY_LIGHT};
            }}
        """)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            name = name_input.text().strip()
            if not name:
                show_error(self, "Error", "Driver name is required")
                return

            driver_data = {
                'name': name,
                'age': age_input.value() if age_input.value() > 0 else None,
                'phone': phone_input.text().strip() or None,
                'email': email_input.text().strip() or None,
                'license_number': license_input.text().strip() or None,
                'relationship': relationship_combo.currentText().lower()
            }

            try:
                driver_id = self.vehicle_manager.add_driver(profile_id, driver_data)
                if driver_id:
                    show_info(self, "Success", f"Driver '{name}' added successfully")
                    self.refresh_profiles()
                else:
                    show_error(self, "Error", "Failed to add driver")
            except Exception as e:
                show_error(self, "Error", f"Failed to add driver: {e}")

    def _show_profile_info_dialog(self):
        """Show detailed customer/user information for selected profile"""
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout,
                                       QLabel, QPushButton, QMessageBox, QApplication)
        from PySide6.QtCore import Qt, QTimer

        selected = self._get_selected()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a profile first.")
            return

        item_type = selected.get("type", "profile")

        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("ℹ️ Profile Information")
        dialog.setMinimumWidth(450)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
                color: #FFFFFF;
            }
            QLabel {
                color: #FFFFFF;
                padding: 4px;
            }
            QLabel[class="header"] {
                font-size: 16px;
                font-weight: bold;
                color: #58A6FF;
                padding: 8px 0;
            }
            QLabel[class="value"] {
                background-color: #2D2D2D;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Consolas', monospace;
            }
        """)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)

        # Extract the actual data from the nested structure
        # Tree items store data as {'type': 'owner', 'data': {...}} so we need the inner dict
        actual_data = selected.get('data', selected)

        # Header
        header_label = QLabel(f"📋 {actual_data.get('name', 'Unknown')}")
        header_label.setProperty("class", "header")
        layout.addWidget(header_label)

        # Create info grid
        form = QFormLayout()
        form.setSpacing(8)

        if item_type in ("profile", "vehicle"):
            # Vehicle profile info - look up owner for customer fields
            owner_id = selected.get('owner_id') or actual_data.get('owner_id')
            owner_info = {}
            if owner_id and isinstance(owner_id, int):
                owner_info = self.vehicle_manager.get_owner_by_id(owner_id) or {}

            api_key_display = actual_data.get("api_key") or owner_info.get("api_key") or "Not set"
            if api_key_display and len(api_key_display) > 20:
                api_key_display = api_key_display[:20] + "..."
            info_fields = [
                ("👤 Customer Name", owner_info.get("name") or actual_data.get("name") or "Not set"),
                ("📧 Email", owner_info.get("email") or "Not set"),
                ("📱 Phone", owner_info.get("phone") or "Not set"),
                ("🚗 Vehicle", f"{actual_data.get('year', '')} {actual_data.get('make', '')} {actual_data.get('model', '')}".strip() or "Not set"),
                ("🔖 License Plate", actual_data.get("license_plate") or "Not set"),
                ("🔑 API Key", api_key_display or "Not set"),
                ("📅 Created", actual_data.get("created_at") or "Unknown"),
                ("🔄 Last Updated", actual_data.get("updated_at") or "Unknown"),
                ("📊 Category", actual_data.get("category") or "Personal"),
            ]
        elif item_type == "owner":
            api_key_display = actual_data.get("api_key", "Not set")
            if api_key_display and len(api_key_display) > 20:
                api_key_display = api_key_display[:20] + "..."
            info_fields = [
                ("👤 Owner Name", actual_data.get("name") or "Unknown"),
                ("📧 Email", actual_data.get("email") or "Not set"),
                ("📱 Phone", actual_data.get("phone") or "Not set"),
                ("🔑 API Key", api_key_display or "Not set"),
                ("🏷️ Role", actual_data.get("role") or "owner"),
                ("📅 Created", actual_data.get("created_at") or "Unknown"),
            ]
        elif item_type == "driver":
            info_fields = [
                ("👤 Driver Name", actual_data.get("name") or "Unknown"),
                ("📧 Email", actual_data.get("email") or "Not set"),
                ("📱 Phone", actual_data.get("phone") or "Not set"),
                ("🪪 License #", actual_data.get("license_number") or "Not set"),
                ("👥 Relationship", actual_data.get("relationship") or "Driver"),
                ("🎂 Age", str(actual_data.get("age")) if actual_data.get("age") else "Not set"),
                ("📅 Created", actual_data.get("created_at") or "Unknown"),
            ]
        else:
            info_fields = [("Type", item_type)]

        for label_text, value in info_fields:
            label = QLabel(label_text)
            value_label = QLabel(str(value) if value else "Not set")
            value_label.setProperty("class", "value")
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            form.addRow(label, value_label)

        layout.addLayout(form)

        # Copy All button
        copy_btn = QPushButton("📋 Copy All Info")
        copy_btn.setStyleSheet(self._get_button_style('secondary'))
        def copy_all():
            text = "\n".join([f"{label}: {value}" for label, value in info_fields])
            QApplication.clipboard().setText(text)
            copy_btn.setText("✓ Copied!")
            QTimer.singleShot(1500, lambda: copy_btn.setText("📋 Copy All Info"))
        copy_btn.clicked.connect(copy_all)
        layout.addWidget(copy_btn)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(self._get_button_style('primary'))
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def _edit_driver_dialog(self, driver: dict, profile_id: int):
        """Open dialog to edit an existing driver"""
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout,
                                       QLineEdit, QSpinBox, QComboBox,
                                       QDialogButtonBox, QLabel)

        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Driver")
        dialog.setMinimumWidth(400)
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {ProfessionalTheme.BACKGROUND_SECONDARY};
                color: {ProfessionalTheme.TEXT_PRIMARY};
            }}
            QLabel {{
                color: {ProfessionalTheme.TEXT_PRIMARY};
                font-size: 12px;
            }}
            QLineEdit, QSpinBox, QComboBox {{
                background-color: {ProfessionalTheme.CARD_BG};
                color: {ProfessionalTheme.TEXT_PRIMARY};
                border: 1px solid {ProfessionalTheme.BORDER};
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
            }}
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
                border-color: {ProfessionalTheme.PRIMARY};
            }}
        """)

        layout = QVBoxLayout(dialog)

        # Header
        header = QLabel(f"Edit Driver: {driver.get('name', '')}")
        header.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {ProfessionalTheme.TEXT_PRIMARY}; margin-bottom: 10px;")
        layout.addWidget(header)

        # Form
        form = QFormLayout()

        name_input = QLineEdit()
        name_input.setText(driver.get('name', ''))
        form.addRow("Name *:", name_input)

        age_input = QSpinBox()
        age_input.setRange(0, 100)
        age_input.setValue(driver.get('age', 0) or 0)
        form.addRow("Age:", age_input)

        phone_input = QLineEdit()
        phone_input.setText(driver.get('phone', '') or '')
        form.addRow("Phone:", phone_input)

        email_input = QLineEdit()
        email_input.setText(driver.get('email', '') or '')
        form.addRow("Email:", email_input)

        license_input = QLineEdit()
        license_input.setText(driver.get('license_number', '') or '')
        form.addRow("License #:", license_input)

        relationship_combo = QComboBox()
        relationships = ["Driver", "Owner", "Spouse", "Child", "Employee", "Other"]
        relationship_combo.addItems(relationships)
        current_rel = (driver.get('relationship', '') or 'driver').title()
        if current_rel in relationships:
            relationship_combo.setCurrentText(current_rel)
        form.addRow("Relationship:", relationship_combo)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        buttons.setStyleSheet(f"""
            QPushButton {{
                background-color: {ProfessionalTheme.PRIMARY};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {ProfessionalTheme.PRIMARY_LIGHT};
            }}
        """)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            name = name_input.text().strip()
            if not name:
                show_error(self, "Error", "Driver name is required")
                return

            driver_data = {
                'name': name,
                'age': age_input.value() if age_input.value() > 0 else None,
                'phone': phone_input.text().strip() or None,
                'email': email_input.text().strip() or None,
                'license_number': license_input.text().strip() or None,
                'relationship': relationship_combo.currentText().lower()
            }

            try:
                success = self.vehicle_manager.update_driver(driver.get('driver_id'), driver_data)
                if success:
                    show_info(self, "Success", f"Driver '{name}' updated successfully")
                    self.refresh_profiles()
                else:
                    show_error(self, "Error", "Failed to update driver")
            except Exception as e:
                show_error(self, "Error", f"Failed to update driver: {e}")

    def _remove_driver(self, driver_id: str):
        """Confirm and remove a driver"""
        from PySide6.QtWidgets import QMessageBox

        # Get driver info
        driver = self.vehicle_manager.get_driver_by_id(driver_id)
        if not driver:
            show_error(self, "Error", "Driver not found")
            return

        driver_name = driver.get('name', 'Unknown')

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Remove Driver",
            f"Are you sure you want to remove driver '{driver_name}'?\n\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                success = self.vehicle_manager.remove_driver(driver_id)
                if success:
                    show_info(self, "Success", f"Driver '{driver_name}' removed")
                    self.refresh_profiles()
                else:
                    show_error(self, "Error", "Failed to remove driver")
            except Exception as e:
                show_error(self, "Error", f"Failed to remove driver: {e}")

    def _set_primary_driver(self, driver_id: str, profile_id: int):
        """Set a driver as the primary driver for a profile"""
        try:
            success = self.vehicle_manager.set_primary_driver(profile_id, driver_id)
            if success:
                show_info(self, "Success", "Primary driver updated")
                self.refresh_profiles()
            else:
                show_error(self, "Error", "Failed to set primary driver")
        except Exception as e:
            show_error(self, "Error", f"Failed to set primary driver: {e}")

    def _set_guardian_role(self, driver_id: str, new_role: str,
                           driver_name: str = "Unknown", profile_id: int = None):
        """Change the guardian role of a driver with confirmation and server sync"""
        from PySide6.QtWidgets import QMessageBox

        role_label = new_role.replace('_', '-').title()
        action = "Promote" if new_role == 'co_guardian' else "Demote"

        # Confirmation dialog
        reply = QMessageBox.question(
            self,
            f"{action} Driver",
            f"Are you sure you want to {action.lower()} '{driver_name}' to {role_label}?\n\n"
            + ("Co-Guardians get full fleet dashboard access and receive driving event alerts."
               if new_role == 'co_guardian'
               else "This will remove fleet dashboard access and alert notifications."),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            # Update local DB first
            success = self.vehicle_manager.update_driver(driver_id, {'guardian_role': new_role})
            if not success:
                show_error(self, "Error", "Failed to update guardian role locally")
                return

            # Sync to server
            server_synced = False
            try:
                from server_api_client import ServerAPIClient
                client = ServerAPIClient()
                if profile_id:
                    resp = client._make_request(
                        'PUT',
                        f'/api/guardian/drivers/{profile_id}/role/{driver_id}',
                        data={'role': new_role}
                    )
                    server_synced = resp.success
                    if not resp.success:
                        profiles_logger.warning(
                            f"Server sync for guardian role failed: {resp.error}")
            except Exception as e:
                profiles_logger.warning(f"Could not sync guardian role to server: {e}")

            sync_note = "" if server_synced else "\n(Server sync pending - will sync on next connection)"
            show_info(self, "Success",
                      f"'{driver_name}' is now {role_label}.{sync_note}")
            self.refresh_profiles()
        except Exception as e:
            show_error(self, "Error", f"Failed to update guardian role: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # OWNER MANAGEMENT METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def _add_owner_dialog(self):
        """Open dialog to add a new owner/customer with server sync"""
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout,
                                       QLineEdit, QDialogButtonBox, QLabel,
                                       QComboBox, QCheckBox, QMessageBox)

        dialog = QDialog(self)
        dialog.setWindowTitle("Add Customer")
        dialog.setMinimumWidth(450)
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {ProfessionalTheme.BACKGROUND_SECONDARY};
                color: {ProfessionalTheme.TEXT_PRIMARY};
            }}
            QLabel {{
                color: {ProfessionalTheme.TEXT_PRIMARY};
                font-size: 12px;
            }}
            QLineEdit, QComboBox {{
                background-color: {ProfessionalTheme.CARD_BG};
                color: {ProfessionalTheme.TEXT_PRIMARY};
                border: 1px solid {ProfessionalTheme.BORDER};
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border-color: {ProfessionalTheme.PRIMARY};
            }}
            QCheckBox {{
                color: {ProfessionalTheme.TEXT_PRIMARY};
                font-size: 12px;
            }}
        """)

        layout = QVBoxLayout(dialog)

        # Header
        header = QLabel("Add New Customer")
        header.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {ProfessionalTheme.TEXT_PRIMARY}; margin-bottom: 10px;")
        layout.addWidget(header)

        # Info label
        info_label = QLabel("Customer will be created on the server with API key access.")
        info_label.setStyleSheet(f"color: {ProfessionalTheme.TEXT_SECONDARY}; font-size: 11px; margin-bottom: 10px;")
        layout.addWidget(info_label)

        # Form
        form = QFormLayout()

        name_input = QLineEdit()
        name_input.setPlaceholderText("Enter customer name")
        form.addRow("Name *:", name_input)

        email_input = QLineEdit()
        email_input.setPlaceholderText("Enter email address (required for API key)")
        form.addRow("Email *:", email_input)

        phone_input = QLineEdit()
        phone_input.setPlaceholderText("Enter phone number")
        form.addRow("Phone:", phone_input)

        # Tier selection
        tier_combo = QComboBox()
        tier_combo.addItems(["Free", "Premium", "Admin"])
        tier_combo.setCurrentText("Free")
        form.addRow("Tier:", tier_combo)

        # Send email checkbox
        send_email_check = QCheckBox("Send API key email to customer")
        send_email_check.setChecked(True)
        form.addRow("", send_email_check)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        buttons.setStyleSheet(f"""
            QPushButton {{
                background-color: {ProfessionalTheme.PRIMARY};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {ProfessionalTheme.PRIMARY_LIGHT};
            }}
        """)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            name = name_input.text().strip()
            email = email_input.text().strip()

            if not name:
                show_error(self, "Error", "Customer name is required")
                return None

            if not email:
                show_error(self, "Error", "Email is required for API key access")
                return None

            tier = tier_combo.currentText().lower()
            send_email = send_email_check.isChecked()

            owner_data = {
                'name': name,
                'email': email,
                'phone': phone_input.text().strip() or None,
                'role': 'owner',
                'tier': tier,
                'apps': 'obd,guardian'
            }

            try:
                # First create user on server (generates API key)
                server_user_id = None
                api_key = None
                try:
                    from server_api_client import get_unified_user_client
                    client = get_unified_user_client()
                    response = client.create_user(
                        name=name,
                        email=email,
                        phone=phone_input.text().strip() or None,
                        tier=tier,
                        role='owner'
                    )
                    if response.get('success'):
                        server_user_id = response.get('user_id')
                        api_key = response.get('api_key')
                        owner_data['user_id'] = server_user_id
                        owner_data['api_key'] = api_key
                        print(f"[DEBUG] _add_owner_dialog: Server user created with ID {server_user_id}")

                        if send_email and api_key:
                            # Email would be sent by server automatically
                            print(f"[DEBUG] _add_owner_dialog: Email would be sent to {email}")
                    else:
                        error = response.get('error', 'Unknown error')
                        print(f"[WARNING] _add_owner_dialog: Server user creation failed: {error}")
                        # Ask if user wants to continue with local-only creation
                        reply = QMessageBox.question(
                            self,
                            "Server Unavailable",
                            f"Could not create user on server: {error}\n\n"
                            "Do you want to create a local-only profile?\n"
                            "(API key will not be available)",
                            QMessageBox.Yes | QMessageBox.No,
                            QMessageBox.No
                        )
                        if reply != QMessageBox.Yes:
                            return None
                except Exception as e:
                    print(f"[WARNING] _add_owner_dialog: Server connection failed: {e}")
                    # Ask if user wants to continue with local-only creation
                    reply = QMessageBox.question(
                        self,
                        "Server Unavailable",
                        f"Could not connect to server: {e}\n\n"
                        "Do you want to create a local-only profile?\n"
                        "(API key will not be available)",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    if reply != QMessageBox.Yes:
                        return None

                # Create local owner record
                owner_id = self.vehicle_manager.add_owner(owner_data)
                print(f"[DEBUG] _add_owner_dialog: add_owner returned owner_id={owner_id}")

                if owner_id:
                    success_msg = f"Customer '{name}' added successfully!"
                    if api_key:
                        success_msg += f"\n\nAPI Key: {api_key[:8]}...{api_key[-4:]}"
                        if send_email:
                            success_msg += f"\n\nEmail notification sent to {email}"
                    show_info(self, "Success", success_msg)
                    self.refresh_profiles()
                    print(f"[DEBUG] _add_owner_dialog: Returning owner_id={owner_id}")
                    return owner_id
                else:
                    show_error(self, "Error", "Failed to add customer")
            except Exception as e:
                print(f"[ERROR] _add_owner_dialog: Exception: {e}")
                show_error(self, "Error", f"Failed to add customer: {e}")

        print("[DEBUG] _add_owner_dialog: Returning None")
        return None

    def _edit_owner_dialog(self, owner: dict):
        """Open dialog to edit an existing owner"""
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout,
                                       QLineEdit, QDialogButtonBox, QLabel,
                                       QComboBox, QCheckBox, QHBoxLayout)

        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Owner")
        dialog.setMinimumWidth(400)
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {ProfessionalTheme.BACKGROUND_SECONDARY};
                color: {ProfessionalTheme.TEXT_PRIMARY};
            }}
            QLabel {{
                color: {ProfessionalTheme.TEXT_PRIMARY};
                font-size: 12px;
            }}
            QLineEdit, QComboBox {{
                background-color: {ProfessionalTheme.CARD_BG};
                color: {ProfessionalTheme.TEXT_PRIMARY};
                border: 1px solid {ProfessionalTheme.BORDER};
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border-color: {ProfessionalTheme.PRIMARY};
            }}
            QCheckBox {{
                color: {ProfessionalTheme.TEXT_PRIMARY};
                spacing: 8px;
            }}
        """)

        layout = QVBoxLayout(dialog)

        # Header
        header = QLabel(f"Edit Owner: {owner.get('name', '')}")
        header.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {ProfessionalTheme.TEXT_PRIMARY}; margin-bottom: 10px;")
        layout.addWidget(header)

        # Form
        form = QFormLayout()

        name_input = QLineEdit()
        name_input.setText(owner.get('name', ''))
        form.addRow("Name *:", name_input)

        email_input = QLineEdit()
        email_input.setText(owner.get('email', '') or '')
        form.addRow("Email:", email_input)

        phone_input = QLineEdit()
        phone_input.setText(owner.get('phone', '') or '')
        form.addRow("Phone:", phone_input)

        role_combo = QComboBox()
        role_combo.addItems(["owner", "fleet_manager", "admin"])
        current_role = owner.get('role', 'owner')
        if current_role in ["owner", "fleet_manager", "admin"]:
            role_combo.setCurrentText(current_role)
        form.addRow("Role:", role_combo)

        # Apps checkboxes
        apps_layout = QHBoxLayout()
        current_apps = (owner.get('apps', '') or 'obd,guardian').split(',')
        obd_check = QCheckBox("OBD App")
        obd_check.setChecked('obd' in current_apps)
        guardian_check = QCheckBox("Guardian App")
        guardian_check.setChecked('guardian' in current_apps)
        apps_layout.addWidget(obd_check)
        apps_layout.addWidget(guardian_check)
        form.addRow("Apps:", apps_layout)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        buttons.setStyleSheet(f"""
            QPushButton {{
                background-color: {ProfessionalTheme.PRIMARY};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {ProfessionalTheme.PRIMARY_LIGHT};
            }}
        """)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            name = name_input.text().strip()
            if not name:
                show_error(self, "Error", "Owner name is required")
                return

            # Build apps string
            apps_list = []
            if obd_check.isChecked():
                apps_list.append('obd')
            if guardian_check.isChecked():
                apps_list.append('guardian')

            owner_data = {
                'name': name,
                'email': email_input.text().strip() or None,
                'phone': phone_input.text().strip() or None,
                'role': role_combo.currentText(),
                'apps': ','.join(apps_list) if apps_list else 'obd'
            }

            try:
                success = self.vehicle_manager.update_owner(owner.get('owner_id'), owner_data)
                if success:
                    show_info(self, "Success", f"Owner '{name}' updated successfully")
                    self.refresh_profiles()
                else:
                    show_error(self, "Error", "Failed to update owner")
            except Exception as e:
                show_error(self, "Error", f"Failed to update owner: {e}")

    def _delete_owner(self, owner_id: int):
        """Confirm and delete an owner"""
        from PySide6.QtWidgets import QMessageBox

        # Get owner info
        owner = self.vehicle_manager.get_owner_by_id(owner_id)
        if not owner:
            show_error(self, "Error", "Owner not found")
            return

        owner_name = owner.get('name', 'Unknown')
        vehicle_count = owner.get('vehicle_count', 0)

        # Confirm deletion
        msg = f"Are you sure you want to delete owner '{owner_name}'?"
        if vehicle_count > 0:
            msg += f"\n\n{vehicle_count} vehicle(s) will be unassigned from this owner."
        msg += "\n\nThis action cannot be undone."

        reply = QMessageBox.question(
            self,
            "Delete Owner",
            msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                success = self.vehicle_manager.delete_owner(owner_id)
                if success:
                    show_info(self, "Success", f"Owner '{owner_name}' deleted")
                    self.refresh_profiles()
                else:
                    show_error(self, "Error", "Failed to delete owner")
            except Exception as e:
                show_error(self, "Error", f"Failed to delete owner: {e}")

    def _add_vehicle_for_owner(self, owner_id: int):
        """Open simplified add vehicle dialog with owner pre-selected"""
        print(f"[DEBUG] _add_vehicle_for_owner called with owner_id={owner_id}")
        # Use the new streamlined vehicle dialog
        self._add_vehicle_dialog(owner_id)

    def _add_profile_with_owner(self, owner_id: int = None):
        """Open add profile dialog with optional owner pre-selection"""
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout,
                                       QLineEdit, QSpinBox, QComboBox,
                                       QDialogButtonBox, QLabel)

        dialog = QDialog(self)
        dialog.setWindowTitle("Add Vehicle Profile")
        dialog.setMinimumWidth(450)
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {ProfessionalTheme.BACKGROUND_SECONDARY};
                color: {ProfessionalTheme.TEXT_PRIMARY};
            }}
            QLabel {{
                color: {ProfessionalTheme.TEXT_PRIMARY};
                font-size: 12px;
            }}
            QLineEdit, QSpinBox, QComboBox {{
                background-color: {ProfessionalTheme.CARD_BG};
                color: {ProfessionalTheme.TEXT_PRIMARY};
                border: 1px solid {ProfessionalTheme.BORDER};
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
            }}
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
                border-color: {ProfessionalTheme.PRIMARY};
            }}
        """)

        layout = QVBoxLayout(dialog)

        # Header
        header = QLabel("Add New Vehicle Profile")
        header.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {ProfessionalTheme.TEXT_PRIMARY}; margin-bottom: 10px;")
        layout.addWidget(header)

        # Form
        form = QFormLayout()

        # Owner selection
        owner_combo = QComboBox()
        owner_combo.addItem("-- No Owner --", None)
        owner_combo.addItem("+ Create New Owner...", "new")
        owners = self.vehicle_manager.get_all_owners()
        for o in owners:
            owner_combo.addItem(o.get('name', ''), o.get('owner_id'))
        # Pre-select owner if provided
        if owner_id:
            for i in range(owner_combo.count()):
                if owner_combo.itemData(i) == owner_id:
                    owner_combo.setCurrentIndex(i)
                    break
        form.addRow("Owner:", owner_combo)

        # Vehicle info
        name_input = QLineEdit()
        name_input.setPlaceholderText("e.g., Nissan Patrol Y61")
        form.addRow("Name:", name_input)

        make_input = QLineEdit()
        make_input.setPlaceholderText("e.g., Nissan")
        form.addRow("Make *:", make_input)

        model_input = QLineEdit()
        model_input.setPlaceholderText("e.g., Patrol")
        form.addRow("Model *:", model_input)

        year_input = QSpinBox()
        year_input.setRange(1900, 2030)
        year_input.setValue(2020)
        form.addRow("Year *:", year_input)

        vin_input = QLineEdit()
        vin_input.setPlaceholderText("Vehicle Identification Number")
        form.addRow("VIN:", vin_input)

        license_input = QLineEdit()
        license_input.setPlaceholderText("License plate number")
        form.addRow("License Plate:", license_input)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        buttons.setStyleSheet(f"""
            QPushButton {{
                background-color: {ProfessionalTheme.PRIMARY};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {ProfessionalTheme.PRIMARY_LIGHT};
            }}
        """)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            make = make_input.text().strip()
            model = model_input.text().strip()
            year = year_input.value()

            if not make or not model:
                show_error(self, "Error", "Make and Model are required")
                return

            # Handle owner selection
            selected_owner_id = owner_combo.currentData()
            if selected_owner_id == "new":
                # Open add owner dialog
                selected_owner_id = self._add_owner_dialog()
                if not selected_owner_id:
                    return  # Cancelled

            # Build profile name from make/model/year if not provided
            name = name_input.text().strip()
            if not name:
                name = f"{make} {model} {year}"

            profile_data = {
                'name': name,
                'make': make,
                'model': model,
                'year': year,
                'vin': vin_input.text().strip() or None,
                'license_plate': license_input.text().strip() or None,
                'owner_id': selected_owner_id
            }

            try:
                result = self.vehicle_manager.add_profile(profile_data)
                if result:
                    # Check if result is a dict (new API key response) or int (legacy)
                    if isinstance(result, dict):
                        profile_id = result.get('profile_id')
                        api_key = result.get('api_key')

                        if api_key:
                            # Show API key dialog
                            self._show_api_key_dialog(api_key, profile_id, name)
                        else:
                            show_info(self, "Success", f"Vehicle '{name}' added successfully")
                    else:
                        # Legacy int return
                        show_info(self, "Success", f"Vehicle '{name}' added successfully")

                    self.refresh_profiles()
                else:
                    show_error(self, "Error", "Failed to add vehicle profile")
            except Exception as e:
                show_error(self, "Error", f"Failed to add vehicle: {e}")

    def _show_api_key_dialog(self, api_key: str, profile_id: int, profile_name: str):
        """
        Show API key to user after profile creation.

        Args:
            api_key: The generated API key
            profile_id: The profile ID
            profile_name: The profile name
        """
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QTextEdit, QHBoxLayout
        from PySide6.QtCore import Qt

        dialog = QDialog(self)
        dialog.setWindowTitle("Profile Created - API Key Generated")
        dialog.setMinimumWidth(600)
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {ProfessionalTheme.BACKGROUND_SECONDARY};
                color: {ProfessionalTheme.TEXT_PRIMARY};
            }}
            QLabel {{
                color: {ProfessionalTheme.TEXT_PRIMARY};
            }}
            QTextEdit {{
                background-color: {ProfessionalTheme.CARD_BG};
                color: {ProfessionalTheme.TEXT_PRIMARY};
                border: 2px solid {ProfessionalTheme.PRIMARY};
                border-radius: 8px;
                padding: 12px;
                font-family: 'Courier New', monospace;
                font-size: 11px;
            }}
            QPushButton {{
                background-color: {ProfessionalTheme.PRIMARY};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                min-width: 120px;
            }}
            QPushButton:hover {{
                background-color: {ProfessionalTheme.PRIMARY_LIGHT};
            }}
        """)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)

        # Success icon and title
        title = QLabel("✅ Profile Created Successfully!")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {ProfessionalTheme.PRIMARY}; margin-bottom: 10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Info message
        info = QLabel(
            f"<p>Vehicle profile <b>{profile_name}</b> has been created.</p>"
            f"<p><b>Profile ID:</b> {profile_id}</p>"
            f"<p>An API key has been generated for this profile. This key allows access from the mobile app.</p>"
        )
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 12px; margin: 10px 0;")
        layout.addWidget(info)

        # API Key label
        key_label = QLabel("🔑 <b>API Key:</b>")
        key_label.setStyleSheet("font-size: 13px; margin-top: 10px;")
        layout.addWidget(key_label)

        # API Key display (read-only, selectable)
        key_display = QTextEdit()
        key_display.setPlainText(api_key)
        key_display.setReadOnly(True)
        key_display.setMaximumHeight(80)
        key_display.setLineWrapMode(QTextEdit.WidgetWidth)
        layout.addWidget(key_display)

        # Warning message
        warning = QLabel("⚠️ <b>Important:</b> Save this API key securely. You'll need it to connect the mobile app.")
        warning.setStyleSheet(f"color: {ProfessionalTheme.WARNING}; font-size: 11px; margin: 5px 0;")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        copy_btn = QPushButton("📋 Copy to Clipboard")
        copy_btn.clicked.connect(lambda: self._copy_to_clipboard(api_key))
        button_layout.addWidget(copy_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ProfessionalTheme.CARD_BG};
                color: {ProfessionalTheme.TEXT_PRIMARY};
                border: 1px solid {ProfessionalTheme.BORDER};
            }}
            QPushButton:hover {{
                background-color: {ProfessionalTheme.BACKGROUND_SECONDARY};
            }}
        """)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        dialog.exec()

    def _copy_to_clipboard(self, text: str):
        """
        Copy text to clipboard.

        Args:
            text: Text to copy
        """
        from PySide6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        clipboard.setText(text)
        show_info(self, "Copied!", "API key copied to clipboard successfully")

    def _assign_vehicle_to_owner_dialog(self, profile: dict):
        """Show dialog to assign a vehicle to an owner"""
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout,
                                       QComboBox, QDialogButtonBox, QLabel)

        dialog = QDialog(self)
        dialog.setWindowTitle("Assign Vehicle to Owner")
        dialog.setMinimumWidth(350)
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {ProfessionalTheme.BACKGROUND_SECONDARY};
                color: {ProfessionalTheme.TEXT_PRIMARY};
            }}
            QLabel {{
                color: {ProfessionalTheme.TEXT_PRIMARY};
                font-size: 12px;
            }}
            QComboBox {{
                background-color: {ProfessionalTheme.CARD_BG};
                color: {ProfessionalTheme.TEXT_PRIMARY};
                border: 1px solid {ProfessionalTheme.BORDER};
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
            }}
        """)

        layout = QVBoxLayout(dialog)

        # Header
        vehicle_name = profile.get('name', f"{profile.get('make', '')} {profile.get('model', '')}")
        header = QLabel(f"Assign '{vehicle_name}' to Owner")
        header.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {ProfessionalTheme.TEXT_PRIMARY}; margin-bottom: 10px;")
        layout.addWidget(header)

        # Owner selection
        form = QFormLayout()
        owner_combo = QComboBox()
        owner_combo.addItem("-- No Owner (Unassign) --", None)
        owner_combo.addItem("+ Create New Owner...", "new")
        owners = self.vehicle_manager.get_all_owners()
        current_owner_id = profile.get('owner_id')
        for o in owners:
            owner_combo.addItem(o.get('name', ''), o.get('owner_id'))
            if o.get('owner_id') == current_owner_id:
                owner_combo.setCurrentIndex(owner_combo.count() - 1)
        form.addRow("Owner:", owner_combo)
        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        buttons.setStyleSheet(f"""
            QPushButton {{
                background-color: {ProfessionalTheme.PRIMARY};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {ProfessionalTheme.PRIMARY_LIGHT};
            }}
        """)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            selected_owner_id = owner_combo.currentData()

            if selected_owner_id == "new":
                selected_owner_id = self._add_owner_dialog()
                if not selected_owner_id:
                    return

            try:
                profile_id = profile.get('profile_id')
                if selected_owner_id:
                    success = self.vehicle_manager.assign_vehicle_to_owner(profile_id, selected_owner_id)
                else:
                    success = self.vehicle_manager.unassign_vehicle_from_owner(profile_id)

                if success:
                    show_info(self, "Success", "Vehicle owner updated")
                    self.refresh_profiles()
                else:
                    show_error(self, "Error", "Failed to update vehicle owner")
            except Exception as e:
                show_error(self, "Error", f"Failed to assign owner: {e}")

    def _generate_owner_api_key(self, owner: dict):
        """Generate and sync API key for an owner"""
        import secrets
        import hashlib
        from datetime import datetime

        owner_id = owner.get('owner_id')
        owner_name = owner.get('name', 'Unknown')

        try:
            # Generate key with owner prefix
            key = f"owner_{secrets.token_urlsafe(24)}"
            key_hash = hashlib.sha256(key.encode()).hexdigest()

            # Update owner with API key
            owner_data = {
                'api_key': key,
                'api_key_hash': key_hash
            }
            success = self.vehicle_manager.update_owner(owner_id, owner_data)

            if success:
                # Show the key to user
                from PySide6.QtWidgets import QMessageBox
                msg = QMessageBox(self)
                msg.setWindowTitle("API Key Generated")
                msg.setText(f"API Key for '{owner_name}':")
                msg.setInformativeText(f"{key}\n\nCopy this key now - it won't be shown again!")
                msg.setIcon(QMessageBox.Information)
                msg.exec()

                # Sync to server
                self._sync_owner_api_key_to_server(owner, key)
                self.refresh_profiles()
            else:
                show_error(self, "Error", "Failed to generate API key")
        except Exception as e:
            show_error(self, "Error", f"Failed to generate API key: {e}")

    def _generate_driver_api_key(self, driver: dict, profile_id: int):
        """Generate and sync API key for a driver"""
        import secrets
        import hashlib

        driver_id = driver.get('driver_id')
        driver_name = driver.get('name', 'Unknown')

        try:
            # Generate key with driver prefix
            key = f"driver_{secrets.token_urlsafe(24)}"
            key_hash = hashlib.sha256(key.encode()).hexdigest()

            # Update driver with API key
            driver_data = {
                'api_key': key,
                'api_key_hash': key_hash
            }
            success = self.vehicle_manager.update_driver(driver_id, driver_data)

            if success:
                # Show the key to user
                from PySide6.QtWidgets import QMessageBox
                msg = QMessageBox(self)
                msg.setWindowTitle("API Key Generated")
                msg.setText(f"API Key for driver '{driver_name}':")
                msg.setInformativeText(f"{key}\n\nThis key grants OBD App access only.\nCopy this key now - it won't be shown again!")
                msg.setIcon(QMessageBox.Information)
                msg.exec()

                # Sync to server
                self._sync_driver_api_key_to_server(driver, profile_id, key)
                self.refresh_profiles()
            else:
                show_error(self, "Error", "Failed to generate API key")
        except Exception as e:
            show_error(self, "Error", f"Failed to generate API key: {e}")

    def _sync_owner_api_key_to_server(self, owner: dict, api_key: str):
        """Sync owner's API key to server"""
        try:
            from api_key_sync import ApiKeySync
            sync = ApiKeySync()

            key_data = {
                'name': owner.get('name', 'Owner'),
                'role': 'owner',
                'apps': (owner.get('apps', '') or 'obd,guardian').split(','),
                'owner_id': owner.get('owner_id'),
                'profile_id': None,  # Owner-level key
                'tier': 'premium',
                'permissions': ['vehicle_data', 'predict', 'diagnostic', 'llm_chat', 'admin']
            }

            success = sync.sync_api_key(api_key, key_data)
            if not success:
                profiles_logger.warning(f"Failed to sync owner API key to server")
        except Exception as e:
            profiles_logger.error(f"Error syncing owner API key: {e}")

    def _sync_driver_api_key_to_server(self, driver: dict, profile_id: int, api_key: str):
        """Sync driver's API key to server"""
        try:
            from api_key_sync import ApiKeySync
            sync = ApiKeySync()

            key_data = {
                'name': driver.get('name', 'Driver'),
                'role': 'driver',
                'apps': ['obd'],  # Drivers can only use OBD app
                'owner_id': None,
                'driver_id': driver.get('driver_id'),
                'profile_id': profile_id,
                'tier': 'free',
                'permissions': ['vehicle_data', 'predict']
            }

            success = sync.sync_api_key(api_key, key_data)
            if not success:
                profiles_logger.warning(f"Failed to sync driver API key to server")
        except Exception as e:
            profiles_logger.error(f"Error syncing driver API key: {e}")

    def _get_child_profiles(self, parent_id: int) -> list:
        """Get all child profiles for a parent"""
        return [p for p in self._profiles if p.get('parent_profile_id') == parent_id]

    def _select_profile_in_table(self, profile: dict):
        """Select a profile in the table"""
        for row, p in enumerate(self._profiles):
            if p.get('profile_id') == profile.get('profile_id'):
                self.table.selectRow(row)
                break

    def _generate_api_key_for_profile(self, profile_id, profile_name: str) -> str:
        """Generate API key for a profile and sync to server"""
        import secrets
        import uuid
        from datetime import datetime

        # Ensure profile_id is an integer (not a dict or other type)
        if isinstance(profile_id, dict):
            profile_id = profile_id.get('profile_id')
        profile_id = int(profile_id) if profile_id else None

        if not profile_id:
            raise ValueError("Invalid profile_id")

        # Generate key with premium prefix
        chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
        key = 'P_' + ''.join(secrets.choice(chars) for _ in range(26))

        # Create key data
        key_id = f"key_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
        key_data = {
            'key_hash': hashlib.sha256(key.encode()).hexdigest(),
            'key_encrypted': self._encrypt_api_key(key),
            'key_hidden': f"{key[:4]}{'•' * 20}{key[-4:]}",
            'name': profile_name,
            'tier': 'premium',
            'profile_id': profile_id,  # Always store as integer
            'profile_name': profile_name,
            'permissions': ['vehicle_data', 'predict', 'diagnostic', 'llm_chat'],
            'created': datetime.now().isoformat(),
            'status': 'active'
        }

        # Save to api_keys.json
        try:
            api_keys_file = CONFIG.API_KEYS_FILE if CONFIG else Path("config/api_keys.json")
            api_keys = {}
            if api_keys_file.exists():
                with open(api_keys_file, 'r') as f:
                    api_keys = json.load(f)

            api_keys[key_id] = key_data

            with open(api_keys_file, 'w') as f:
                json.dump(api_keys, f, indent=2)

            # Sync to server
            try:
                from api_key_sync import sync_single_key_to_server
                sync_single_key_to_server(key_id, key_data)
            except Exception as sync_error:
                logger.warning(f"Failed to sync API key to server: {sync_error}")

        except Exception as e:
            logger.error(f"Failed to save API key: {e}")

        return key

    def _encrypt_api_key(self, key: str) -> str:
        """Encrypt API key using XOR with admin password"""
        import base64
        password = "YOUR_ADMIN_PASSWORD"
        key_bytes = hashlib.sha256(password.encode()).digest()
        encrypted = []
        for i, char in enumerate(key):
            key_byte = key_bytes[i % len(key_bytes)]
            encrypted.append(chr(ord(char) ^ key_byte))
        encrypted_text = ''.join(encrypted)
        return base64.b64encode(encrypted_text.encode()).decode()

    def _show_api_key_created_dialog(self, profile_name: str, api_key: str):
        """Show dialog with the newly created API key"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout

        dialog = QDialog(self)
        dialog.setWindowTitle("API Key Created")
        dialog.setMinimumWidth(500)
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {ProfessionalTheme.BACKGROUND};
            }}
            QLabel {{
                color: {ProfessionalTheme.TEXT_PRIMARY};
            }}
        """)

        layout = QVBoxLayout(dialog)

        # Success message
        success_label = QLabel(f"✅ Child profile '{profile_name}' created successfully!")
        success_label.setStyleSheet(f"color: {ProfessionalTheme.SUCCESS}; font-size: 14px; font-weight: bold;")
        layout.addWidget(success_label)

        # Instructions
        instructions = QLabel("Save this API key - it will be used to connect from Guardian or Predict OBD apps:")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # API key field
        key_field = QLineEdit(api_key)
        key_field.setReadOnly(True)
        key_field.setStyleSheet("""
            QLineEdit {
                background-color: #1E1E1E;
                color: #4CAF50;
                border: 2px solid #4CAF50;
                border-radius: 6px;
                padding: 10px;
                font-family: 'Consolas', monospace;
                font-size: 12px;
            }
        """)
        layout.addWidget(key_field)

        # Copy button
        btn_layout = QHBoxLayout()
        copy_btn = QPushButton("📋 Copy to Clipboard")
        copy_btn.setStyleSheet(self._get_button_style('primary'))
        copy_btn.clicked.connect(lambda: (
            QApplication.clipboard().setText(api_key),
            show_info(self, "Copied", "API key copied to clipboard!")
        ))
        btn_layout.addWidget(copy_btn)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(self._get_button_style('secondary'))
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        dialog.exec()

    def update_live_snapshot(self, data):
        """Update live snapshot display"""
        if not data:
            for lbl in self.live_labels.values():
                lbl.setText("-")
            return
        
        mapping = {
            'rpm': ['rpm', 'engine_rpm'],
            'speed': ['speed', 'vehicle_speed'],
            'coolant_temp': ['coolant_temp', 'engine_coolant_temp'],
            'battery_voltage': ['battery_voltage', 'battery'],
            'engine_load': ['engine_load', 'calculated_engine_load']
        }
        
        for key, label in self.live_labels.items():
            value = None
            for alt in mapping.get(key, [key]):
                if alt in data:
                    value = data[alt]
                    break
            label.setText(str(value) if value is not None else "-")


# =============================================================================
#   AI INSIGHTS TAB
# =============================================================================

class AIInsightsTab(QWidget):
    """AI-powered insights dashboard"""
    
    def __init__(self, ai_module, get_active_profile=None, parent=None):
        super().__init__(parent)
        self.ai_module = ai_module
        self.get_active_profile = get_active_profile
        
        self.current_profile = None
        self.latest_snapshot = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("AI Insights Dashboard")
        title.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {ProfessionalTheme.TEXT_PRIMARY};")
        
        self.profile_label = QLabel("Profile: None")
        self.profile_label.setStyleSheet(f"color: {ProfessionalTheme.TEXT_SECONDARY};")
        
        self.refresh_btn = QPushButton("[SYNC] Refresh Insights")
        self.refresh_btn.setStyleSheet(self._get_button_style('primary'))
        self.refresh_btn.clicked.connect(self.refresh_insights)
        
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.profile_label)
        header.addSpacing(20)
        header.addWidget(self.refresh_btn)
        layout.addLayout(header)
        
        # Main content
        content = QHBoxLayout()
        
        # Left: Summary cards
        left = QVBoxLayout()
        
        summary_group = QGroupBox("Health Summary")
        summary_layout = QFormLayout(summary_group)
        
        self.health_score = QLabel("--")
        self.health_score.setStyleSheet(f"font-size: 24px; font-weight: 700; color: {ProfessionalTheme.SUCCESS};")
        self.health_label = QLabel("Unknown")
        self.alerts_count = QLabel("0")
        self.risk_level = QLabel("LOW")
        
        summary_layout.addRow("Health Score:", self.health_score)
        summary_layout.addRow("Status:", self.health_label)
        summary_layout.addRow("Active Alerts:", self.alerts_count)
        summary_layout.addRow("Risk Level:", self.risk_level)
        
        left.addWidget(summary_group)
        
        # Live snapshot
        snapshot_group = QGroupBox("Live Snapshot")
        snapshot_layout = QVBoxLayout(snapshot_group)
        self.snapshot_text = QPlainTextEdit()
        self.snapshot_text.setReadOnly(True)
        self.snapshot_text.setMaximumHeight(150)
        snapshot_layout.addWidget(self.snapshot_text)
        left.addWidget(snapshot_group)
        
        left.addStretch()
        content.addLayout(left, 1)
        
        # Right: Detailed report
        report_group = QGroupBox("AI Analysis Report")
        report_layout = QVBoxLayout(report_group)
        self.report_text = QPlainTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setPlaceholderText("Press 'Refresh Insights' to generate AI analysis...")
        report_layout.addWidget(self.report_text)
        content.addWidget(report_group, 2)
        
        layout.addLayout(content, 1)
    
    def on_profile_changed(self, profile):
        self.current_profile = profile
        name = profile.get('name', 'Unknown') if profile else 'None'
        self.profile_label.setText(f"Profile: {name}")
    
    def update_live_snapshot(self, snapshot):
        self.latest_snapshot = snapshot
        if snapshot:
            lines = [f"{k}: {v}" for k, v in list(snapshot.items())[:8]]
            self.snapshot_text.setPlainText("\n".join(lines))
        else:
            self.snapshot_text.setPlainText("No live data")
    
    def refresh_insights(self):
        profile = self.current_profile
        if not profile and self.get_active_profile:
            profile = self.get_active_profile()
        
        if not profile:
            show_info(self, "No Profile", "Please load a vehicle profile first")
            return
        
        if not self.latest_snapshot:
            show_info(self, "No Data", "Start Live Data to generate insights")
            return
        
        try:
            dashboard = self.ai_module.get_dashboard_summary(
                vehicle_profile=profile,
                latest_data=self.latest_snapshot,
                history=[]
            )
            insights = self.ai_module.generate_comprehensive_insights(dashboard)
            
            # Update summary
            self.health_score.setText(str(dashboard.get('health_score', '--')))
            self.health_label.setText(str(dashboard.get('health_label', 'Unknown')))
            self.alerts_count.setText(str(dashboard.get('alerts_count', 0)))
            self.risk_level.setText(str(dashboard.get('alerts_risk_level', 'LOW')))
            
            # Color code health score
            score = dashboard.get('health_score', 0)
            if score >= 80:
                self.health_score.setStyleSheet(f"font-size: 24px; font-weight: 700; color: {ProfessionalTheme.SUCCESS};")
            elif score >= 60:
                self.health_score.setStyleSheet(f"font-size: 24px; font-weight: 700; color: {ProfessionalTheme.WARNING};")
            else:
                self.health_score.setStyleSheet(f"font-size: 24px; font-weight: 700; color: {ProfessionalTheme.DANGER};")
            
            # Update report
            lines = []
            if insights.get('health_overview'):
                lines.append(f"HEALTH OVERVIEW\n{insights['health_overview']}\n")
            if insights.get('maintenance_priority'):
                lines.append(f"MAINTENANCE PRIORITY\n{insights['maintenance_priority']}\n")
            if insights.get('cost_optimization'):
                lines.append(f"COST OPTIMIZATION\n{insights['cost_optimization']}\n")
            if insights.get('emergency_actions'):
                lines.append(f"EMERGENCY ACTIONS\n{insights['emergency_actions']}\n")
            
            self.report_text.setPlainText("\n".join(lines) if lines else "No specific insights available.")

        except Exception as e:
            show_error(self, "AI Error", f"Failed to generate insights: {e}")

    def _get_button_style(self, style_type: str = 'primary') -> str:
        """Get consistent button style based on type."""
        styles = {
            'primary': """
                QPushButton {
                    background-color: #C40000;
                    color: #F0F6FC;
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
                    background-color: #B71C1C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
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
                QPushButton:pressed {
                    background-color: #161B22;
                }
            """,
            'danger': """
                QPushButton {
                    background-color: #DA3633;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #F85149;
                }
                QPushButton:pressed {
                    background-color: #B62324;
                }
            """,
            'success': """
                QPushButton {
                    background-color: #238636;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #2EA043;
                }
                QPushButton:pressed {
                    background-color: #196C2E;
                }
            """
        }
        return styles.get(style_type, styles['primary'])


# =============================================================================
#   HISTORICAL CHARTS TAB
# =============================================================================

class HistoricalChartsTab(QWidget):
    """Historical data visualization"""
    
    def __init__(self, data_logger, parent=None):
        super().__init__(parent)
        self.data_logger = data_logger
        self.session_data = []
        self._setup_ui()
        self._load_sessions()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("Historical Data")
        title.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {ProfessionalTheme.TEXT_PRIMARY};")
        
        self.session_combo = QComboBox()
        self.session_combo.setMinimumWidth(300)
        self.session_combo.currentTextChanged.connect(self._load_session_data)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setStyleSheet(self._get_button_style('secondary'))
        self.refresh_btn.clicked.connect(self._load_sessions)
        
        header.addWidget(title)
        header.addStretch()
        header.addWidget(QLabel("Session:"))
        header.addWidget(self.session_combo)
        header.addWidget(self.refresh_btn)
        layout.addLayout(header)
        
        # Content
        splitter = QSplitter(Qt.Horizontal)
        
        # Left: Session info and stats
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        info_group = QGroupBox("Session Information")
        info_layout = QFormLayout(info_group)
        
        self.start_label = QLabel("-")
        self.duration_label = QLabel("-")
        self.points_label = QLabel("-")
        self.vehicle_label = QLabel("-")
        
        info_layout.addRow("Start Time:", self.start_label)
        info_layout.addRow("Duration:", self.duration_label)
        info_layout.addRow("Data Points:", self.points_label)
        info_layout.addRow("Vehicle:", self.vehicle_label)
        
        left_layout.addWidget(info_group)
        
        # Statistics
        stats_group = QGroupBox("Statistics")
        stats_layout = QFormLayout(stats_group)
        
        self.max_rpm = QLabel("-")
        self.avg_speed = QLabel("-")
        self.max_temp = QLabel("-")
        self.min_voltage = QLabel("-")
        
        stats_layout.addRow("Max RPM:", self.max_rpm)
        stats_layout.addRow("Avg Speed:", self.avg_speed)
        stats_layout.addRow("Max Temp:", self.max_temp)
        stats_layout.addRow("Min Voltage:", self.min_voltage)
        
        left_layout.addWidget(stats_group)
        left_layout.addStretch()
        
        splitter.addWidget(left)
        
        # Right: Chart display (text-based for now)
        chart_group = QGroupBox("Data Visualization")
        chart_layout = QVBoxLayout(chart_group)
        
        self.chart_type = QComboBox()
        self.chart_type.addItems(["RPM Over Time", "Speed Over Time", "Temperature Over Time", "Voltage Over Time"])
        self.chart_type.currentTextChanged.connect(self._update_chart)
        chart_layout.addWidget(self.chart_type)
        
        self.chart_display = QPlainTextEdit()
        self.chart_display.setReadOnly(True)
        self.chart_display.setPlaceholderText("Select a session to view data...")
        chart_layout.addWidget(self.chart_display)
        
        splitter.addWidget(chart_group)
        splitter.setSizes([300, 700])
        
        layout.addWidget(splitter, 1)
    
    def _load_sessions(self):
        """Load available sessions"""
        sessions = self.data_logger.list_sessions()
        self.session_combo.clear()
        self.session_combo.addItems(sessions)
    
    def _load_session_data(self, filename):
        """Load data from selected session"""
        if not filename:
            return
        
        import os
        filepath = os.path.join(self.data_logger.log_directory, filename)
        self.session_data = self.data_logger.get_session_data(filepath)
        
        self._update_info()
        self._update_stats()
        self._update_chart()
    
    def _update_info(self):
        """Update session info display"""
        if not self.session_data:
            return
        
        self.points_label.setText(str(len(self.session_data)))
        
        if self.session_data:
            first = self.session_data[0]
            timestamp = first.get('timestamp', '-')
            self.start_label.setText(timestamp[:19] if len(timestamp) > 19 else timestamp)
    
    def _update_stats(self):
        """Calculate and display statistics"""
        if not self.session_data:
            return
        
        rpm_vals = []
        speed_vals = []
        temp_vals = []
        voltage_vals = []
        
        for entry in self.session_data:
            data = entry.get('data', {})
            if data.get('rpm'):
                rpm_vals.append(float(data['rpm']))
            if data.get('speed'):
                speed_vals.append(float(data['speed']))
            if data.get('coolant_temp'):
                temp_vals.append(float(data['coolant_temp']))
            if data.get('battery_voltage'):
                voltage_vals.append(float(data['battery_voltage']))
        
        self.max_rpm.setText(f"{max(rpm_vals):.0f}" if rpm_vals else "-")
        self.avg_speed.setText(f"{sum(speed_vals)/len(speed_vals):.1f}" if speed_vals else "-")
        self.max_temp.setText(f"{max(temp_vals):.1f}°C" if temp_vals else "-")
        self.min_voltage.setText(f"{min(voltage_vals):.1f}V" if voltage_vals else "-")
    
    def _update_chart(self):
        """Update chart display"""
        if not self.session_data:
            self.chart_display.setPlainText("No data available")
            return
        
        chart_type = self.chart_type.currentText()
        
        # Extract relevant data
        key_map = {
            "RPM Over Time": "rpm",
            "Speed Over Time": "speed",
            "Temperature Over Time": "coolant_temp",
            "Voltage Over Time": "battery_voltage"
        }
        
        key = key_map.get(chart_type, "rpm")
        values = []
        
        for entry in self.session_data:
            data = entry.get('data', {})
            if data.get(key):
                values.append(float(data[key]))
        
        if values:
            text = f"Chart: {chart_type}\n\n"
            text += f"Data Points: {len(values)}\n"
            text += f"Min: {min(values):.1f}\n"
            text += f"Max: {max(values):.1f}\n"
            text += f"Average: {sum(values)/len(values):.1f}\n"
            
            # Simple ASCII visualization
            text += "\n--- Trend ---\n"
            normalized = [(v - min(values)) / (max(values) - min(values) + 0.001) for v in values[-50:]]
            for val in normalized:
                bars = int(val * 40)
                text += "█" * bars + "\n"
            
            self.chart_display.setPlainText(text)
        else:
            self.chart_display.setPlainText(f"No {key} data in this session")

    def _get_button_style(self, style_type: str = 'primary') -> str:
        """Get consistent button style based on type."""
        styles = {
            'primary': """
                QPushButton {
                    background-color: #C40000;
                    color: #F0F6FC;
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
                    background-color: #B71C1C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
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
                QPushButton:pressed {
                    background-color: #161B22;
                }
            """,
            'danger': """
                QPushButton {
                    background-color: #DA3633;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #F85149;
                }
                QPushButton:pressed {
                    background-color: #B62324;
                }
            """,
            'success': """
                QPushButton {
                    background-color: #238636;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #2EA043;
                }
                QPushButton:pressed {
                    background-color: #196C2E;
                }
            """
        }
        return styles.get(style_type, styles['primary'])


# =============================================================================
#   MAIN WINDOW - UPDATED WITH PROFILE CALLBACKS
# =============================================================================

class MainWindow(QMainWindow):
    """Main Application Window with Full Integration"""
    
    def _get_button_style(self, style_type: str = 'primary') -> str:
        """Get consistent button style based on type."""
        styles = {
            'primary': """
                QPushButton {
                    background-color: #C40000;
                    color: #F0F6FC;
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
                    background-color: #B71C1C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
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
                    border-color: #8B949E;
                }
                QPushButton:pressed {
                    background-color: #161B22;
                }
                QPushButton:disabled {
                    background-color: #161B22;
                    color: #484F58;
                    border-color: #30363D;
                }
            """,
            'danger': """
                QPushButton {
                    background-color: #C40000;
                    color: #F0F6FC;
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
                    background-color: #B71C1C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """,
            'success': """
                QPushButton {
                    background-color: #4CAF50;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #66BB6A;
                }
                QPushButton:pressed {
                    background-color: #388E3C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """,
            'warning': """
                QPushButton {
                    background-color: #FFC107;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #FFB300;
                }
                QPushButton:pressed {
                    background-color: #FF8F00;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """,
            'info': """
                QPushButton {
                    background-color: #2196F3;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #42A5F5;
                }
                QPushButton:pressed {
                    background-color: #1976D2;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """
        }
        return styles.get(style_type, styles['primary'])
    
    def __init__(self):
        super().__init__()
        
        # Initialize LLM assistant (singleton)
        self.llm_assistant = get_llm_assistant()
        
        self.setWindowTitle(f"Predict — Professional Car AI v{APP_VERSION}")
        
        try:
            self.setWindowIcon(QIcon("car_icon.ico"))
        except Exception:
            pass
        
        self.resize(1700, 950)
        self.setMinimumSize(1200, 700)
        
        # Initialize core managers
        self._init_managers()
        
        # Build UI
        self._build_ui()
        
        # Setup timers and connections
        self._setup_timers()

        # Check for desktop app updates
        self._check_for_updates()

        # Auto-sync owners table on startup
        self._sync_owners_on_startup()

        logger.info("MainWindow initialized successfully")

    def _sync_owners_on_startup(self):
        """Sync unified_users to owners table on Desktop startup"""
        try:
            from sync_owners_table import sync_owners
            logger.info("Performing automatic owner data sync...")
            success = sync_owners()
            if success:
                logger.info("Owner data sync completed successfully")
            else:
                logger.warning("Owner data sync returned False")
        except Exception as e:
            logger.error(f"Failed to sync owner data: {e}")

    def _init_managers(self):
        """Initialize all core managers and modules"""
        # PID Learning Manager
        pid_dir = os.path.join(os.getcwd(), "learned_pids")
        self.pid_manager = PIDLearningManager(pid_dir)
        
        # Connectivity Manager
        try:
            self.connectivity = ProfessionalConnectivityManager(pid_manager=self.pid_manager)
        except TypeError:
            self.connectivity = ProfessionalConnectivityManager()
            if hasattr(self.connectivity, 'pid_manager'):
                self.connectivity.pid_manager = self.pid_manager
        
        # Connect live data signal
        if hasattr(self.connectivity, 'live_data'):
            self.connectivity.live_data.connect(self._on_live_data)
        
        # Vehicle Manager
        self.vehicle_manager = VehicleProfileManager()

        # Historical Data Manager - Permanent storage for AI learning
        self.historical_data_manager = HistoricalDataManager()

        # Backup Manager - Automatic backups to D:\Backup
        self.backup_manager = BackupManager()
        # Start automatic backup scheduler (daily at 2:00 AM)
        self.backup_manager.schedule_automatic_backups(daily_time='02:00')

        # Initialize Production Systems (integrity, monitoring, enterprise backup)
        self._init_production_systems()

        # AI Modules - INTEGRATED
        self.unified_ai = UnifiedAIModule()
        self.predictive_engine = PredictiveFailureEngine()

        # Enhanced AI Learning - Cross-vehicle learning with vehicle-specific predictions
        self.enhanced_ai = EnhancedAILearning()
        # Load models in background thread to avoid blocking UI
        self._ai_models_loaded = False
        self._load_ai_models_background()

        # AI Auto-Retraining Scheduler - Daily training at 3:00 AM
        self.ai_retraining = AIAutoRetrainingScheduler(
            self.enhanced_ai,
            self.historical_data_manager,
            self.vehicle_manager
        )
        # Start automatic retraining (daily at 3:00 AM)
        self.ai_retraining.start(training_time='03:00')

        # Scheduled Predictions - Daily predictions for all vehicles at 2:30 AM
        try:
            from scheduled_predictions import ScheduledPredictionRunner
            self.scheduled_predictions = ScheduledPredictionRunner(schedule_time='02:30')
            self.scheduled_predictions.start_daemon()
            logger.info("Scheduled predictions daemon started (daily at 02:30)")
        except Exception as e:
            logger.warning(f"Scheduled predictions not available: {e}")
            self.scheduled_predictions = None

        # Two-Way Communication Hub - Desktop <-> Mobile bidirectional messaging
        from two_way_communication import TwoWayCommunicationHub
        self.communication_hub = TwoWayCommunicationHub()

        # Trip Analytics - Automatic trip detection with GPS tracking
        from trip_analytics import TripAnalytics
        self.trip_analytics = TripAnalytics(self.historical_data_manager)

        # Driving Score Analyzer - Real-time behavior analysis
        from driving_score import DrivingScoreAnalyzer
        self.driving_score = DrivingScoreAnalyzer()

        # Fuel Tracking System - Manual fillup logging and analysis
        from fuel_tracking import FuelTrackingSystem
        self.fuel_tracking = FuelTrackingSystem()

        # Maintenance Reminders - Mileage/time-based service reminders
        from maintenance_reminders import MaintenanceRemindersSystem
        self.maintenance_reminders = MaintenanceRemindersSystem(self.vehicle_manager)

        # AI Alert Notifications - Push notifications for AI-detected issues
        from ai_alert_notifications import AIAlertNotificationSystem
        self.ai_alerts = AIAlertNotificationSystem(
            self.communication_hub,
            self.enhanced_ai,
            self.predictive_engine
        )

        # Multi-Vehicle Comparison - Fleet analytics
        from multi_vehicle_comparison import MultiVehicleComparison
        self.multi_vehicle = MultiVehicleComparison(
            self.vehicle_manager,
            self.historical_data_manager,
            self.enhanced_ai,
            self.fuel_tracking,
            self.driving_score,
            self.trip_analytics
        )

        # Geofencing Alerts - Desert area warnings
        from geofencing_alerts import GeofencingAlertSystem
        self.geofencing = GeofencingAlertSystem(self.communication_hub)

        # Custom Alerts - User-defined thresholds
        from custom_alerts import CustomAlertsSystem
        self.custom_alerts = CustomAlertsSystem(self.communication_hub)

        # Data Export - CSV/Excel export
        from desktop_data_export import DataExportSystem
        self.data_export = DataExportSystem(
            self.historical_data_manager,
            self.vehicle_manager,
            self.fuel_tracking,
            self.trip_analytics
        )

        # Initialize PDF Exporter before it's used
        self.pdf_exporter = PDFExporter()

        # Initialize AlertNotificationManager in _init_managers (already done above)
        # Note: The notification manager is initialized and started in _init_managers()

        # PDF API Service - Mobile PDF requests
        from pdf_api_service import PDFAPIService
        self.pdf_api = PDFAPIService(
            self.pdf_exporter,
            self.historical_data_manager,
            self.vehicle_manager
        )

        logger.info("All new feature modules initialized successfully")

        # Prediction Accuracy Tracker
        if ACCURACY_TRACKER_AVAILABLE:
            self.accuracy_tracker = get_accuracy_tracker()
            logger.info("Prediction Accuracy Tracker initialized")
        else:
            self.accuracy_tracker = None
            logger.warning("Prediction Accuracy Tracker not available")

        # Alert Notification Manager - Centralized multi-channel notification system
        if ALERT_NOTIFICATION_MANAGER_AVAILABLE:
            self.alert_notification_manager = get_notification_manager()
            
            # Configure notification channels (load from settings or use defaults)
            # Email channel configuration (can be customized in settings)
            email_config = {
                'smtp_server': 'smtp.gmail.com',
                'smtp_port': 587,
                'username': '',  # User should configure in settings
                'password': '',  # User should configure in settings
                'from_address': 'noreply@predictobd.com'
            }
            self.alert_notification_manager.configure_channel('email', email_config)
            
            # Push notification configuration (placeholder for Firebase)
            push_config = {
                'firebase_key': ''  # Configure in settings
            }
            self.alert_notification_manager.configure_channel('push', push_config)
            
            # Start the notification manager
            self.alert_notification_manager.start()
            logger.info("AlertNotificationManager initialized and started")
        else:
            self.alert_notification_manager = None
            logger.warning("Alert Notification Manager not available")

        # Device Heartbeat Manager - Track device online/offline status
        if HEARTBEAT_MANAGER_AVAILABLE:
            self.heartbeat_manager = get_heartbeat_manager()
            
            # Register callback for device status changes to trigger notifications
            if self.alert_notification_manager:
                def _device_status_callback(device_id: str, old_status: 'DeviceStatus', new_status: 'DeviceStatus'):
                    """Send notification when device status changes"""
                    try:
                        # Get device info
                        device_info = self.heartbeat_manager.get_device_status(device_id)
                        profile_name = device_info.get('profile_name', 'Unknown') if device_info else 'Unknown'
                        
                        # Map DeviceStatus enum to string
                        old_status_str = old_status.value if hasattr(old_status, 'value') else str(old_status)
                        new_status_str = new_status.value if hasattr(new_status, 'value') else str(new_status)
                        
                        # Send notification for offline events (important for monitoring)
                        if new_status_str == 'offline':
                            from alert_notifications import NotificationPriority
                            self.alert_notification_manager.send_notification(
                                title=f"Device Offline: {device_id}",
                                message=f"Device {device_id} (Profile: {profile_name}) has gone offline.",
                                priority=NotificationPriority.HIGH,
                                channels=['push', 'email'],
                                metadata={
                                    'device_id': device_id,
                                    'profile_name': profile_name,
                                    'event_type': 'device_offline',
                                    'old_status': old_status_str,
                                    'new_status': new_status_str
                                }
                            )
                            logger.info(f"Sent offline notification for device {device_id}")
                        
                        # Also notify when device comes back online
                        elif new_status_str == 'online' and old_status_str == 'offline':
                            from alert_notifications import NotificationPriority
                            self.alert_notification_manager.send_notification(
                                title=f"Device Online: {device_id}",
                                message=f"Device {device_id} (Profile: {profile_name}) is back online.",
                                priority=NotificationPriority.INFO,
                                channels=['push'],
                                metadata={
                                    'device_id': device_id,
                                    'profile_name': profile_name,
                                    'event_type': 'device_online',
                                    'old_status': old_status_str,
                                    'new_status': new_status_str
                                }
                            )
                            logger.info(f"Sent online notification for device {device_id}")
                    
                    except Exception as e:
                        logger.error(f"Error sending device status notification: {e}")
                
                # Register the callback
                self.heartbeat_manager.register_callback(_device_status_callback)
                logger.info("Device heartbeat callback registered with alert notification manager")
            
            # Start heartbeat monitoring
            self.heartbeat_manager.start_monitoring()
            logger.info("Device Heartbeat Manager started")
        else:
            self.heartbeat_manager = None
            logger.warning("Device Heartbeat Manager not available")

        # Enhanced Prediction Engine - LSTM, ESP32, Feedback integration
        self.enhanced_engine = None
        if ENHANCED_ENGINE_AVAILABLE:
            try:
                self.enhanced_engine = create_enhanced_engine()
                # Connect to existing AI modules
                self.enhanced_engine.set_unified_ai(self.unified_ai)
                self.enhanced_engine.set_predictive_engine(self.predictive_engine)
                logger.info("Enhanced Prediction Engine initialized (LSTM, ESP32, Feedback)")
            except Exception as e:
                logger.warning(f"Failed to initialize Enhanced Prediction Engine: {e}")
                self.enhanced_engine = None

        # Share learned parameters between AI modules
        self._integrate_ai_modules()

        # Other managers
        self.profile_manager = ProfileManager()
        self.cloud_sync = CloudSyncManager()
        self.vin_decoder = VINDecoder(db_path="./data/vehicle_profiles.db")
        
        # Data logger
        self.data_logger = SecureDataLogger()

        # Database path
        self.profile_db_path = './data/vehicle_profiles.db'

        # Mobile server for Android OBD app
        if MOBILE_SERVER_AVAILABLE:
            try:
                self.mobile_wrapper = MobileServerWrapper(port=8000)
                self.mobile_bridge = MobileDataBridge()

                # Connect signals
                self.mobile_wrapper.data_received.connect(self._on_mobile_data_raw)
                self.mobile_bridge.mobile_data_ready.connect(self._on_mobile_data_unified)
                self.mobile_bridge.connection_status.connect(self._on_mobile_connection_status)

                logger.info("Mobile server components initialized successfully")
                
                # Initialize Direct Report Server (Port 8001)
                self.report_server = DirectReportServer(port=8001)
                self.report_server.report_requested.connect(self._on_remote_report_requested)
                if self.report_server.start():
                    logger.info("Report server listening on port 8001")
                
                # Initialize WebSocket Client for real-time updates
                self.ws_client = LiveDataWebSocketClient("http://localhost:8000")
                
                # Connect WebSocket signals
                self.ws_client.data_received.connect(self._on_websocket_data)
                self.ws_client.car_connected.connect(self._on_car_connected)
                self.ws_client.car_disconnected.connect(self._on_car_disconnected)
                self.ws_client.connection_status.connect(self._on_ws_status_changed)
                
                # Start WebSocket connection
                self.ws_client.start()
                logger.info("WebSocket client started for real-time updates")
                
            except Exception as e:
                logger.error(f"Mobile server initialization error: {e}")
                self.mobile_wrapper = None
                self.mobile_bridge = None
                self.ws_client = None
        else:
            self.mobile_wrapper = None
            self.mobile_bridge = None
            self.ws_client = None
            logger.info("Mobile server not available")

        # PDF Queue Processor - Check for pending PDF requests from Android app
        self.pdf_queue_timer = QTimer(self)
        self.pdf_queue_timer.timeout.connect(self._process_pdf_queue)
        self.pdf_queue_timer.start(30000)  # Check every 30 seconds (reduced for performance)
        logger.info("PDF queue processor started")
        
        # LLM API Server - Start in background thread for mobile app integration
        try:
            from threading import Thread
            self.llm_api_thread = Thread(target=start_llm_api_server, args=(8080,), daemon=True)
            self.llm_api_thread.start()
            logger.info("LLM API server started on port 8080")
        except Exception as e:
            logger.warning(f"Failed to start LLM API server: {e}")

        # State
        self.active_profile = None
        self.latest_snapshot = None
        self.history_buffer = []
        self.data_source = 'usb'  # Track current data source: 'usb' or 'android'
        
        # Initialize PID Profile Resolver if available
        if PID_PROFILE_AVAILABLE:
            try:
                possible_paths = [
                    os.path.join(os.getcwd(), "configs", "pid_profiles"),
                    "./configs/pid_profiles",
                ]
                for path in possible_paths:
                    if os.path.exists(path):
                        self.pid_resolver = PIDProfileResolver(path)
                        logger.info(f"PID resolver initialized: {path}")
                        break
            except Exception as e:
                logger.warning(f"Could not initialize PID resolver: {e}")
                self.pid_resolver = None

        # Real-Time Server Sync - WebSocket connection for live owner/driver updates
        try:
            from realtime_sync import ServerSyncClient
            server_url = CONFIG.REMOTE_SERVER_URL if CONFIG else "http://localhost:8000"
            ws_url = server_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws"
            self.server_sync = ServerSyncClient(server_url=ws_url)
            self.server_sync.add_callback(self._on_server_sync_event)
            logger.info(f"ServerSyncClient initialized: {ws_url}")
        except Exception as e:
            logger.warning(f"ServerSyncClient not available: {e}")
            self.server_sync = None

    def _on_server_sync_event(self, event):
        """Handle real-time sync events from WebSocket server"""
        try:
            from realtime_sync import SyncEventType

            if event.event_type == SyncEventType.NEW_OWNER_REGISTERED:
                # New owner registered via Android app
                owner_data = event.data
                logger.info(f"New owner registered: {owner_data.get('name')} ({owner_data.get('email')})")

                # Refresh profiles list to show new owner
                if hasattr(self, 'profile_selector'):
                    self.profile_selector.refresh_profiles()

                # Show notification toast
                if hasattr(self, '_show_notification_toast'):
                    self._show_notification_toast(
                        f"New Owner Registered",
                        f"{owner_data.get('name')} has registered with {owner_data.get('vehicle_make')} {owner_data.get('vehicle_model')}",
                        "success"
                    )
                else:
                    # Fallback to logger
                    logger.info(f"New owner: {owner_data.get('name')} - {owner_data.get('vehicle_make')} {owner_data.get('vehicle_model')} {owner_data.get('vehicle_year')}")

            elif event.event_type == SyncEventType.NEW_DRIVER_REGISTERED:
                # New driver registered
                driver_data = event.data
                logger.info(f"New driver registered: {driver_data.get('name')}")

                # Refresh profiles
                if hasattr(self, 'profile_selector'):
                    self.profile_selector.refresh_profiles()

            elif event.event_type == SyncEventType.CONNECTION_STATUS:
                # WebSocket connection status changed
                connected = event.data.get('connected', False)
                if connected:
                    logger.info("WebSocket connected - real-time updates active")
                else:
                    logger.warning("WebSocket disconnected - real-time updates paused")

            elif event.event_type == SyncEventType.VEHICLE_RESEARCH_UPDATE:
                # Vehicle research completed or failed on the server
                profile_id = event.profile_id or event.data.get('profile_id')
                status = event.data.get('status', 'unknown')
                logger.info(f"Research update for vehicle {profile_id}: {status}")

                # If the info panel is currently showing this vehicle, refresh its research section
                if (hasattr(self, 'profiles_tab') and
                        hasattr(self.profiles_tab, 'info_panel') and
                        self.profiles_tab.info_panel and
                        self.profiles_tab.info_panel.isVisible() and
                        self.profiles_tab.info_panel.current_type == 'vehicle' and
                        self.profiles_tab.info_panel.current_id == profile_id):
                    self.profiles_tab._fetch_vehicle_research_async(profile_id)

        except Exception as e:
            logger.error(f"Error handling server sync event: {e}")

    def _integrate_ai_modules(self):
        """Integrate unified AI module with predictive engine"""
        try:
            # Share learned parameters
            if hasattr(self.predictive_engine, 'learned_thresholds'):
                self.unified_ai.learned_params = self.predictive_engine.learned_thresholds
            
            # Share model feature importances
            if hasattr(self.predictive_engine, 'model_feature_importances'):
                self.unified_ai.feature_importance_cache = self.predictive_engine.model_feature_importances
            
            # Setup cross-module callbacks
            if hasattr(self.unified_ai, 'add_feedback'):
                # When predictive engine makes predictions, feed back to unified AI
                pass
            
            logger.info("AI modules integrated successfully")
        except Exception as e:
            logger.warning(f"AI integration partial: {e}")

    def _load_ai_models_background(self):
        """Load AI models in background thread to avoid blocking UI startup"""
        def load_models_worker():
            try:
                logger.info("Background: Loading AI models...")
                self.enhanced_ai.load_models()
                self._ai_models_loaded = True
                logger.info("Background: AI models loaded successfully")
            except Exception as e:
                logger.warning(f"Background: AI model loading failed: {e}")
                self._ai_models_loaded = False

        from threading import Thread
        model_thread = Thread(target=load_models_worker, daemon=True)
        model_thread.start()
        logger.info("AI model loading started in background thread")

    def _init_production_systems(self):
        """
        Initialize production-grade systems:
        - System integrity checks
        - Background monitoring
        - Enterprise backup scheduling
        """
        if not PRODUCTION_SYSTEMS_AVAILABLE:
            logger.info("Production systems not available - skipping initialization")
            return

        try:
            # Run startup integrity check
            logger.info("Running startup integrity check...")
            passed, report = run_startup_integrity_check()

            if not passed:
                violations = report.get('violations', [])
                critical_count = sum(1 for v in violations if v.get('severity') == 'critical')

                if critical_count > 0:
                    # Show warning for critical issues
                    QMessageBox.warning(
                        self,
                        "System Integrity Warning",
                        f"System integrity check found {critical_count} critical issues.\n\n"
                        f"Total violations: {len(violations)}\n\n"
                        "The application will continue, but some features may not work correctly.\n"
                        "Run 'python system_integrity.py' for details."
                    )
                    logger.warning(f"Integrity check found {critical_count} critical violations")
                else:
                    logger.info(f"Integrity check found {len(violations)} non-critical issues (auto-repaired)")
            else:
                logger.info("Startup integrity check passed")

            # Start background monitoring service
            start_monitoring()
            logger.info("Background monitoring service started")

            # Start enterprise backup scheduler (supplements existing BackupManager)
            start_scheduled_backups(daily_time="02:30")  # 30 mins after legacy backup
            logger.info("Enterprise backup scheduler started")

        except Exception as e:
            logger.error(f"Production systems initialization error: {e}")
            # Don't block app startup - log and continue

    def _build_ui(self):
        """Build the main UI"""
        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        
        # Header Dashboard
        self.header = HeaderDashboard()
        # Connect vehicle switcher signal
        self.header.vehicle_changed.connect(self._on_vehicle_switched)
        # Connect voice command signal
        self.header.voice_command_requested.connect(self._on_voice_command)
        root_layout.addWidget(self.header)

        # Main content area: Sidebar + Pages
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Sidebar Navigation
        self.sidebar = SidebarNavigation()
        self.sidebar.navigation_changed.connect(self._on_navigation_changed)
        content_layout.addWidget(self.sidebar)

        # Stacked widget for pages with premium gradient background
        self.pages = QStackedWidget()
        self.pages.setStyleSheet("""
            QStackedWidget {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0D1117,
                    stop:0.5 #0D1117,
                    stop:1 #161B22
                );
            }
        """)
        content_layout.addWidget(self.pages, 1)

        # Initialize pages
        self._init_pages()

        root_layout.addLayout(content_layout, 1)
        
        # Status Bar
        self.statusBar().showMessage("Ready")
        
        self.setCentralWidget(central)
    
    def _init_pages(self):
        """Initialize all pages"""
        # Create page mapping dictionary
        self.page_map = {}

        # Dashboard (NEW - Home screen)
        self.dashboard = DashboardWidget()
        self.dashboard.connect_clicked.connect(lambda: self._navigate_to("connection"))
        self.dashboard.reports_clicked.connect(lambda: self._navigate_to("reports"))
        self.dashboard.training_clicked.connect(lambda: self._navigate_to("ai_training"))
        self.dashboard.settings_clicked.connect(lambda: self._navigate_to("settings"))
        self.pages.addWidget(self.dashboard)
        self.page_map["dashboard"] = self.dashboard

        # Profiles Tab
        self.profiles_tab = ProfilesTab(
            vehicle_manager=self.vehicle_manager,
            on_profile_loaded=self._on_profile_loaded,
            vin_decoder=self.vin_decoder,
            data_logger=self.data_logger,
            parent=self
        )
        
        # Populate vehicle switcher with available profiles
        self._populate_vehicle_switcher()
        # Set connectivity manager for VIN reading capability
        self.profiles_tab.connectivity_manager = self.connectivity
        
        # ===== LIVE DATA TAB =====
        # Use the fixed LiveDataTab from live_data_tab.py
        try:
            self.live_data_tab = FixedLiveDataTab(
                connectivity_manager=self.connectivity,
                on_snapshot=self._on_live_data,
                parent=self
            )
            logger.info("Using FixedLiveDataTab from live_data_tab.py")
        except Exception as e:
            logger.error(f"Failed to initialize FixedLiveDataTab: {e}")
            # Fallback widget
            self.live_data_tab = QWidget()
            layout = QVBoxLayout(self.live_data_tab)
            error_label = QLabel(f"Live Data Tab Error: {e}")
            error_label.setStyleSheet("color: red; font-size: 16px;")
            layout.addWidget(error_label)
        
        # Connection Tab - UPDATED WITH PROFILE CALLBACK
        self.connection_tab = ConnectionTab(
            connectivity=self.connectivity,
            get_active_profile=self._get_active_profile,  # NEW PARAMETER
            parent=self,
        )
        
        # DTC Codes Tab
        self.dtc_tab = DTCTab(
            connectivity_manager=self.connectivity,
            get_active_profile=self._get_active_profile,
            ai_module=self.unified_ai,
            parent=self
        )

        # Historical Charts Tab
        self.charts_tab = HistoricalChartsTab(
            data_logger=self.data_logger,
            parent=self
        )
        
        # PID Learning Tab (from imported module)
        try:
            self.pid_tab = PIDLearningTab(
                connectivity=self.connectivity,
                pid_manager=self.pid_manager,
                parent=self
            )
        except Exception as e:
            logger.warning(f"PID Learning Tab init error: {e}")
            self.pid_tab = QWidget()
        
        # AI Training Tab (from imported module)
        try:
            self.ai_training_tab = AITrainingTab(
                predictive_engine=self.predictive_engine,
                unified_ai=self.unified_ai,
                parent=self
            )
        except Exception as e:
            logger.warning(f"AI Training Tab init error: {e}")
            self.ai_training_tab = QWidget()
        
        # AI Insights Tab
        self.ai_insights_tab = AIInsightsTab(
            ai_module=self.unified_ai,
            get_active_profile=self._get_active_profile,
            parent=self
        )
        
        # Failure Forecast Tab - INTEGRATED WITH BOTH AI MODULES
        self.forecast_tab = FailureForecastTab(
            predictive_engine=self.predictive_engine,
            unified_ai=self.unified_ai,
            get_active_profile=self._get_active_profile,
            get_latest_snapshot=self._get_latest_snapshot,
            get_recent_history=self._get_recent_history,
            parent=self
        )
        
        # Reports Tab (from imported module)
        try:
            self.reports_tab = ReportsTab(
                ai_module=self.unified_ai,
                get_active_profile=self._get_active_profile,
                get_latest_snapshot=self._get_latest_snapshot,
                mobile_wrapper=self.mobile_wrapper,
                parent=self
            )
            logger.info("ReportsTab initialized successfully")
        except Exception as e:
            logger.warning(f"Reports Tab init error: {e}")
            import traceback
            traceback.print_exc()
            self.reports_tab = QWidget()
            layout = QVBoxLayout(self.reports_tab)
            error_label = QLabel(f"Reports Tab Error: {e}")
            error_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
            error_label.setWordWrap(True)
            layout.addWidget(error_label)
        
        # Server Tab (from imported module) - formerly Cloud Sync Tab
        try:
            self.server_tab = ServerTab(
                mobile_wrapper=self.mobile_wrapper,
                parent=self
            )
        except Exception as e:
            logger.warning(f"Server Tab init error: {e}")
            self.server_tab = QWidget()

        # Service History Tab (NEW)
        try:
            from service_history_tab import ServiceHistoryTab
            from settings_tab import SettingsTab
            self.service_history_tab = ServiceHistoryTab(
                profile_db_path=self.profile_db_path
            )
            # Connect service_logged signal to refresh profiles tab
            if hasattr(self.service_history_tab, 'service_logged'):
                self.service_history_tab.service_logged.connect(self._on_service_logged)
            # Connect Enhanced Prediction Engine for LSTM/Feedback features
            if self.enhanced_engine and hasattr(self.service_history_tab, 'set_enhanced_engine'):
                self.service_history_tab.set_enhanced_engine(self.enhanced_engine)
                logger.info("Enhanced engine connected to Service History Tab")
            logger.info("Service History Tab initialized successfully")
        except Exception as e:
            logger.warning(f"Service History Tab init error: {e}")
            self.service_history_tab = QWidget()
            layout = QVBoxLayout(self.service_history_tab)
            error_label = QLabel(f"Service History Tab Error: {e}")
            error_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
            layout.addWidget(error_label)

        # Advanced Features Tab (NEW)
        try:
            from advanced_features_tab import AdvancedFeaturesTab
            self.advanced_features_tab = AdvancedFeaturesTab(parent_window=self)
            logger.info("Advanced Features Tab initialized successfully")
        except Exception as e:
            logger.warning(f"Advanced Features Tab init error: {e}")
            self.advanced_features_tab = QWidget()
            layout = QVBoxLayout(self.advanced_features_tab)
            error_label = QLabel(f"Advanced Features Tab Error: {e}")
            error_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
            layout.addWidget(error_label)

        # Settings Tab (NEW)
        try:
            self.settings_tab = SettingsTab(parent=self)
            logger.info("Settings Tab initialized successfully")
        except Exception as e:
            logger.warning(f"Settings Tab init error: {e}")
            self.settings_tab = QWidget()
            layout = QVBoxLayout(self.settings_tab)
            error_label = QLabel(f"Settings Tab Error: {e}")
            error_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
            layout.addWidget(error_label)

        # Vehicle Catalog Editor Tab (optional)
        if CATALOG_EDITOR_AVAILABLE:
            try:
                self.catalog_tab = VehicleCatalogEditor()
                # Add to advanced section later if needed
            except Exception as e:
                logger.warning(f"Catalog Editor Tab init error: {e}")

        # Subscription Management Tab (Admin)
        if MANAGEMENT_TABS_AVAILABLE:
            try:
                self.subscription_tab = SubscriptionTab(parent=self)
                logger.info("Subscription Management Tab initialized successfully")
            except Exception as e:
                logger.warning(f"Subscription Management Tab init error: {e}")
                self.subscription_tab = QWidget()
                layout = QVBoxLayout(self.subscription_tab)
                error_label = QLabel(f"Subscription Tab Error: {e}")
                error_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
                layout.addWidget(error_label)
        else:
            self.subscription_tab = QWidget()
            layout = QVBoxLayout(self.subscription_tab)
            error_label = QLabel("Subscription Management not available")
            error_label.setStyleSheet("color: #8B949E; font-size: 14px; padding: 20px;")
            layout.addWidget(error_label)

        # Customer Management Tab removed - functionality merged into Profile tab

        # Admin Dashboard
        if MANAGEMENT_TABS_AVAILABLE:
            try:
                self.admin_dashboard = AdminDashboard(parent=self)
                logger.info("Admin Dashboard initialized successfully")
            except Exception as e:
                logger.warning(f"Admin Dashboard init error: {e}")
                self.admin_dashboard = QWidget()
                layout = QVBoxLayout(self.admin_dashboard)
                error_label = QLabel(f"Admin Dashboard Error: {e}")
                error_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
                layout.addWidget(error_label)
        else:
            self.admin_dashboard = QWidget()
            layout = QVBoxLayout(self.admin_dashboard)
            error_label = QLabel("Admin Dashboard not available")
            error_label.setStyleSheet("color: #8B949E; font-size: 14px; padding: 20px;")
            layout.addWidget(error_label)

        # Data Management Tab (NEW)
        if DATA_MANAGEMENT_TAB_AVAILABLE:
            try:
                self.data_management_tab = DataManagementTab(parent=self)
                logger.info("Data Management Tab initialized successfully")
            except Exception as e:
                logger.warning(f"Data Management Tab init error: {e}")
                self.data_management_tab = QWidget()
                layout = QVBoxLayout(self.data_management_tab)
                error_label = QLabel(f"Data Management Tab Error: {e}")
                error_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
                layout.addWidget(error_label)
        else:
            self.data_management_tab = QWidget()
            layout = QVBoxLayout(self.data_management_tab)
            error_label = QLabel("Data Management not available")
            error_label.setStyleSheet("color: #8B949E; font-size: 14px; padding: 20px;")
            layout.addWidget(error_label)

        # Devices Tab (NEW)
        if DEVICES_TAB_AVAILABLE:
            try:
                self.devices_tab = DevicesTab(parent=self)
                logger.info("Devices Tab initialized successfully")
            except Exception as e:
                logger.warning(f"Devices Tab init error: {e}")
                self.devices_tab = QWidget()
                layout = QVBoxLayout(self.devices_tab)
                error_label = QLabel(f"Devices Tab Error: {e}")
                error_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
                layout.addWidget(error_label)
        else:
            self.devices_tab = QWidget()
            layout = QVBoxLayout(self.devices_tab)
            error_label = QLabel("Devices not available")
            error_label.setStyleSheet("color: #8B949E; font-size: 14px; padding: 20px;")
            layout.addWidget(error_label)

        # Notifications Tab (NEW)
        if NOTIFICATIONS_TAB_AVAILABLE:
            try:
                self.notifications_tab = NotificationsTab(parent=self)
                logger.info("Notifications Tab initialized successfully")
            except Exception as e:
                logger.warning(f"Notifications Tab init error: {e}")
                self.notifications_tab = QWidget()
                layout = QVBoxLayout(self.notifications_tab)
                error_label = QLabel(f"Notifications Tab Error: {e}")
                error_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
                layout.addWidget(error_label)
        else:
            self.notifications_tab = QWidget()
            layout = QVBoxLayout(self.notifications_tab)
            error_label = QLabel("Notifications not available")
            error_label.setStyleSheet("color: #8B949E; font-size: 14px; padding: 20px;")
            layout.addWidget(error_label)

        # User Management Tab (NEW - Admin Only)
        if USER_MANAGEMENT_TAB_AVAILABLE:
            try:
                self.user_management_tab = UserManagementTab(parent=self)
                logger.info("User Management Tab initialized successfully")
            except Exception as e:
                logger.warning(f"User Management Tab init error: {e}")
                self.user_management_tab = QWidget()
                layout = QVBoxLayout(self.user_management_tab)
                error_label = QLabel(f"User Management Tab Error: {e}")
                error_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
                layout.addWidget(error_label)

        # Tier Management Tab (NEW - FREE/PRO/PREMIUM subscription tiers)
        if TIER_MANAGEMENT_AVAILABLE:
            try:
                self.tier_management_tab = SubscriptionManagementTab(parent=self)
                logger.info("Tier Management Tab initialized successfully")
            except Exception as e:
                logger.warning(f"Tier Management Tab init error: {e}")
                self.tier_management_tab = QWidget()
                layout = QVBoxLayout(self.tier_management_tab)
                error_label = QLabel(f"Tier Management Tab Error: {e}")
                error_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
                layout.addWidget(error_label)
        else:
            self.tier_management_tab = QWidget()
            layout = QVBoxLayout(self.tier_management_tab)
            error_label = QLabel("Tier Management not available")
            error_label.setStyleSheet("color: #8B949E; font-size: 14px; padding: 20px;")
            layout.addWidget(error_label)

        # PID Atlas Browser Tab
        try:
            from predict.desktop.tabs.pid_atlas_tab import PIDAtlasTab
            from predict.desktop.api_client import PredictAPIClient
            self.pid_atlas_tab = PIDAtlasTab(api_client=PredictAPIClient(), parent=self)
            logger.info("PID Atlas Tab initialized successfully")
        except Exception as e:
            logger.warning(f"PID Atlas Tab init error: {e}")
            self.pid_atlas_tab = QWidget()
            layout = QVBoxLayout(self.pid_atlas_tab)
            error_label = QLabel(f"PID Atlas Tab Error: {e}")
            error_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
            layout.addWidget(error_label)

        # AI Chat Tab (NEW - LLM Assistant Integration)
        try:
            self.chat_tab = ChatTab(self.llm_assistant)
            logger.info("AI Chat Tab initialized successfully")
        except Exception as e:
            logger.warning(f"AI Chat Tab init error: {e}")
            self.chat_tab = QWidget()
            layout = QVBoxLayout(self.chat_tab)
            error_label = QLabel(f"AI Chat Tab Error: {e}")
            error_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
            layout.addWidget(error_label)
        else:
            self.user_management_tab = QWidget()
            layout = QVBoxLayout(self.user_management_tab)
            error_label = QLabel("User Management not available")
            error_label.setStyleSheet("color: #8B949E; font-size: 14px; padding: 20px;")
            layout.addWidget(error_label)

        # ==================== PHASE 2 TABS ====================
        # Fuel Tracking Tab
        if FUEL_TRACKING_TAB_AVAILABLE:
            try:
                self.fuel_tracking_tab = FuelTrackingTab(
                    fuel_system=self.fuel_tracking
                )
                logger.info("Fuel Tracking Tab initialized successfully")
            except Exception as e:
                logger.warning(f"Fuel Tracking Tab init error: {e}")
                self.fuel_tracking_tab = QWidget()
                layout = QVBoxLayout(self.fuel_tracking_tab)
                error_label = QLabel(f"Fuel Tracking Tab Error: {e}")
                error_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
                layout.addWidget(error_label)
        else:
            self.fuel_tracking_tab = QWidget()
            layout = QVBoxLayout(self.fuel_tracking_tab)
            error_label = QLabel("Fuel Tracking not available")
            error_label.setStyleSheet("color: #8B949E; font-size: 14px; padding: 20px;")
            layout.addWidget(error_label)

        # Driving Score Tab
        if DRIVING_SCORE_TAB_AVAILABLE:
            try:
                self.driving_score_tab = DrivingScoreTab(
                    score_system=self.driving_score
                )
                logger.info("Driving Score Tab initialized successfully")
            except Exception as e:
                logger.warning(f"Driving Score Tab init error: {e}")
                self.driving_score_tab = QWidget()
                layout = QVBoxLayout(self.driving_score_tab)
                error_label = QLabel(f"Driving Score Tab Error: {e}")
                error_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
                layout.addWidget(error_label)
        else:
            self.driving_score_tab = QWidget()
            layout = QVBoxLayout(self.driving_score_tab)
            error_label = QLabel("Driving Score not available")
            error_label.setStyleSheet("color: #8B949E; font-size: 14px; padding: 20px;")
            layout.addWidget(error_label)

        # Geofencing Tab
        if GEOFENCING_TAB_AVAILABLE:
            try:
                self.geofencing_tab = GeofencingTab(
                    geofence_manager=self.geofencing
                )
                logger.info("Geofencing Tab initialized successfully")
            except Exception as e:
                logger.warning(f"Geofencing Tab init error: {e}")
                self.geofencing_tab = QWidget()
                layout = QVBoxLayout(self.geofencing_tab)
                error_label = QLabel(f"Geofencing Tab Error: {e}")
                error_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
                layout.addWidget(error_label)
        else:
            self.geofencing_tab = QWidget()
            layout = QVBoxLayout(self.geofencing_tab)
            error_label = QLabel("Geofencing not available")
            error_label.setStyleSheet("color: #8B949E; font-size: 14px; padding: 20px;")
            layout.addWidget(error_label)

        # ESP32 Sensors Tab
        if ESP32_SENSORS_TAB_AVAILABLE:
            try:
                self.esp32_sensors_tab = ESP32SensorsTab(sensor_manager=None)
                logger.info("ESP32 Sensors Tab initialized successfully")
            except Exception as e:
                logger.warning(f"ESP32 Sensors Tab init error: {e}")
                self.esp32_sensors_tab = QWidget()
                layout = QVBoxLayout(self.esp32_sensors_tab)
                error_label = QLabel(f"ESP32 Sensors Tab Error: {e}")
                error_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
                layout.addWidget(error_label)
        else:
            self.esp32_sensors_tab = QWidget()
            layout = QVBoxLayout(self.esp32_sensors_tab)
            error_label = QLabel("ESP32 Sensors not available")
            error_label.setStyleSheet("color: #8B949E; font-size: 14px; padding: 20px;")
            layout.addWidget(error_label)

        # Maintenance Reminders Tab
        if MAINTENANCE_REMINDERS_TAB_AVAILABLE:
            try:
                self.maintenance_reminders_tab = MaintenanceRemindersTab(
                    reminder_system=self.maintenance_reminders
                )
                logger.info("Maintenance Reminders Tab initialized successfully")
            except Exception as e:
                logger.warning(f"Maintenance Reminders Tab init error: {e}")
                self.maintenance_reminders_tab = QWidget()
                layout = QVBoxLayout(self.maintenance_reminders_tab)
                error_label = QLabel(f"Maintenance Reminders Tab Error: {e}")
                error_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
                layout.addWidget(error_label)
        else:
            self.maintenance_reminders_tab = QWidget()
            layout = QVBoxLayout(self.maintenance_reminders_tab)
            error_label = QLabel("Maintenance Reminders not available")
            error_label.setStyleSheet("color: #8B949E; font-size: 14px; padding: 20px;")
            layout.addWidget(error_label)

        # Recall Alerts Tab
        if RECALL_ALERTS_TAB_AVAILABLE:
            try:
                self.recall_alerts_tab = RecallAlertsTab(recall_system=None)
                logger.info("Recall Alerts Tab initialized successfully")
            except Exception as e:
                logger.warning(f"Recall Alerts Tab init error: {e}")
                self.recall_alerts_tab = QWidget()
                layout = QVBoxLayout(self.recall_alerts_tab)
                error_label = QLabel(f"Recall Alerts Tab Error: {e}")
                error_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
                layout.addWidget(error_label)
        else:
            self.recall_alerts_tab = QWidget()
            layout = QVBoxLayout(self.recall_alerts_tab)
            error_label = QLabel("Recall Alerts not available")
            error_label.setStyleSheet("color: #8B949E; font-size: 14px; padding: 20px;")
            layout.addWidget(error_label)

        # Analytics Tab (Phase 4)
        if ANALYTICS_TAB_AVAILABLE:
            try:
                self.analytics_tab = AnalyticsTab(
                    get_historical_data=lambda: getattr(self.historical_data, 'get_all_readings', lambda: [])()
                )
                logger.info("Analytics Tab initialized successfully")
            except Exception as e:
                logger.warning(f"Analytics Tab init error: {e}")
                self.analytics_tab = QWidget()
                layout = QVBoxLayout(self.analytics_tab)
                error_label = QLabel(f"Analytics Tab Error: {e}")
                error_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
                layout.addWidget(error_label)
        else:
            self.analytics_tab = QWidget()
            layout = QVBoxLayout(self.analytics_tab)
            error_label = QLabel("Analytics not available")
            error_label.setStyleSheet("color: #8B949E; font-size: 14px; padding: 20px;")
            layout.addWidget(error_label)

        # Help Tab (Phase 5)
        if HELP_TAB_AVAILABLE:
            try:
                self.help_tab = HelpTab()
                logger.info("Help Tab initialized successfully")
            except Exception as e:
                logger.warning(f"Help Tab init error: {e}")
                self.help_tab = QWidget()
                layout = QVBoxLayout(self.help_tab)
                error_label = QLabel(f"Help Tab Error: {e}")
                error_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
                layout.addWidget(error_label)
        else:
            self.help_tab = QWidget()
            layout = QVBoxLayout(self.help_tab)
            error_label = QLabel("Help not available")
            error_label.setStyleSheet("color: #8B949E; font-size: 14px; padding: 20px;")
            layout.addWidget(error_label)

        # Add pages to stacked widget and map them
        self.pages.addWidget(self.profiles_tab)
        self.page_map["profiles"] = self.profiles_tab

        self.pages.addWidget(self.service_history_tab)
        self.page_map["service_history"] = self.service_history_tab

        self.pages.addWidget(self.live_data_tab)
        self.page_map["live_data"] = self.live_data_tab

        # Status page removed (was duplicate of live_data)

        self.pages.addWidget(self.connection_tab)
        self.page_map["connection"] = self.connection_tab

        self.pages.addWidget(self.dtc_tab)
        self.page_map["dtc"] = self.dtc_tab

        self.pages.addWidget(self.charts_tab)
        self.page_map["historical"] = self.charts_tab

        self.pages.addWidget(self.pid_tab)
        self.page_map["pid_learning"] = self.pid_tab

        self.pages.addWidget(self.ai_training_tab)
        self.page_map["ai_training"] = self.ai_training_tab

        self.pages.addWidget(self.ai_insights_tab)
        self.page_map["ai_insights"] = self.ai_insights_tab

        self.pages.addWidget(self.forecast_tab)
        self.page_map["forecast"] = self.forecast_tab

        self.pages.addWidget(self.reports_tab)
        self.page_map["reports"] = self.reports_tab

        self.pages.addWidget(self.advanced_features_tab)
        self.page_map["advanced"] = self.advanced_features_tab

        self.pages.addWidget(self.settings_tab)
        self.page_map["settings"] = self.settings_tab

        # Server tab v2.0 - Now accessible from sidebar navigation!
        self.pages.addWidget(self.server_tab)
        self.page_map["server"] = self.server_tab

        # Admin tabs - Subscription and Admin Dashboard (Customer Management merged into Profile tab)
        self.pages.addWidget(self.subscription_tab)
        self.page_map["subscriptions"] = self.subscription_tab

        self.pages.addWidget(self.admin_dashboard)
        self.page_map["admin_dashboard"] = self.admin_dashboard

        # New tabs - Data Management, Devices, Notifications, User Management
        self.pages.addWidget(self.data_management_tab)
        self.page_map["data_management"] = self.data_management_tab

        self.pages.addWidget(self.devices_tab)
        self.page_map["devices"] = self.devices_tab

        self.pages.addWidget(self.notifications_tab)
        self.page_map["notifications"] = self.notifications_tab

        self.pages.addWidget(self.user_management_tab)
        self.page_map["users"] = self.user_management_tab

        # Tier Management Tab (NEW - FREE/PRO/PREMIUM)
        self.pages.addWidget(self.tier_management_tab)
        self.page_map["tier_management"] = self.tier_management_tab

        # PID Atlas Browser
        self.pages.addWidget(self.pid_atlas_tab)
        self.page_map["pid_atlas"] = self.pid_atlas_tab

        # AI Chat Tab (NEW)
        self.pages.addWidget(self.chat_tab)
        self.page_map["ai_chat"] = self.chat_tab

        # ==================== PHASE 2 TABS ====================
        # Fuel Tracking
        self.pages.addWidget(self.fuel_tracking_tab)
        self.page_map["fuel_tracking"] = self.fuel_tracking_tab

        # Driving Score
        self.pages.addWidget(self.driving_score_tab)
        self.page_map["driving_score"] = self.driving_score_tab

        # Geofencing
        self.pages.addWidget(self.geofencing_tab)
        self.page_map["geofencing"] = self.geofencing_tab

        # ESP32 Sensors
        self.pages.addWidget(self.esp32_sensors_tab)
        self.page_map["esp32_sensors"] = self.esp32_sensors_tab

        # Maintenance Reminders
        self.pages.addWidget(self.maintenance_reminders_tab)
        self.page_map["maintenance_reminders"] = self.maintenance_reminders_tab

        # Recall Alerts
        self.pages.addWidget(self.recall_alerts_tab)
        self.page_map["recall_alerts"] = self.recall_alerts_tab

        # Analytics (Phase 4)
        self.pages.addWidget(self.analytics_tab)
        self.page_map["analytics"] = self.analytics_tab

        # Help (Phase 5)
        self.pages.addWidget(self.help_tab)
        self.page_map["help"] = self.help_tab

        logger.info(f"Initialized {len(self.page_map)} pages")

    def _on_navigation_changed(self, page_id: str):
        """Handle navigation change from sidebar"""
        self._navigate_to(page_id)

    def _navigate_to(self, page_id: str):
        """Navigate to a specific page"""
        if page_id in self.page_map:
            widget = self.page_map[page_id]
            self.pages.setCurrentWidget(widget)
            self.sidebar.set_active_page(page_id)
            logger.info(f"Navigated to: {page_id}")
        else:
            logger.warning(f"Page not found: {page_id}")

    def _check_for_updates(self):
        """Check server for newer desktop version and notify user"""
        try:
            import requests
            response = requests.get(
                "https://predict.previlium.com/api/app/version",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                latest = data.get("desktop_latest_version", "1.0.0")
                update_url = data.get("desktop_update_url", "")
                # Compare versions
                current_parts = [int(x) for x in APP_VERSION.split(".")]
                latest_parts = [int(x) for x in latest.split(".")]
                for i in range(max(len(current_parts), len(latest_parts))):
                    c = current_parts[i] if i < len(current_parts) else 0
                    l = latest_parts[i] if i < len(latest_parts) else 0
                    if l > c:
                        QMessageBox.information(
                            self,
                            "Update Available",
                            f"A new version of PREDICT Desktop is available.\n\n"
                            f"Current: v{APP_VERSION}\n"
                            f"Latest: v{latest}\n\n"
                            f"Download from:\n{update_url}"
                        )
                        break
                    elif c > l:
                        break
        except Exception as e:
            logger.debug(f"Version check skipped: {e}")

    def _setup_timers(self):
        """Setup update timers"""
        # Header update timer (reduced frequency to improve performance)
        self.header_timer = QTimer(self)
        self.header_timer.timeout.connect(self._update_header)
        self.header_timer.start(30000)  # Every 30 seconds (was 5s)

        # Sync status update timer
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self._update_sync_status)
        self.sync_timer.start(60000)  # Every 60 seconds (was 10s)

        # Online status check timer
        self.online_check_timer = QTimer(self)
        self.online_check_timer.timeout.connect(self._check_online_status)
        self.online_check_timer.start(30000)  # Every 30 seconds (was 5s)

        # Start WebSocket connection for real-time owner/driver updates
        if self.server_sync:
            try:
                self.server_sync.start()
                logger.info("WebSocket connection started for real-time updates")
            except Exception as e:
                logger.warning(f"Failed to start WebSocket connection: {e}")

        # Initial update
        self._update_header()

    def _populate_vehicle_switcher(self):
        """Populate vehicle switcher with all available profiles"""
        try:
            profiles = self.vehicle_manager.get_all_profiles()
            if profiles:
                self.header.populate_vehicles(profiles)
                # Set current vehicle if active profile exists
                if self.active_profile:
                    profile_id = self.active_profile.get('profile_id', '')
                    self.header.set_current_vehicle(profile_id)
        except Exception as e:
            logger.error(f"Error populating vehicle switcher: {e}")
    
    def _update_header(self):
        """Update header dashboard"""
        try:
            is_connected = getattr(self.connectivity, 'connected', False)
            conn_type = getattr(self.connectivity, 'connection_type', 'unknown')
            data = getattr(self.connectivity, 'latest_merged', None)
            has_data = data and isinstance(data, dict) and len(data) > 0
            
            # Convert ConnectionType enum to string if needed
            if hasattr(conn_type, 'value'):
                conn_type = conn_type.value
            elif hasattr(conn_type, 'name'):
                conn_type = conn_type.name
            else:
                conn_type = str(conn_type)
            
            if is_connected and has_data:
                self.header.update_connection("connected", "Receiving Data", conn_type)
                self.header.update_quality(95)
                # Update dashboard connection status
                self.dashboard.update_connection_status(True)
            elif is_connected:
                self.header.update_connection("connecting", "No Data", conn_type)
                self.header.update_quality(50)
                # Update dashboard connection status
                self.dashboard.update_connection_status(False)
            else:
                self.header.update_connection("disconnected", "Disconnected")
                self.header.update_quality(0)
                # Update dashboard connection status
                self.dashboard.update_connection_status(False)

            # Update profile
            profile_name = self.active_profile.get('name', 'None') if self.active_profile else 'None'
            self.header.update_profile(profile_name)

            # Update AI status
            ai_status = "Ready"
            ai_training_count = 0
            if hasattr(self.predictive_engine, 'models') and self.predictive_engine.models:
                ai_status = "Active"
                ai_training_count = len(self.predictive_engine.models)
            self.header.update_ai_status(ai_status)
        except Exception as e:
            logger.error(f"Error updating header: {e}")

    def _update_sync_status(self):
        """Update sync status in header"""
        try:
            if not self.cloud_sync:
                self.header.update_sync_status('disabled')
                return
            
            # Get sync status from cloud sync manager
            status_dict = self.cloud_sync.get_sync_status()
            
            # Determine status string
            if status_dict.get('syncing', False):
                sync_status = 'syncing'
                last_sync = None
            elif status_dict.get('last_sync'):
                last_sync_time = status_dict['last_sync']
                if last_sync_time:
                    # Format time string
                    try:
                        sync_dt = datetime.fromisoformat(last_sync_time)
                        now = datetime.now()
                        diff = now - sync_dt
                        
                        if diff.total_seconds() < 60:
                            time_str = "just now"
                        elif diff.total_seconds() < 3600:
                            time_str = f"{diff.total_seconds() // 60} min ago"
                        elif diff.total_seconds() < 86400:
                            time_str = f"{diff.total_seconds() // 3600} hours ago"
                        else:
                            time_str = f"{diff.days} days ago"
                    except Exception:
                        time_str = "recently"
                else:
                    time_str = None
                
                if status_dict.get('error'):
                    sync_status = 'error'
                    last_sync = time_str
                else:
                    sync_status = 'synced'
                    last_sync = time_str
                
                self.header.update_sync_status(sync_status, last_sync)
                
        except Exception:
            logger.error(f"Error updating sync status")
            self.header.update_sync_status('error')
    
    def _on_voice_command(self):
        """Handle voice command button click - simulate voice input through LLM"""
        try:
            # Simulate voice input by showing a dialog
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton
            
            dialog = QDialog(self)
            dialog.setWindowTitle("Voice Command")
            dialog.setMinimumWidth(400)
            
            layout = QVBoxLayout(dialog)
            
            # Instructions
            instructions = QLabel("Speak a command to control your vehicle:")
            instructions.setStyleSheet("color: #F0F6FC; font-size: 13px;")
            layout.addWidget(instructions)
            
            # Command input
            command_input = QTextEdit()
            command_input.setPlaceholderText("e.g., 'Start Engine', 'Lock Vehicle', 'Show Status'")
            command_input.setStyleSheet("""
                QTextEdit {
                    background-color: #21262D;
                    color: #F0F6FC;
                    border: 1px solid #30363D;
                    border-radius: 6px;
                    padding: 8px;
                    font-size: 12px;
                }
            """)
            layout.addWidget(command_input)
            
            # Buttons
            buttons = QHBoxLayout()
            send_btn = QPushButton("Send Command")
            send_btn.setStyleSheet("background-color: #C40000; color: white; padding: 8px 16px; border-radius: 6px; font-weight: bold;")
            cancel_btn = QPushButton("Cancel")
            cancel_btn.setStyleSheet("background-color: #21262D; color: #F0F6FC; padding: 8px 16px; border-radius: 6px;")
            
            buttons.addWidget(send_btn)
            buttons.addWidget(cancel_btn)
            layout.addLayout(buttons)
            
            # Execute dialog
            if dialog.exec() == QDialog.Accepted:
                command = command_input.toPlainText().strip()
                if command:
                    # Send command to LLM assistant for processing
                    if self.llm_assistant:
                        self.llm_assistant.chat(
                            f"Vehicle command: {command}. Execute this command for the current vehicle.",
                            context="voice_command"
                        )
                        self.voice_status_label.setText(f"Command sent: {command}")
                        self.voice_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
                    else:
                        QMessageBox.warning(self, "LLM Not Available", "LLM assistant is not available. Voice commands require the LLM module.")
                else:
                    self.voice_status_label.setText("Command cancelled")
        except Exception as e:
            logger.error(f"Voice command error: {e}")
            self.voice_status_label.setText("Error")
            self.voice_status_label.setStyleSheet("color: #F44336;")

            # Update dashboard AI training sessions count
            self.dashboard.update_training_sessions(ai_training_count)

            # Calculate and update health score based on various factors
            health_score = self._calculate_health_score(is_connected, has_data, data)
            self.dashboard.update_health_score(health_score)

            # Update alerts count (count from alert notifications if available)
            alerts_count = 0
            if hasattr(self, 'alert_notifications') and self.alert_notifications:
                # Try to get active alerts count
                alerts_count = len(getattr(self.alert_notifications, 'active_alerts', []))
            self.dashboard.update_alerts_count(alerts_count)

            # Update distance driven (from trip analytics if available)
            if hasattr(self, 'trip_analytics') and self.trip_analytics and hasattr(self.trip_analytics, 'get_today_distance'):
                try:
                    distance = self.trip_analytics.get_today_distance()
                    self.dashboard.update_distance(distance if distance else 0.0)
                except:
                    self.dashboard.update_distance(0.0)

        except Exception as e:
            logger.debug(f"Header update error: {e}")

    def _calculate_health_score(self, is_connected: bool, has_data: bool, data: dict) -> int:
        """Calculate vehicle health score based on various factors"""
        try:
            score = 50  # Base score

            # Connection bonus
            if is_connected and has_data:
                score += 20
            elif is_connected:
                score += 10

            # Check for DTCs (diagnostic trouble codes)
            if data and isinstance(data, dict):
                # No DTCs is good
                dtc_count = len(data.get('dtc_codes', []))
                if dtc_count == 0:
                    score += 15
                elif dtc_count <= 2:
                    score += 5
                else:
                    score -= 10

                # Check critical parameters
                # Battery voltage (good: 12-14.5V)
                battery_voltage = data.get('BATTERY_VOLTAGE') or data.get('VOLTAGE')
                if battery_voltage:
                    try:
                        voltage = float(battery_voltage)
                        if 12.0 <= voltage <= 14.5:
                            score += 10
                        elif voltage < 11.5:
                            score -= 15
                    except:
                        pass

                # Engine coolant temperature (good: 80-100°C)
                coolant_temp = data.get('COOLANT_TEMP') or data.get('ENGINE_COOLANT_TEMP')
                if coolant_temp:
                    try:
                        temp = float(coolant_temp)
                        if 80 <= temp <= 100:
                            score += 5
                        elif temp > 110:
                            score -= 10
                    except:
                        pass

            # Cap score between 0 and 100
            return max(0, min(100, score))

        except Exception as e:
            logger.debug(f"Health score calculation error: {e}")
            return 75  # Default to "good" score
    
    def _check_online_status(self):
        """Check for online profiles via mobile wrapper (fast, non-blocking)"""
        active_ids = set()

        # Check via mobile wrapper (local only - fast)
        if self.mobile_wrapper:
            try:
                local_ids = self.mobile_wrapper.get_active_sessions() or []
                active_ids.update(str(x) for x in local_ids)
            except Exception:
                pass  # Ignore errors

        # Update profiles tab with combined online IDs
        self.profiles_tab.update_online_status(list(active_ids))

    def _get_first_raw_api_key(self):
        """Get the first raw API key from backup files"""
        import os

        # Use config path or fallback to legacy path
        if CONFIG:
            keys_folder = str(CONFIG.get_customer_api_keys_dir("default"))
        else:
            keys_folder = "C:/OBDserver/API_KEYS"

        # Also check legacy path if primary doesn't exist
        if not os.path.exists(keys_folder):
            keys_folder = "C:/OBDserver/API_KEYS"

        if not os.path.exists(keys_folder):
            return None

        for filename in os.listdir(keys_folder):
            if filename.endswith("_apikey.txt"):
                filepath = os.path.join(keys_folder, filename)
                try:
                    with open(filepath, 'r') as f:
                        content = f.read()
                        for line in content.split('\n'):
                            line = line.strip()
                            if line and len(line) == 9 and line.isalnum():
                                return line
                except:
                    pass
        return None

    def _on_profile_loaded(self, profile):
        """Handle profile loaded event"""
        # Call _set_active_profile to update connectivity manager
        self._set_active_profile(profile)
    
    def _on_vehicle_switched(self, profile_id: str):
        """Handle vehicle switch from header dropdown"""
        try:
            # Get profile from vehicle manager
            profile = self.vehicle_manager.get_profile(profile_id)
            if not profile:
                logger.warning(f"Profile not found: {profile_id}")
                return
            
            # Set as active profile
            self._set_active_profile(profile)
            
            # Update header profile label
            self.header.update_profile(profile.get('name', 'Unknown'))
            
            # Update header vehicle switcher selection
            self.header.set_current_vehicle(profile_id)
            
            # Refresh tabs that depend on active profile
            self._refresh_tabs_for_profile(profile)
            
            logger.info(f"Switched to vehicle: {profile.get('name')}")
            
        except Exception as e:
            logger.error(f"Error switching vehicle: {e}")
            show_error(self, "Vehicle Switch Error", f"Failed to switch vehicle:\n{e}")
    
    def _refresh_tabs_for_profile(self, profile: Dict[str, Any]):
        """Refresh all tabs when profile changes"""
        # Update profiles tab
        if hasattr(self, 'profiles_tab') and hasattr(self.profiles_tab, 'refresh_profiles'):
            self.profiles_tab.refresh_profiles()
        
        # Update vehicle switcher with latest profiles
        self._populate_vehicle_switcher()
        
        # Update connection tab
        if hasattr(self, 'connection_tab') and hasattr(self.connection_tab, '_update_profile_status'):
            self.connection_tab._update_profile_status()
        
        # Update analytics tabs
        if hasattr(self, 'failure_forecast_tab'):
            try:
                self.failure_forecast_tab.refresh_forecast()
            except Exception as e:
                logger.warning(f"Failed to refresh failure forecast: {e}")

        # Notify tabs
        self.ai_insights_tab.on_profile_changed(profile)

        # Notify service history tab about loaded profile
        if hasattr(self, 'service_history_tab') and hasattr(self.service_history_tab, 'set_profile'):
            self.service_history_tab.set_profile(profile.get('name'))

        # Sync profile to mobile server
        if self.mobile_wrapper:
            self.mobile_wrapper.set_active_profile(profile.get('name'))
        if self.mobile_bridge:
            profile_id = profile.get('profile_id')
            self.mobile_bridge.set_active_profile(profile.get('name'), profile_id)
            # Start server polling for this profile
            if profile_id:
                self.mobile_bridge.start_server_polling(profile_id, interval_ms=1000)
                logger.info(f"Server polling started for profile {profile.get('name')} (ID: {profile_id})")

        # Start logging session
        self.data_logger.start_session(profile)

        self._update_header()
        self.statusBar().showMessage(f"Profile loaded: {profile.get('name', 'Unknown')}")

    def _on_service_logged(self, service_data):
        """Handle service logged event - refresh profiles tab and notify AI"""
        profile_name = service_data.get('profile')

        # Refresh profiles tab service history display
        if profile_name and hasattr(self.profiles_tab, '_load_service_history'):
            self.profiles_tab._load_service_history(profile_name)

        # Feed service data to AI for learning
        try:
            # Get full service record from database
            import sqlite3
            conn = sqlite3.connect('./data/service_history.db')
            c = conn.cursor()
            c.execute("""
                SELECT component_type, service_km, expected_lifespan_km,
                       actual_usage_km, condition_at_replacement, part_brand,
                       part_spec
                FROM service_records
                WHERE profile_name = ?
                ORDER BY id DESC LIMIT 1
            """, (profile_name,))
            record = c.fetchone()
            conn.close()

            if record:
                component, service_km, expected_km, actual_km, condition, brand, spec = record

                # Feed to UnifiedAIModule for learning
                if hasattr(self.unified_ai, 'learn_from_service_history'):
                    self.unified_ai.learn_from_service_history({
                        'profile': profile_name,
                        'component': component,
                        'service_km': service_km,
                        'expected_lifespan_km': expected_km,
                        'actual_usage_km': actual_km,
                        'condition': condition,
                        'brand': brand,
                        'spec': spec
                    })

                # Feed to PredictiveFailureEngine
                if hasattr(self.predictive_engine, 'update_component_data'):
                    self.predictive_engine.update_component_data({
                        'profile': profile_name,
                        'component': component,
                        'actual_lifespan': actual_km,
                        'expected_lifespan': expected_km,
                        'degradation_rate': (actual_km / expected_km) if expected_km else 1.0
                    })

                logger.info(f"Service data fed to AI models: {component} for {profile_name}")

        except Exception as e:
            logger.error(f"Error feeding service data to AI: {e}")

        logger.info(f"Service logged for {profile_name}: {service_data.get('component')}")

    def _on_mobile_data_raw(self, mobile_data: dict):
        """Handle raw Mobile OBD data from mobile server"""
        try:
            if self.mobile_bridge:
                # Process and convert to unified format
                self.mobile_bridge.process_mobile_data(mobile_data)
                logger.debug("Mobile data forwarded to bridge")
        except Exception as e:
            logger.error(f"Error processing Mobile data: {e}")

    def _on_mobile_data_unified(self, unified_frame: dict):
        """Handle converted Mobile data in unified format"""
        # Set data source
        self.data_source = 'mobile_app'

        # Update last_seen timestamp for the profile
        try:
            metadata = unified_frame.get('metadata', {})
            profile_name = metadata.get('profile_name') or metadata.get('vehicle_id')
            if profile_name and self.vehicle_manager:
                self.vehicle_manager.update_last_seen_by_name(profile_name)
                logger.debug(f"Updated last_seen for profile: {profile_name}")
        except Exception as e:
            logger.error(f"Error updating last_seen: {e}")

        # Update Profiles Tab connection indicator - data is flowing!
        if hasattr(self, 'profiles_tab') and hasattr(self.profiles_tab, 'update_connection_status'):
            device_id = unified_frame.get('metadata', {}).get('vehicle_id', 'mobile')
            self.profiles_tab.update_connection_status(device_id, 'connected')

        # Feed to same pipeline as USB OBD data
        self._on_live_data(unified_frame)

        logger.debug("Mobile unified data processed")

    def _on_mobile_connection_status(self, device_id: str, status: str):
        """Handle Mobile app connection status changes"""
        # Accept both 'active' and 'connected' as online states
        is_online = status.lower() in ['active', 'connected']
        
        status_msg = f"Mobile: {device_id} - {'Online' if is_online else 'Offline'}"
        logger.info(status_msg)
        self.statusBar().showMessage(status_msg, 5000)

        # Update Reports Tab status
        if hasattr(self, 'reports_tab') and hasattr(self.reports_tab, 'update_mobile_status'):
            self.reports_tab.update_mobile_status(is_online, device_id)

        # Update Connection Tab status
        if hasattr(self, 'connection_tab') and hasattr(self.connection_tab, 'android_connection_label'):
            if is_online:
                self.connection_tab.android_connection_label.setText(f"Mobile: {device_id} connected")
                self.connection_tab.android_connection_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            else:
                self.connection_tab.android_connection_label.setText(f"Mobile: {device_id} disconnected")
                self.connection_tab.android_connection_label.setStyleSheet("color: #F44336; font-weight: bold;")

        # Update Profiles Tab connection indicator
        if hasattr(self, 'profiles_tab') and hasattr(self.profiles_tab, 'update_connection_status'):
            self.profiles_tab.update_connection_status(device_id, status)

    def _on_websocket_data(self, data: dict):
        """Handle real-time data from WebSocket"""
        # Process same as polling data
        self._on_live_data(data)

    def _on_car_connected(self, car_info: dict):
        """Handle new car connection via WebSocket"""
        device_id = car_info.get('device_id', 'unknown')
        self._log(f"🟢 New car connected: {device_id}")
        # Update connected cars list in profiles tab
        if hasattr(self, 'profiles_tab') and hasattr(self.profiles_tab, 'refresh_profiles'):
            self.profiles_tab.refresh_profiles()
        # Update Profiles Tab connection indicator
        if hasattr(self, 'profiles_tab') and hasattr(self.profiles_tab, 'update_connection_status'):
            self.profiles_tab.update_connection_status(device_id, 'connected')

    def _on_car_disconnected(self, device_id: str):
        """Handle car disconnection via WebSocket"""
        self._log(f"🔴 Car disconnected: {device_id}")
        # Update connected cars list in profiles tab
        if hasattr(self, 'profiles_tab') and hasattr(self.profiles_tab, 'refresh_profiles'):
            self.profiles_tab.refresh_profiles()
        # Update Profiles Tab connection indicator
        if hasattr(self, 'profiles_tab') and hasattr(self.profiles_tab, 'update_connection_status'):
            self.profiles_tab.update_connection_status(device_id, 'disconnected')

    def _on_ws_status_changed(self, connected: bool):
        """Handle WebSocket connection status change"""
        status = "Connected" if connected else "Disconnected"
        self._log(f"WebSocket: {status}")
        # Could update UI indicator here

    def _log(self, message: str):
        """Log message to status bar"""
        self.statusBar().showMessage(message, 5000)
        logger.info(message)

    def _on_remote_report_requested(self):
        """Handle report request from Mobile app (DirectReportServer)"""
        logger.info("Generating report for Mobile request...")
        try:
            # Use current profile and data
            profile = self.active_profile
            snapshot = self.latest_snapshot
            
            # Generate report using PDF Exporter
            # We use a temp path
            import tempfile
            temp_dir = tempfile.gettempdir()
            report_path = os.path.join(temp_dir, "predict_mobile_report.pdf")
            
            # Generate master report
            result = self.pdf_exporter.generate_master_report(
                profile=profile,
                snapshot=snapshot,
                ai_module=self.unified_ai,
                options={'include_charts': True, 'history': self.history_buffer}
            )
            
            if result.get('success') and self.pdf_exporter.save_pdf(report_path):
                self.report_server.set_report_ready(report_path)
                self.statusBar().showMessage("Report sent to Mobile device", 3000)
            else:
                logger.error("Failed to generate mobile report")
                # We don't set ready, so server will timeout (correct behavior for error)
                
        except Exception as e:
            logger.error(f"Error handling remote report request: {e}")

    def _process_pdf_queue(self):
        """Process pending PDF generation requests from Android app"""
        try:
            pdf_queue_file = CONFIG.REPORTS_QUEUE_FILE if CONFIG else Path("data/pdf_queue.json")
            if not pdf_queue_file.exists():
                return
            
            import json
            from datetime import datetime
            
            # Load queue
            with open(pdf_queue_file, 'r') as f:
                queue_data = json.load(f)
            
            pending = queue_data.get("pending", [])
            if not pending:
                return
            
            # Process first pending request
            request = pending[0]
            request_id = request.get("request_id")
            profile_id = request.get("profile_id")
            profile_name = request.get("profile_name", "Unknown")
            report_type = request.get("report_type", "comprehensive")
            
            logger.info(f"Processing PDF request {request_id} for profile {profile_name}")
            
            # Get profile from database
            if not self.vehicle_manager:
                logger.error("Vehicle manager not available")
                return
            
            profile = self.vehicle_manager.get_profile(profile_id)
            if not profile:
                logger.error(f"Profile {profile_id} not found")
                # Mark as failed
                request["status"] = "failed"
                request["error"] = "Profile not found"
                queue_data["completed"][request_id] = request
                queue_data["pending"] = pending[1:]
                with open(pdf_queue_file, 'w') as f:
                    json.dump(queue_data, f, indent=2)
                return
            
            # Set as active profile temporarily
            old_active = self.active_profile
            self.active_profile = profile
            
            # Generate PDF
            try:
                # Create reports directory if needed
                reports_dir = CONFIG.DATA_DIR / "reports" if CONFIG else Path("data/reports")
                reports_dir.mkdir(parents=True, exist_ok=True)
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"predict_report_{profile_name}_{report_type}_{timestamp}.pdf"
                report_path = reports_dir / filename
                
                # Generate report
                result = self.pdf_exporter.generate_master_report(
                    profile=profile,
                    snapshot=self.latest_snapshot or {},
                    ai_module=self.unified_ai,
                    options={
                        'include_charts': True,
                        'history': self.history_buffer,
                        'report_type': report_type,
                        'include_diagnostics': request.get("include_diagnostics", True),
                        'include_fuel_data': request.get("include_fuel_data", True),
                        'include_trip_data': request.get("include_trip_data", True),
                        'include_maintenance_history': request.get("include_maintenance_history", True),
                        'include_service_records': request.get("include_service_records", True)
                    }
                )
                
                if result.get('success') and self.pdf_exporter.save_pdf(str(report_path)):
                    # Mark as completed
                    request["status"] = "completed"
                    request["file_path"] = str(report_path)
                    request["filename"] = filename
                    request["completed_at"] = datetime.now().isoformat()
                    
                    # Get desktop IP (simplified - could be improved)
                    import socket
                    try:
                        hostname = socket.gethostname()
                        local_ip = socket.gethostbyname(hostname)
                    except:
                        local_ip = "localhost"
                    
                    request["download_url"] = f"http://{local_ip}:8001/report?device_id={request_id}"
                    
                    queue_data["completed"][request_id] = request
                    queue_data["pending"] = pending[1:]
                    
                    logger.info(f"PDF generated successfully: {filename}")
                    self.statusBar().showMessage(f"PDF report generated for {profile_name}", 3000)
                else:
                    request["status"] = "failed"
                    request["error"] = "PDF generation failed"
                    queue_data["completed"][request_id] = request
                    queue_data["pending"] = pending[1:]
                    logger.error(f"Failed to generate PDF for request {request_id}")
                    
            except Exception as e:
                logger.error(f"Error generating PDF: {e}")
                request["status"] = "failed"
                request["error"] = str(e)
                queue_data["completed"][request_id] = request
                queue_data["pending"] = pending[1:]
            finally:
                # Restore old active profile
                self.active_profile = old_active
            
            # Save updated queue
            with open(pdf_queue_file, 'w') as f:
                json.dump(queue_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error processing PDF queue: {e}")

    def _on_live_data(self, data: dict = None):
        """Handle live data update from any source (USB or Android)"""
        # If no data passed, read from latest_merged (USB mode)
        if data is None:
            data = getattr(self.connectivity, 'latest_merged', {})
            self.data_source = 'usb'

        if not data:
            return

        # Add source metadata
        if 'metadata' not in data:
            data['metadata'] = {}
        data['metadata']['source'] = self.data_source

        self.latest_snapshot = data
        
        # Update AI Environmental Context
        if self.unified_ai:
            self.unified_ai.update_environmental_context(data)
        
        # Update tabs
        self.profiles_tab.update_live_snapshot(data)
        self.ai_insights_tab.update_live_snapshot(data)
        self.forecast_tab.update_live_data(data)
        
        # Add to history
        if data and isinstance(data, dict):
            self.history_buffer.append(data)
            if len(self.history_buffer) > 100:
                self.history_buffer.pop(0)
            
            # Log data
            self.data_logger.log_data(data)

            # Save to historical storage for AI learning
            if self.active_profile and self.historical_data_manager:
                try:
                    profile_name = self.active_profile.get('name')
                    profile_id = self.active_profile.get('profile_id')
                    if profile_name and profile_id:
                        # Flatten data for storage
                        storage_data = self._flatten_data_for_storage(data)
                        self.historical_data_manager.append_obd_data(
                            profile_name, profile_id, storage_data
                        )

                        # Process through new feature modules
                        self._process_new_features(profile_id, profile_name, storage_data)

                except Exception as e:
                    logger.error(f"Error saving to historical storage: {e}")

    def _flatten_data_for_storage(self, data: dict) -> dict:
        """Flatten nested data structure for storage"""
        flattened = {}

        # Copy top-level values
        for key, value in data.items():
            if not isinstance(value, dict):
                flattened[key] = value

        # Flatten OBD data
        if 'obd' in data and isinstance(data['obd'], dict):
            for category, signals in data['obd'].items():
                if isinstance(signals, dict):
                    for signal_name, signal_data in signals.items():
                        if isinstance(signal_data, dict) and 'value' in signal_data:
                            flattened[signal_name] = signal_data['value']
                        else:
                            flattened[f'{category}_{signal_name}'] = signal_data

        # Add metadata
        if 'metadata' in data:
            for key, value in data['metadata'].items():
                flattened[f'meta_{key}'] = value

        # Add timestamp if not present
        if 'timestamp' not in flattened:
            flattened['timestamp'] = datetime.now().isoformat()

        return flattened

    def _process_new_features(self, profile_id: int, profile_name: str, data: dict):
        """Process data through new feature modules"""
        try:
            # Keep reference to previous data for driving score calculations
            if not hasattr(self, '_previous_data'):
                self._previous_data = {}

            previous = self._previous_data.get(profile_id)

            # 1. Trip Analytics - Track trips with GPS
            if self.trip_analytics:
                try:
                    trip_event = self.trip_analytics.process_data_point(
                        profile_id, profile_name, data
                    )
                    if trip_event:
                        logger.debug(f"Trip event: {trip_event.get('event')}")
                except Exception as e:
                    logger.error(f"Trip analytics error: {e}")

            # 2. Driving Score - Analyze behavior
            if self.driving_score:
                try:
                    score_update = self.driving_score.process_data_point(
                        profile_id, profile_name, data, previous
                    )
                    if score_update:
                        current_score = score_update.get('driving_score')
                        logger.debug(f"Driving score: {current_score}")
                except Exception as e:
                    logger.error(f"Driving score error: {e}")

            # 3. Custom Alerts - Check thresholds
            if self.custom_alerts:
                try:
                    alerts = self.custom_alerts.process_data(profile_id, profile_name, data)
                    if alerts:
                        logger.info(f"Custom alerts triggered: {len(alerts)}")
                except Exception as e:
                    logger.error(f"Custom alerts error: {e}")

            # 4. Geofencing - Check GPS location
            if self.geofencing and 'gps' in data:
                try:
                    gps = data.get('gps', {})
                    lat = gps.get('latitude')
                    lon = gps.get('longitude')
                    if lat and lon:
                        geo_events = self.geofencing.process_gps_data(
                            profile_id, profile_name, lat, lon
                        )
                        if geo_events:
                            logger.info(f"Geofence events: {len(geo_events)}")
                except Exception as e:
                    logger.error(f"Geofencing error: {e}")

            # 5. AI Alerts - Check for AI-detected issues
            if self.ai_alerts and self.enhanced_ai:
                try:
                    # Get AI prediction
                    prediction = self.enhanced_ai.predict_health(profile_name, profile_id, data)
                    if prediction:
                        ai_alerts = self.ai_alerts.process_ai_prediction(
                            profile_id, profile_name, prediction, data
                        )
                        if ai_alerts:
                            logger.info(f"AI alerts triggered: {len(ai_alerts)}")
                except Exception as e:
                    logger.error(f"AI alerts error: {e}")

            # 6. Enhanced Prediction Engine - LSTM, ESP32, Feedback
            if self.enhanced_engine:
                try:
                    # Feed live data to enhanced engine for LSTM predictions
                    enhanced_prediction = self.enhanced_engine.process_live_data(
                        profile_id=profile_id,
                        profile_name=profile_name,
                        obd_data=data
                    )
                    if enhanced_prediction and enhanced_prediction.get('lstm_prediction'):
                        lstm_pred = enhanced_prediction['lstm_prediction']
                        failure_prob = lstm_pred.get('failure_probability', 0)
                        
                        if failure_prob > 0.7:
                            logger.warning(
                                f"LSTM High failure probability: {failure_prob:.1%} "
                                f"Type: {lstm_pred.get('failure_type')} "
                                f"Days: {lstm_pred.get('days_to_failure')}"
                            )
                            
                            # Send alert notification for critical LSTM predictions
                            if self.alert_notification_manager:
                                try:
                                    from alert_notifications import NotificationPriority
                                    
                                    # Determine priority based on probability
                                    if failure_prob >= 0.9:
                                        priority = NotificationPriority.CRITICAL
                                        channels = ['push', 'email', 'sms']
                                    elif failure_prob >= 0.8:
                                        priority = NotificationPriority.HIGH
                                        channels = ['push', 'email']
                                    else:
                                        priority = NotificationPriority.WARNING
                                        channels = ['push']
                                    
                                    self.alert_notification_manager.send_notification(
                                        title=f"⚠️ AI Failure Prediction: {profile_name}",
                                        message=(
                                            f"High failure probability detected: {failure_prob:.1%}\n"
                                            f"Failure Type: {lstm_pred.get('failure_type', 'Unknown')}\n"
                                            f"Estimated Days to Failure: {lstm_pred.get('days_to_failure', 'Unknown')}\n"
                                            f"Profile: {profile_name} (ID: {profile_id})"
                                        ),
                                        priority=priority,
                                        channels=channels,
                                        metadata={
                                            'profile_id': profile_id,
                                            'profile_name': profile_name,
                                            'prediction_type': 'lstm',
                                            'failure_probability': failure_prob,
                                            'failure_type': lstm_pred.get('failure_type'),
                                            'days_to_failure': lstm_pred.get('days_to_failure'),
                                            'event_type': 'ai_prediction'
                                        }
                                    )
                                    logger.info(f"Sent AI prediction alert for {profile_name}: {failure_prob:.1%}")
                                except Exception as e:
                                    logger.error(f"Error sending AI prediction alert: {e}")

                    # 7. Process DTCs for automatic feedback confirmation
                    dtc_codes = data.get('dtc_codes', [])
                    if dtc_codes and profile_name:
                        dtc_result = self.enhanced_engine.process_dtc_codes(
                            vehicle_id=profile_name,
                            dtc_codes=dtc_codes
                        )
                        if dtc_result.get('confirmations'):
                            logger.info(f"DTCs confirmed {len(dtc_result['confirmations'])} predictions")
                            # Track accuracy for confirmed predictions
                            if self.accuracy_tracker:
                                for conf in dtc_result.get('confirmations'):
                                    self.accuracy_tracker.confirm_prediction(
                                        prediction_id=conf.get('prediction_id', ''),
                                        actual_outcome='failed',
                                        was_correct=True,
                                        notes=f"Confirmed by DTC: {conf.get('dtc_code')}"
                                    )
                        if dtc_result.get('new_alerts'):
                            for alert in dtc_result['new_alerts']:
                                logger.warning(f"DTC Alert: {alert['message']}")
                except Exception as e:
                    logger.error(f"Enhanced prediction engine error: {e}")

            # Store current data as previous for next iteration
            self._previous_data[profile_id] = data

        except Exception as e:
            logger.error(f"Error processing new features: {e}")

    def _get_active_profile(self):
        """Get the currently active vehicle profile"""
        return self.active_profile
    
    def _set_active_profile(self, profile):
        """
        Set the active vehicle profile.
        Also updates the connectivity manager and starts server polling.
        """
        self.active_profile = profile

        # Save profile info to historical storage
        if profile and self.historical_data_manager:
            try:
                self.historical_data_manager.save_profile_info(profile)
            except Exception as e:
                logger.error(f"Error saving profile info to historical storage: {e}")

        # Update connectivity manager with profile
        if self.connectivity and profile:
            self.connectivity.set_vehicle_profile(profile)

        # Start server polling for this profile (if mobile bridge available)
        if self.mobile_bridge and profile:
            profile_id = profile.get('profile_id')
            if profile_id:
                # Stop any existing polling first
                self.mobile_bridge.stop_server_polling()
                # Start polling for this profile
                self.mobile_bridge.set_active_profile(profile.get('name'), profile_id)
                self.mobile_bridge.start_server_polling(profile_id, interval_ms=1000)
                logger.info(f"Started server polling for profile: {profile.get('name')} (ID: {profile_id})")
            else:
                # No profile_id - this might be a profile without server integration
                self.mobile_bridge.stop_server_polling()
                logger.info(f"Profile has no profile_id - server polling not started")
        elif self.mobile_bridge:
            # No profile selected - stop polling
            self.mobile_bridge.stop_server_polling()

        # Update connection tab
        if hasattr(self, 'connection_tab'):
            try:
                self.connection_tab._update_profile_status()
            except Exception:
                pass
    
    def _get_latest_snapshot(self):
        return self.latest_snapshot
    
    def _get_recent_history(self):
        return self.history_buffer[-50:] if self.history_buffer else []
    
    def closeEvent(self, event):
        """Handle window close"""
        # End logging session
        self.data_logger.end_session()
        
        # Disconnect WebSocket
        if hasattr(self, 'ws_client') and self.ws_client:
            try:
                self.ws_client.stop()
                logger.info("WebSocket client stopped")
            except Exception as e:
                logger.error(f"Error stopping WebSocket: {e}")

        # Stop Alert Notification Manager
        if hasattr(self, 'alert_notification_manager') and self.alert_notification_manager:
            try:
                self.alert_notification_manager.stop()
                logger.info("AlertNotificationManager stopped")
            except Exception as e:
                logger.error(f"Error stopping notification manager: {e}")
        
        # Stop Device Heartbeat Manager
        if hasattr(self, 'heartbeat_manager') and self.heartbeat_manager:
            try:
                self.heartbeat_manager.stop_monitoring()
                logger.info("Device Heartbeat Manager stopped")
            except Exception as e:
                logger.error(f"Error stopping heartbeat manager: {e}")
        
        # Disconnect
        try:
            self.connectivity.disconnect()
        except Exception:
            pass
        
        logger.info("Application closing")
        event.accept()


# =============================================================================
#   APPLICATION ENTRY POINT
# =============================================================================

def main():
    """Main application entry point"""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('predict_app.log', mode='a')
        ]
    )

    logger.info("=" * 50)
    logger.info(f"Starting Predict - Professional Car AI v{APP_VERSION}")
    logger.info("=" * 50)

    # CRITICAL: Create QApplication BEFORE importing any widget modules
    # PySide6 requires QApplication to exist before any QWidget subclasses are instantiated
    global app
    app = QApplication(sys.argv)
    logger.info("QApplication created")

    # Create and show splash screen immediately
    splash = PredictSplashScreen()
    splash.show()
    splash.set_progress(5, "Initializing application...")
    QApplication.processEvents()

    # Configure application
    app.setApplicationName("Predict")
    app.setApplicationVersion(APP_VERSION)
    splash.set_progress(10, "Applying theme...")

    # Apply professional theme
    ProfessionalTheme.apply_theme(app)
    splash.set_progress(15, "Loading core modules...")

    # Now import all Qt-dependent modules
    logger.info("Importing Qt-dependent modules...")
    import_modules()
    splash.set_progress(40, "Loading additional modules...")
    import_additional_modules()
    logger.info("All modules imported successfully")
    splash.set_progress(60, "Initializing AI assistant...")

    # Initialize LLM assistant (lazy loading - will load on first use)
    logger.info("Initializing LLM assistant (lazy loading)...")
    llm_assistant = get_llm_assistant()
    # Model will load when first used in chat tab to improve startup performance
    logger.info("LLM assistant initialized, creating main window...")
    splash.set_progress(75, "Creating main window...")

    # Now create main window
    try:
        window = MainWindow()
        logger.info("Main window created successfully")
        splash.set_progress(95, "Finalizing...")
        window.show()
        splash.set_progress(100, "Ready!")
        # Close splash screen after main window is visible
        splash.finish(window)
    except Exception as e:
        splash.close()
        logger.critical(f"Failed to create main window: {e}")
        QMessageBox.critical(None, "Startup Error", f"Failed to start application:\n{e}")
        sys.exit(1)

    # Run application
    exit_code = app.exec()
    logger.info(f"Application exited with code: {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()