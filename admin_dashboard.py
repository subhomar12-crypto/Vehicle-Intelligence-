"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Admin Dashboard

Admin Dashboard - Overview of System Status (v2.0)
Refactored with clean card-based layout
Displays subscription statistics, customer counts, and system health
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout, QScrollArea, QGroupBox, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

try:
    from config import get_config
    CONFIG = get_config()
except ImportError:
    CONFIG = None

try:
    from pricing_config_dialog import PricingConfigDialog
    PRICING_DIALOG_AVAILABLE = True
except ImportError:
    PRICING_DIALOG_AVAILABLE = False

try:
    from audit_log_viewer import AuditLogViewer
    AUDIT_VIEWER_AVAILABLE = True
except ImportError:
    AUDIT_VIEWER_AVAILABLE = False

logger = logging.getLogger(__name__)


class StatCard(QFrame):
    """A card displaying a single statistic with colored accent"""

    def __init__(self, title: str, value: str, subtitle: str = "", color: str = "#C40000", parent=None):
        super().__init__(parent)
        self.setFixedHeight(110)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #1E2329;
                border: 2px solid {color};
                border-radius: 10px;
                padding: 12px;
            }}
            QFrame:hover {{
                background-color: #252B33;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        # Title
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 9))
        title_label.setStyleSheet("color: #8B949E; border: none;")
        layout.addWidget(title_label)

        # Value
        self.value_label = QLabel(value)
        self.value_label.setFont(QFont("Segoe UI", 26, QFont.Bold))
        self.value_label.setStyleSheet(f"color: {color}; border: none;")
        layout.addWidget(self.value_label)

        # Subtitle
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setFont(QFont("Segoe UI", 8))
            subtitle_label.setStyleSheet("color: #6E7681; border: none;")
            layout.addWidget(subtitle_label)

        layout.addStretch()

    def update_value(self, value: str):
        self.value_label.setText(value)


