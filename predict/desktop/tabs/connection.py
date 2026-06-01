"""
Connection tab for OBD adapter configuration.

Manages COM port selection, baud rate, protocol, and connection status.
"""

import logging
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QComboBox, QPushButton, QGroupBox,
    QTreeWidget, QTreeWidgetItem, QSplitter,
    QMessageBox,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor

from predict.desktop.theme import PredictTheme

logger = logging.getLogger(__name__)


try:
    import serial.tools.list_ports
    _has_serial = True
except ImportError:
    _has_serial = False


class ConnectionTab(QWidget):
    """
    Tab for managing OBD adapter connection.
    
    Features:
    - COM port selection with auto-detection
    - Baud rate configuration
    - Protocol selection
    - Vehicle profile selection (Owner -> Vehicle -> Driver tree)
    - Connection status indicator
    """
    
    # Protocols
    PROTOCOLS = [
        "Auto",
        "SAE J1850 PWM",
        "SAE J1850 VPW",
        "ISO 9141-2",
        "ISO 14230-4 (KWP 5-baud)",
        "ISO 14230-4 (KWP fast)",
        "ISO 15765-4 (CAN 11-bit, 500 kbaud)",
        "ISO 15765-4 (CAN 29-bit, 500 kbaud)",
        "ISO 15765-4 (CAN 11-bit, 250 kbaud)",
        "ISO 15765-4 (CAN 29-bit, 250 kbaud)",
    ]
    
    # Baud rates
    BAUD_RATES = ["9600", "38400", "115200", "230400"]
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._connected = False
        self._selected_profile: Optional[Dict[str, Any]] = None
        self._setup_ui()
        self._refresh_ports()
    
    def _setup_ui(self) -> None:
        """Setup the tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("OBD Connection")
        title.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY};")
        font = QFont(PredictTheme.FONT_FAMILY, 18, QFont.Weight.Bold)
        title.setFont(font)
        layout.addWidget(title)
        
        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left: Vehicle selection tree
        vehicle_group = QGroupBox("Select Vehicle")
        vehicle_group.setStyleSheet(PredictTheme.get_card_stylesheet())
        vehicle_layout = QVBoxLayout(vehicle_group)
        
        self.vehicle_tree = QTreeWidget()
        self.vehicle_tree.setHeaderLabels(["#", "Name", "Make", "Model", "Year", "VIN", "★", "ℹ️"])
        self.vehicle_tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.vehicle_tree.setIndentation(20)
        self.vehicle_tree.setRootIsDecorated(True)
        self.vehicle_tree.setAnimated(True)
        self.vehicle_tree.itemSelectionChanged.connect(self._on_vehicle_selected)
        self.vehicle_tree.setStyleSheet(PredictTheme.get_table_stylesheet())
        vehicle_layout.addWidget(self.vehicle_tree)
        
        splitter.addWidget(vehicle_group)
        
        # Right: Connection settings
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Connection settings group
        settings_group = QGroupBox("Connection Settings")
        settings_group.setStyleSheet(PredictTheme.get_card_stylesheet())
        settings_layout = QFormLayout(settings_group)
        
        # COM Port
        port_layout = QHBoxLayout()
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(200)
        port_layout.addWidget(self.port_combo)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_ports)
        port_layout.addWidget(refresh_btn)
        port_layout.addStretch()
        
        settings_layout.addRow("COM Port:", port_layout)
        
        # Baud Rate
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(self.BAUD_RATES)
        self.baud_combo.setCurrentText("115200")
        settings_layout.addRow("Baud Rate:", self.baud_combo)
        
        # Protocol
        self.protocol_combo = QComboBox()
        self.protocol_combo.addItems(self.PROTOCOLS)
        self.protocol_combo.setCurrentIndex(0)
        settings_layout.addRow("Protocol:", self.protocol_combo)
        
        right_layout.addWidget(settings_group)
        
        # Status group
        status_group = QGroupBox("Status")
        status_group.setStyleSheet(PredictTheme.get_card_stylesheet())
        status_layout = QFormLayout(status_group)
        
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet(f"color: {PredictTheme.DANGER}; font-weight: bold;")
        status_layout.addRow("Status:", self.status_label)
        
        self.protocol_label = QLabel("--")
        status_layout.addRow("Protocol:", self.protocol_label)
        
        self.ecu_label = QLabel("--")
        status_layout.addRow("ECU:", self.ecu_label)
        
        right_layout.addWidget(status_group)
        
        # Connection buttons
        btn_layout = QHBoxLayout()
        
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("primary")
        self.connect_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PredictTheme.SUCCESS};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #146c43;
            }}
        """)
        self.connect_btn.clicked.connect(self._on_connect)
        btn_layout.addWidget(self.connect_btn)
        
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PredictTheme.DANGER};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #bb2d3b;
            }}
        """)
        self.disconnect_btn.clicked.connect(self._on_disconnect)
        self.disconnect_btn.setEnabled(False)
        btn_layout.addWidget(self.disconnect_btn)
        
        btn_layout.addStretch()
        right_layout.addLayout(btn_layout)
        right_layout.addStretch()
        
        splitter.addWidget(right_widget)
        splitter.setSizes([600, 400])
        
        layout.addWidget(splitter)
        
        # Load sample vehicle data
        self._load_sample_vehicles()
    
    def _load_sample_vehicles(self) -> None:
        """Load sample vehicle data for testing."""
        # Owner 1
        owner1 = QTreeWidgetItem(["1", "John Doe", "", "", "", "", "", "ℹ️"])
        owner1.setData(0, Qt.ItemDataRole.UserRole, {"type": "owner", "id": 1})
        font = owner1.font(1)
        font.setBold(True)
        owner1.setFont(1, font)
        owner1.setForeground(1, QColor(PredictTheme.ACCENT_EMERALD))
        self.vehicle_tree.addTopLevelItem(owner1)
        
        # Vehicle 1.1
        veh11 = QTreeWidgetItem(["", "  Toyota Camry", "Toyota", "Camry", "2020", "JTDBU4EE3B9123456", "★", "ℹ️"])
        veh11.setData(0, Qt.ItemDataRole.UserRole, {"type": "vehicle", "id": 101, "profile_id": 1001})
        owner1.addChild(veh11)
        
        # Driver 1.1.1
        driver111 = QTreeWidgetItem(["", "    John (Owner)", "", "", "", "", "", ""])
        driver111.setData(0, Qt.ItemDataRole.UserRole, {"type": "driver", "id": 201})
        veh11.addChild(driver111)
        
        # Owner 2
        owner2 = QTreeWidgetItem(["2", "Jane Smith", "", "", "", "", "", "ℹ️"])
        owner2.setData(0, Qt.ItemDataRole.UserRole, {"type": "owner", "id": 2})
        font = owner2.font(1)
        font.setBold(True)
        owner2.setFont(1, font)
        owner2.setForeground(1, QColor(PredictTheme.ACCENT_CYAN))
        self.vehicle_tree.addTopLevelItem(owner2)
        
        # Vehicle 2.1
        veh21 = QTreeWidgetItem(["", "  Honda Accord", "Honda", "Accord", "2019", "1HGCV1F3XKA123456", "", "ℹ️"])
        veh21.setData(0, Qt.ItemDataRole.UserRole, {"type": "vehicle", "id": 102, "profile_id": 1002})
        owner2.addChild(veh21)
    
    def _refresh_ports(self) -> None:
        """Refresh available COM ports."""
        self.port_combo.clear()
        
        if _has_serial:
            try:
                ports = serial.tools.list_ports.comports()
                for port in ports:
                    self.port_combo.addItem(f"{port.device} - {port.description}", port.device)
                logger.debug(f"Found {len(ports)} serial ports")
            except Exception as e:
                logger.error(f"Failed to list ports: {e}")
                self.port_combo.addItem("COM1 - (Auto)")
        else:
            # Fallback
            for i in range(1, 10):
                self.port_combo.addItem(f"COM{i} - (Simulated)")
            logger.warning("PySerial not available, using simulated ports")
    
    def _on_vehicle_selected(self) -> None:
        """Handle vehicle selection."""
        items = self.vehicle_tree.selectedItems()
        if not items:
            return
        
        item = items[0]
        data = item.data(0, Qt.ItemDataRole.UserRole)
        
        if data and data.get("type") == "vehicle":
            self._selected_profile = data
            logger.debug(f"Selected vehicle profile: {data.get('profile_id')}")
    
    def _on_connect(self) -> None:
        """Handle connect button."""
        if not self._selected_profile:
            QMessageBox.warning(self, "No Vehicle Selected", "Please select a vehicle from the tree.")
            return
        
        port = self.port_combo.currentData()
        if not port:
            port = self.port_combo.currentText().split(" - ")[0]
        
        baud = self.baud_combo.currentText()
        protocol = self.protocol_combo.currentText()
        
        logger.info(f"Connecting to {port} at {baud} baud with {protocol} protocol")
        
        # Simulate connection
        self._connected = True
        self._update_status()
        
        QMessageBox.information(self, "Connected", f"Connected to OBD adapter on {port}")
    
    def _on_disconnect(self) -> None:
        """Handle disconnect button."""
        logger.info("Disconnecting from OBD adapter")
        self._connected = False
        self._update_status()
    
    def _update_status(self) -> None:
        """Update connection status display."""
        if self._connected:
            self.status_label.setText("Connected")
            self.status_label.setStyleSheet(f"color: {PredictTheme.SUCCESS}; font-weight: bold;")
            self.protocol_label.setText(self.protocol_combo.currentText())
            self.ecu_label.setText("ELM327 v1.5")
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
        else:
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet(f"color: {PredictTheme.DANGER}; font-weight: bold;")
            self.protocol_label.setText("--")
            self.ecu_label.setText("--")
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)
    
    def is_connected(self) -> bool:
        """Check if OBD connection is active."""
        return self._connected
    
    def get_selected_profile(self) -> Optional[Dict[str, Any]]:
        """Get selected vehicle profile."""
        return self._selected_profile


# Need to import QColor
from PySide6.QtGui import QColor
