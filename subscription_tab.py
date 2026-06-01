"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Subscription Tab

Predict OBD - Subscription Management Tab v2.0
Refactored with clean card-based layout
Comprehensive UI for managing customer subscriptions, payments, and licenses.
"""

import os
import json
from datetime import datetime
from typing import Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QGridLayout, QComboBox, QLineEdit, QSpinBox, QMessageBox,
    QDialog, QFormLayout, QTextEdit, QListWidget, QListWidgetItem,
    QCheckBox, QScrollArea, QFrame
)
from PySide6.QtGui import QFont, QColor
from PySide6.QtCore import Qt, QTimer, Signal

from ui_common import ProfessionalTheme
from config import get_config
from subscription_manager import (
    get_subscription_manager, SubscriptionPlan, Subscription
)
from audit_logger import log_audit_event, AuditEventType


class SubscriptionTab(QWidget):
    """
    Subscription Management Tab - Refactored v2.0
    Admin interface for customer subscriptions with clean card-based layout.
    """

    subscription_updated = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_config()
        self.sub_manager = get_subscription_manager()
        self._selected_customer = None

        self._setup_ui()
        self._load_subscriptions()

        # Auto-refresh every 30 seconds
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._load_subscriptions)
        self.refresh_timer.start(30000)

    def _create_card(self, title: str, color: str) -> QGroupBox:
        """Create a styled card container"""
        card = QGroupBox(title)
        card.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 13px;
                color: {color};
                border: 2px solid {color};
                border-radius: 8px;
                margin-top: 12px;
                padding: 15px;
                background-color: #1E2329;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
                background-color: #1E2329;
            }}
        """)
        return card

    def _setup_ui(self):
        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: #0D1117; }")

        # Main content
        content = QWidget()
        main_layout = QVBoxLayout(content)
        main_layout.setSpacing(15)

        # ========================================
        # HEADER
        # ========================================
        header_layout = QHBoxLayout()
        title = QLabel("Subscription Management")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #F0F6FC;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.btn_new_subscription = QPushButton("+ New Subscription")
        self.btn_new_subscription.setStyleSheet(self._get_button_style('success'))
        self.btn_new_subscription.clicked.connect(self._show_new_subscription_dialog)
        header_layout.addWidget(self.btn_new_subscription)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setStyleSheet(self._get_button_style('info'))
        self.btn_refresh.clicked.connect(self._load_subscriptions)
        header_layout.addWidget(self.btn_refresh)

        main_layout.addLayout(header_layout)

        # ========================================
        # TOP ROW - Stats
        # ========================================
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)

        self.lbl_total = self._create_stat_label("Total", "0", "#6F42C1")
        self.lbl_active = self._create_stat_label("Active", "0", "#198754")
        self.lbl_trial = self._create_stat_label("Trial", "0", "#0D6EFD")
        self.lbl_expired = self._create_stat_label("Expired", "0", "#DC3545")
        self.lbl_revenue = self._create_stat_label("Monthly Revenue", "$0", "#FF9800")

        stats_layout.addWidget(self.lbl_total)
        stats_layout.addWidget(self.lbl_active)
        stats_layout.addWidget(self.lbl_trial)
        stats_layout.addWidget(self.lbl_expired)
        stats_layout.addWidget(self.lbl_revenue)

        main_layout.addLayout(stats_layout)

        # ========================================
        # MIDDLE ROW - Filters & Table
        # ========================================
        # Filter card
        filter_card = self._create_card("Filters", "#00BCD4")
        filter_layout = QHBoxLayout(filter_card)

        filter_layout.addWidget(QLabel("Status:"))
        self.filter_status = QComboBox()
        self.filter_status.addItems(["All", "Active", "Expired", "Pending", "Cancelled"])
        self.filter_status.currentTextChanged.connect(self._filter_subscriptions)
        self.filter_status.setStyleSheet(self._get_combo_style())
        filter_layout.addWidget(self.filter_status)

        filter_layout.addWidget(QLabel("Plan:"))
        self.filter_plan = QComboBox()
        self.filter_plan.addItems(["All", "Trial", "Basic", "Professional", "Enterprise"])
        self.filter_plan.currentTextChanged.connect(self._filter_subscriptions)
        self.filter_plan.setStyleSheet(self._get_combo_style())
        filter_layout.addWidget(self.filter_plan)

        filter_layout.addStretch()

        main_layout.addWidget(filter_card)

        # Subscription table card
        table_card = self._create_card("Subscriptions", "#C40000")
        table_layout = QVBoxLayout(table_card)

        self.subscription_table = QTableWidget()
        self.subscription_table.setColumnCount(5)
        self.subscription_table.setHorizontalHeaderLabels([
            "Customer", "Plan", "Status", "Expires", "Payment"
        ])
        self.subscription_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.subscription_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.subscription_table.setSelectionMode(QTableWidget.SingleSelection)
        self.subscription_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.subscription_table.setMinimumHeight(250)
        self._apply_table_styling(self.subscription_table)
        table_layout.addWidget(self.subscription_table)

        main_layout.addWidget(table_card)

        # ========================================
        # BOTTOM ROW - Details & Actions
        # ========================================
        details_layout = QHBoxLayout()
        details_layout.setSpacing(15)

        # Details card (left)
        details_card = self._create_card("Subscription Details", "#2196F3")
        details_grid = QGridLayout(details_card)
        details_grid.setSpacing(8)

        self.detail_labels = {}
        detail_fields = [
            ("Customer ID:", "customer_id"),
            ("Plan:", "plan"),
            ("Status:", "status"),
            ("Start Date:", "start_date"),
            ("End Date:", "end_date"),
            ("Days Remaining:", "days_remaining"),
            ("Payment Status:", "payment_status"),
            ("License Key:", "license_key"),
        ]

        for i, (label_text, attr_name) in enumerate(detail_fields):
            label = QLabel(label_text)
            label.setStyleSheet("color: #8B949E; font-size: 11px;")
            value = QLabel("-")
            value.setStyleSheet("color: #F0F6FC; font-weight: 600;")
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.detail_labels[attr_name] = value
            details_grid.addWidget(label, i // 2, (i % 2) * 2)
            details_grid.addWidget(value, i // 2, (i % 2) * 2 + 1)

        details_layout.addWidget(details_card)

        # Features & Actions card (right)
        actions_card = self._create_card("Actions & Features", "#4CAF50")
        actions_layout = QVBoxLayout(actions_card)

        # Features list
        self.features_list = QListWidget()
        self.features_list.setMaximumHeight(120)
        self.features_list.setStyleSheet("""
            QListWidget {
                background-color: #21262D;
                border: 1px solid #30363D;
                border-radius: 5px;
                color: #F0F6FC;
            }
        """)
        actions_layout.addWidget(self.features_list)

        # Action buttons grid
        buttons_grid = QGridLayout()
        buttons_grid.setSpacing(8)

        self.btn_activate = QPushButton("Activate")
        self.btn_activate.setStyleSheet(self._get_button_style('success'))
        self.btn_activate.clicked.connect(self._activate_subscription)
        buttons_grid.addWidget(self.btn_activate, 0, 0)

        self.btn_suspend = QPushButton("Suspend")
        self.btn_suspend.setStyleSheet(self._get_button_style('warning'))
        self.btn_suspend.clicked.connect(self._suspend_subscription)
        buttons_grid.addWidget(self.btn_suspend, 0, 1)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setStyleSheet(self._get_button_style('danger'))
        self.btn_cancel.clicked.connect(self._cancel_subscription)
        buttons_grid.addWidget(self.btn_cancel, 1, 0)

        self.btn_renew = QPushButton("Renew (+30 days)")
        self.btn_renew.setStyleSheet(self._get_button_style('info'))
        self.btn_renew.clicked.connect(self._renew_subscription)
        buttons_grid.addWidget(self.btn_renew, 1, 1)

        self.btn_change_plan = QPushButton("Change Plan")
        self.btn_change_plan.setStyleSheet(self._get_button_style('primary'))
        self.btn_change_plan.clicked.connect(self._change_plan)
        buttons_grid.addWidget(self.btn_change_plan, 2, 0)

        self.btn_record_payment = QPushButton("Record Payment")
        self.btn_record_payment.setStyleSheet(self._get_button_style('success'))
        self.btn_record_payment.clicked.connect(self._record_payment)
        buttons_grid.addWidget(self.btn_record_payment, 2, 1)

        self.btn_regenerate_key = QPushButton("Regenerate License")
        self.btn_regenerate_key.setStyleSheet(self._get_button_style('secondary'))
        self.btn_regenerate_key.clicked.connect(self._regenerate_license_key)
        buttons_grid.addWidget(self.btn_regenerate_key, 3, 0)

        self.btn_view_history = QPushButton("Audit History")
        self.btn_view_history.setStyleSheet(self._get_button_style('secondary'))
        self.btn_view_history.clicked.connect(self._view_audit_history)
        buttons_grid.addWidget(self.btn_view_history, 3, 1)

        actions_layout.addLayout(buttons_grid)

        details_layout.addWidget(actions_card, 1)
        main_layout.addLayout(details_layout)
        main_layout.addStretch()

        scroll.setWidget(content)

        # Container layout
        container_layout = QVBoxLayout(self)
        container_layout.setContentsMargins(12, 12, 12, 12)
        container_layout.addWidget(scroll)

        # Disable actions initially
        self._set_actions_enabled(False)

    def _create_stat_label(self, title: str, value: str, color: str) -> QFrame:
        """Create a statistic label widget."""
        widget = QFrame()
        widget.setStyleSheet(f"""
            QFrame {{
                background-color: #1E2329;
                border: 2px solid {color};
                border-radius: 8px;
                padding: 10px;
            }}
        """)

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color: #8B949E; font-size: 11px;")
        title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_lbl)

        value_lbl = QLabel(value)
        value_lbl.setFont(QFont("Segoe UI", 20, QFont.Bold))
        value_lbl.setStyleSheet(f"color: {color};")
        value_lbl.setAlignment(Qt.AlignCenter)
        value_lbl.setObjectName(f"stat_{title.lower().replace(' ', '_')}")
        layout.addWidget(value_lbl)

        return widget

    def _load_subscriptions(self):
        """Load all subscriptions into the table."""
        self.subscription_table.setRowCount(0)

        customers_dir = self.config.CUSTOMERS_DIR
        if not customers_dir.exists():
            return

        stats = {"total": 0, "active": 0, "trial": 0, "expired": 0, "revenue": 0}

        plan_prices = {
            "trial": 0, "basic": 29, "professional": 79, "enterprise": 199
        }

        for customer_dir in sorted(customers_dir.iterdir()):
            if not customer_dir.is_dir() or "_deleted_" in customer_dir.name:
                continue

            customer_id = customer_dir.name
            subscription = self.sub_manager.load_subscription(customer_id)

            if not subscription:
                continue

            stats["total"] += 1

            if subscription.status == "active":
                stats["active"] += 1
                stats["revenue"] += plan_prices.get(subscription.plan, 0)
            elif subscription.status == "trial" or subscription.plan == "trial":
                stats["trial"] += 1
            elif subscription.status == "expired":
                stats["expired"] += 1

            # Add row
            row = self.subscription_table.rowCount()
            self.subscription_table.insertRow(row)

            self.subscription_table.setItem(row, 0, QTableWidgetItem(customer_id))
            self.subscription_table.setItem(row, 1, QTableWidgetItem(subscription.plan.upper()))

            status_item = QTableWidgetItem(subscription.status.upper())
            status_item.setForeground(self._get_status_color(subscription.status))
            self.subscription_table.setItem(row, 2, status_item)

            expires = subscription.end_date or "N/A"
            self.subscription_table.setItem(row, 3, QTableWidgetItem(str(expires)))

            payment_item = QTableWidgetItem(subscription.payment_status.upper())
            payment_item.setForeground(self._get_payment_color(subscription.payment_status))
            self.subscription_table.setItem(row, 4, payment_item)

        # Update stats
        self._update_stats(stats)
        self._filter_subscriptions()

    def _filter_subscriptions(self):
        """Filter the subscription table."""
        status_filter = self.filter_status.currentText().lower()
        plan_filter = self.filter_plan.currentText().lower()

        for row in range(self.subscription_table.rowCount()):
            show = True

            if status_filter != "all":
                status = self.subscription_table.item(row, 2).text().lower()
                if status != status_filter:
                    show = False

            if plan_filter != "all":
                plan = self.subscription_table.item(row, 1).text().lower()
                if plan != plan_filter:
                    show = False

            self.subscription_table.setRowHidden(row, not show)

    def _on_selection_changed(self):
        """Handle selection change."""
        selected = self.subscription_table.selectedItems()
        if not selected:
            self._selected_customer = None
            self._clear_details()
            self._set_actions_enabled(False)
            return

        row = selected[0].row()
        customer_id = self.subscription_table.item(row, 0).text()
        self._selected_customer = customer_id

        subscription = self.sub_manager.load_subscription(customer_id)
        if subscription:
            self._display_subscription(subscription)
            self._set_actions_enabled(True)

    def _display_subscription(self, sub: Subscription):
        """Display subscription details."""
        self.detail_labels["customer_id"].setText(sub.customer_id)
        self.detail_labels["plan"].setText(sub.plan.upper())
        self.detail_labels["status"].setText(sub.status.upper())
        self.detail_labels["start_date"].setText(sub.start_date or "N/A")
        self.detail_labels["end_date"].setText(sub.end_date or "N/A")

        days = sub.days_remaining()
        if days is not None:
            self.detail_labels["days_remaining"].setText(f"{days} days")
            if days <= 7:
                self.detail_labels["days_remaining"].setStyleSheet("color: #DC3545; font-weight: 600;")
            elif days <= 30:
                self.detail_labels["days_remaining"].setStyleSheet("color: #FFC107; font-weight: 600;")
            else:
                self.detail_labels["days_remaining"].setStyleSheet("color: #198754; font-weight: 600;")
        else:
            self.detail_labels["days_remaining"].setText("N/A")

        self.detail_labels["payment_status"].setText(sub.payment_status.upper())
        self.detail_labels["license_key"].setText(sub.license_key or "Not Generated")

        # Display features
        self.features_list.clear()
        for feature, enabled in sub.features.items():
            icon = "ON" if enabled else "OFF"
            color = "#198754" if enabled else "#6E7681"
            item = QListWidgetItem(f"[{icon}] {feature.replace('_', ' ').title()}")
            item.setForeground(QColor(color))
            self.features_list.addItem(item)

    def _clear_details(self):
        """Clear the details panel."""
        for label in self.detail_labels.values():
            label.setText("-")
            label.setStyleSheet("color: #F0F6FC; font-weight: 600;")
        self.features_list.clear()

    def _set_actions_enabled(self, enabled: bool):
        """Enable or disable action buttons."""
        buttons = [
            self.btn_activate, self.btn_suspend, self.btn_cancel,
            self.btn_renew, self.btn_change_plan, self.btn_record_payment,
            self.btn_regenerate_key, self.btn_view_history
        ]
        for btn in buttons:
            btn.setEnabled(enabled)

    def _update_stats(self, stats: dict):
        """Update statistics labels."""
        for widget in [self.lbl_total, self.lbl_active, self.lbl_trial, self.lbl_expired, self.lbl_revenue]:
            # Find child QLabel with objectName starting with "stat_"
            for child in widget.findChildren(QLabel):
                if child.objectName() and child.objectName().startswith("stat_"):
                    stat_name = child.objectName()
                    if "total" in stat_name:
                        child.setText(str(stats["total"]))
                    elif "active" in stat_name:
                        child.setText(str(stats["active"]))
                    elif "trial" in stat_name:
                        child.setText(str(stats["trial"]))
                    elif "expired" in stat_name:
                        child.setText(str(stats["expired"]))
                    elif "revenue" in stat_name:
                        child.setText(f"${stats['revenue']}")

    # ==================== ACTION HANDLERS ====================

    def _show_new_subscription_dialog(self):
        """Show dialog to create a new subscription."""
        dialog = NewSubscriptionDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self._load_subscriptions()

    def _activate_subscription(self):
        """Activate the selected subscription."""
        if not self._selected_customer:
            return

        reply = QMessageBox.question(
            self, "Confirm Activation",
            f"Activate subscription for {self._selected_customer}?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            sub = self.sub_manager.load_subscription(self._selected_customer)
            if sub:
                sub.status = "active"
                self.sub_manager.save_subscription(sub)

                log_audit_event(
                    AuditEventType.SUBSCRIPTION_RENEWED,
                    customer_id=self._selected_customer,
                    details={"action": "manual_activation", "operator": "admin"}
                )

                self._load_subscriptions()
                QMessageBox.information(self, "Success", "Subscription activated.")

    def _suspend_subscription(self):
        """Suspend the selected subscription."""
        if not self._selected_customer:
            return

        reason, ok = QMessageBox.getText(
            self, "Suspension Reason",
            "Enter reason for suspension:"
        )

        if ok and reason:
            sub = self.sub_manager.load_subscription(self._selected_customer)
            if sub:
                sub.status = "suspended"
                self.sub_manager.save_subscription(sub)

                log_audit_event(
                    AuditEventType.SUBSCRIPTION_EXPIRED,
                    customer_id=self._selected_customer,
                    details={"action": "suspended", "reason": reason, "operator": "admin"}
                )

                self._load_subscriptions()
                QMessageBox.information(self, "Success", "Subscription suspended.")

    def _cancel_subscription(self):
        """Cancel the selected subscription."""
        if not self._selected_customer:
            return

        reply = QMessageBox.warning(
            self, "Confirm Cancellation",
            f"Cancel subscription for {self._selected_customer}?\n\n"
            "This will revoke access immediately.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            success, msg = self.sub_manager.cancel_subscription(
                self._selected_customer,
                reason="admin_cancelled",
                cancelled_by="admin"
            )

            if success:
                self._load_subscriptions()
                QMessageBox.information(self, "Success", msg)
            else:
                QMessageBox.warning(self, "Error", msg)

    def _renew_subscription(self):
        """Renew the selected subscription."""
        if not self._selected_customer:
            return

        days, ok = QInputDialog.getInt(
            self, "Renewal Period",
            "Enter number of days to add:",
            30, 1, 365
        )

        if ok:
            success, msg = self.sub_manager.renew_subscription(
                self._selected_customer,
                payment_succeeded=True,
                payment_details={"method": "manual", "days_added": days},
                renewed_by="admin"
            )

            if success:
                self._load_subscriptions()
                QMessageBox.information(self, "Success", f"Subscription renewed for {days} days.")
            else:
                QMessageBox.warning(self, "Error", msg)

    def _change_plan(self):
        """Change the subscription plan."""
        if not self._selected_customer:
            return

        plans = ["trial", "basic", "professional", "enterprise"]
        plan, ok = QInputDialog.getItem(
            self, "Change Plan",
            "Select new plan:",
            plans, 0, False
        )

        if ok:
            success, msg = self.sub_manager.upgrade_plan(
                self._selected_customer,
                SubscriptionPlan(plan),
                upgraded_by="admin"
            )

            if success:
                self._load_subscriptions()
                QMessageBox.information(self, "Success", msg)
            else:
                QMessageBox.warning(self, "Error", msg)

    def _record_payment(self):
        """Record a manual payment."""
        if not self._selected_customer:
            return

        dialog = RecordPaymentDialog(self._selected_customer, self)
        if dialog.exec() == QDialog.Accepted:
            self._load_subscriptions()

    def _regenerate_license_key(self):
        """Regenerate the license key."""
        if not self._selected_customer:
            return

        reply = QMessageBox.question(
            self, "Confirm Regeneration",
            "Generate a new license key?\n\n"
            "The old key will be invalidated.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            success, msg, new_key = self.sub_manager.regenerate_license_key(
                self._selected_customer,
                regenerated_by="admin"
            )

            if success:
                self._load_subscriptions()
                self._on_selection_changed()
                QMessageBox.information(
                    self, "Success",
                    f"New license key generated:\n\n{new_key}"
                )
            else:
                QMessageBox.warning(self, "Error", msg)

    def _view_audit_history(self):
        """View subscription audit history."""
        if not self._selected_customer:
            return

        sub = self.sub_manager.load_subscription(self._selected_customer)
        if not sub:
            return

        dialog = AuditHistoryDialog(sub, self)
        dialog.exec()

    # ==================== STYLE HELPERS ====================

    def _get_status_color(self, status: str) -> QColor:
        """Get color for subscription status."""
        colors = {
            "active": QColor("#198754"),
            "trial": QColor("#0D6EFD"),
            "expired": QColor("#DC3545"),
            "cancelled": QColor("#6E7681"),
            "suspended": QColor("#FFC107"),
            "pending": QColor("#FFC107"),
        }
        return colors.get(status.lower(), QColor("#F0F6FC"))

    def _get_payment_color(self, status: str) -> QColor:
        """Get color for payment status."""
        colors = {
            "succeeded": QColor("#198754"),
            "failed": QColor("#DC3545"),
            "pending": QColor("#FFC107"),
            "refunded": QColor("#0D6EFD"),
        }
        return colors.get(status.lower(), QColor("#F0F6FC"))

    def _get_button_style(self, style_type: str = 'primary') -> str:
        """Get consistent button stylesheet"""
        styles = {
            'primary': """
                QPushButton {
                    background-color: #C40000;
                    color: white;
                    border: none;
                    padding: 10px 16px;
                    font-size: 11px;
                    font-weight: bold;
                    border-radius: 5px;
                }
                QPushButton:hover { background-color: #E53935; }
                QPushButton:pressed { background-color: #B71C1C; }
                QPushButton:disabled { background-color: #30363D; color: #6E7681; }
            """,
            'secondary': """
                QPushButton {
                    background-color: #2C3E50;
                    color: white;
                    border: none;
                    padding: 10px 16px;
                    font-size: 11px;
                    font-weight: 600;
                    border-radius: 5px;
                }
                QPushButton:hover { background-color: #34495E; }
                QPushButton:disabled { background-color: #1A252F; color: #6E7681; }
            """,
            'danger': """
                QPushButton {
                    background-color: #DC3545;
                    color: white;
                    border: none;
                    padding: 10px 16px;
                    font-size: 11px;
                    font-weight: bold;
                    border-radius: 5px;
                }
                QPushButton:hover { background-color: #E53935; }
                QPushButton:disabled { background-color: #30363D; color: #6E7681; }
            """,
            'success': """
                QPushButton {
                    background-color: #198754;
                    color: white;
                    border: none;
                    padding: 10px 16px;
                    font-size: 11px;
                    font-weight: bold;
                    border-radius: 5px;
                }
                QPushButton:hover { background-color: #20C997; }
                QPushButton:disabled { background-color: #30363D; color: #6E7681; }
            """,
            'warning': """
                QPushButton {
                    background-color: #FFC107;
                    color: #212529;
                    border: none;
                    padding: 10px 16px;
                    font-size: 11px;
                    font-weight: bold;
                    border-radius: 5px;
                }
                QPushButton:hover { background-color: #FFD54F; }
                QPushButton:disabled { background-color: #30363D; color: #6E7681; }
            """,
            'info': """
                QPushButton {
                    background-color: #0D6EFD;
                    color: white;
                    border: none;
                    padding: 10px 16px;
                    font-size: 11px;
                    font-weight: bold;
                    border-radius: 5px;
                }
                QPushButton:hover { background-color: #1976D2; }
                QPushButton:disabled { background-color: #30363D; color: #6E7681; }
            """
        }
        return styles.get(style_type, styles['primary'])

    def _apply_table_styling(self, table_widget):
        """Apply table styling"""
        table_widget.setStyleSheet("""
            QTableWidget {
                background-color: #1E2329;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                gridline-color: #30363D;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #30363D;
            }
            QTableWidget::item:selected {
                background-color: #C40000;
                color: white;
            }
            QTableWidget::item:hover {
                background-color: #2C3E50;
            }
            QHeaderView::section {
                background-color: #161B22;
                color: #F0F6FC;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #C40000;
                font-weight: 600;
                font-size: 11px;
            }
        """)

    def _get_combo_style(self) -> str:
        """Get combobox stylesheet."""
        return """
            QComboBox {
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 5px;
                padding: 5px 10px;
                min-width: 100px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                width: 12px;
                height: 12px;
            }
        """


# ==================== DIALOGS ====================

class NewSubscriptionDialog(QDialog):
    """Dialog for creating a new subscription."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Subscription")
        self.setMinimumWidth(400)
        self.config = get_config()
        self.sub_manager = get_subscription_manager()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.txt_customer_id = QLineEdit()
        self.txt_customer_id.setPlaceholderText("e.g., customer_001")
        form.addRow("Customer ID:", self.txt_customer_id)

        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("Customer name")
        form.addRow("Name:", self.txt_name)

        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("email@example.com")
        form.addRow("Email:", self.txt_email)

        self.cmb_plan = QComboBox()
        self.cmb_plan.addItems(["trial", "basic", "professional", "enterprise"])
        form.addRow("Plan:", self.cmb_plan)

        self.spn_duration = QSpinBox()
        self.spn_duration.setRange(1, 365)
        self.spn_duration.setValue(30)
        self.spn_duration.setSuffix(" days")
        form.addRow("Duration:", self.spn_duration)

        self.chk_start_now = QCheckBox("Start immediately")
        self.chk_start_now.setChecked(True)
        form.addRow("", self.chk_start_now)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_create = QPushButton("Create")
        btn_create.setStyleSheet("background-color: #198754; color: white; padding: 10px 20px; border-radius: 5px; font-weight: bold;")
        btn_create.clicked.connect(self._create_subscription)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet("background-color: #6C757D; color: white; padding: 10px 20px; border-radius: 5px;")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_create)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _create_subscription(self):
        customer_id = self.txt_customer_id.text().strip()
        if not customer_id:
            QMessageBox.warning(self, "Error", "Customer ID is required.")
            return

        # Create customer directory
        from directory_manager import DirectoryManager
        dir_manager = DirectoryManager()
        dir_manager.create_customer(customer_id)

        # Update profile
        profile_file = self.config.get_customer_profile(customer_id)
        if profile_file.exists():
            with open(profile_file, 'r') as f:
                profile = json.load(f)

            profile["name"] = self.txt_name.text().strip()
            profile["email"] = self.txt_email.text().strip()

            with open(profile_file, 'w') as f:
                json.dump(profile, f, indent=2)

        # Create subscription
        plan = SubscriptionPlan(self.cmb_plan.currentText())
        success, msg, sub = self.sub_manager.create_subscription(
            customer_id=customer_id,
            plan=plan,
            duration_days=self.spn_duration.value(),
            start_immediately=self.chk_start_now.isChecked(),
            created_by="admin"
        )

        if success:
            # Generate API key for this subscription
            try:
                from subscription_manager import generate_api_key_for_subscription
                api_key = generate_api_key_for_subscription(
                    customer_id=customer_id,
                    plan=plan.value,
                    profile_id=None,
                    profile_name=self.txt_name.text().strip() or "Default"
                )

                # Map plan to tier name
                plan_to_tier = {
                    "trial": "Free",
                    "basic": "Free",
                    "professional": "Premium",
                    "premium": "Premium",
                    "enterprise": "Premium"
                }
                tier_name = plan_to_tier.get(plan.value.lower(), "Free")

                QMessageBox.information(
                    self, "Success",
                    f"Subscription created!\n\n"
                    f"Customer: {customer_id}\n"
                    f"Plan: {plan.value.upper()}\n"
                    f"License Key:\n{sub.license_key}\n\n"
                    f"{'='*40}\n"
                    f"API KEY GENERATED!\n"
                    f"{'='*40}\n"
                    f"Tier: {tier_name}\n"
                    f"API Key:\n{api_key}\n\n"
                    f"This API key has been saved to the Server tab.\n"
                    f"Send this key to the customer for Android app setup."
                )
            except Exception as e:
                # If API key generation fails, still show success but warn
                QMessageBox.warning(
                    self, "Success with Warning",
                    f"Subscription created!\n\n"
                    f"Customer: {customer_id}\n"
                    f"Plan: {plan.value.upper()}\n"
                    f"License Key:\n{sub.license_key}\n\n"
                    f"⚠️ WARNING: API key generation failed: {e}\n"
                    f"You can manually generate an API key from the Server tab."
                )

            self.accept()
        else:
            QMessageBox.warning(self, "Error", msg)


class RecordPaymentDialog(QDialog):
    """Dialog for recording a manual payment."""

    def __init__(self, customer_id: str, parent=None):
        super().__init__(parent)
        self.customer_id = customer_id
        self.setWindowTitle(f"Record Payment - {customer_id}")
        self.setMinimumWidth(350)
        self.sub_manager = get_subscription_manager()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.cmb_method = QComboBox()
        self.cmb_method.addItems([
            "Bank Transfer", "Cash", "Credit Card (Manual)",
            "PayPal", "Other"
        ])
        form.addRow("Payment Method:", self.cmb_method)

        self.txt_amount = QLineEdit()
        self.txt_amount.setPlaceholderText("0.00")
        form.addRow("Amount ($):", self.txt_amount)

        self.txt_reference = QLineEdit()
        self.txt_reference.setPlaceholderText("Transaction ID or reference")
        form.addRow("Reference:", self.txt_reference)

        self.spn_extend_days = QSpinBox()
        self.spn_extend_days.setRange(0, 365)
        self.spn_extend_days.setValue(30)
        self.spn_extend_days.setSuffix(" days")
        form.addRow("Extend by:", self.spn_extend_days)

        self.txt_notes = QTextEdit()
        self.txt_notes.setMaximumHeight(80)
        form.addRow("Notes:", self.txt_notes)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_record = QPushButton("Record Payment")
        btn_record.setStyleSheet("background-color: #198754; color: white; padding: 10px 20px; border-radius: 5px; font-weight: bold;")
        btn_record.clicked.connect(self._record_payment)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet("background-color: #6C757D; color: white; padding: 10px 20px; border-radius: 5px;")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_record)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _record_payment(self):
        payment_details = {
            "method": self.cmb_method.currentText(),
            "amount": self.txt_amount.text(),
            "reference": self.txt_reference.text(),
            "notes": self.txt_notes.toPlainText(),
            "recorded_at": datetime.now().isoformat(),
            "days_extended": self.spn_extend_days.value()
        }

        success, msg = self.sub_manager.renew_subscription(
            self.customer_id,
            payment_succeeded=True,
            payment_details=payment_details,
            renewed_by="admin"
        )

        if success:
            log_audit_event(
                AuditEventType.SUBSCRIPTION_RENEWED,
                customer_id=self.customer_id,
                details={"payment": payment_details}
            )
            QMessageBox.information(self, "Success", "Payment recorded successfully.")
            self.accept()
        else:
            QMessageBox.warning(self, "Error", msg)


class AuditHistoryDialog(QDialog):
    """Dialog for viewing subscription audit history."""

    def __init__(self, subscription: Subscription, parent=None):
        super().__init__(parent)
        self.subscription = subscription
        self.setWindowTitle(f"Audit History - {subscription.customer_id}")
        self.setMinimumSize(500, 400)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Audit log table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Timestamp", "Event", "Actor", "Details"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._apply_table_styling(self.table)

        # Load audit log
        for entry in reversed(self.subscription.audit_log):
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QTableWidgetItem(entry.get("timestamp", "")))
            self.table.setItem(row, 1, QTableWidgetItem(entry.get("event_type", "")))
            self.table.setItem(row, 2, QTableWidgetItem(entry.get("actor", "")))
            self.table.setItem(row, 3, QTableWidgetItem(str(entry.get("details", {}))))

        layout.addWidget(self.table)

        # Close button
        btn_close = QPushButton("Close")
        btn_close.setStyleSheet("background-color: #6C757D; color: white; padding: 10px 20px; border-radius: 5px;")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def _apply_table_styling(self, table_widget):
        """Apply table styling"""
        table_widget.setStyleSheet("""
            QTableWidget {
                background-color: #1E2329;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QHeaderView::section {
                background-color: #161B22;
                color: #F0F6FC;
                padding: 8px;
                font-weight: 600;
            }
        """)
