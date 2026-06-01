"""
Fleet Requests Management Tab — Admin fleet access request approval.

Tab 7 of 7 in the PREDICT Desktop GUI.
Displays incoming fleet access requests, allows approve (with vehicle limit
and auto API key generation) or deny.
"""

import logging
import time
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QComboBox, QHeaderView, QDialog, QSpinBox,
    QLineEdit, QMessageBox, QApplication, QInputDialog,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont

from predict.desktop.workers import APIWorker
from predict.desktop.api_client import PredictAPIClient

logger = logging.getLogger(__name__)


def _relative_time(ts: float) -> str:
    """Convert timestamp to relative time string."""
    if not ts:
        return "—"
    delta = time.time() - ts
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta / 60)}m ago"
    if delta < 86400:
        return f"{int(delta / 3600)}h ago"
    return f"{int(delta / 86400)}d ago"


class FleetApprovalDialog(QDialog):
    """Dialog for approving a fleet request with vehicle limit and notes."""

    def __init__(self, request_data: dict, parent=None):
        super().__init__(parent)
        self.request_data = request_data
        self.result_data = None
        self.setWindowTitle("Approve Fleet Request")
        self.setMinimumWidth(450)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Request info
        info_label = QLabel(
            f"<b>Company:</b> {self.request_data.get('company_name', '—')}<br>"
            f"<b>Contact:</b> {self.request_data.get('name', '—')} "
            f"({self.request_data.get('email', '—')})<br>"
            f"<b>Requested Cars:</b> {self.request_data.get('fleet_size', '—')}<br>"
            f"<b>Current Tier:</b> {self.request_data.get('current_tier', '—')}"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Message from requester
        notes = self.request_data.get("notes")
        if notes:
            msg_label = QLabel(f"<b>Message:</b> {notes}")
            msg_label.setWordWrap(True)
            layout.addWidget(msg_label)

        layout.addSpacing(8)

        # Vehicle limit
        limit_layout = QHBoxLayout()
        limit_label = QLabel("Vehicle Limit:")
        self._limit_spin = QSpinBox()
        self._limit_spin.setRange(1, 500)
        try:
            default_limit = int(self.request_data.get("fleet_size", "3"))
        except (ValueError, TypeError):
            default_limit = 3
        self._limit_spin.setValue(default_limit)
        limit_layout.addWidget(limit_label)
        limit_layout.addWidget(self._limit_spin)
        limit_layout.addStretch()
        layout.addLayout(limit_layout)

        # Admin notes
        notes_label = QLabel("Admin Notes (optional):")
        self._notes_input = QLineEdit()
        self._notes_input.setPlaceholderText("e.g. Payment received via bank transfer")
        layout.addWidget(notes_label)
        layout.addWidget(self._notes_input)

        # What happens
        summary = QLabel(
            "<br><b>On approval:</b><br>"
            "• Tier upgraded to <span style='color:#C40000'>Premium</span><br>"
            "• Vehicle limit set to custom value<br>"
            "• API key auto-generated"
        )
        summary.setWordWrap(True)
        layout.addWidget(summary)

        # Buttons
        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        approve_btn = QPushButton("Approve && Generate Key")
        approve_btn.setStyleSheet(
            "QPushButton { background-color: #2ea043; color: white; "
            "padding: 8px 16px; border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #3fb950; }"
        )
        approve_btn.clicked.connect(self._on_approve)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(approve_btn)
        layout.addLayout(btn_layout)

    def _on_approve(self):
        self.result_data = {
            "vehicle_limit": self._limit_spin.value(),
            "notes": self._notes_input.text().strip(),
        }
        self.accept()


class ApiKeyResultDialog(QDialog):
    """Dialog showing the generated API key after approval."""

    def __init__(self, result: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fleet Access Granted")
        self.setMinimumWidth(500)
        self._setup_ui(result)

    def _setup_ui(self, result: dict):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        summary = QLabel(
            f"<span style='color:#2ea043; font-size:16px'>Fleet Access Granted</span><br><br>"
            f"<b>User ID:</b> {result.get('user_id')}<br>"
            f"<b>New Tier:</b> Premium<br>"
            f"<b>Vehicle Limit:</b> {result.get('vehicle_limit')}<br>"
            f"<b>Key Name:</b> {result.get('key_name')}"
        )
        summary.setWordWrap(True)
        layout.addWidget(summary)

        key_label = QLabel("<b>API Key (copy and send to customer):</b>")
        layout.addWidget(key_label)

        self._key_display = QLineEdit()
        self._key_display.setText(result.get("api_key", ""))
        self._key_display.setReadOnly(True)
        self._key_display.setStyleSheet(
            "QLineEdit { background-color: #0d1117; color: #58a6ff; "
            "font-family: Consolas, monospace; font-size: 13px; "
            "padding: 10px; border: 1px solid #30363d; border-radius: 4px; }"
        )
        self._key_display.selectAll()
        layout.addWidget(self._key_display)

        btn_layout = QHBoxLayout()
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.setStyleSheet(
            "QPushButton { background-color: #C40000; color: white; "
            "padding: 8px 16px; border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #e04040; }"
        )
        copy_btn.clicked.connect(self._copy_key)
        done_btn = QPushButton("Done")
        done_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(copy_btn)
        btn_layout.addWidget(done_btn)
        layout.addLayout(btn_layout)

    def _copy_key(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self._key_display.text())
        QMessageBox.information(self, "Copied", "API key copied to clipboard.")


STATUS_COLORS = {
    "pending": QColor("#d29922"),
    "approved": QColor("#2ea043"),
    "rejected": QColor("#f85149"),
}


class FleetRequestsTab(QWidget):
    """Tab for managing fleet access requests."""

    def __init__(self, api_client: PredictAPIClient, parent=None):
        super().__init__(parent)
        self._api = api_client
        self._worker: Optional[APIWorker] = None
        self._pending_count = 0

        self._setup_ui()
        self._connect_signals()

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._load_data)
        self._poll_timer.start(30_000)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Top bar
        top_layout = QHBoxLayout()
        filter_label = QLabel("Status:")
        self._filter_combo = QComboBox()
        self._filter_combo.addItems(["pending", "approved", "rejected", "all"])
        self._filter_combo.setCurrentText("pending")
        self._filter_combo.setMinimumWidth(120)

        self._refresh_btn = QPushButton("Refresh")
        self._pending_label = QLabel("")
        self._pending_label.setStyleSheet("color: #d29922; font-weight: bold;")

        top_layout.addWidget(filter_label)
        top_layout.addWidget(self._filter_combo)
        top_layout.addWidget(self._refresh_btn)
        top_layout.addStretch()
        top_layout.addWidget(self._pending_label)
        layout.addLayout(top_layout)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(8)
        self._table.setHorizontalHeaderLabels([
            "Name", "Email", "Company", "Fleet Size",
            "Current Tier", "Status", "Requested", "Actions"
        ])
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setStretchLastSection(True)

        header = self._table.horizontalHeader()
        header.resizeSection(0, 140)
        header.resizeSection(1, 200)
        header.resizeSection(2, 150)
        header.resizeSection(3, 80)
        header.resizeSection(4, 90)
        header.resizeSection(5, 80)
        header.resizeSection(6, 100)
        layout.addWidget(self._table)

        # Bottom actions
        action_layout = QHBoxLayout()
        self._approve_btn = QPushButton("Approve Selected")
        self._approve_btn.setStyleSheet(
            "QPushButton { background-color: #2ea043; color: white; "
            "padding: 8px 16px; border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #3fb950; }"
        )
        self._deny_btn = QPushButton("Deny Selected")
        self._deny_btn.setStyleSheet(
            "QPushButton { background-color: #f85149; color: white; "
            "padding: 8px 16px; border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #ff6e6e; }"
        )
        action_layout.addStretch()
        action_layout.addWidget(self._approve_btn)
        action_layout.addWidget(self._deny_btn)
        layout.addLayout(action_layout)

    def _connect_signals(self):
        self._filter_combo.currentTextChanged.connect(self._load_data)
        self._refresh_btn.clicked.connect(self._load_data)
        self._approve_btn.clicked.connect(self._on_approve)
        self._deny_btn.clicked.connect(self._on_deny)

    def _load_data(self):
        if self._worker and self._worker.isRunning():
            return
        status_filter = self._filter_combo.currentText()
        self._worker = APIWorker(
            self._api.get_fleet_requests,
            status=status_filter,
            limit=100,
        )
        self._worker.finished.connect(self._on_data_loaded)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_data_loaded(self, data: dict):
        requests_list = data.get("requests", [])
        self._table.setRowCount(len(requests_list))

        pending = 0
        for row, req in enumerate(requests_list):
            name_item = QTableWidgetItem(req.get("name") or "—")
            name_item.setData(Qt.UserRole, req)
            self._table.setItem(row, 0, name_item)
            self._table.setItem(row, 1, QTableWidgetItem(req.get("email") or "—"))
            self._table.setItem(row, 2, QTableWidgetItem(req.get("company_name") or "—"))
            self._table.setItem(row, 3, QTableWidgetItem(req.get("fleet_size") or "—"))
            self._table.setItem(row, 4, QTableWidgetItem(req.get("current_tier") or "—"))

            status = req.get("status", "pending")
            status_item = QTableWidgetItem(status.capitalize())
            color = STATUS_COLORS.get(status, QColor("#8b949e"))
            status_item.setForeground(color)
            font = QFont()
            font.setBold(True)
            status_item.setFont(font)
            self._table.setItem(row, 5, status_item)

            self._table.setItem(row, 6, QTableWidgetItem(
                _relative_time(req.get("requested_at", 0))
            ))

            if status == "pending":
                pending += 1
                self._table.setItem(row, 7, QTableWidgetItem("Select row to act"))
            else:
                self._table.setItem(row, 7, QTableWidgetItem("—"))

        self._pending_count = pending
        self._update_pending_label()

    def _on_error(self, error_msg: str):
        logger.error(f"Fleet requests load failed: {error_msg}")

    def _update_pending_label(self):
        if self._pending_count > 0:
            self._pending_label.setText(f"Pending: {self._pending_count}")
        else:
            self._pending_label.setText("")

    def _get_selected_request(self) -> Optional[dict]:
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a request first.")
            return None
        item = self._table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _on_approve(self):
        req = self._get_selected_request()
        if not req:
            return
        if req.get("status") != "pending":
            QMessageBox.warning(self, "Not Pending", "This request has already been processed.")
            return

        dialog = FleetApprovalDialog(req, self)
        if dialog.exec_() != QDialog.Accepted:
            return

        result_data = dialog.result_data
        request_id = req["request_id"]

        self._worker = APIWorker(
            self._api.approve_fleet_request,
            request_id=request_id,
            vehicle_limit=result_data["vehicle_limit"],
            notes=result_data["notes"],
        )
        self._worker.finished.connect(self._on_approve_complete)
        self._worker.error.connect(lambda err: QMessageBox.critical(
            self, "Approval Failed", f"Could not approve request:\n{err}"
        ))
        self._worker.start()

    def _on_approve_complete(self, result: dict):
        key_dialog = ApiKeyResultDialog(result, self)
        key_dialog.exec_()
        self._load_data()

    def _on_deny(self):
        req = self._get_selected_request()
        if not req:
            return
        if req.get("status") != "pending":
            QMessageBox.warning(self, "Not Pending", "This request has already been processed.")
            return

        reason, ok = QInputDialog.getText(
            self, "Deny Fleet Request",
            f"Deny request from {req.get('name', '—')} ({req.get('company_name', '—')})?\n\n"
            "Reason (optional):"
        )
        if not ok:
            return

        request_id = req["request_id"]
        self._worker = APIWorker(
            self._api.deny_fleet_request,
            request_id=request_id,
            reason=reason,
        )
        self._worker.finished.connect(lambda _: self._on_deny_complete())
        self._worker.error.connect(lambda err: QMessageBox.critical(
            self, "Denial Failed", f"Could not deny request:\n{err}"
        ))
        self._worker.start()

    def _on_deny_complete(self):
        QMessageBox.information(self, "Denied", "Fleet request has been denied.")
        self._load_data()

    def get_pending_count(self) -> int:
        return self._pending_count

    def cleanup(self):
        self._poll_timer.stop()
