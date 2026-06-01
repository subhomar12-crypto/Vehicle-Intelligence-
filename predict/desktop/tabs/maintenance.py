"""
Maintenance tab for service schedule management.

Tracks upcoming maintenance, overdue items, and service history.
"""

import logging
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QGroupBox, QTreeWidget, QTreeWidgetItem, QSplitter,
    QDialog, QFormLayout, QLineEdit, QComboBox, QMessageBox,
    QDateEdit,
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont, QColor

from predict.desktop.theme import PredictTheme

logger = logging.getLogger(__name__)


class AddMaintenanceDialog(QDialog):
    """Dialog for adding maintenance item."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Add Maintenance Item")
        self.setMinimumWidth(400)
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Setup dialog UI."""
        layout = QFormLayout(self)
        
        # Item type
        self.item_combo = QComboBox()
        self.item_combo.addItems([
            "Oil Change",
            "Tire Rotation",
            "Brake Inspection",
            "Air Filter Replacement",
            "Spark Plug Replacement",
            "Transmission Fluid",
            "Coolant Flush",
            "Battery Check",
            "Timing Belt",
            "Custom",
        ])
        self.item_combo.setEditable(True)
        layout.addRow("Maintenance Item:", self.item_combo)
        
        # Interval (miles)
        self.interval_input = QLineEdit()
        self.interval_input.setPlaceholderText("e.g., 5000")
        layout.addRow("Interval (miles):", self.interval_input)
        
        # Interval (months)
        self.months_input = QLineEdit()
        self.months_input.setPlaceholderText("e.g., 6")
        layout.addRow("Interval (months):", self.months_input)
        
        # Last performed date
        self.last_date = QDateEdit()
        self.last_date.setCalendarPopup(True)
        self.last_date.setDate(QDate.currentDate())
        layout.addRow("Last Performed:", self.last_date)
        
        # Last mileage
        self.last_mileage = QLineEdit()
        self.last_mileage.setPlaceholderText("e.g., 45000")
        layout.addRow("Last Mileage:", self.last_mileage)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addRow(btn_layout)
    
    def get_data(self) -> Dict[str, Any]:
        """Get dialog data."""
        return {
            "item": self.item_combo.currentText(),
            "interval_miles": self.interval_input.text(),
            "interval_months": self.months_input.text(),
            "last_date": self.last_date.date().toString("yyyy-MM-dd"),
            "last_mileage": self.last_mileage.text(),
        }


