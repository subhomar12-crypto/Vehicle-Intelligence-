"""
PDF Reports Tab - Report generation and monitoring.

Tab 4 of 6 in the PREDICT Desktop GUI.
"""

import logging
import time
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGroupBox, QLineEdit, QComboBox, QListWidget, QListWidgetItem,
    QCheckBox, QRadioButton, QButtonGroup, QProgressBar, QTableWidget,
    QTableWidgetItem, QMessageBox, QFileDialog, QCompleter
)
from PySide6.QtCore import QTimer, Qt, QStringListModel

from predict.desktop.theme import PredictTheme, get_table_stylesheet
from predict.desktop.workers import APIWorker
from predict.desktop.api_client import PredictAPIClient

logger = logging.getLogger(__name__)


class PDFTab(QWidget):
    """Tab for PDF report generation."""

    def __init__(self, api_client: PredictAPIClient, parent=None):
        super().__init__(parent)
        self._api = api_client
        self._selected_owner_id = None
        self._vehicles = []
        self._pending_reports = {}  # report_id -> timer

        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI layout."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Generate Report Section
        generate_group = QGroupBox("Generate New Report")
        generate_layout = QVBoxLayout(generate_group)

        # Owner search with type-ahead autocomplete
        owner_layout = QHBoxLayout()
        owner_layout.addWidget(QLabel("Owner:"))
        self._owner_search = QLineEdit()
        self._owner_search.setPlaceholderText("Search by name, email, or plate...")
        self._owner_search.returnPressed.connect(self._on_search_owner)

        # Setup type-ahead autocomplete
        self._autocomplete = QCompleter()
        self._autocomplete.setCaseSensitivity(Qt.CaseInsensitive)
        self._autocomplete.setFilterMode(Qt.MatchContains)
        self._owner_search.setCompleter(self._autocomplete)
        self._autocomplete.activated.connect(self._on_autocomplete_selected)

        # Debounce timer for type-ahead search
        self._autocomplete_timer = QTimer(self)
        self._autocomplete_timer.setSingleShot(True)
        self._autocomplete_timer.setInterval(300)
        self._autocomplete_timer.timeout.connect(self._on_autocomplete_search)
        self._owner_search.textChanged.connect(self._on_text_changed)

        # Cache for autocomplete results: display_text -> user_id
        self._autocomplete_map = {}

        owner_layout.addWidget(self._owner_search)

        self._search_btn = QPushButton("Search")
        self._search_btn.clicked.connect(self._on_search_owner)
        owner_layout.addWidget(self._search_btn)
        generate_layout.addLayout(owner_layout)

        # Owner results combo
        self._owner_combo = QComboBox()
        self._owner_combo.currentIndexChanged.connect(self._on_owner_selected)
        generate_layout.addWidget(self._owner_combo)

        # Vehicle list
        self._vehicle_list = QListWidget()
        self._vehicle_list.setSelectionMode(QListWidget.MultiSelection)
        generate_layout.addWidget(QLabel("Select Vehicles:"))
        generate_layout.addWidget(self._vehicle_list)

        # Report type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Report Type:"))
        self._report_type = QComboBox()
        self._report_type.addItems([
            "Full Diagnostic", "Maintenance", "Trip Summary", "Invoice"
        ])
        type_layout.addWidget(self._report_type)
        type_layout.addStretch()
        generate_layout.addLayout(type_layout)

        # Options
        options_layout = QHBoxLayout()
        self._combined_radio = QRadioButton("Combined")
        self._separate_radio = QRadioButton("Separate")
        self._combined_radio.setChecked(True)
        self._option_group = QButtonGroup()
        self._option_group.addButton(self._combined_radio)
        self._option_group.addButton(self._separate_radio)

        self._include_llm = QCheckBox("Include LLM")

        options_layout.addWidget(self._combined_radio)
        options_layout.addWidget(self._separate_radio)
        options_layout.addWidget(self._include_llm)
        options_layout.addStretch()
        generate_layout.addLayout(options_layout)

        # Generate button and progress
        gen_btn_layout = QHBoxLayout()
        self._generate_btn = QPushButton("Generate Report")
        self._generate_btn.setObjectName("primary")
        self._generate_btn.setStyleSheet(
            f"background-color: {PredictTheme.PRIMARY}; color: white; padding: 8px 16px;"
        )
        self._generate_btn.clicked.connect(self._on_generate)

        self._progress = QProgressBar()
        self._progress.setVisible(False)

        gen_btn_layout.addWidget(self._generate_btn)
        gen_btn_layout.addWidget(self._progress)
        gen_btn_layout.addStretch()
        generate_layout.addLayout(gen_btn_layout)

        layout.addWidget(generate_group)

        # Recent Reports Section
        recent_group = QGroupBox("Recent Reports")
        recent_layout = QVBoxLayout(recent_group)

        self._reports_table = QTableWidget()
        self._reports_table.setColumnCount(6)
        self._reports_table.setHorizontalHeaderLabels(
            ["Date", "Owner", "Vehicle", "Type", "Status", "Actions"]
        )
        self._reports_table.setStyleSheet(get_table_stylesheet())
        recent_layout.addWidget(self._reports_table)

        layout.addWidget(recent_group)

    def _on_search_owner(self):
        """Search for owner."""
        query = self._owner_search.text().strip()
        if not query:
            return

        self._search_btn.setEnabled(False)
        worker = APIWorker(self._api.search_users, query, 20)
        worker.finished.connect(self._on_search_results)
        worker.error.connect(self._on_search_error)
        worker.start()

    def _on_search_results(self, result: dict):
        """Handle search results."""
        self._search_btn.setEnabled(True)
        users = result.get("users", [])

        self._owner_combo.clear()

        for user in users:
            name = user.get("name", "Unknown")
            email = user.get("email", "")
            display = f"{name} ({email})"
            self._owner_combo.addItem(display, user.get("id"))

    def _on_text_changed(self, text: str):
        """Handle text input change — debounced type-ahead."""
        if len(text.strip()) >= 2:
            self._autocomplete_timer.start()
        else:
            self._autocomplete_timer.stop()

    def _on_autocomplete_search(self):
        """Fire autocomplete search after debounce."""
        query = self._owner_search.text().strip()
        if len(query) < 2:
            return

        worker = APIWorker(self._api.search_users, query, 10)
        worker.finished.connect(self._on_autocomplete_results)
        worker.start()

    def _on_autocomplete_results(self, result: dict):
        """Update autocomplete dropdown with search results."""
        users = result.get("users", [])
        suggestions = []
        self._autocomplete_map.clear()

        for user in users:
            name = user.get("name", "Unknown")
            email = user.get("email", "")
            display = f"{name} ({email})"
            suggestions.append(display)
            self._autocomplete_map[display] = user.get("id")

        model = QStringListModel()
        model.setStringList(suggestions)
        self._autocomplete.setModel(model)
        if suggestions:
            self._autocomplete.complete()

    def _on_autocomplete_selected(self, text: str):
        """Handle autocomplete selection — set owner directly."""
        user_id = self._autocomplete_map.get(text)
        if user_id:
            self._selected_owner_id = user_id
            self._owner_search.setText(text)
            # Block the timer from re-firing
            self._autocomplete_timer.stop()
            # Populate the combo and load vehicles
            self._owner_combo.clear()
            self._owner_combo.addItem(text, user_id)
            self._owner_combo.setCurrentIndex(0)
            # Load vehicles directly
            worker = APIWorker(self._api.get_user_vehicles, user_id)
            worker.finished.connect(self._on_vehicles_loaded)
            worker.start()

    def _on_search_error(self, error_msg: str):
        """Handle search error."""
        self._search_btn.setEnabled(True)
        logger.error(f"Search error: {error_msg}")

    def _on_owner_selected(self, index: int):
        """Handle owner selection."""
        user_id = self._owner_combo.itemData(index)
        if not user_id:
            return

        self._selected_owner_id = user_id

        # Load vehicles
        worker = APIWorker(self._api.get_user_vehicles, user_id)
        worker.finished.connect(self._on_vehicles_loaded)
        worker.start()

    def _on_vehicles_loaded(self, result: dict):
        """Handle vehicles loaded."""
        vehicles = result.get("vehicles", [])
        self._vehicles = vehicles

        self._vehicle_list.clear()
        for v in vehicles:
            name = f"{v.get('make', '')} {v.get('model', '')} ({v.get('year', '')})"
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, v.get("id"))
            item.setCheckState(Qt.Unchecked)
            self._vehicle_list.addItem(item)

    def _on_generate(self):
        """Generate report."""
        if not self._selected_owner_id:
            QMessageBox.warning(self, "Warning", "Please select an owner first")
            return

        # Get selected vehicles
        selected_vehicles = []
        for i in range(self._vehicle_list.count()):
            item = self._vehicle_list.item(i)
            if item.checkState() == Qt.Checked:
                selected_vehicles.append(item.data(Qt.UserRole))

        if not selected_vehicles:
            QMessageBox.warning(self, "Warning", "Please select at least one vehicle")
            return

        self._generate_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)

        report_type = self._report_type.currentText().lower().replace(" ", "_")
        include_llm = self._include_llm.isChecked()

        # Generate for each vehicle
        for vehicle_id in selected_vehicles:
            worker = APIWorker(
                self._api.generate_report,
                vehicle_id,
                report_type,
                include_llm
            )
            worker.finished.connect(self._on_report_generated)
            worker.error.connect(self._on_generate_error)
            worker.start()

    def _on_report_generated(self, result: dict):
        """Handle report generation started."""
        report_id = result.get("report_id")
        if report_id:
            # Start polling for status
            timer = QTimer(self)
            timer.timeout.connect(lambda: self._check_report_status(report_id))
            timer.start(2000)
            self._pending_reports[report_id] = timer

        self._progress.setValue(50)

    def _on_generate_error(self, error_msg: str):
        """Handle generate error."""
        self._generate_btn.setEnabled(True)
        self._progress.setVisible(False)
        QMessageBox.critical(self, "Error", f"Failed to generate report:\n{error_msg}")

    def _check_report_status(self, report_id: int):
        """Check report generation status."""
        worker = APIWorker(self._api.get_report_status, report_id)
        worker.finished.connect(lambda r: self._on_status_update(report_id, r))
        worker.start()

    def _on_status_update(self, report_id: int, result: dict):
        """Handle status update."""
        status = result.get("status", "unknown")

        if status == "ready":
            # Stop polling
            timer = self._pending_reports.pop(report_id, None)
            if timer:
                timer.stop()

            self._progress.setValue(100)
            self._generate_btn.setEnabled(True)
            QMessageBox.information(self, "Success", "Report generated successfully!")
            self._load_report_history()

        elif status == "failed":
            timer = self._pending_reports.pop(report_id, None)
            if timer:
                timer.stop()

    def _load_report_history(self):
        """Load report history."""
        worker = APIWorker(self._api.get_report_history, 50)
        worker.finished.connect(self._on_history_loaded)
        worker.start()

    def _on_history_loaded(self, result: dict):
        """Handle history loaded."""
        reports = result.get("reports", [])
        self._reports_table.setRowCount(len(reports))

        for i, r in enumerate(reports):
            self._reports_table.setItem(i, 0, QTableWidgetItem(
                self._format_timestamp(r.get("created_at"))
            ))
            self._reports_table.setItem(i, 1, QTableWidgetItem("Owner"))
            self._reports_table.setItem(i, 2, QTableWidgetItem(str(r.get("vehicle_id"))))
            self._reports_table.setItem(i, 3, QTableWidgetItem(r.get("report_type", "Unknown")))

            status = r.get("status", "Unknown")
            status_item = QTableWidgetItem(status)
            if status == "ready":
                status_item.setForeground(Qt.green)
            elif status == "generating":
                status_item.setForeground(Qt.yellow)
            else:
                status_item.setForeground(Qt.red)
            self._reports_table.setItem(i, 4, status_item)

            # Actions buttons
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 4, 4, 4)

            download_btn = QPushButton("Download")
            download_btn.clicked.connect(lambda checked, rid=r.get("id"): self._on_download(rid))

            delete_btn = QPushButton("Delete")
            delete_btn.clicked.connect(lambda checked, rid=r.get("id"): self._on_delete(rid))

            actions_layout.addWidget(download_btn)
            actions_layout.addWidget(delete_btn)
            self._reports_table.setCellWidget(i, 5, actions_widget)

    def _on_download(self, report_id: int):
        """Download report."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Report", f"report_{report_id}.pdf", "PDF Files (*.pdf)"
        )
        if not file_path:
            return

        self._download_path = file_path
        worker = APIWorker(self._api.download_report, report_id)
        worker.finished.connect(lambda resp: self._on_download_complete(resp, file_path))
        worker.error.connect(lambda e: QMessageBox.critical(self, "Error", f"Download failed: {e}"))
        worker.start()

    def _on_download_complete(self, response, file_path: str):
        """Handle download complete — write file."""
        try:
            with open(file_path, "wb") as f:
                f.write(response.content)
            QMessageBox.information(self, "Success", "Report downloaded successfully")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file: {e}")

    def _on_delete(self, report_id: int):
        """Delete report."""
        reply = QMessageBox.question(
            self, "Confirm", "Delete this report?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            worker = APIWorker(self._api.delete_report, report_id)
            worker.finished.connect(self._load_report_history)
            worker.start()

    def _format_timestamp(self, ts: float) -> str:
        """Format timestamp."""
        if not ts:
            return "N/A"
        try:
            return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
        except Exception:
            return str(ts)
