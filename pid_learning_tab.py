"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Pid Learning Tab
"""

import os
import json
import csv
import traceback
import time
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPlainTextEdit,
                             QPushButton, QHBoxLayout, QGroupBox, QFileDialog,
                             QMessageBox, QProgressBar, QTableWidget, QTableWidgetItem,
                             QHeaderView, QTabWidget, QLineEdit, QTextEdit,
                             QComboBox, QCheckBox, QFormLayout, QDialog, QDialogButtonBox,
                             QScrollArea, QFrame)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, QThread, Signal

# Import centralized configuration
try:
    from config import get_config
    CONFIG = get_config()
except ImportError:
    CONFIG = None


# ================================
# PID LEARNING MANAGER - FIXED PATH
# ================================

class PIDLearningManager:
    """Manages learning and storage of custom OBD PIDs"""

    # Default save path - will use CONFIG if available
    @property
    def DEFAULT_PID_PATH(self):
        if CONFIG:
            return str(CONFIG.CONFIG_DIR / "pid_profiles")
        # Fallback for development
        return os.path.join(os.path.dirname(__file__), "learned_pids")

    def __init__(self, learned_pids_directory=None):
        # Use specified path or default
        if learned_pids_directory is None:
            learned_pids_directory = self.DEFAULT_PID_PATH
        
        self.learned_pids_directory = learned_pids_directory
        self.learned_pids = {}
        self.ensure_directory()
        self.load_learned_pids()
    
    def ensure_directory(self):
        """Create learned PIDs directory if it doesn't exist"""
        try:
            if not os.path.exists(self.learned_pids_directory):
                os.makedirs(self.learned_pids_directory)
                print(f"Created directory: {self.learned_pids_directory}")
        except Exception as e:
            print(f"Error creating directory {self.learned_pids_directory}: {e}")
            # Fallback to local directory
            self.learned_pids_directory = os.path.join(os.path.dirname(__file__), "learned_pids")
            try:
                if not os.path.exists(self.learned_pids_directory):
                    os.makedirs(self.learned_pids_directory)
            except:
                pass
    
    def load_learned_pids(self):
        """Load all learned PIDs from JSON files"""
        self.learned_pids = {}
        try:
            if not os.path.exists(self.learned_pids_directory):
                print(f"Directory {self.learned_pids_directory} does not exist")
                return
                
            for filename in os.listdir(self.learned_pids_directory):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.learned_pids_directory, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            pid_data = json.load(f)
                            pid_hex = pid_data.get('hex_code', '').upper()
                            if pid_hex:
                                self.learned_pids[pid_hex] = pid_data
                    except Exception as e:
                        print(f"Error loading PID file {filename}: {e}")
            print(f"Loaded {len(self.learned_pids)} learned PIDs from {self.learned_pids_directory}")
        except Exception as e:
            print(f"Error loading learned PIDs: {e}")
    
    def save_pid(self, pid_data):
        """Save a single PID to JSON file"""
        try:
            pid_hex = pid_data.get('hex_code', '').upper()
            if not pid_hex:
                return False, "Invalid PID hex code"
            
            self.ensure_directory()
            
            filename = f"pid_{pid_hex}.json"
            filepath = os.path.join(self.learned_pids_directory, filename)
            
            # Add metadata
            pid_data['saved_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
            pid_data['hex_code'] = pid_hex
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(pid_data, f, indent=2)
            
            self.learned_pids[pid_hex] = pid_data
            return True, f"PID {pid_hex} saved successfully to {filepath}"
        except Exception as e:
            return False, f"Error saving PID: {e}"
    
    def save_all_pids(self, pids_dict):
        """Save multiple PIDs at once"""
        saved_count = 0
        errors = []
        
        for pid_hex, pid_data in pids_dict.items():
            success, message = self.save_pid(pid_data)
            if success:
                saved_count += 1
            else:
                errors.append(message)
        
        return saved_count, errors
    
    def delete_pid(self, pid_hex):
        """Delete a learned PID"""
        try:
            pid_hex = pid_hex.upper()
            filename = f"pid_{pid_hex}.json"
            filepath = os.path.join(self.learned_pids_directory, filename)
            
            if os.path.exists(filepath):
                os.remove(filepath)
                self.learned_pids.pop(pid_hex, None)
                return True, f"PID {pid_hex} deleted successfully"
            else:
                return False, f"PID {pid_hex} not found"
        except Exception as e:
            return False, f"Error deleting PID: {e}"
    
    def get_all_pids(self):
        """Get all learned PIDs"""
        return self.learned_pids
    
    def get_pid(self, pid_hex):
        """Get a specific PID by hex code"""
        return self.learned_pids.get(pid_hex.upper())
    
    def import_from_csv(self, csv_filepath):
        """Import PIDs from CSV file"""
        try:
            imported_count = 0
            with open(csv_filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    pid_data = {
                        'hex_code': row.get('hex_code', '').strip().upper(),
                        'name': row.get('name', '').strip(),
                        'description': row.get('description', '').strip(),
                        'formula': row.get('formula', '').strip(),
                        'units': row.get('units', '').strip(),
                        'min_value': row.get('min_value', ''),
                        'max_value': row.get('max_value', ''),
                        'category': row.get('category', 'Custom'),
                        'vehicle_specific': str(row.get('vehicle_specific', 'No')).lower() == 'yes',
                        'validation_required': str(row.get('validation_required', 'Yes')).lower() == 'yes'
                    }
                    
                    if pid_data['hex_code']:
                        success, message = self.save_pid(pid_data)
                        if success:
                            imported_count += 1
            
            self.load_learned_pids()
            return True, f"Successfully imported {imported_count} PIDs from CSV"
        except Exception as e:
            return False, f"Error importing CSV: {e}"
    
    def export_to_csv(self, csv_filepath):
        """Export all PIDs to CSV file"""
        try:
            with open(csv_filepath, 'w', encoding='utf-8', newline='') as f:
                fieldnames = ['hex_code', 'name', 'description', 'formula', 'units', 
                            'min_value', 'max_value', 'category', 'vehicle_specific', 'validation_required']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for pid_data in self.learned_pids.values():
                    writer.writerow({
                        'hex_code': pid_data.get('hex_code', ''),
                        'name': pid_data.get('name', ''),
                        'description': pid_data.get('description', ''),
                        'formula': pid_data.get('formula', ''),
                        'units': pid_data.get('units', ''),
                        'min_value': pid_data.get('min_value', ''),
                        'max_value': pid_data.get('max_value', ''),
                        'category': pid_data.get('category', 'Custom'),
                        'vehicle_specific': 'Yes' if pid_data.get('vehicle_specific', False) else 'No',
                        'validation_required': 'Yes' if pid_data.get('validation_required', True) else 'No'
                    })
            
            return True, f"Successfully exported {len(self.learned_pids)} PIDs to CSV"
        except Exception as e:
            return False, f"Error exporting CSV: {e}"


# ================================
# PID EDIT DIALOG
# ================================

class PIDEditDialog(QDialog):
    """Dialog for editing PID parameters"""
    
    def __init__(self, pid_data=None, parent=None):
        super().__init__(parent)
        self.pid_data = pid_data or {}
        self.setWindowTitle("Edit PID" if pid_data else "Add New PID")
        self.setMinimumWidth(500)
        self._build_ui()
        
    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        
        self.hex_edit = QLineEdit(self.pid_data.get('hex_code', ''))
        self.hex_edit.setPlaceholderText("e.g., 0C or 2F")
        form.addRow("Hex Code:", self.hex_edit)
        
        self.name_edit = QLineEdit(self.pid_data.get('name', ''))
        self.name_edit.setPlaceholderText("e.g., Engine RPM")
        form.addRow("Name:", self.name_edit)
        
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlainText(self.pid_data.get('description', ''))
        self.desc_edit.setMaximumHeight(80)
        form.addRow("Description:", self.desc_edit)
        
        self.formula_edit = QLineEdit(self.pid_data.get('formula', ''))
        self.formula_edit.setPlaceholderText("e.g., ((A*256)+B)/4")
        form.addRow("Formula:", self.formula_edit)
        
        self.units_edit = QLineEdit(self.pid_data.get('units', ''))
        self.units_edit.setPlaceholderText("e.g., RPM, km/h, °C")
        form.addRow("Units:", self.units_edit)
        
        self.min_edit = QLineEdit(str(self.pid_data.get('min_value', '')))
        form.addRow("Min Value:", self.min_edit)
        
        self.max_edit = QLineEdit(str(self.pid_data.get('max_value', '')))
        form.addRow("Max Value:", self.max_edit)
        
        self.category_combo = QComboBox()
        self.category_combo.addItems(['Engine', 'Fuel', 'Temperature', 'Speed', 'Emissions', 
                                      'Transmission', 'Electrical', 'Custom', 'Mode_01'])
        current_cat = self.pid_data.get('category', 'Custom')
        idx = self.category_combo.findText(current_cat)
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)
        form.addRow("Category:", self.category_combo)
        
        self.vehicle_specific_check = QCheckBox()
        self.vehicle_specific_check.setChecked(self.pid_data.get('vehicle_specific', False))
        form.addRow("Vehicle Specific:", self.vehicle_specific_check)
        
        layout.addLayout(form)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_pid_data(self):
        """Get the edited PID data"""
        return {
            'hex_code': self.hex_edit.text().strip().upper(),
            'name': self.name_edit.text().strip(),
            'description': self.desc_edit.toPlainText().strip(),
            'formula': self.formula_edit.text().strip(),
            'units': self.units_edit.text().strip(),
            'min_value': self.min_edit.text().strip(),
            'max_value': self.max_edit.text().strip(),
            'category': self.category_combo.currentText(),
            'vehicle_specific': self.vehicle_specific_check.isChecked(),
            'validation_required': True
        }


# ================================
# PID SCAN THREAD - FIXED
# ================================

class PIDScanThread(QThread):
    """Background thread for comprehensive PID scanning"""
    update_signal = Signal(str)
    progress_signal = Signal(int)
    finished_signal = Signal(dict)
    error_signal = Signal(str)

    def __init__(self, connectivity_manager, parent=None):
        super().__init__(parent)
        self.connectivity_manager = connectivity_manager
        self.pids_found = {}
        self.is_running = True

    def run(self):
        try:
            self.update_signal.emit("🚗 Starting comprehensive PID scan...")
            
            # Check connection
            is_connected = False
            if hasattr(self.connectivity_manager, 'connected'):
                is_connected = self.connectivity_manager.connected
            elif hasattr(self.connectivity_manager, 'is_connected'):
                if callable(self.connectivity_manager.is_connected):
                    is_connected = self.connectivity_manager.is_connected()
                else:
                    is_connected = self.connectivity_manager.is_connected

            if not is_connected:
                self.error_signal.emit("Not connected to vehicle. Please connect first using the Connection tab.")
                return
            
            # Try different methods to query PIDs
            if hasattr(self.connectivity_manager, 'obd_connection') and self.connectivity_manager.obd_connection:
                self._scan_via_python_obd()
            elif hasattr(self.connectivity_manager, 'direct_elm') and self.connectivity_manager.direct_elm:
                self._scan_via_direct_elm()
            else:
                self.error_signal.emit("No valid OBD connection available")
                return
            
            self.update_signal.emit(f"✅ Scan completed! Found {len(self.pids_found)} active PIDs.")
            self.finished_signal.emit(self.pids_found)
            
        except Exception as e:
            error_msg = f"❌ Critical error: {str(e)}\n{traceback.format_exc()}"
            self.error_signal.emit(error_msg)
    
    def _scan_via_python_obd(self):
        """Scan using python-OBD library"""
        import obd
        
        self.update_signal.emit("Using python-OBD for scanning...")
        
        # Get supported commands
        supported = self.connectivity_manager.obd_connection.supported_commands
        total = len(supported)
        
        for i, cmd in enumerate(supported):
            if not self.is_running:
                break
            
            try:
                response = self.connectivity_manager.obd_connection.query(cmd)
                
                if response and not response.is_null():
                    value = response.value
                    if hasattr(value, 'magnitude'):
                        value = value.magnitude
                    
                    pid_hex = cmd.pid if hasattr(cmd, 'pid') else cmd.command[-2:]
                    if isinstance(pid_hex, int):
                        pid_hex = f"{pid_hex:02X}"
                    
                    self.pids_found[pid_hex] = {
                        'hex_code': pid_hex,
                        'name': cmd.name if hasattr(cmd, 'name') else f"PID_{pid_hex}",
                        'description': cmd.desc if hasattr(cmd, 'desc') else f"Discovered PID {pid_hex}",
                        'formula': 'Standard OBD',
                        'units': str(response.unit) if hasattr(response, 'unit') else 'Raw',
                        'min_value': '0',
                        'max_value': '255',
                        'category': 'Mode_01',
                        'vehicle_specific': False,
                        'validation_required': False,
                        'last_value': str(value)
                    }
                    self.update_signal.emit(f"🎉 FOUND: {pid_hex} ({cmd.name}) = {value}")
                
            except Exception as e:
                pass  # Skip failed queries
            
            progress = int((i + 1) / total * 100) if total > 0 else 0
            self.progress_signal.emit(progress)
    
    def _scan_via_direct_elm(self):
        """Scan using direct ELM327 commands"""
        self.update_signal.emit("Using direct ELM327 for scanning...")
        
        # COMPREHENSIVE OBD-II PID ranges
        pid_ranges = [
            (0x00, 0x20),   # Mode 01 - Basic PIDs
            (0x20, 0x40),   # Mode 01 - Extended PIDs
            (0x40, 0x60),   # Mode 01 - More extended PIDs
            (0x60, 0x80),   # Mode 01 - Even more extended PIDs
            (0x80, 0xA0),   # Mode 01 - Additional PIDs
            (0xA0, 0xC0),   # Mode 01 - Manufacturer specific PIDs
        ]
        
        total_pids = sum(end - start for start, end in pid_ranges)
        current_progress = 0
        
        for range_num, (start, end) in enumerate(pid_ranges):
            if not self.is_running:
                break
                
            mode = 1
            self.update_signal.emit(f"🔍 Scanning Range: {start:02X}-{end:02X} ({end-start} PIDs)")
            
            for pid in range(start, end):
                if not self.is_running:
                    break
                    
                pid_hex = f"{pid:02X}"
                
                try:
                    time.sleep(0.05)  # Small delay
                    
                    # Send command
                    cmd = f"01{pid_hex}"
                    response = self.connectivity_manager.direct_elm.send_command(cmd)
                    
                    if (response and 
                        response.strip() and 
                        "NO DATA" not in response.upper() and 
                        "ERROR" not in response.upper() and
                        "UNABLE" not in response.upper() and
                        "TIMEOUT" not in response.upper() and
                        "?" not in response and
                        len(response.strip()) > 2):
                        
                        self.pids_found[pid_hex] = {
                            'hex_code': pid_hex,
                            'name': f"Discovered_PID_{pid_hex}",
                            'description': f"Discovered PID {pid_hex} - Response: {response}",
                            'formula': 'A',
                            'units': 'Raw',
                            'min_value': '0',
                            'max_value': '255',
                            'category': f'Mode_{mode:02d}',
                            'vehicle_specific': True,
                            'validation_required': True,
                            'raw_response': response
                        }
                        self.update_signal.emit(f"🎉 FOUND: {pid_hex} → {response}")
                
                except Exception as e:
                    pass  # Skip errors silently
                
                current_progress += 1
                if total_pids > 0:
                    progress_percent = int((current_progress / total_pids) * 100)
                    self.progress_signal.emit(progress_percent)
    
    def stop(self):
        """Stop the scanning thread"""
        self.is_running = False


# ================================
# PID LEARNING TAB - FIXED WITH ROBUST ERROR HANDLING
# ================================

class PIDLearningTab(QWidget):
    """PID Learning tab with comprehensive PID management."""

    def __init__(self, connectivity=None, pid_manager=None, parent=None):
        super().__init__(parent)
        
        self.connectivity = connectivity
        self.scan_thread = None
        self.init_error = None
        
        # Create PID manager with FIXED path
        try:
            if pid_manager is None:
                self.pid_manager = PIDLearningManager()  # Uses default path
            else:
                self.pid_manager = pid_manager
        except Exception as e:
            self.init_error = f"PID Manager Error: {e}"
            self.pid_manager = None
        
        # Always build UI, even if there are errors
        self._build_ui()
        
        # Refresh table if manager is available
        if self.pid_manager:
            try:
                self._refresh_pid_table()
            except Exception as e:
                print(f"Error refreshing PID table: {e}")

    def _build_ui(self):
        """Build the user interface"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Title
        title = QLabel("🔧 PID Learning & Management")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #C40000;")
        main_layout.addWidget(title)
        
        # Show error if initialization failed
        if self.init_error:
            error_label = QLabel(f"⚠️ {self.init_error}")
            error_label.setStyleSheet("color: #ff6b6b; background-color: #2a2a2a; padding: 10px; border-radius: 5px;")
            error_label.setWordWrap(True)
            main_layout.addWidget(error_label)
        
        # Save path info
        if self.pid_manager:
            path_label = QLabel(f"📁 Save Path: {self.pid_manager.learned_pids_directory}")
        else:
            path_label = QLabel(f"📁 Save Path: Not configured")
        path_label.setStyleSheet("color: #888; font-size: 11px; padding: 5px;")
        main_layout.addWidget(path_label)

        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #444;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #ccc;
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #C40000;
                color: white;
            }
        """)
        main_layout.addWidget(self.tab_widget)

        # Tab 1: PID Management
        self._build_management_tab()
        
        # Tab 2: PID Discovery
        self._build_discovery_tab()
        
        # Tab 3: Import/Export
        self._build_import_export_tab()

    def _build_management_tab(self):
        """Build the PID management tab"""
        management_tab = QWidget()
        management_layout = QVBoxLayout(management_tab)
        management_layout.setContentsMargins(10, 10, 10, 10)
        
        # PID Table Group
        table_group = QGroupBox("📋 Learned PIDs")
        table_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #444;
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
        table_layout = QVBoxLayout(table_group)
        
        # Table controls
        controls_layout = QHBoxLayout()
        
        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.setStyleSheet(self._get_button_style('secondary'))
        self.btn_refresh.clicked.connect(self._refresh_pid_table)
        
        self.btn_add_pid = QPushButton("➕ Add New PID")
        self.btn_add_pid.setStyleSheet(self._get_button_style('success'))
        self.btn_add_pid.clicked.connect(self._add_new_pid)
        
        self.btn_edit_pid = QPushButton("✏️ Edit Selected")
        self.btn_edit_pid.setStyleSheet(self._get_button_style('secondary'))
        self.btn_edit_pid.clicked.connect(self._edit_selected_pid)
        
        self.btn_delete_pid = QPushButton("🗑️ Delete Selected")
        self.btn_delete_pid.setStyleSheet(self._get_button_style('danger'))
        self.btn_delete_pid.clicked.connect(self._delete_selected_pid)
        
        controls_layout.addWidget(self.btn_refresh)
        controls_layout.addWidget(self.btn_add_pid)
        controls_layout.addWidget(self.btn_edit_pid)
        controls_layout.addWidget(self.btn_delete_pid)
        controls_layout.addStretch()
        
        table_layout.addLayout(controls_layout)
        
        # PID Table
        self.pid_table = QTableWidget()
        self.pid_table.setColumnCount(6)
        self.pid_table.setHorizontalHeaderLabels(["Hex Code", "Name", "Category", "Units", "Formula", "Vehicle Specific"])
        self.pid_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.pid_table.setAlternatingRowColors(True)
        self._apply_table_styling(self.pid_table)
        self.pid_table.doubleClicked.connect(self._edit_selected_pid)
        table_layout.addWidget(self.pid_table)
        
        management_layout.addWidget(table_group)
        self.tab_widget.addTab(management_tab, "📋 PID Management")

    def _build_discovery_tab(self):
        """Build the PID discovery tab"""
        discovery_tab = QWidget()
        discovery_layout = QVBoxLayout(discovery_tab)
        discovery_layout.setContentsMargins(10, 10, 10, 10)
        
        # Discovery Group
        discovery_group = QGroupBox("🔍 Comprehensive PID Discovery")
        discovery_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #444;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
        """)
        discovery_group_layout = QVBoxLayout(discovery_group)
        
        # Info text
        info_text = (
            "This will scan ALL standard OBD-II PID ranges to discover every available parameter from your vehicle.\n\n"
            "⚠️ Make sure you are connected via the Connection tab first.\n\n"
        )
        if self.pid_manager:
            info_text += f"💾 Discovered PIDs will be saved to:\n{self.pid_manager.learned_pids_directory}"
        
        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        info_label.setStyleSheet("""
            color: #ccc; 
            background-color: #2a2a2a; 
            padding: 15px; 
            border-radius: 5px;
            border-left: 4px solid #C40000;
        """)
        discovery_group_layout.addWidget(info_label)
        
        # Discovery controls
        discovery_controls = QHBoxLayout()
        
        self.btn_get_obd_pids = QPushButton("🚗 Start Comprehensive PID Scan")
        self.btn_get_obd_pids.setStyleSheet(self._get_button_style('success'))
        self.btn_get_obd_pids.clicked.connect(self._get_obd_pids_from_car)
        
        self.btn_stop_scan = QPushButton("🛑 Stop Scan")
        self.btn_stop_scan.setStyleSheet(self._get_button_style('danger'))
        self.btn_stop_scan.clicked.connect(self._stop_scan)
        self.btn_stop_scan.setEnabled(False)
        
        discovery_controls.addWidget(self.btn_get_obd_pids)
        discovery_controls.addWidget(self.btn_stop_scan)
        discovery_controls.addStretch()
        
        discovery_group_layout.addLayout(discovery_controls)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444;
                border-radius: 5px;
                text-align: center;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #C40000;
            }
        """)
        discovery_group_layout.addWidget(self.progress_bar)
        
        # Log output
        log_label = QLabel("📜 Scan Log:")
        log_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        discovery_group_layout.addWidget(log_label)
        
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(300)
        self.log_output.setStyleSheet("""
            font-family: Consolas, 'Courier New', monospace; 
            font-size: 11px;
            background-color: #1a1a1a;
            color: #0f0;
            border: 1px solid #444;
            padding: 10px;
        """)
        self.log_output.setPlainText("Ready to scan. Connect to vehicle and click 'Start Comprehensive PID Scan'.")
        discovery_group_layout.addWidget(self.log_output)
        
        discovery_layout.addWidget(discovery_group)
        self.tab_widget.addTab(discovery_tab, "🔍 PID Discovery")

    def _build_import_export_tab(self):
        """Build the import/export tab"""
        import_export_tab = QWidget()
        import_export_layout = QVBoxLayout(import_export_tab)
        import_export_layout.setContentsMargins(10, 10, 10, 10)
        
        # Import/Export Group
        import_group = QGroupBox("📁 Import/Export PIDs")
        import_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #444;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
        """)
        import_layout = QVBoxLayout(import_group)
        
        # Import section
        import_info = QLabel(
            "Import PIDs from a CSV file or export your learned PIDs for backup/sharing.\n\n"
            "CSV Format: hex_code, name, description, formula, units, min_value, max_value, category"
        )
        import_info.setWordWrap(True)
        import_info.setStyleSheet("color: #aaa; padding: 10px;")
        import_layout.addWidget(import_info)
        
        btn_layout = QHBoxLayout()
        
        btn_import = QPushButton("📥 Import from CSV")
        btn_import.setStyleSheet(self._get_button_style('secondary'))
        btn_import.clicked.connect(self._import_from_csv)
        
        btn_export = QPushButton("📤 Export to CSV")
        btn_export.setStyleSheet(self._get_button_style('secondary'))
        btn_export.clicked.connect(self._export_to_csv)
        
        btn_layout.addWidget(btn_import)
        btn_layout.addWidget(btn_export)
        btn_layout.addStretch()
        
        import_layout.addLayout(btn_layout)
        import_layout.addStretch()
        
        import_export_layout.addWidget(import_group)
        import_export_layout.addStretch()
        
        self.tab_widget.addTab(import_export_tab, "📁 Import/Export")

    def _refresh_pid_table(self):
        """Refresh the PID table"""
        if not self.pid_manager:
            return
            
        try:
            self.pid_manager.load_learned_pids()
            pids = self.pid_manager.get_all_pids()
            
            self.pid_table.setRowCount(len(pids))
            
            for row, (hex_code, pid_data) in enumerate(pids.items()):
                self.pid_table.setItem(row, 0, QTableWidgetItem(hex_code))
                self.pid_table.setItem(row, 1, QTableWidgetItem(pid_data.get('name', '')))
                self.pid_table.setItem(row, 2, QTableWidgetItem(pid_data.get('category', '')))
                self.pid_table.setItem(row, 3, QTableWidgetItem(pid_data.get('units', '')))
                self.pid_table.setItem(row, 4, QTableWidgetItem(pid_data.get('formula', '')))
                self.pid_table.setItem(row, 5, QTableWidgetItem('Yes' if pid_data.get('vehicle_specific') else 'No'))
        except Exception as e:
            print(f"Error refreshing PID table: {e}")

    def _add_new_pid(self):
        """Add a new PID"""
        if not self.pid_manager:
            QMessageBox.warning(self, "Error", "PID Manager not available")
            return
            
        dialog = PIDEditDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            pid_data = dialog.get_pid_data()
            if pid_data.get('hex_code'):
                success, message = self.pid_manager.save_pid(pid_data)
                if success:
                    self._refresh_pid_table()
                    QMessageBox.information(self, "Success", message)
                else:
                    QMessageBox.critical(self, "Error", message)
            else:
                QMessageBox.warning(self, "Invalid", "Hex code is required")

    def _edit_selected_pid(self):
        """Edit selected PID"""
        if not self.pid_manager:
            return
            
        selected = self.pid_table.selectedItems()
        if not selected:
            QMessageBox.information(self, "Select PID", "Please select a PID to edit")
            return
        
        row = selected[0].row()
        hex_code = self.pid_table.item(row, 0).text()
        pid_data = self.pid_manager.get_pid(hex_code)
        
        if pid_data:
            dialog = PIDEditDialog(pid_data, parent=self)
            if dialog.exec() == QDialog.Accepted:
                new_data = dialog.get_pid_data()
                success, message = self.pid_manager.save_pid(new_data)
                if success:
                    self._refresh_pid_table()
                    QMessageBox.information(self, "Success", message)
                else:
                    QMessageBox.critical(self, "Error", message)

    def _delete_selected_pid(self):
        """Delete selected PID"""
        if not self.pid_manager:
            return
            
        selected = self.pid_table.selectedItems()
        if not selected:
            QMessageBox.information(self, "Select PID", "Please select a PID to delete")
            return
        
        row = selected[0].row()
        hex_code = self.pid_table.item(row, 0).text()
        
        reply = QMessageBox.question(self, "Confirm Delete", 
                                     f"Delete PID {hex_code}?",
                                     QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            success, message = self.pid_manager.delete_pid(hex_code)
            if success:
                self._refresh_pid_table()
                QMessageBox.information(self, "Success", message)
            else:
                QMessageBox.critical(self, "Error", message)

    def _get_obd_pids_from_car(self):
        """Get OBD PIDs data from connected car"""
        try:
            if not self.connectivity:
                QMessageBox.warning(
                    self, 
                    "Not Available", 
                    "Connectivity manager is not available.\n\n"
                    "Please make sure you're connected to a vehicle."
                )
                return
            
            # Check connection status
            is_connected = False
            if hasattr(self.connectivity, 'connected'):
                is_connected = self.connectivity.connected
            elif hasattr(self.connectivity, 'is_connected'):
                if callable(self.connectivity.is_connected):
                    is_connected = self.connectivity.is_connected()
                else:
                    is_connected = self.connectivity.is_connected
            
            if not is_connected:
                QMessageBox.warning(
                    self, 
                    "Not Connected", 
                    "Please connect to a vehicle first using the Connection tab.\n\n"
                    "1. Go to the Connection tab\n"
                    "2. Select your COM port (e.g., COM6)\n"
                    "3. Click 'Connect to Port'\n"
                    "4. Then return here to scan PIDs"
                )
                return
            
            # Confirm scan
            save_path = self.pid_manager.learned_pids_directory if self.pid_manager else "Not configured"
            reply = QMessageBox.question(
                self, 
                "Comprehensive PID Scan",
                f"This will scan OBD-II PID ranges to discover available parameters.\n\n"
                f"• Scans 192 different PIDs\n"
                f"• Takes several minutes to complete\n" 
                f"• PIDs will be saved to:\n  {save_path}\n\n"
                "Do you want to continue?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
            
            self.log_output.clear()
            self.log_output.appendPlainText("🚗 STARTING COMPREHENSIVE OBD PID SCAN")
            self.log_output.appendPlainText("=" * 50)
            self.log_output.appendPlainText(f"Save path: {save_path}")
            self.log_output.appendPlainText("")
            
            self.btn_get_obd_pids.setEnabled(False)
            self.btn_stop_scan.setEnabled(True)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Start scanning thread
            self.scan_thread = PIDScanThread(self.connectivity)
            self.scan_thread.update_signal.connect(self._on_scan_update)
            self.scan_thread.progress_signal.connect(self._on_scan_progress)
            self.scan_thread.finished_signal.connect(self._on_scan_finished)
            self.scan_thread.error_signal.connect(self._on_scan_error)
            self.scan_thread.start()
            
        except Exception as e:
            error_msg = f"Error starting scan: {str(e)}"
            self.log_output.appendPlainText(f"✗ {error_msg}")
            QMessageBox.critical(self, "Scan Error", error_msg)
            self._reset_scan_ui()

    def _stop_scan(self):
        """Stop the ongoing scan"""
        if self.scan_thread and self.scan_thread.isRunning():
            self.scan_thread.stop()
            self.scan_thread.quit()
            self.scan_thread.wait(2000)
            self.log_output.appendPlainText("")
            self.log_output.appendPlainText("🛑 SCAN STOPPED BY USER")
            if hasattr(self.scan_thread, 'pids_found'):
                self.log_output.appendPlainText(f"Found {len(self.scan_thread.pids_found)} PIDs before stopping")
        self._reset_scan_ui()

    def _reset_scan_ui(self):
        """Reset UI after scan completion"""
        self.btn_get_obd_pids.setEnabled(True)
        self.btn_stop_scan.setEnabled(False)
        self.progress_bar.setVisible(False)

    def _on_scan_update(self, message):
        """Handle scan status updates"""
        self.log_output.appendPlainText(message)
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def _on_scan_progress(self, value):
        """Handle scan progress updates"""
        self.progress_bar.setValue(value)

    def _on_scan_finished(self, pids_found):
        """Handle scan completion"""
        self._reset_scan_ui()
        
        if pids_found:
            self.log_output.appendPlainText("")
            self.log_output.appendPlainText("✅ SCAN COMPLETED!")
            self.log_output.appendPlainText(f"🎯 Found {len(pids_found)} active PIDs")
            
            # Auto-save discovered PIDs
            saved_count = self._auto_save_discovered_pids(pids_found)
            if self.pid_manager:
                self.log_output.appendPlainText(f"💾 Saved {saved_count} new PIDs to:")
                self.log_output.appendPlainText(f"   {self.pid_manager.learned_pids_directory}")
            
            if saved_count > 0:
                self._refresh_pid_table()
                QMessageBox.information(self, "Scan Complete", 
                                      f"Found {len(pids_found)} PIDs\n"
                                      f"Saved {saved_count} new PIDs")
            else:
                QMessageBox.information(self, "Scan Complete", 
                                      f"Found {len(pids_found)} PIDs (all already in database)")
        else:
            self.log_output.appendPlainText("")
            self.log_output.appendPlainText("❌ SCAN COMPLETED - NO PIDs FOUND")
            QMessageBox.warning(self, "Scan Complete", "No PIDs discovered. Check vehicle connection.")

    def _on_scan_error(self, error_message):
        """Handle scan errors"""
        self._reset_scan_ui()
        self.log_output.appendPlainText("")
        self.log_output.appendPlainText(f"❌ ERROR: {error_message}")
        QMessageBox.critical(self, "Scan Error", error_message)

    def _auto_save_discovered_pids(self, pids_found):
        """Automatically save discovered PIDs"""
        if not self.pid_manager:
            return 0
            
        saved_count = 0
        existing_pids = self.pid_manager.get_all_pids()
        
        for pid_hex, pid_data in pids_found.items():
            if pid_hex not in existing_pids:
                success, message = self.pid_manager.save_pid(pid_data)
                if success:
                    saved_count += 1
                    self.log_output.appendPlainText(f"✔ Saved: {pid_hex}")
        
        return saved_count

    def _import_from_csv(self):
        """Import PIDs from CSV file"""
        if not self.pid_manager:
            QMessageBox.warning(self, "Error", "PID Manager not available")
            return
            
        try:
            filepath, _ = QFileDialog.getOpenFileName(
                self, "Import PIDs from CSV", "", "CSV Files (*.csv)")
            
            if filepath:
                success, message = self.pid_manager.import_from_csv(filepath)
                if success:
                    self.log_output.appendPlainText(f"✔ {message}")
                    self._refresh_pid_table()
                    QMessageBox.information(self, "Import Successful", message)
                else:
                    self.log_output.appendPlainText(f"✗ {message}")
                    QMessageBox.critical(self, "Import Failed", message)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to import CSV: {str(e)}")

    def _export_to_csv(self):
        """Export PIDs to CSV file"""
        if not self.pid_manager:
            QMessageBox.warning(self, "Error", "PID Manager not available")
            return
            
        try:
            filepath, _ = QFileDialog.getSaveFileName(
                self, "Export PIDs to CSV", "obd_pids_export.csv", "CSV Files (*.csv)")
            
            if filepath:
                success, message = self.pid_manager.export_to_csv(filepath)
                if success:
                    self.log_output.appendPlainText(f"✔ {message}")
                    QMessageBox.information(self, "Export Successful", message)
                else:
                    self.log_output.appendPlainText(f"✗ {message}")
                    QMessageBox.critical(self, "Export Failed", message)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export CSV: {str(e)}")
    
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