class MaintenanceTab(QWidget):
    """
    Tab for maintenance schedule management.
    
    Features:
    - Vehicle selection tree (Owner -> Vehicle -> Driver)
    - Upcoming maintenance table
    - Overdue items highlighting
    - Add maintenance items
    - Default maintenance intervals
    """
    
    # Default maintenance intervals
    DEFAULT_INTERVALS = {
        "Oil Change": {"miles": 5000, "months": 6},
        "Tire Rotation": {"miles": 7500, "months": 6},
        "Brake Inspection": {"miles": 15000, "months": 12},
        "Air Filter Replacement": {"miles": 20000, "months": 12},
        "Spark Plug Replacement": {"miles": 30000, "months": 24},
        "Transmission Fluid": {"miles": 40000, "months": 24},
        "Coolant Flush": {"miles": 50000, "months": 36},
        "Battery Check": {"miles": 0, "months": 12},
        "Timing Belt": {"miles": 60000, "months": 60},
    }
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._selected_vehicle: Optional[Dict[str, Any]] = None
        self._maintenance_items: List[Dict[str, Any]] = []
        self._setup_ui()
        self._load_sample_data()
    
    def _setup_ui(self) -> None:
        """Setup the tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Maintenance Schedule")
        title.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY};")
        font = QFont(PredictTheme.FONT_FAMILY, 18, QFont.Weight.Bold)
        title.setFont(font)
        layout.addWidget(title)
        
        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Vehicle selection tree
        vehicle_group = QGroupBox("Select Vehicle")
        vehicle_group.setStyleSheet(PredictTheme.get_card_stylesheet())
        vehicle_layout = QVBoxLayout(vehicle_group)
        
        self.vehicle_tree = QTreeWidget()
        self.vehicle_tree.setHeaderLabels(["#", "Name", "Make", "Model", "Year", "VIN", "Mileage", ""])
        self.vehicle_tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.vehicle_tree.setIndentation(20)
        self.vehicle_tree.setRootIsDecorated(True)
        self.vehicle_tree.setAnimated(True)
        self.vehicle_tree.itemSelectionChanged.connect(self._on_vehicle_selected)
        self.vehicle_tree.setStyleSheet(PredictTheme.get_table_stylesheet())
        vehicle_layout.addWidget(self.vehicle_tree)
        
        splitter.addWidget(vehicle_group)
        
        # Maintenance schedule
        schedule_widget = QWidget()
        schedule_layout = QVBoxLayout(schedule_widget)
        schedule_layout.setContentsMargins(0, 0, 0, 0)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("Add Maintenance Item")
        self.add_btn.setObjectName("primary")
        self.add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PredictTheme.PRIMARY};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #E00000;
            }}
        """)
        self.add_btn.clicked.connect(self._add_maintenance)
        btn_layout.addWidget(self.add_btn)
        
        btn_layout.addStretch()
        schedule_layout.addLayout(btn_layout)
        
        # Upcoming maintenance
        upcoming_group = QGroupBox("Upcoming Maintenance")
        upcoming_group.setStyleSheet(PredictTheme.get_card_stylesheet(PredictTheme.SUCCESS))
        upcoming_layout = QVBoxLayout(upcoming_group)
        
        self.upcoming_table = QTableWidget()
        self.upcoming_table.setColumnCount(5)
        self.upcoming_table.setHorizontalHeaderLabels(["Item", "Due Date", "Due Mileage", "Priority", "Status"])
        self.upcoming_table.setStyleSheet(PredictTheme.get_table_stylesheet())
        upcoming_layout.addWidget(self.upcoming_table)
        
        schedule_layout.addWidget(upcoming_group)
        
        # Overdue items
        overdue_group = QGroupBox("Overdue Items")
        overdue_group.setStyleSheet(PredictTheme.get_card_stylesheet(PredictTheme.DANGER))
        overdue_layout = QVBoxLayout(overdue_group)
        
        self.overdue_table = QTableWidget()
        self.overdue_table.setColumnCount(4)
        self.overdue_table.setHorizontalHeaderLabels(["Item", "Was Due", "Overdue By", "Action"])
        self.overdue_table.setStyleSheet(PredictTheme.get_table_stylesheet())
        overdue_layout.addWidget(self.overdue_table)
        
        schedule_layout.addWidget(overdue_group)
        
        splitter.addWidget(schedule_widget)
        splitter.setSizes([400, 600])
        
        layout.addWidget(splitter)
        
        # Load sample vehicles
        self._load_sample_vehicles()
    
    def _load_sample_vehicles(self) -> None:
        """Load sample vehicle data."""
        # Owner 1
        owner1 = QTreeWidgetItem(["1", "John Doe", "", "", "", "", "", "ℹ️"])
        owner1.setData(0, Qt.ItemDataRole.UserRole, {"type": "owner", "id": 1})
        font = owner1.font(1)
        font.setBold(True)
        owner1.setFont(1, font)
        owner1.setForeground(1, QColor(PredictTheme.ACCENT_EMERALD))
        self.vehicle_tree.addTopLevelItem(owner1)
        
        # Vehicle 1.1
        veh11 = QTreeWidgetItem(["", "  Toyota Camry", "Toyota", "Camry", "2020", "JTDBU4EE3B9123456", "45,230 mi", "ℹ️"])
        veh11.setData(0, Qt.ItemDataRole.UserRole, {"type": "vehicle", "id": 101, "profile_id": 1001, "mileage": 45230})
        owner1.addChild(veh11)
        
        # Vehicle 1.2
        veh12 = QTreeWidgetItem(["", "  Toyota RAV4", "Toyota", "RAV4", "2018", "JTMZFREV2HJ123456", "67,890 mi", "ℹ️"])
        veh12.setData(0, Qt.ItemDataRole.UserRole, {"type": "vehicle", "id": 102, "profile_id": 1002, "mileage": 67890})
        owner1.addChild(veh12)
    
    def _load_sample_data(self) -> None:
        """Load sample maintenance data."""
        self._maintenance_items = [
            {
                "vehicle_id": 1001,
                "item": "Oil Change",
                "due_date": "2024-02-15",
                "due_mileage": 50000,
                "priority": "Normal",
                "status": "Upcoming",
                "overdue": False,
            },
            {
                "vehicle_id": 1001,
                "item": "Tire Rotation",
                "due_date": "2024-01-20",
                "due_mileage": 52000,
                "priority": "Normal",
                "status": "Upcoming",
                "overdue": False,
            },
            {
                "vehicle_id": 1001,
                "item": "Air Filter",
                "due_date": "2023-12-01",
                "due_mileage": 47000,
                "priority": "Low",
                "status": "Overdue",
                "overdue": True,
                "overdue_by": "45 days",
            },
        ]
        self._update_tables()
    
    def _update_tables(self) -> None:
        """Update maintenance tables."""
        if not self._selected_vehicle:
            return
        
        vehicle_id = self._selected_vehicle.get("profile_id")
        
        # Filter items for selected vehicle
        upcoming = [i for i in self._maintenance_items if i["vehicle_id"] == vehicle_id and not i.get("overdue", False)]
        overdue = [i for i in self._maintenance_items if i["vehicle_id"] == vehicle_id and i.get("overdue", False)]
        
        # Update upcoming table
        self.upcoming_table.setRowCount(len(upcoming))
        for row, item in enumerate(upcoming):
            self.upcoming_table.setItem(row, 0, QTableWidgetItem(item["item"]))
            self.upcoming_table.setItem(row, 1, QTableWidgetItem(item["due_date"]))
            self.upcoming_table.setItem(row, 2, QTableWidgetItem(f"{item['due_mileage']:,} mi"))
            
            priority_item = QTableWidgetItem(item["priority"])
            if item["priority"] == "High":
                priority_item.setForeground(QColor(PredictTheme.DANGER))
            elif item["priority"] == "Normal":
                priority_item.setForeground(QColor(PredictTheme.WARNING))
            self.upcoming_table.setItem(row, 3, priority_item)
            
            self.upcoming_table.setItem(row, 4, QTableWidgetItem(item["status"]))
        
        # Update overdue table
        self.overdue_table.setRowCount(len(overdue))
        for row, item in enumerate(overdue):
            self.overdue_table.setItem(row, 0, QTableWidgetItem(item["item"]))
            
            due_item = QTableWidgetItem(item["due_date"])
            due_item.setForeground(QColor(PredictTheme.DANGER))
            self.overdue_table.setItem(row, 1, due_item)
            
            overdue_item = QTableWidgetItem(item.get("overdue_by", "Unknown"))
            overdue_item.setForeground(QColor(PredictTheme.DANGER))
            font = overdue_item.font()
            font.setBold(True)
            overdue_item.setFont(font)
            self.overdue_table.setItem(row, 2, overdue_item)
            
            action_btn = QPushButton("Schedule Now")
            action_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {PredictTheme.DANGER};
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 8px;
                }}
            """)
            self.overdue_table.setCellWidget(row, 3, action_btn)
        
        self.upcoming_table.resizeColumnsToContents()
        self.overdue_table.resizeColumnsToContents()
    
    def _on_vehicle_selected(self) -> None:
        """Handle vehicle selection."""
        items = self.vehicle_tree.selectedItems()
        if not items:
            return
        
        item = items[0]
        data = item.data(0, Qt.ItemDataRole.UserRole)
        
        if data and data.get("type") == "vehicle":
            self._selected_vehicle = data
            logger.debug(f"Selected vehicle: {data.get('profile_id')}")
            self._update_tables()
    
    def _add_maintenance(self) -> None:
        """Add new maintenance item."""
        if not self._selected_vehicle:
            QMessageBox.warning(self, "No Vehicle Selected", "Please select a vehicle first.")
            return
        
        dialog = AddMaintenanceDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            logger.info(f"Adding maintenance item: {data}")
            
            # Add to maintenance items
            new_item = {
                "vehicle_id": self._selected_vehicle.get("profile_id"),
                "item": data["item"],
                "due_date": "2024-03-01",  # Calculate based on interval
                "due_mileage": 50000,  # Calculate based on interval
                "priority": "Normal",
                "status": "Upcoming",
                "overdue": False,
            }
            self._maintenance_items.append(new_item)
            self._update_tables()
