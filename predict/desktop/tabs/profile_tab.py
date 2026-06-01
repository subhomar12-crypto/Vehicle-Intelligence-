"""
Profile Management Tab - User search, list, and detail view.

Tab 1 of 6 in the PREDICT Desktop GUI.
"""

import logging
import time
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel, QHeaderView, QMessageBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from predict.desktop.theme import PredictTheme, get_table_stylesheet
from predict.desktop.workers import APIWorker
from predict.desktop.api_client import PredictAPIClient

logger = logging.getLogger(__name__)


class ProfileTab(QWidget):
    """Tab for managing user profiles."""

    def __init__(self, api_client: PredictAPIClient, ws_listener=None, parent=None):
        super().__init__(parent)
        self._api = api_client
        self._ws_listener = ws_listener
        self._offset = 0
        self._limit = 50
        self._current_query = ""
        self._total_users = 0
        self._worker = None

        self._setup_ui()
        self._connect_signals()

        # Connect WebSocket if provided
        if ws_listener:
            ws_listener.user_change.connect(self._on_user_change)


    def _setup_ui(self):
        """Set up the UI layout."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Top: Search bar
        search_layout = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search by name, email, or plate...")
        self._search_input.setMinimumWidth(300)

        self._search_btn = QPushButton("Search")
        self._refresh_btn = QPushButton("Refresh")

        search_layout.addWidget(self._search_input)
        search_layout.addWidget(self._search_btn)
        search_layout.addWidget(self._refresh_btn)
        search_layout.addStretch()

        layout.addLayout(search_layout)

        # Middle: Users table
        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels(
            ["Name", "Email", "Plate", "Tier", "Status", "Last Seen", "Actions"]
        )
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setStyleSheet(get_table_stylesheet())

        layout.addWidget(self._table)

        # Bottom: Pagination
        pagination_layout = QHBoxLayout()
        self._showing_label = QLabel("Showing 0 users")
        self._prev_btn = QPushButton("Prev")
        self._next_btn = QPushButton("Next")

        pagination_layout.addWidget(self._showing_label)
        pagination_layout.addStretch()
        pagination_layout.addWidget(self._prev_btn)
        pagination_layout.addWidget(self._next_btn)

        layout.addLayout(pagination_layout)

        self.setLayout(layout)

    def _connect_signals(self):
        """Connect widget signals to slots."""
        self._search_btn.clicked.connect(self._on_search)
        self._search_input.returnPressed.connect(self._on_search)
        self._refresh_btn.clicked.connect(self._on_refresh)
        self._prev_btn.clicked.connect(self._on_prev_page)
        self._next_btn.clicked.connect(self._on_next_page)
        self._table.cellDoubleClicked.connect(self._on_row_double_clicked)

    def _on_search(self):
        """Handle search button click."""
        self._current_query = self._search_input.text().strip()
        self._offset = 0
        self._load_users()

    def _on_refresh(self):
        """Handle refresh button click."""
        self._load_users()

    def _on_prev_page(self):
        """Go to previous page."""
        if self._offset >= self._limit:
            self._offset -= self._limit
            self._load_users()

    def _on_next_page(self):
        """Go to next page."""
        if self._offset + self._limit < self._total_users:
            self._offset += self._limit
            self._load_users()

    def _on_user_change(self, data: dict):
        """Handle WebSocket user change event."""
        logger.debug(f"User change received: {data}")
        self._load_users()

    def _load_users(self):
        """Load users from API."""
        self._search_btn.setEnabled(False)
        self._refresh_btn.setEnabled(False)

        self._worker = APIWorker(
            self._api.search_users,
            self._current_query,
            self._limit,
            self._offset
        )
        self._worker.finished.connect(self._on_users_loaded)
        self._worker.error.connect(self._on_load_error)
        self._worker.start()

    def _on_users_loaded(self, result: dict):
        """Handle users loaded from API."""
        self._search_btn.setEnabled(True)
        self._refresh_btn.setEnabled(True)

        users = result.get("users", [])
        self._total_users = result.get("total", 0)

        self._populate_table(users)
        self._update_pagination()

    def _on_load_error(self, error_msg: str):
        """Handle load error."""
        self._search_btn.setEnabled(True)
        self._refresh_btn.setEnabled(True)
        logger.error(f"Failed to load users: {error_msg}")

    def _populate_table(self, users: list):
        """Populate the table with user data."""
        self._table.setRowCount(len(users))

        for row, user in enumerate(users):
            user_id = user.get("id", 0)
            name = user.get("name", "N/A")
            email = user.get("email", "N/A")
            plate = user.get("car_plate", "N/A")
            tier = user.get("tier", "free")
            status = user.get("status", "active").capitalize()
            last_login = user.get("last_login")

            # Name item with user_id stored
            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.UserRole, user_id)
            self._table.setItem(row, 0, name_item)

            self._table.setItem(row, 1, QTableWidgetItem(email))
            self._table.setItem(row, 2, QTableWidgetItem(plate))

            # Tier with color coding
            tier_item = QTableWidgetItem(tier.capitalize())
            tier_color = self._get_tier_color(tier)
            if tier_color:
                tier_item.setBackground(QColor(tier_color))
            self._table.setItem(row, 3, tier_item)

            self._table.setItem(row, 4, QTableWidgetItem(status))

            # Last seen relative time
            last_seen = self._format_relative_time(last_login)
            self._table.setItem(row, 5, QTableWidgetItem(last_seen))
            
            # Actions: Delete button
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)
            
            delete_btn = QPushButton("Delete")
            delete_btn.setStyleSheet(f"background-color: {PredictTheme.DANGER}; color: white; padding: 2px 8px;")
            delete_btn.clicked.connect(lambda checked, uid=user_id, uname=name: self._on_delete_user(uid, uname))
            
            actions_layout.addWidget(delete_btn)
            actions_layout.addStretch()
            self._table.setCellWidget(row, 6, actions_widget)

    def _get_tier_color(self, tier: str) -> Optional[str]:
        """Get color for tier."""
        tier_colors = {
            "free": PredictTheme.TEXT_MUTED,
            "pro": PredictTheme.SUCCESS,
            "premium": PredictTheme.WARNING,
            "admin": PredictTheme.DANGER,
        }
        return tier_colors.get(tier.lower())

    def _format_relative_time(self, timestamp: Optional[float]) -> str:
        """Format timestamp as relative time."""
        if not timestamp:
            return "Never"

        now = time.time()
        diff = now - timestamp

        if diff < 60:
            return "Just now"
        elif diff < 3600:
            return f"{int(diff // 60)} min ago"
        elif diff < 86400:
            return f"{int(diff // 3600)} hours ago"
        else:
            return f"{int(diff // 86400)} days ago"

    def _update_pagination(self):
        """Update pagination controls."""
        start = self._offset + 1
        end = min(self._offset + self._limit, self._total_users)
        self._showing_label.setText(f"Showing {start}-{end} of {self._total_users} users")

        self._prev_btn.setEnabled(self._offset > 0)
        self._next_btn.setEnabled(self._offset + self._limit < self._total_users)

    def _on_row_double_clicked(self, row: int, column: int):
        """Handle row double-click to open user detail."""
        # Ignore if clicking on actions column
        if column == 6:
            return
            
        name_item = self._table.item(row, 0)
        if not name_item:
            return

        user_id = name_item.data(Qt.UserRole)
        if not user_id:
            return

        # Import here to avoid circular imports
        from predict.desktop.tabs.user_detail_dialog import UserDetailDialog

        dialog = UserDetailDialog(user_id, self._api, self)
        dialog.exec()

        # Refresh after dialog closes
        self._load_users()

    def _on_delete_user(self, user_id: int, user_name: str):
        """Handle delete user button click."""
        reply = QMessageBox.warning(
            self, "Confirm Delete",
            f"Are you sure you want to delete user '{user_name}'?\n\n"
            "This will permanently delete all user data including vehicles, "
            "predictions, and API keys.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return

        self._worker = APIWorker(self._api.delete_user, user_id, hard_delete=True)
        self._worker.finished.connect(lambda r: self._on_delete_complete(r, user_name))
        self._worker.error.connect(lambda e: self._on_delete_error(e, user_name))
        self._worker.start()

    def _on_delete_complete(self, result: dict, user_name: str):
        """Handle user deletion complete."""
        QMessageBox.information(self, "Success", f"User '{user_name}' deleted successfully.")
        self._load_users()  # Refresh the table

    def _on_delete_error(self, error_msg: str, user_name: str):
        """Handle user deletion error."""
        QMessageBox.critical(self, "Error", f"Failed to delete '{user_name}':\n{error_msg}")
