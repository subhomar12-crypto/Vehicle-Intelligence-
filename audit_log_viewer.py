"""
PREDICT - Vehicle Intelligence Platform
Copyright (c) 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: February 2026
Module: Audit Log Viewer Dialog

Standalone dialog for viewing the subscription audit log.
Can view all entries or filter by specific user.
Supports filtering by action type, date range, and export to CSV.
"""

import logging
import sqlite3
import csv
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QLineEdit, QComboBox, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QDateEdit,
    QFrame, QSpinBox, QFileDialog, QWidget, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtGui import QFont

logger = logging.getLogger(__name__)

# Database path
DB_PATH = Path("C:/OBDserver/Previlium_OBD_Server/data/predict.db")


class AuditLogViewer(QDialog):
    """
    Standalone Audit Log Viewer Dialog

    Shows subscription audit log entries with filtering:
    - Filter by user (optional)
    - Filter by action type
    - Filter by date range
    - Pagination for large datasets
    - Export to CSV
    """

    # Action types for filtering
    ACTION_TYPES = [
        ("All Actions", None),
        ("Tier Change", "tier_change"),
        ("Limit Change", "limit_change"),
        ("Feature Toggle", "feature_toggle"),
        ("Suspend", "suspend"),
        ("Activate", "activate"),
        ("Usage Reset", "usage_reset"),
        ("Account Created", "account_created"),
        ("Password Change", "password_change"),
    ]

    def __init__(self, user_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.user_id_filter = user_id  # If set, filter by this user
        self.current_page = 0
        self.page_size = 50
        self.total_entries = 0

        self.setWindowTitle("Audit Log Viewer" + (f" - User {user_id}" if user_id else ""))
        self.setMinimumSize(900, 600)
        self._apply_styling()
        self._setup_ui()
        self._load_audit_log()

    def _apply_styling(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #0D1117;
            }
            QLabel {
                color: #F0F6FC;
            }
            QGroupBox {
                color: #F0F6FC;
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #30363D;
                border-radius: 8px;
                margin-top: 16px;
                padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                background-color: #0D1117;
            }
            QPushButton {
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #30363D;
            }
            QPushButton:disabled {
                background-color: #161B22;
                color: #6B7280;
            }
            QLineEdit, QComboBox, QDateEdit, QSpinBox {
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 6px 10px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #21262D;
                color: #F0F6FC;
                selection-background-color: #C40000;
            }
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header_layout = QHBoxLayout()

        title = QLabel("Subscription Audit Log")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Export button
        export_btn = QPushButton("Export to CSV")
        export_btn.clicked.connect(self._export_to_csv)
        header_layout.addWidget(export_btn)

        layout.addLayout(header_layout)

        # Filters
        filter_group = QGroupBox("Filters")
        filter_layout = QHBoxLayout(filter_group)
        filter_layout.setSpacing(16)

        # User filter
        if not self.user_id_filter:
            filter_layout.addWidget(QLabel("User ID:"))
            self.txt_user_filter = QLineEdit()
            self.txt_user_filter.setPlaceholderText("All users")
            self.txt_user_filter.setMaximumWidth(100)
            filter_layout.addWidget(self.txt_user_filter)

        # Action type filter
        filter_layout.addWidget(QLabel("Action:"))
        self.combo_action = QComboBox()
        for label, _ in self.ACTION_TYPES:
            self.combo_action.addItem(label)
        self.combo_action.setMinimumWidth(150)
        filter_layout.addWidget(self.combo_action)

        # Date range filter
        filter_layout.addWidget(QLabel("From:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        filter_layout.addWidget(self.date_from)

        filter_layout.addWidget(QLabel("To:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        filter_layout.addWidget(self.date_to)

        filter_layout.addStretch()

        # Apply filter button
        apply_btn = QPushButton("Apply Filters")
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #C40000;
                border-color: #C40000;
            }
            QPushButton:hover {
                background-color: #A00000;
            }
        """)
        apply_btn.clicked.connect(self._apply_filters)
        filter_layout.addWidget(apply_btn)

        layout.addWidget(filter_group)

        # Results table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Date/Time", "User ID", "User Email", "Action", "Field", "Old Value", "New Value"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #0D1117;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 4px;
                gridline-color: #21262D;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:selected {
                background-color: #21262D;
            }
            QTableWidget::item:alternate {
                background-color: #161B22;
            }
            QHeaderView::section {
                background-color: #21262D;
                color: #8B949E;
                font-weight: bold;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #C40000;
            }
        """)
        layout.addWidget(self.table, stretch=1)

        # Pagination
        pagination_layout = QHBoxLayout()

        self.lbl_total = QLabel("0 entries")
        self.lbl_total.setStyleSheet("color: #8B949E;")
        pagination_layout.addWidget(self.lbl_total)

        pagination_layout.addStretch()

        self.btn_prev = QPushButton("< Previous")
        self.btn_prev.clicked.connect(self._prev_page)
        self.btn_prev.setEnabled(False)
        pagination_layout.addWidget(self.btn_prev)

        self.lbl_page = QLabel("Page 1")
        self.lbl_page.setStyleSheet("color: #F0F6FC; padding: 0 16px;")
        pagination_layout.addWidget(self.lbl_page)

        self.btn_next = QPushButton("Next >")
        self.btn_next.clicked.connect(self._next_page)
        pagination_layout.addWidget(self.btn_next)

        layout.addLayout(pagination_layout)

        # Close button
        close_layout = QHBoxLayout()
        close_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_layout.addWidget(close_btn)

        layout.addLayout(close_layout)

    def _get_filter_values(self) -> Dict[str, Any]:
        """Get current filter values."""
        filters = {}

        # User filter
        if self.user_id_filter:
            filters['user_id'] = self.user_id_filter
        elif hasattr(self, 'txt_user_filter') and self.txt_user_filter.text().strip():
            try:
                filters['user_id'] = int(self.txt_user_filter.text().strip())
            except ValueError:
                pass

        # Action filter
        action_idx = self.combo_action.currentIndex()
        if action_idx > 0:  # Not "All Actions"
            filters['action'] = self.ACTION_TYPES[action_idx][1]

        # Date range
        from_date = self.date_from.date()
        filters['from_timestamp'] = datetime(from_date.year(), from_date.month(), from_date.day()).timestamp()

        to_date = self.date_to.date()
        # Add 1 day to include the entire "to" date
        filters['to_timestamp'] = datetime(to_date.year(), to_date.month(), to_date.day()).timestamp() + 86400

        return filters

    def _load_audit_log(self):
        """Load audit log entries from database."""
        try:
            if not DB_PATH.exists():
                self.lbl_total.setText("Database not found")
                return

            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Check if table exists
            cur.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='subscription_audit_log'
            """)
            if not cur.fetchone():
                self.lbl_total.setText("Audit log table not found")
                conn.close()
                return

            # Build query with filters
            filters = self._get_filter_values()

            where_clauses = []
            params = []

            if 'user_id' in filters:
                where_clauses.append("sal.user_id = ?")
                params.append(filters['user_id'])

            if 'action' in filters:
                where_clauses.append("sal.action = ?")
                params.append(filters['action'])

            if 'from_timestamp' in filters:
                where_clauses.append("sal.timestamp >= ?")
                params.append(filters['from_timestamp'])

            if 'to_timestamp' in filters:
                where_clauses.append("sal.timestamp <= ?")
                params.append(filters['to_timestamp'])

            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

            # Get total count
            count_sql = f"""
                SELECT COUNT(*) as cnt FROM subscription_audit_log sal
                WHERE {where_sql}
            """
            cur.execute(count_sql, params)
            self.total_entries = cur.fetchone()['cnt']

            # Get paginated results with user email
            query_sql = f"""
                SELECT
                    sal.timestamp,
                    sal.user_id,
                    COALESCE(u.email, 'Unknown') as user_email,
                    sal.action,
                    sal.field_name,
                    sal.old_value,
                    sal.new_value,
                    sal.reason
                FROM subscription_audit_log sal
                LEFT JOIN unified_users u ON sal.user_id = u.user_id
                WHERE {where_sql}
                ORDER BY sal.timestamp DESC
                LIMIT ? OFFSET ?
            """
            params.extend([self.page_size, self.current_page * self.page_size])

            cur.execute(query_sql, params)
            rows = cur.fetchall()

            conn.close()

            # Populate table
            self.table.setRowCount(len(rows))

            for row_idx, row in enumerate(rows):
                # Date/Time
                ts = row['timestamp']
                date_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') if ts else "N/A"
                self.table.setItem(row_idx, 0, QTableWidgetItem(date_str))

                # User ID
                self.table.setItem(row_idx, 1, QTableWidgetItem(str(row['user_id'])))

                # User Email
                self.table.setItem(row_idx, 2, QTableWidgetItem(row['user_email']))

                # Action (formatted)
                action = row['action'] or ''
                action_display = action.replace('_', ' ').title()
                action_item = QTableWidgetItem(action_display)

                # Color code actions
                if action in ['suspend', 'delete']:
                    action_item.setForeground(Qt.red)
                elif action == 'activate':
                    action_item.setForeground(Qt.green)
                elif action == 'tier_change':
                    action_item.setForeground(Qt.yellow)

                self.table.setItem(row_idx, 3, action_item)

                # Field
                self.table.setItem(row_idx, 4, QTableWidgetItem(row['field_name'] or '-'))

                # Old Value
                self.table.setItem(row_idx, 5, QTableWidgetItem(str(row['old_value'] or '-')))

                # New Value
                self.table.setItem(row_idx, 6, QTableWidgetItem(str(row['new_value'] or '-')))

            # Update pagination
            self._update_pagination()

        except Exception as e:
            logger.error(f"Error loading audit log: {e}")
            self.lbl_total.setText(f"Error: {e}")

    def _update_pagination(self):
        """Update pagination controls."""
        total_pages = max(1, (self.total_entries + self.page_size - 1) // self.page_size)
        current_page_display = self.current_page + 1

        self.lbl_total.setText(f"{self.total_entries:,} entries")
        self.lbl_page.setText(f"Page {current_page_display} of {total_pages}")

        self.btn_prev.setEnabled(self.current_page > 0)
        self.btn_next.setEnabled(current_page_display < total_pages)

    def _prev_page(self):
        """Go to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self._load_audit_log()

    def _next_page(self):
        """Go to next page."""
        total_pages = (self.total_entries + self.page_size - 1) // self.page_size
        if self.current_page + 1 < total_pages:
            self.current_page += 1
            self._load_audit_log()

    def _apply_filters(self):
        """Apply filters and reload."""
        self.current_page = 0
        self._load_audit_log()

    def _export_to_csv(self):
        """Export audit log to CSV file."""
        try:
            # Get save file path
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Audit Log",
                f"audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "CSV Files (*.csv)"
            )

            if not file_path:
                return

            if not DB_PATH.exists():
                QMessageBox.warning(self, "Error", "Database not found")
                return

            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Build query with filters (no pagination)
            filters = self._get_filter_values()

            where_clauses = []
            params = []

            if 'user_id' in filters:
                where_clauses.append("sal.user_id = ?")
                params.append(filters['user_id'])

            if 'action' in filters:
                where_clauses.append("sal.action = ?")
                params.append(filters['action'])

            if 'from_timestamp' in filters:
                where_clauses.append("sal.timestamp >= ?")
                params.append(filters['from_timestamp'])

            if 'to_timestamp' in filters:
                where_clauses.append("sal.timestamp <= ?")
                params.append(filters['to_timestamp'])

            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

            query_sql = f"""
                SELECT
                    sal.timestamp,
                    sal.user_id,
                    COALESCE(u.email, 'Unknown') as user_email,
                    sal.action,
                    sal.field_name,
                    sal.old_value,
                    sal.new_value,
                    sal.reason,
                    sal.admin_id
                FROM subscription_audit_log sal
                LEFT JOIN unified_users u ON sal.user_id = u.user_id
                WHERE {where_sql}
                ORDER BY sal.timestamp DESC
            """

            cur.execute(query_sql, params)
            rows = cur.fetchall()
            conn.close()

            # Write CSV
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # Header
                writer.writerow([
                    "Date/Time", "User ID", "User Email", "Action",
                    "Field", "Old Value", "New Value", "Reason", "Admin ID"
                ])

                # Data
                for row in rows:
                    ts = row['timestamp']
                    date_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') if ts else ""

                    writer.writerow([
                        date_str,
                        row['user_id'],
                        row['user_email'],
                        row['action'],
                        row['field_name'] or '',
                        row['old_value'] or '',
                        row['new_value'] or '',
                        row['reason'] or '',
                        row['admin_id']
                    ])

            QMessageBox.information(
                self,
                "Export Complete",
                f"Exported {len(rows)} entries to:\n{file_path}"
            )

        except Exception as e:
            logger.error(f"Error exporting audit log: {e}")
            QMessageBox.critical(self, "Export Error", f"Failed to export: {e}")


def show_audit_log_viewer(user_id: Optional[int] = None, parent=None):
    """
    Convenience function to show the audit log viewer.

    Args:
        user_id: Optional user ID to filter by
        parent: Parent widget
    """
    dialog = AuditLogViewer(user_id=user_id, parent=parent)
    dialog.exec()


# For standalone testing
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QPalette, QColor

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark palette
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(13, 17, 23))
    palette.setColor(QPalette.WindowText, QColor(240, 246, 252))
    palette.setColor(QPalette.Base, QColor(22, 27, 34))
    palette.setColor(QPalette.Text, QColor(240, 246, 252))
    app.setPalette(palette)

    dialog = AuditLogViewer()
    dialog.exec()

    sys.exit(0)