class AdminDashboard(QWidget):
    """Admin Dashboard showing system overview - Refactored v2.0"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = CONFIG
        self._setup_ui()
        self._load_data()

        # Auto-refresh timer
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._load_data)
        self.refresh_timer.start(30000)  # Refresh every 30 seconds

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
        main_layout.setSpacing(18)

        # ========================================
        # HEADER
        # ========================================
        header_layout = QHBoxLayout()
        title = QLabel("Admin Dashboard")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title.setStyleSheet("color: #F0F6FC;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        # Audit Log button (opens audit log viewer)
        if AUDIT_VIEWER_AVAILABLE:
            audit_btn = QPushButton("Audit Log")
            audit_btn.setStyleSheet(self._get_button_style('secondary'))
            audit_btn.clicked.connect(self._open_audit_log)
            header_layout.addWidget(audit_btn)

        # Configure Pricing button (opens pricing dialog)
        if PRICING_DIALOG_AVAILABLE:
            pricing_btn = QPushButton("Configure Pricing")
            pricing_btn.setStyleSheet(self._get_button_style('warning'))
            pricing_btn.clicked.connect(self._open_pricing_config)
            header_layout.addWidget(pricing_btn)

        refresh_btn = QPushButton("Refresh Data")
        refresh_btn.setStyleSheet(self._get_button_style('primary'))
        refresh_btn.clicked.connect(self._load_data)
        header_layout.addWidget(refresh_btn)

        main_layout.addLayout(header_layout)

        # ========================================
        # TOP ROW - Subscription Stats
        # ========================================
        sub_stats_layout = QHBoxLayout()
        sub_stats_layout.setSpacing(15)

        self.total_subs_card = StatCard("Total Subscriptions", "0", "All time", "#0D6EFD")
        self.active_subs_card = StatCard("Active Subscriptions", "0", "Currently active", "#198754")
        self.trial_subs_card = StatCard("Trial Subscriptions", "0", "In trial period", "#FFC107")
        self.expired_subs_card = StatCard("Expired Subscriptions", "0", "Need attention", "#DC3545")

        sub_stats_layout.addWidget(self.total_subs_card)
        sub_stats_layout.addWidget(self.active_subs_card)
        sub_stats_layout.addWidget(self.trial_subs_card)
        sub_stats_layout.addWidget(self.expired_subs_card)

        main_layout.addLayout(sub_stats_layout)

        # ========================================
        # SECOND ROW - Customer & Revenue Stats
        # ========================================
        cust_stats_layout = QHBoxLayout()
        cust_stats_layout.setSpacing(15)

        self.total_customers_card = StatCard("Total Customers", "0", "Registered accounts", "#6F42C1")
        self.active_customers_card = StatCard("Active Customers", "0", "With active subscription", "#20C997")
        self.api_keys_card = StatCard("API Keys", "0", "Total issued", "#FD7E14")
        self.revenue_card = StatCard("Monthly Revenue", "$0", "This month", "#C40000")

        cust_stats_layout.addWidget(self.total_customers_card)
        cust_stats_layout.addWidget(self.active_customers_card)
        cust_stats_layout.addWidget(self.api_keys_card)
        cust_stats_layout.addWidget(self.revenue_card)

        main_layout.addLayout(cust_stats_layout)

        # ========================================
        # MIDDLE ROW - System Health & Plan Distribution
        # ========================================
        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(15)

        # System Health Card
        health_card = self._create_card("System Health", "#4CAF50")
        health_layout = QGridLayout(health_card)
        health_layout.setSpacing(10)

        # Status items
        health_items = [
            ("Integrity Check:", "Checking...", "integrity_status"),
            ("Last Backup:", "Unknown", "backup_status"),
            ("Monitoring:", "Unknown", "monitoring_status"),
            ("Data Directory:", "Checking...", "data_status"),
        ]

        for i, (label_text, default_value, attr_name) in enumerate(health_items):
            label = QLabel(label_text)
            label.setStyleSheet("color: #8B949E; font-size: 11px;")
            health_layout.addWidget(label, i, 0)

            value_label = QLabel(default_value)
            value_label.setStyleSheet("color: #FFC107; font-weight: bold;")
            setattr(self, attr_name, value_label)
            health_layout.addWidget(value_label, i, 1)

        health_layout.setColumnStretch(1, 1)
        middle_layout.addWidget(health_card)

        # Plan Distribution Card
        plan_card = self._create_card("Subscription Plans Distribution", "#FF9800")
        plan_layout = QVBoxLayout(plan_card)

        self.plan_bars_layout = QVBoxLayout()
        self.plan_bars_layout.setSpacing(8)
        plan_layout.addLayout(self.plan_bars_layout)

        middle_layout.addWidget(plan_card, 1)
        main_layout.addLayout(middle_layout)

        # ========================================
        # BOTTOM - Recent Activity Table
        # ========================================
        activity_card = self._create_card("Recent Activity", "#2196F3")
        activity_layout = QVBoxLayout(activity_card)

        self.activity_table = QTableWidget()
        self.activity_table.setColumnCount(4)
        self.activity_table.setHorizontalHeaderLabels(["Time", "Type", "Customer", "Details"])
        self.activity_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.activity_table.setMinimumHeight(200)
        self.activity_table.setMaximumHeight(250)
        self._apply_table_styling(self.activity_table)
        activity_layout.addWidget(self.activity_table)

        main_layout.addWidget(activity_card)
        main_layout.addStretch()

        scroll.setWidget(content)

        # Container layout
        container_layout = QVBoxLayout(self)
        container_layout.setContentsMargins(15, 15, 15, 15)
        container_layout.addWidget(scroll)

    def _load_data(self):
        """Load and display dashboard data"""
        try:
            # Load subscription stats
            sub_stats = self._get_subscription_stats()
            self.total_subs_card.update_value(str(sub_stats.get('total', 0)))
            self.active_subs_card.update_value(str(sub_stats.get('active', 0)))
            self.trial_subs_card.update_value(str(sub_stats.get('trial', 0)))
            self.expired_subs_card.update_value(str(sub_stats.get('expired', 0)))

            # Load customer stats
            cust_stats = self._get_customer_stats()
            self.total_customers_card.update_value(str(cust_stats.get('total', 0)))
            self.active_customers_card.update_value(str(cust_stats.get('active', 0)))
            self.api_keys_card.update_value(str(cust_stats.get('api_keys', 0)))

            # Revenue
            self.revenue_card.update_value(f"${sub_stats.get('revenue', 0):,.2f}")

            # Update health status
            self._update_health_status()

            # Update recent activity
            self._update_activity_table()

            # Update plan distribution
            self._update_plan_distribution(sub_stats.get('by_plan', {}))

        except Exception as e:
            logger.error(f"Error loading dashboard data: {e}")

    def _open_pricing_config(self):
        """Open the Pricing Configuration dialog."""
        if not PRICING_DIALOG_AVAILABLE:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Not Available",
                "Pricing Configuration dialog is not available."
            )
            return

        try:
            dialog = PricingConfigDialog(parent=self)
            dialog.pricing_updated.connect(self._on_pricing_updated)
            dialog.exec()
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            logger.error(f"Error opening pricing config: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to open Pricing Configuration: {e}"
            )

    def _on_pricing_updated(self):
        """Handle pricing update from dialog."""
        # Refresh data to show updated revenue calculations
        self._load_data()
        logger.info("Pricing configuration updated")

    def _open_audit_log(self):
        """Open the Audit Log Viewer dialog."""
        if not AUDIT_VIEWER_AVAILABLE:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Not Available",
                "Audit Log Viewer is not available."
            )
            return

        try:
            # Open without user_id filter to show all entries
            dialog = AuditLogViewer(user_id=None, parent=self)
            dialog.exec()
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            logger.error(f"Error opening audit log: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to open Audit Log Viewer: {e}"
            )

    def _get_subscription_stats(self) -> Dict[str, Any]:
        """Get subscription statistics"""
        stats = {
            'total': 0,
            'active': 0,
            'trial': 0,
            'expired': 0,
            'cancelled': 0,
            'revenue': 0.0,
            'by_plan': {}
        }

        if not self.config:
            return stats

        customers_dir = self.config.CUSTOMERS_DIR
        if not customers_dir.exists():
            return stats

        plan_prices = {
            'trial': 0,
            'basic': 29.99,
            'professional': 79.99,
            'enterprise': 199.99
        }

        for customer_dir in customers_dir.iterdir():
            if not customer_dir.is_dir():
                continue

            sub_file = customer_dir / "subscription.json"
            if not sub_file.exists():
                continue

            try:
                with open(sub_file, 'r') as f:
                    sub = json.load(f)

                stats['total'] += 1
                status = sub.get('status', 'unknown')
                plan = sub.get('plan', 'unknown')

                if status == 'active':
                    stats['active'] += 1
                    stats['revenue'] += plan_prices.get(plan, 0)
                elif status == 'trial':
                    stats['trial'] += 1
                elif status in ['expired', 'past_due']:
                    stats['expired'] += 1
                elif status == 'cancelled':
                    stats['cancelled'] += 1

                stats['by_plan'][plan] = stats['by_plan'].get(plan, 0) + 1

            except Exception as e:
                logger.warning(f"Error reading subscription: {e}")

        return stats

    def _get_customer_stats(self) -> Dict[str, Any]:
        """Get customer statistics"""
        stats = {
            'total': 0,
            'active': 0,
            'api_keys': 0
        }

        if not self.config:
            return stats

        customers_dir = self.config.CUSTOMERS_DIR
        if not customers_dir.exists():
            return stats

        for customer_dir in customers_dir.iterdir():
            if not customer_dir.is_dir():
                continue

            profile_file = customer_dir / "profile.json"
            if profile_file.exists():
                stats['total'] += 1

                try:
                    with open(profile_file, 'r') as f:
                        profile = json.load(f)
                    if profile.get('status') == 'active':
                        stats['active'] += 1
                except:
                    pass

        # Count API keys
        api_keys_file = self.config.API_KEYS_FILE
        if api_keys_file.exists():
            try:
                with open(api_keys_file, 'r') as f:
                    api_keys = json.load(f)
                stats['api_keys'] = len(api_keys)
            except:
                pass

        return stats

    def _update_health_status(self):
        """Update system health indicators"""
        # Check integrity
        try:
            from system_integrity import run_startup_integrity_check
            passed, report = run_startup_integrity_check()
            if passed:
                self.integrity_status.setText("Passed")
                self.integrity_status.setStyleSheet("color: #198754; font-weight: bold;")
            else:
                violations = len(report.get('violations', []))
                self.integrity_status.setText(f"Issues ({violations})")
                self.integrity_status.setStyleSheet("color: #DC3545; font-weight: bold;")
        except:
            self.integrity_status.setText("Not Available")
            self.integrity_status.setStyleSheet("color: #6E7681;")

        # Check backup
        try:
            from enterprise_backup import EnterpriseBackupManager
            backup_mgr = EnterpriseBackupManager()
            backups = backup_mgr.list_backups()
            if backups:
                latest = backups[0]
                timestamp = latest.get('timestamp', 'Unknown')
                # Format timestamp for display
                if timestamp != 'Unknown':
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        timestamp = dt.strftime('%Y-%m-%d %H:%M')
                    except:
                        pass
                self.backup_status.setText(timestamp)
                self.backup_status.setStyleSheet("color: #198754;")
            else:
                self.backup_status.setText("No backups found")
                self.backup_status.setStyleSheet("color: #FFC107;")
        except:
            self.backup_status.setText("Not available")
            self.backup_status.setStyleSheet("color: #6E7681;")

        # Check monitoring
        try:
            from monitoring_alerts import AlertMonitor
            self.monitoring_status.setText("Active")
            self.monitoring_status.setStyleSheet("color: #198754; font-weight: bold;")
        except:
            self.monitoring_status.setText("Not configured")
            self.monitoring_status.setStyleSheet("color: #6E7681;")

        # Check data directory
        if self.config and self.config.DATA_DIR.exists():
            self.data_status.setText("OK")
            self.data_status.setStyleSheet("color: #198754; font-weight: bold;")
        else:
            self.data_status.setText("Not found")
            self.data_status.setStyleSheet("color: #DC3545; font-weight: bold;")

    def _update_activity_table(self):
        """Update recent activity table"""
        self.activity_table.setRowCount(0)

        activities = []

        if not self.config:
            return

        # Gather recent subscription activities
        customers_dir = self.config.CUSTOMERS_DIR
        if customers_dir.exists():
            for customer_dir in customers_dir.iterdir():
                if not customer_dir.is_dir():
                    continue

                sub_file = customer_dir / "subscription.json"
                if not sub_file.exists():
                    continue

                try:
                    with open(sub_file, 'r') as f:
                        sub = json.load(f)

                    # Add creation activity
                    created = sub.get('created_at', '')
                    if created:
                        activities.append({
                            'time': created,
                            'type': 'Subscription Created',
                            'customer': sub.get('customer_id', 'Unknown'),
                            'details': f"Plan: {sub.get('plan', 'Unknown')}"
                        })

                    # Add from audit log
                    for log_entry in sub.get('audit_log', [])[-3:]:
                        activities.append({
                            'time': log_entry.get('timestamp', ''),
                            'type': log_entry.get('action', 'Unknown'),
                            'customer': sub.get('customer_id', 'Unknown'),
                            'details': log_entry.get('details', '')[:50]
                        })

                except Exception as e:
                    logger.warning(f"Error reading subscription activity: {e}")

        # Sort by time descending and take top 10
        activities.sort(key=lambda x: x.get('time', ''), reverse=True)
        activities = activities[:10]

        # Populate table
        for activity in activities:
            row = self.activity_table.rowCount()
            self.activity_table.insertRow(row)

            # Format time
            time_str = activity.get('time', '')
            if time_str:
                try:
                    dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    time_str = dt.strftime('%Y-%m-%d %H:%M')
                except:
                    pass

            self.activity_table.setItem(row, 0, QTableWidgetItem(time_str))
            self.activity_table.setItem(row, 1, QTableWidgetItem(activity.get('type', '')))
            self.activity_table.setItem(row, 2, QTableWidgetItem(activity.get('customer', '')))
            self.activity_table.setItem(row, 3, QTableWidgetItem(activity.get('details', '')))

    def _update_plan_distribution(self, by_plan: Dict[str, int]):
        """Update plan distribution bars"""
        # Clear existing bars
        while self.plan_bars_layout.count():
            item = self.plan_bars_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not by_plan:
            label = QLabel("No subscription data available")
            label.setStyleSheet("color: #6E7681; font-style: italic;")
            self.plan_bars_layout.addWidget(label)
            return

        total = sum(by_plan.values())
        if total == 0:
            return

        plan_colors = {
            'trial': '#FFC107',
            'basic': '#0D6EFD',
            'professional': '#198754',
            'enterprise': '#6F42C1'
        }

        for plan, count in sorted(by_plan.items(), key=lambda x: x[1], reverse=True):
            row = QHBoxLayout()

            # Plan name
            name_label = QLabel(plan.capitalize())
            name_label.setFixedWidth(100)
            name_label.setStyleSheet("color: #C9D1D9; font-weight: 600;")
            row.addWidget(name_label)

            # Progress bar
            progress = QProgressBar()
            progress.setMaximum(total)
            progress.setValue(count)
            progress.setTextVisible(False)
            progress.setFixedHeight(22)
            color = plan_colors.get(plan, '#8B949E')
            progress.setStyleSheet(f"""
                QProgressBar {{
                    background-color: #30363D;
                    border-radius: 4px;
                }}
                QProgressBar::chunk {{
                    background-color: {color};
                    border-radius: 4px;
                }}
            """)
            row.addWidget(progress, 1)

            # Count and percentage
            percentage = (count * 100) // total if total > 0 else 0
            count_label = QLabel(f"{count} ({percentage}%)")
            count_label.setFixedWidth(80)
            count_label.setAlignment(Qt.AlignRight)
            count_label.setStyleSheet("color: #8B949E;")
            row.addWidget(count_label)

            container = QWidget()
            container.setLayout(row)
            self.plan_bars_layout.addWidget(container)

    def _get_button_style(self, style_type: str = 'primary') -> str:
        """Get consistent button stylesheet"""
        styles = {
            'primary': """
                QPushButton {
                    background-color: #C40000;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    font-size: 12px;
                    font-weight: bold;
                    border-radius: 6px;
                }
                QPushButton:hover { background-color: #E53935; }
                QPushButton:pressed { background-color: #B71C1C; }
            """,
            'secondary': """
                QPushButton {
                    background-color: #2C3E50;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    font-size: 12px;
                    font-weight: 600;
                    border-radius: 5px;
                }
                QPushButton:hover { background-color: #34495E; }
            """,
            'warning': """
                QPushButton {
                    background-color: #F59E0B;
                    color: #000000;
                    border: none;
                    padding: 10px 20px;
                    font-size: 12px;
                    font-weight: bold;
                    border-radius: 6px;
                }
                QPushButton:hover { background-color: #FBBF24; }
                QPushButton:pressed { background-color: #D97706; }
            """,
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
