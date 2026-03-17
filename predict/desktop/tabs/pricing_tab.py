"""
Pricing Admin Tab -- Parts & services price management for the Qatar market.

Provides CRUD for parts/service prices, web-price search trigger, and
category/text filtering.  Follows the same APIWorker pattern used by
every other desktop tab.
"""

import logging
from datetime import date
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QComboBox, QHeaderView, QLineEdit, QTabWidget,
    QDialog, QFormLayout, QDoubleSpinBox, QSpinBox, QDateEdit, QMessageBox,
    QFrame,
)
from PySide6.QtCore import Qt, QTimer, QDate
from PySide6.QtGui import QColor, QFont

from predict.desktop.workers import APIWorker
from predict.desktop.api_client import PredictAPIClient

logger = logging.getLogger(__name__)

CATEGORIES = [
    "All", "oil", "filter", "battery", "brake_pad",
    "spark_plug", "coolant", "other",
]

COMPONENT_IDS = [
    "engine_oil", "coolant_system", "battery", "brakes",
    "transmission_fluid", "spark_plugs", "catalytic_converter",
    "o2_sensors", "air_filter", "fuel_system",
]

# Reusable dark-theme table stylesheet (matches PIDAtlasTab / other tabs)
_TABLE_STYLE = """
    QTableWidget {
        background-color: #0D1117;
        color: #C9D1D9;
        border: 1px solid #30363D;
        gridline-color: #21262D;
        font-size: 12px;
    }
    QTableWidget::item {
        padding: 4px 8px;
    }
    QTableWidget::item:selected {
        background-color: #1F2937;
    }
    QHeaderView::section {
        background-color: #161B22;
        color: #8B949E;
        border: none;
        border-bottom: 1px solid #30363D;
        padding: 6px 8px;
        font-weight: bold;
        font-size: 11px;
    }
"""

_BTN_PRIMARY = (
    "QPushButton { background-color: #C40000; color: white; "
    "padding: 8px 16px; border-radius: 4px; font-weight: bold; }"
    "QPushButton:hover { background-color: #e04040; }"
)

_BTN_SECONDARY = (
    "QPushButton { background-color: #21262D; color: #C9D1D9; "
    "padding: 6px 14px; border: 1px solid #30363D; border-radius: 4px; }"
    "QPushButton:hover { background-color: #30363D; }"
)

_BTN_DANGER = (
    "QPushButton { background-color: #f85149; color: white; "
    "padding: 4px 10px; border-radius: 3px; font-size: 11px; }"
    "QPushButton:hover { background-color: #ff6e6e; }"
)

_BTN_SUCCESS = (
    "QPushButton { background-color: #2ea043; color: white; "
    "padding: 8px 16px; border-radius: 4px; font-weight: bold; }"
    "QPushButton:hover { background-color: #3fb950; }"
)


# ===================================================================
# Add Price Dialog
# ===================================================================

