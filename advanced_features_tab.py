"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Advanced Features Tab

Advanced Features Tab - Database Management, System Info, and Debug Tools
Created: 2025-12-16

Provides advanced utilities for:
- Database management (backup, restore, vacuum, optimize)
- System information and performance monitoring
- Debug tools (logs, cache, connections, test reports)
- Data export/import functionality
"""

import os
import shutil
import sqlite3
import json
import psutil
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QTabWidget, QTextEdit, QProgressBar, QFileDialog,
    QMessageBox, QSpinBox, QMainWindow
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
import logging

logger = logging.getLogger(__name__)


class AdvancedFeaturesTab(QWidget):
    """Advanced features tab with database management, system info, and debug tools"""

    def __init__(self, parent=None, parent_window=None):
        # Handle case where MainWindow is passed as parent
        # Tabs should not have MainWindow as Qt parent - they're managed by QTabWidget
        if parent is not None and isinstance(parent, QMainWindow):
            # MainWindow passed as parent - use it as parent_window instead
            logger.info(f"AdvancedFeaturesTab.__init__: MainWindow passed as parent, converting to parent_window")
            parent_window = parent
            parent = None

        logger.info(f"AdvancedFeaturesTab.__init__: parent={parent}, parent_window={type(parent_window).__name__ if parent_window else None}")
        super().__init__(parent)
        self.parent_window = parent_window if parent_window is not None else parent
        self.update_timer = None
        self._setup_ui()
        self._start_monitoring()

    def _setup_ui(self):
        """Build the advanced features UI"""
        logger.info("AdvancedFeaturesTab: Creating layout")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header
        header = QLabel("🔧 Advanced Features & System Tools")
        header.setFont(QFont("Arial", 18, QFont.Bold))
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        # Subtitle
        subtitle = QLabel(
            "Database management, system monitoring, debug tools, and data export/import utilities."
        )
        subtitle.setWordWrap(True)
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #8B949E; font-size: 13px; margin-bottom: 10px;")
        layout.addWidget(subtitle)

        # Tab widget for sub-sections
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 2px solid #30363D;
                border-radius: 5px;
                background-color: #0D1117;
            }
            QTabBar::tab {
                background-color: #161B22;
                color: #C9D1D9;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
            QTabBar::tab:selected {
                background-color: #30363D;
                color: #0DCAF0;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background-color: #21262D;
            }
        """)

        # Add sub-tabs
        self.tab_widget.addTab(self._create_database_tab(), "💾 Database")
        self.tab_widget.addTab(self._create_system_info_tab(), "📊 System Info")
        self.tab_widget.addTab(self._create_debug_tab(), "🐛 Debug Tools")
        self.tab_widget.addTab(self._create_export_import_tab(), "📤 Export/Import")

        layout.addWidget(self.tab_widget)
        logger.info("AdvancedFeaturesTab: UI initialization complete")

    def _create_database_tab(self) -> QWidget:
        """Create database management sub-tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Database Management Group
        db_group = QGroupBox("💾 Database Management")
        db_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #0DCAF0;
                border: 2px solid #0DCAF0;
                border-radius: 5px;
                padding: 15px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        db_layout = QVBoxLayout(db_group)

        # Database info
        self.db_info_label = QLabel("Loading database information...")
        self.db_info_label.setStyleSheet("background-color: #161B22; padding: 10px; border-radius: 5px; font-size: 12px;")
        self.db_info_label.setWordWrap(True)
        db_layout.addWidget(self.db_info_label)

        # Action buttons
        btn_layout = QHBoxLayout()

        self.backup_db_btn = QPushButton("📦 Backup Databases")
        self.backup_db_btn.setStyleSheet(self._get_button_style('success'))
        self.backup_db_btn.clicked.connect(self._backup_databases)
        btn_layout.addWidget(self.backup_db_btn)

        self.restore_db_btn = QPushButton("♻️ Restore Backup")
        self.restore_db_btn.setStyleSheet(self._get_button_style('warning'))
        self.restore_db_btn.clicked.connect(self._restore_databases)
        btn_layout.addWidget(self.restore_db_btn)

        self.vacuum_db_btn = QPushButton("🧹 Vacuum & Optimize")
        self.vacuum_db_btn.setStyleSheet(self._get_button_style('info'))
        self.vacuum_db_btn.clicked.connect(self._vacuum_databases)
        btn_layout.addWidget(self.vacuum_db_btn)

        db_layout.addLayout(btn_layout)

        # Clear old data section
        clear_group = QGroupBox("🗑️ Clear Old Data")
        clear_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                color: #FF6B6B;
                border: 2px solid #FF6B6B;
                border-radius: 5px;
                padding: 15px;
                margin-top: 10px;
            }
        """)
        clear_layout = QVBoxLayout(clear_group)

        clear_help = QLabel("⚠️ Remove data older than specified days to free up space. This action cannot be undone!")
        clear_help.setWordWrap(True)
        clear_help.setStyleSheet("color: #FF6B6B; font-size: 11px; font-weight: normal;")
        clear_layout.addWidget(clear_help)

        clear_btn_layout = QHBoxLayout()
        clear_btn_layout.addWidget(QLabel("Clear data older than:"))
        self.clear_days_spin = QSpinBox()
        self.clear_days_spin.setMinimum(30)
        self.clear_days_spin.setMaximum(365)
        self.clear_days_spin.setValue(90)
        self.clear_days_spin.setSuffix(" days")
        clear_btn_layout.addWidget(self.clear_days_spin)

        self.clear_old_data_btn = QPushButton("🗑️ Clear Old Data")
        self.clear_old_data_btn.setStyleSheet(self._get_button_style('danger'))
        self.clear_old_data_btn.clicked.connect(self._clear_old_data)
        clear_btn_layout.addWidget(self.clear_old_data_btn)
        clear_btn_layout.addStretch()

        clear_layout.addLayout(clear_btn_layout)
        db_layout.addWidget(clear_group)

        layout.addWidget(db_group)
        layout.addStretch()

        # Update database info
        self._update_database_info()

        return widget

    def _create_system_info_tab(self) -> QWidget:
        """Create system information sub-tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # System Info Group
        sys_group = QGroupBox("📊 System Performance Monitor")
        sys_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #4CAF50;
                border: 2px solid #4CAF50;
                border-radius: 5px;
                padding: 15px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        sys_layout = QVBoxLayout(sys_group)

        # CPU Usage
        cpu_layout = QHBoxLayout()
        cpu_label = QLabel("🖥️ CPU Usage:")
        cpu_label.setMinimumWidth(120)
        cpu_layout.addWidget(cpu_label)
        self.cpu_progress = QProgressBar()
        self.cpu_progress.setStyleSheet(self._get_progress_style())
        cpu_layout.addWidget(self.cpu_progress, 1)
        self.cpu_value_label = QLabel("0%")
        self.cpu_value_label.setMinimumWidth(60)
        self.cpu_value_label.setStyleSheet("font-weight: bold; color: #0DCAF0;")
        cpu_layout.addWidget(self.cpu_value_label)
        sys_layout.addLayout(cpu_layout)

        # Memory Usage
        mem_layout = QHBoxLayout()
        mem_label = QLabel("💾 Memory Usage:")
        mem_label.setMinimumWidth(120)
        mem_layout.addWidget(mem_label)
        self.mem_progress = QProgressBar()
        self.mem_progress.setStyleSheet(self._get_progress_style())
        mem_layout.addWidget(self.mem_progress, 1)
        self.mem_value_label = QLabel("0%")
        self.mem_value_label.setMinimumWidth(60)
        self.mem_value_label.setStyleSheet("font-weight: bold; color: #0DCAF0;")
        mem_layout.addWidget(self.mem_value_label)
        sys_layout.addLayout(mem_layout)

        # Disk Usage
        disk_layout = QHBoxLayout()
        disk_label = QLabel("💿 Disk Usage:")
        disk_label.setMinimumWidth(120)
        disk_layout.addWidget(disk_label)
        self.disk_progress = QProgressBar()
        self.disk_progress.setStyleSheet(self._get_progress_style())
        disk_layout.addWidget(self.disk_progress, 1)
        self.disk_value_label = QLabel("0%")
        self.disk_value_label.setMinimumWidth(60)
        self.disk_value_label.setStyleSheet("font-weight: bold; color: #0DCAF0;")
        disk_layout.addWidget(self.disk_value_label)
        sys_layout.addLayout(disk_layout)

        # Detailed system info
        self.sys_details = QTextEdit()
        self.sys_details.setReadOnly(True)
        self.sys_details.setMaximumHeight(200)
        self.sys_details.setStyleSheet("""
            QTextEdit {
                background-color: #161B22;
                color: #C9D1D9;
                border: 1px solid #30363D;
                border-radius: 5px;
                padding: 10px;
                font-family: 'Courier New';
                font-size: 11px;
            }
        """)
        sys_layout.addWidget(self.sys_details)

        layout.addWidget(sys_group)
        layout.addStretch()

        return widget

    def _create_debug_tab(self) -> QWidget:
        """Create debug tools sub-tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Debug Tools Group
        debug_group = QGroupBox("🐛 Debug & Diagnostics")
        debug_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #FFC107;
                border: 2px solid #FFC107;
                border-radius: 5px;
                padding: 15px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        debug_layout = QVBoxLayout(debug_group)

        # Action buttons
        btn_layout = QHBoxLayout()

        self.view_logs_btn = QPushButton("📄 View Logs")
        self.view_logs_btn.setStyleSheet(self._get_button_style('info'))
        self.view_logs_btn.clicked.connect(self._view_logs)
        btn_layout.addWidget(self.view_logs_btn)

        self.clear_cache_btn = QPushButton("🧹 Clear Cache")
        self.clear_cache_btn.setStyleSheet(self._get_button_style('warning'))
        self.clear_cache_btn.clicked.connect(self._clear_cache)
        btn_layout.addWidget(self.clear_cache_btn)

        self.test_connection_btn = QPushButton("🔌 Test OBD Connection")
        self.test_connection_btn.setStyleSheet(self._get_button_style('success'))
        self.test_connection_btn.clicked.connect(self._test_connection)
        btn_layout.addWidget(self.test_connection_btn)

        self.debug_report_btn = QPushButton("📋 Generate Debug Report")
        self.debug_report_btn.setStyleSheet(self._get_button_style('danger'))
        self.debug_report_btn.clicked.connect(self._generate_debug_report)
        btn_layout.addWidget(self.debug_report_btn)

        debug_layout.addLayout(btn_layout)

        # Debug output area
        debug_output_label = QLabel("Debug Output:")
        debug_output_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        debug_layout.addWidget(debug_output_label)

        self.debug_output = QTextEdit()
        self.debug_output.setReadOnly(True)
        self.debug_output.setStyleSheet("""
            QTextEdit {
                background-color: #0D1117;
                color: #58A6FF;
                border: 1px solid #30363D;
                border-radius: 5px;
                padding: 10px;
                font-family: 'Courier New';
                font-size: 11px;
            }
        """)
        self.debug_output.setPlaceholderText("Debug information will appear here...")
        debug_layout.addWidget(self.debug_output)

        layout.addWidget(debug_group)

        return widget

    def _create_export_import_tab(self) -> QWidget:
        """Create export/import sub-tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Export Group
        export_group = QGroupBox("📤 Export Data")
        export_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #4CAF50;
                border: 2px solid #4CAF50;
                border-radius: 5px;
                padding: 15px;
                margin-top: 10px;
            }
        """)
        export_layout = QVBoxLayout(export_group)

        export_help = QLabel("💡 Export vehicle profiles, service history, and training data to JSON format.")
        export_help.setWordWrap(True)
        export_help.setStyleSheet("background-color: #161B22; padding: 8px; border-radius: 5px; font-size: 11px; font-weight: normal;")
        export_layout.addWidget(export_help)

        export_btn_layout = QHBoxLayout()
        self.export_profiles_btn = QPushButton("📤 Export Profiles")
        self.export_profiles_btn.setStyleSheet(self._get_button_style('success'))
        self.export_profiles_btn.clicked.connect(self._export_profiles)
        export_btn_layout.addWidget(self.export_profiles_btn)

        self.export_service_btn = QPushButton("📤 Export Service History")
        self.export_service_btn.setStyleSheet(self._get_button_style('success'))
        self.export_service_btn.clicked.connect(self._export_service_history)
        export_btn_layout.addWidget(self.export_service_btn)

        self.export_all_btn = QPushButton("📤 Export All Data")
        self.export_all_btn.setStyleSheet(self._get_button_style('info'))
        self.export_all_btn.clicked.connect(self._export_all_data)
        export_btn_layout.addWidget(self.export_all_btn)

        export_layout.addLayout(export_btn_layout)
        layout.addWidget(export_group)

        # Import Group
        import_group = QGroupBox("📥 Import Data")
        import_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #FFC107;
                border: 2px solid #FFC107;
                border-radius: 5px;
                padding: 15px;
                margin-top: 10px;
            }
        """)
        import_layout = QVBoxLayout(import_group)

        import_help = QLabel("⚠️ Import data from JSON backup files. This will merge with existing data.")
        import_help.setWordWrap(True)
        import_help.setStyleSheet("background-color: #161B22; padding: 8px; border-radius: 5px; font-size: 11px; font-weight: normal;")
        import_layout.addWidget(import_help)

        import_btn_layout = QHBoxLayout()
        self.import_data_btn = QPushButton("📥 Import Data File")
        self.import_data_btn.setStyleSheet(self._get_button_style('warning'))
        self.import_data_btn.clicked.connect(self._import_data)
        import_btn_layout.addWidget(self.import_data_btn)
        import_btn_layout.addStretch()

        import_layout.addLayout(import_btn_layout)
        layout.addWidget(import_group)

        layout.addStretch()

        return widget

    def _start_monitoring(self):
        """Start system monitoring timer"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_system_info)
        self.update_timer.start(2000)  # Update every 2 seconds
        self._update_system_info()  # Initial update

    def _update_system_info(self):
        """Update system performance metrics"""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=0.1)
            self.cpu_progress.setValue(int(cpu_percent))
            self.cpu_value_label.setText(f"{cpu_percent:.1f}%")

            # Memory
            mem = psutil.virtual_memory()
            self.mem_progress.setValue(int(mem.percent))
            self.mem_value_label.setText(f"{mem.percent:.1f}%")

            # Disk
            disk = psutil.disk_usage('c:' if os.name == 'nt' else '/')
            self.disk_progress.setValue(int(disk.percent))
            self.disk_value_label.setText(f"{disk.percent:.1f}%")

            # Detailed info
            details = f"""System Information (Updated: {datetime.now().strftime('%H:%M:%S')})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPU Cores: {psutil.cpu_count(logical=False)} physical, {psutil.cpu_count(logical=True)} logical
CPU Frequency: {psutil.cpu_freq().current:.0f} MHz (Max: {psutil.cpu_freq().max:.0f} MHz)

Memory: {mem.used / (1024**3):.2f} GB / {mem.total / (1024**3):.2f} GB
Available: {mem.available / (1024**3):.2f} GB

Disk: {disk.used / (1024**3):.2f} GB / {disk.total / (1024**3):.2f} GB
Free: {disk.free / (1024**3):.2f} GB
"""
            self.sys_details.setPlainText(details)

        except Exception as e:
            logger.error(f"Error updating system info: {e}")

    def _update_database_info(self):
        """Update database information display"""
        try:
            db_files = [
                "./data/vehicle_profiles.db",
                "./data/fleet_learning.db",
                "./data/training_cache.db"
            ]

            info_lines = []
            total_size = 0

            for db_file in db_files:
                if os.path.exists(db_file):
                    size = os.path.getsize(db_file) / (1024 * 1024)  # MB
                    total_size += size

                    # Get record counts
                    conn = sqlite3.connect(db_file)
                    c = conn.cursor()
                    tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()

                    table_info = []
                    for table in tables:
                        count = c.execute(f"SELECT COUNT(*) FROM {table[0]}").fetchone()[0]
                        if count > 0:
                            table_info.append(f"{table[0]}: {count} records")

                    conn.close()

                    info_lines.append(f"📁 {os.path.basename(db_file)}: {size:.2f} MB")
                    if table_info:
                        info_lines.append(f"   {', '.join(table_info)}")

            info_text = f"💡 <b>Database Summary:</b><br>"
            info_text += f"Total Size: {total_size:.2f} MB<br><br>"
            info_text += "<br>".join(info_lines)

            self.db_info_label.setText(info_text)

        except Exception as e:
            self.db_info_label.setText(f"⚠️ Error loading database info: {e}")

    def _backup_databases(self):
        """Backup all databases"""
        try:
            backup_dir = QFileDialog.getExistingDirectory(self, "Select Backup Directory")
            if not backup_dir:
                return

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_folder = os.path.join(backup_dir, f"predict_backup_{timestamp}")
            os.makedirs(backup_folder, exist_ok=True)

            db_files = [
                "./data/vehicle_profiles.db",
                "./data/fleet_learning.db",
                "./data/training_cache.db"
            ]

            backed_up = 0
            for db_file in db_files:
                if os.path.exists(db_file):
                    dest = os.path.join(backup_folder, os.path.basename(db_file))
                    shutil.copy2(db_file, dest)
                    backed_up += 1

            QMessageBox.information(
                self, "Backup Complete",
                f"Successfully backed up {backed_up} database(s) to:\n{backup_folder}"
            )
            self._update_database_info()

        except Exception as e:
            QMessageBox.critical(self, "Backup Error", f"Failed to backup databases:\n{e}")

    def _restore_databases(self):
        """Restore databases from backup"""
        reply = QMessageBox.question(
            self, "Restore Databases",
            "⚠️ This will replace current databases with backup files.\n\n"
            "Current data will be lost! Continue?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.No:
            return

        try:
            backup_dir = QFileDialog.getExistingDirectory(self, "Select Backup Folder")
            if not backup_dir:
                return

            restored = 0
            for filename in os.listdir(backup_dir):
                if filename.endswith('.db'):
                    src = os.path.join(backup_dir, filename)
                    dest = os.path.join("./data", filename)
                    shutil.copy2(src, dest)
                    restored += 1

            QMessageBox.information(
                self, "Restore Complete",
                f"Successfully restored {restored} database(s).\n\n"
                "Please restart the application for changes to take effect."
            )
            self._update_database_info()

        except Exception as e:
            QMessageBox.critical(self, "Restore Error", f"Failed to restore databases:\n{e}")

    def _vacuum_databases(self):
        """Vacuum and optimize all databases"""
        try:
            db_files = [
                "./data/vehicle_profiles.db",
                "./data/fleet_learning.db",
                "./data/training_cache.db"
            ]

            optimized = 0
            for db_file in db_files:
                if os.path.exists(db_file):
                    conn = sqlite3.connect(db_file)
                    conn.execute("VACUUM")
                    conn.execute("ANALYZE")
                    conn.close()
                    optimized += 1

            QMessageBox.information(
                self, "Optimization Complete",
                f"Successfully optimized {optimized} database(s).\n\n"
                "Database files have been compacted and analyzed."
            )
            self._update_database_info()

        except Exception as e:
            QMessageBox.critical(self, "Optimization Error", f"Failed to optimize databases:\n{e}")

    def _clear_old_data(self):
        """Clear data older than specified days"""
        days = self.clear_days_spin.value()

        reply = QMessageBox.question(
            self, "Clear Old Data",
            f"⚠️ This will permanently delete all data older than {days} days.\n\n"
            "This action cannot be undone! Continue?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.No:
            return

        try:
            cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)

            # Clear old snapshots from vehicle_profiles.db
            conn = sqlite3.connect("./data/vehicle_profiles.db")
            c = conn.cursor()
            c.execute("DELETE FROM snapshots WHERE timestamp < ?", (cutoff_date,))
            deleted_snapshots = c.rowcount
            conn.commit()
            conn.close()

            QMessageBox.information(
                self, "Clear Complete",
                f"Deleted {deleted_snapshots} snapshot(s) older than {days} days."
            )
            self._update_database_info()

        except Exception as e:
            QMessageBox.critical(self, "Clear Error", f"Failed to clear old data:\n{e}")

    def _view_logs(self):
        """View application logs"""
        log_file = "./data/predict.log"
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    logs = f.read()
                self.debug_output.setPlainText(logs)
            except Exception as e:
                self.debug_output.setPlainText(f"Error reading log file: {e}")
        else:
            self.debug_output.setPlainText("No log file found.")

    def _clear_cache(self):
        """Clear application cache"""
        try:
            cache_files = [
                "./data/training_cache.db",
                "./data/.temp"
            ]

            cleared = 0
            for cache_file in cache_files:
                if os.path.exists(cache_file):
                    if os.path.isfile(cache_file):
                        os.remove(cache_file)
                    elif os.path.isdir(cache_file):
                        shutil.rmtree(cache_file)
                    cleared += 1

            self.debug_output.append(f"\n[{datetime.now().strftime('%H:%M:%S')}] Cache cleared: {cleared} item(s) removed")
            QMessageBox.information(self, "Cache Cleared", "Application cache has been cleared successfully.")

        except Exception as e:
            self.debug_output.append(f"\n[{datetime.now().strftime('%H:%M:%S')}] Error clearing cache: {e}")

    def _test_connection(self):
        """Test OBD connection"""
        self.debug_output.append(f"\n[{datetime.now().strftime('%H:%M:%S')}] Testing OBD connection...")
        self.debug_output.append("This feature requires connectivity_module integration.")

    def _generate_debug_report(self):
        """Generate comprehensive debug report"""
        try:
            report = f"""PREDICT OBD DEBUG REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*60}

SYSTEM INFORMATION:
- CPU: {psutil.cpu_percent()}% ({psutil.cpu_count()} cores)
- Memory: {psutil.virtual_memory().percent}% ({psutil.virtual_memory().used / (1024**3):.2f} GB used)
- Disk: {psutil.disk_usage('c:' if os.name == 'nt' else '/').percent}%

DATABASE STATUS:
"""
            db_files = ["./data/vehicle_profiles.db", "./data/fleet_learning.db", "./data/training_cache.db"]
            for db_file in db_files:
                if os.path.exists(db_file):
                    size = os.path.getsize(db_file) / (1024 * 1024)
                    report += f"- {os.path.basename(db_file)}: {size:.2f} MB\n"

            report += f"\n{'='*60}\nEND OF REPORT"

            self.debug_output.setPlainText(report)

            # Offer to save
            reply = QMessageBox.question(
                self, "Save Debug Report",
                "Debug report generated. Save to file?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                filename, _ = QFileDialog.getSaveFileName(
                    self, "Save Debug Report",
                    f"debug_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    "Text Files (*.txt)"
                )
                if filename:
                    with open(filename, 'w') as f:
                        f.write(report)
                    QMessageBox.information(self, "Saved", f"Debug report saved to:\n{filename}")

        except Exception as e:
            self.debug_output.append(f"\n[ERROR] Failed to generate debug report: {e}")

    def _export_profiles(self):
        """Export vehicle profiles to JSON"""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Export Vehicle Profiles",
                f"profiles_export_{datetime.now().strftime('%Y%m%d')}.json",
                "JSON Files (*.json)"
            )
            if not filename:
                return

            conn = sqlite3.connect("./data/vehicle_profiles.db")
            c = conn.cursor()
            profiles = c.execute("SELECT * FROM profiles").fetchall()

            # Convert to JSON-friendly format
            export_data = {
                "export_date": datetime.now().isoformat(),
                "export_type": "vehicle_profiles",
                "profiles": [dict(zip([col[0] for col in c.description], row)) for row in profiles]
            }
            conn.close()

            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2)

            QMessageBox.information(self, "Export Complete", f"Exported {len(profiles)} profile(s) to:\n{filename}")

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export profiles:\n{e}")

    def _export_service_history(self):
        """Export service history to JSON"""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Export Service History",
                f"service_history_export_{datetime.now().strftime('%Y%m%d')}.json",
                "JSON Files (*.json)"
            )
            if not filename:
                return

            conn = sqlite3.connect("./data/vehicle_profiles.db")
            c = conn.cursor()
            services = c.execute("SELECT * FROM service_records").fetchall()

            export_data = {
                "export_date": datetime.now().isoformat(),
                "export_type": "service_history",
                "records": [dict(zip([col[0] for col in c.description], row)) for row in services]
            }
            conn.close()

            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2)

            QMessageBox.information(self, "Export Complete", f"Exported {len(services)} record(s) to:\n{filename}")

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export service history:\n{e}")

    def _export_all_data(self):
        """Export all data to JSON"""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Export All Data",
                f"predict_full_export_{datetime.now().strftime('%Y%m%d')}.json",
                "JSON Files (*.json)"
            )
            if not filename:
                return

            # Collect all data
            export_data = {
                "export_date": datetime.now().isoformat(),
                "export_type": "full_backup",
                "data": {}
            }

            # Export profiles
            conn = sqlite3.connect("./data/vehicle_profiles.db")
            c = conn.cursor()
            tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()

            for table in tables:
                table_name = table[0]
                rows = c.execute(f"SELECT * FROM {table_name}").fetchall()
                export_data["data"][table_name] = [
                    dict(zip([col[0] for col in c.description], row)) for row in rows
                ]

            conn.close()

            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2)

            QMessageBox.information(self, "Export Complete", f"Full data export saved to:\n{filename}")

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export data:\n{e}")

    def _import_data(self):
        """Import data from JSON file"""
        reply = QMessageBox.question(
            self, "Import Data",
            "⚠️ This will merge imported data with existing data.\n\n"
            "Duplicate entries may be created. Continue?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.No:
            return

        try:
            filename, _ = QFileDialog.getOpenFileName(
                self, "Import Data File",
                "",
                "JSON Files (*.json)"
            )
            if not filename:
                return

            with open(filename, 'r') as f:
                import_data = json.load(f)

            QMessageBox.information(
                self, "Import",
                "Import functionality is under development.\n\n"
                f"File loaded: {filename}\n"
                f"Export type: {import_data.get('export_type', 'unknown')}"
            )

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import data:\n{e}")

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

    def _get_progress_style(self) -> str:
        """Get consistent progress bar styling"""
        return """
            QProgressBar {
                border: 1px solid #30363D;
                border-radius: 5px;
                background-color: #161B22;
                text-align: center;
                color: #C9D1D9;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #0DCAF0;
                border-radius: 4px;
            }
        """

    def closeEvent(self, event):
        """Clean up when tab is closed"""
        if self.update_timer:
            self.update_timer.stop()
        super().closeEvent(event)