class AddPriceDialog(QDialog):
    """Dialog for manually adding a new part price."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Part Price")
        self.setMinimumWidth(480)
        self.result_data: Optional[dict] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)

        # Category
        self._category_combo = QComboBox()
        self._category_combo.addItems(CATEGORIES[1:])  # skip "All"
        form.addRow("Category:", self._category_combo)

        # Component ID
        self._component_combo = QComboBox()
        self._component_combo.addItem("")  # optional
        self._component_combo.addItems(COMPONENT_IDS)
        form.addRow("Component:", self._component_combo)

        # Name
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("e.g. Mobil 1 5W-30 Full Synthetic 4L")
        form.addRow("Name:", self._name_input)

        # Brand
        self._brand_input = QLineEdit()
        self._brand_input.setPlaceholderText("e.g. Mobil")
        form.addRow("Brand:", self._brand_input)

        # Part Number
        self._part_number_input = QLineEdit()
        self._part_number_input.setPlaceholderText("e.g. 153668")
        form.addRow("Part Number:", self._part_number_input)

        # Vehicle Make
        self._make_input = QLineEdit()
        self._make_input.setPlaceholderText("e.g. Nissan (leave blank for universal)")
        form.addRow("Vehicle Make:", self._make_input)

        # Vehicle Model
        self._model_input = QLineEdit()
        self._model_input.setPlaceholderText("e.g. Patrol")
        form.addRow("Vehicle Model:", self._model_input)

        # Year Range
        year_layout = QHBoxLayout()
        self._year_min_spin = QSpinBox()
        self._year_min_spin.setRange(1990, 2040)
        self._year_min_spin.setSpecialValueText("Any")
        self._year_min_spin.setValue(1990)
        year_layout.addWidget(self._year_min_spin)
        year_layout.addWidget(QLabel("to"))
        self._year_max_spin = QSpinBox()
        self._year_max_spin.setRange(1990, 2040)
        self._year_max_spin.setSpecialValueText("Any")
        self._year_max_spin.setValue(2040)
        year_layout.addWidget(self._year_max_spin)
        form.addRow("Year Range:", year_layout)

        # Price QAR
        self._price_spin = QDoubleSpinBox()
        self._price_spin.setRange(0.01, 99999.99)
        self._price_spin.setDecimals(2)
        self._price_spin.setSuffix(" QAR")
        self._price_spin.setValue(50.00)
        form.addRow("Price:", self._price_spin)

        # Supplier
        self._supplier_input = QLineEdit()
        self._supplier_input.setPlaceholderText("e.g. Al Muftah Auto Parts")
        form.addRow("Supplier:", self._supplier_input)

        # Price Date
        self._date_edit = QDateEdit()
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDate(QDate.currentDate())
        self._date_edit.setMaximumDate(QDate.currentDate())
        form.addRow("Price Date:", self._date_edit)

        layout.addLayout(form)
        layout.addSpacing(8)

        # Buttons
        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(_BTN_SUCCESS)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def _on_save(self):
        name = self._name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Name is required.")
            return

        data: dict = {
            "category": self._category_combo.currentText(),
            "name": name,
            "price_qar": self._price_spin.value(),
            "source": "admin",
            "price_date": self._date_edit.date().toString("yyyy-MM-dd"),
        }

        component = self._component_combo.currentText()
        if component:
            data["component_id"] = component

        brand = self._brand_input.text().strip()
        if brand:
            data["brand"] = brand

        part_number = self._part_number_input.text().strip()
        if part_number:
            data["part_number"] = part_number

        make = self._make_input.text().strip()
        if make:
            data["vehicle_make"] = make

        model = self._model_input.text().strip()
        if model:
            data["vehicle_model"] = model

        year_min = self._year_min_spin.value()
        year_max = self._year_max_spin.value()
        if year_min > 1990:
            data["year_min"] = year_min
        if year_max < 2040:
            data["year_max"] = year_max

        supplier = self._supplier_input.text().strip()
        if supplier:
            data["supplier"] = supplier

        self.result_data = data
        self.accept()


# ===================================================================
# Pricing Tab
# ===================================================================

class PricingTab(QWidget):
    """Admin tab for managing parts and service prices."""

    def __init__(self, api_client: PredictAPIClient, parent=None):
        super().__init__(parent)
        self._api = api_client
        self._worker: Optional[APIWorker] = None
        self._parts_data: list = []
        self._services_data: list = []

        self._setup_ui()
        self._connect_signals()
        QTimer.singleShot(800, self._load_data)

    # ----------------------------------------------------------------
    # UI Setup
    # ----------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # -- Header bar --
        header = QFrame()
        header.setFixedHeight(50)
        header.setStyleSheet(
            "QFrame { background-color: #0D1117; border-bottom: 1px solid #30363D; }"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)

        title = QLabel("Parts & Services Pricing")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet("color: #F0F6FC;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #8B949E; font-size: 12px;")
        header_layout.addWidget(self._status_label)

        self._add_btn = QPushButton("+ Add Price")
        self._add_btn.setStyleSheet(_BTN_PRIMARY)
        header_layout.addWidget(self._add_btn)

        layout.addWidget(header)

        # -- Filters row --
        filter_frame = QFrame()
        filter_frame.setFixedHeight(44)
        filter_frame.setStyleSheet(
            "QFrame { background-color: #161B22; border-bottom: 1px solid #21262D; }"
        )
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(16, 4, 16, 4)
        filter_layout.setSpacing(10)

        filter_layout.addWidget(QLabel("Category:"))
        self._category_combo = QComboBox()
        self._category_combo.addItems(CATEGORIES)
        self._category_combo.setMinimumWidth(120)
        filter_layout.addWidget(self._category_combo)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search by name, brand, or part number...")
        self._search_input.setMinimumWidth(250)
        filter_layout.addWidget(self._search_input)

        filter_layout.addStretch()
        layout.addWidget(filter_frame)

        # -- Sub-tabs: Parts / Services --
        self._sub_tabs = QTabWidget()
        self._sub_tabs.setStyleSheet("""
            QTabWidget::pane {
                background: #0D1117;
                border: none;
            }
            QTabBar::tab {
                background: #161B22;
                color: #8B949E;
                padding: 8px 20px;
                border: none;
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected {
                color: #F0F6FC;
                border-bottom: 2px solid #C40000;
            }
            QTabBar::tab:hover {
                color: #C9D1D9;
            }
        """)

        # Parts table
        self._parts_table = self._create_table(
            ["Name", "Brand", "Price (QAR)", "Supplier", "Source", "Vehicle", "Actions"]
        )
        self._sub_tabs.addTab(self._parts_table, "Parts")

        # Services table
        self._services_table = self._create_table(
            ["Service", "Labor", "Parts", "Total (QAR)", "Provider", "Vehicle", "Actions"]
        )
        self._sub_tabs.addTab(self._services_table, "Services")

        layout.addWidget(self._sub_tabs)

        # -- Bottom bar --
        bottom = QFrame()
        bottom.setFixedHeight(48)
        bottom.setStyleSheet(
            "QFrame { background-color: #0D1117; border-top: 1px solid #30363D; }"
        )
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(16, 4, 16, 4)

        self._web_search_btn = QPushButton("Search Prices Online")
        self._web_search_btn.setStyleSheet(_BTN_PRIMARY)
        bottom_layout.addWidget(self._web_search_btn)

        bottom_layout.addStretch()

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setStyleSheet(_BTN_SECONDARY)
        bottom_layout.addWidget(self._refresh_btn)

        layout.addWidget(bottom)

    def _create_table(self, columns: list) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSortingEnabled(True)
        table.setStyleSheet(_TABLE_STYLE)

        header = table.horizontalHeader()
        header.setStretchLastSection(True)
        # Stretch the first column (Name/Service), resize others to content
        for col in range(len(columns)):
            if col == 0:
                header.setSectionResizeMode(col, QHeaderView.Stretch)
            else:
                header.setSectionResizeMode(col, QHeaderView.ResizeToContents)

        return table

    # ----------------------------------------------------------------
    # Signals
    # ----------------------------------------------------------------

    def _connect_signals(self):
        self._add_btn.clicked.connect(self._on_add_price)
        self._refresh_btn.clicked.connect(self._load_data)
        self._web_search_btn.clicked.connect(self._on_web_search)
        self._category_combo.currentTextChanged.connect(self._load_data)
        self._search_input.returnPressed.connect(self._load_data)

    # ----------------------------------------------------------------
    # Data Loading
    # ----------------------------------------------------------------

    def _load_data(self):
        if self._worker and self._worker.isRunning():
            return

        self._status_label.setText("Loading...")
        category = self._category_combo.currentText()
        search = self._search_input.text().strip()

        params_parts: dict = {"limit": 200}
        params_services: dict = {"limit": 200}

        if category and category != "All":
            params_parts["category"] = category
        if search:
            params_parts["search"] = search
            params_services["search"] = search

        # Load parts first, then services on completion
        def fetch_parts():
            return self._api.get("/pricing/parts", params=params_parts)

        self._pending_service_params = params_services
        self._worker = APIWorker(fetch_parts)
        self._worker.finished.connect(self._on_parts_loaded)
        self._worker.error.connect(self._on_load_error)
        self._worker.start()

    def _on_parts_loaded(self, data: dict):
        self._parts_data = data.get("parts", [])
        self._populate_parts_table()

        # Now load services
        params = self._pending_service_params

        def fetch_services():
            return self._api.get("/pricing/services", params=params)

        self._worker = APIWorker(fetch_services)
        self._worker.finished.connect(self._on_services_loaded)
        self._worker.error.connect(self._on_load_error)
        self._worker.start()

    def _on_services_loaded(self, data: dict):
        self._services_data = data.get("services", [])
        self._populate_services_table()

        total = len(self._parts_data) + len(self._services_data)
        self._status_label.setText(
            f"{len(self._parts_data)} parts, "
            f"{len(self._services_data)} services"
        )

    def _on_load_error(self, error_msg: str):
        self._status_label.setText(f"Error: {error_msg}")
        logger.error("Pricing load error: %s", error_msg)

    # ----------------------------------------------------------------
    # Table Population
    # ----------------------------------------------------------------

    def _populate_parts_table(self):
        self._parts_table.setSortingEnabled(False)
        self._parts_table.setRowCount(len(self._parts_data))

        for row, p in enumerate(self._parts_data):
            name_item = QTableWidgetItem(p.get("name") or "")
            name_item.setForeground(QColor("#F0F6FC"))
            name_item.setData(Qt.UserRole, p)
            self._parts_table.setItem(row, 0, name_item)

            brand_item = QTableWidgetItem(p.get("brand") or "")
            brand_item.setForeground(QColor("#C9D1D9"))
            self._parts_table.setItem(row, 1, brand_item)

            price_item = QTableWidgetItem(f"{p.get('price_qar', 0):.2f}")
            price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            price_item.setForeground(QColor("#2EA043"))
            price_item.setFont(QFont("Segoe UI", 11, QFont.Bold))
            self._parts_table.setItem(row, 2, price_item)

            supplier_item = QTableWidgetItem(p.get("supplier") or "")
            supplier_item.setForeground(QColor("#C9D1D9"))
            self._parts_table.setItem(row, 3, supplier_item)

            source = p.get("source") or ""
            source_item = QTableWidgetItem(source)
            source_color = QColor("#58A6FF") if source == "web_search" else QColor("#8B949E")
            source_item.setForeground(source_color)
            self._parts_table.setItem(row, 4, source_item)

            vehicle = self._format_vehicle(p)
            vehicle_item = QTableWidgetItem(vehicle)
            vehicle_item.setForeground(QColor("#8B949E"))
            self._parts_table.setItem(row, 5, vehicle_item)

            # Actions: delete button
            delete_btn = QPushButton("Delete")
            delete_btn.setStyleSheet(_BTN_DANGER)
            part_id = p.get("id")
            delete_btn.clicked.connect(lambda checked, pid=part_id: self._on_delete_part(pid))
            self._parts_table.setCellWidget(row, 6, delete_btn)

        self._parts_table.setSortingEnabled(True)

    def _populate_services_table(self):
        self._services_table.setSortingEnabled(False)
        self._services_table.setRowCount(len(self._services_data))

        for row, s in enumerate(self._services_data):
            svc_item = QTableWidgetItem(s.get("service_type") or "")
            svc_item.setForeground(QColor("#F0F6FC"))
            svc_item.setData(Qt.UserRole, s)
            self._services_table.setItem(row, 0, svc_item)

            labor = s.get("labor_qar")
            labor_text = f"{labor:.2f}" if labor is not None else ""
            labor_item = QTableWidgetItem(labor_text)
            labor_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            labor_item.setForeground(QColor("#C9D1D9"))
            self._services_table.setItem(row, 1, labor_item)

            parts = s.get("parts_qar")
            parts_text = f"{parts:.2f}" if parts is not None else ""
            parts_item = QTableWidgetItem(parts_text)
            parts_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            parts_item.setForeground(QColor("#C9D1D9"))
            self._services_table.setItem(row, 2, parts_item)

            total_item = QTableWidgetItem(f"{s.get('total_qar', 0):.2f}")
            total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            total_item.setForeground(QColor("#2EA043"))
            total_item.setFont(QFont("Segoe UI", 11, QFont.Bold))
            self._services_table.setItem(row, 3, total_item)

            provider_item = QTableWidgetItem(s.get("provider") or "")
            provider_item.setForeground(QColor("#C9D1D9"))
            self._services_table.setItem(row, 4, provider_item)

            vehicle = self._format_vehicle(s)
            vehicle_item = QTableWidgetItem(vehicle)
            vehicle_item.setForeground(QColor("#8B949E"))
            self._services_table.setItem(row, 5, vehicle_item)

            # Services have no DELETE endpoint -- leave actions empty
            self._services_table.setItem(row, 6, QTableWidgetItem(""))

        self._services_table.setSortingEnabled(True)

    @staticmethod
    def _format_vehicle(record: dict) -> str:
        make = record.get("vehicle_make") or ""
        model = record.get("vehicle_model") or ""
        year_min = record.get("year_min")
        year_max = record.get("year_max")

        parts = []
        if make:
            parts.append(make)
        if model:
            parts.append(model)
        if year_min and year_max and year_min != year_max:
            parts.append(f"({year_min}-{year_max})")
        elif year_min:
            parts.append(f"({year_min})")

        return " ".join(parts) if parts else "Universal"

    # ----------------------------------------------------------------
    # Add Price
    # ----------------------------------------------------------------

    def _on_add_price(self):
        dialog = AddPriceDialog(self)
        if dialog.exec_() != QDialog.Accepted or not dialog.result_data:
            return

        payload = dialog.result_data

        def do_create():
            return self._api.post("/pricing/parts", json=payload)

        self._status_label.setText("Saving...")
        self._worker = APIWorker(do_create)
        self._worker.finished.connect(self._on_price_created)
        self._worker.error.connect(lambda err: self._on_action_error("Create", err))
        self._worker.start()

    def _on_price_created(self, data: dict):
        self._status_label.setText("Price added.")
        self._load_data()

    # ----------------------------------------------------------------
    # Delete Part
    # ----------------------------------------------------------------

    def _on_delete_part(self, part_id: int):
        reply = QMessageBox.question(
            self,
            "Delete Price",
            f"Delete part price #{part_id}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        def do_delete():
            return self._api.delete(f"/pricing/parts/{part_id}")

        self._status_label.setText("Deleting...")
        self._worker = APIWorker(do_delete)
        self._worker.finished.connect(lambda _: self._on_delete_complete())
        self._worker.error.connect(lambda err: self._on_action_error("Delete", err))
        self._worker.start()

    def _on_delete_complete(self):
        self._status_label.setText("Deleted.")
        self._load_data()

    # ----------------------------------------------------------------
    # Web Price Search
    # ----------------------------------------------------------------

    def _on_web_search(self):
        # Use the first COMPONENT_ID matching current category, or let admin pick
        category = self._category_combo.currentText()
        component_id = ""

        # Map category to a default component_id
        _cat_to_component = {
            "oil": "engine_oil",
            "filter": "air_filter",
            "battery": "battery",
            "brake_pad": "brakes",
            "spark_plug": "spark_plugs",
            "coolant": "coolant_system",
        }
        if category in _cat_to_component:
            component_id = _cat_to_component[category]
        else:
            # Default to first component
            component_id = COMPONENT_IDS[0]

        payload = {"component_id": component_id}

        self._status_label.setText(f"Searching web for {component_id} prices...")
        self._web_search_btn.setEnabled(False)

        def do_search():
            return self._api.post("/pricing/search", json=payload, timeout=60)

        self._worker = APIWorker(do_search)
        self._worker.finished.connect(self._on_web_search_done)
        self._worker.error.connect(self._on_web_search_error)
        self._worker.start()

    def _on_web_search_done(self, data: dict):
        self._web_search_btn.setEnabled(True)
        count = data.get("query_count", 0)
        self._status_label.setText(f"Web search returned {count} results.")

        results = data.get("results", [])
        if not results:
            QMessageBox.information(
                self, "Web Search", "No prices found online for this component."
            )
            return

        # Show summary
        lines = []
        for r in results[:10]:
            name = r.get("name", "?")
            price = r.get("price_qar", 0)
            source = r.get("source_url") or r.get("source", "")
            lines.append(f"  {name}: {price:.0f} QAR ({source})")

        QMessageBox.information(
            self,
            "Web Search Results",
            f"Found {count} price(s). Top results:\n\n" + "\n".join(lines)
            + "\n\nUse '+ Add Price' to save any to the database.",
        )

    def _on_web_search_error(self, error_msg: str):
        self._web_search_btn.setEnabled(True)
        self._status_label.setText("Web search failed.")
        QMessageBox.warning(
            self, "Web Search Failed",
            f"Could not complete price search:\n{error_msg}",
        )

    # ----------------------------------------------------------------
    # Error Helpers
    # ----------------------------------------------------------------

    def _on_action_error(self, action: str, error_msg: str):
        self._status_label.setText(f"{action} failed.")
        logger.error("Pricing %s error: %s", action, error_msg)
        QMessageBox.critical(
            self, f"{action} Failed",
            f"Could not complete {action.lower()}:\n{error_msg}",
        )

    def cleanup(self):
        """Called by main_window on close."""
        pass
