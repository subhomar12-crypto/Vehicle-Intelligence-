"""
PREDICT - Vehicle Intelligence Platform
Copyright (c) 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: February 2026
Module: Pricing Configuration Dialog

Desktop Admin dialog for configuring subscription tier pricing.
Prices are stored on the server and can be updated anytime without app updates.
Android paywall fetches pricing dynamically from the server.
"""

import logging
import sqlite3
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QLineEdit, QComboBox, QMessageBox,
    QDoubleSpinBox, QSpinBox, QTextEdit, QFrame, QGridLayout
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

logger = logging.getLogger(__name__)

# Database path
DB_PATH = Path("C:/OBDserver/Previlium_OBD_Server/data/predict.db")


@dataclass
class TierPricing:
    """Pricing data for a subscription tier"""
    tier: str
    price_monthly: float
    price_annual: Optional[float] = None
    currency: str = "USD"
    currency_symbol: str = "$"
    description: str = ""
    features_summary: str = ""


class PriceInput(QFrame):
    """Custom price input widget with currency symbol"""

    def __init__(self, label: str, initial_value: float = 0.0,
                 readonly: bool = False, parent=None):
        super().__init__(parent)
        self.readonly = readonly
        self._setup_ui(label, initial_value)

    def _setup_ui(self, label: str, initial_value: float):
        self.setStyleSheet("""
            QFrame {
                background-color: #1E2329;
                border: 1px solid #30363D;
                border-radius: 8px;
                padding: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Label
        title = QLabel(label)
        title.setStyleSheet("color: #8B949E; font-size: 11px; font-weight: bold; border: none;")
        layout.addWidget(title)

        # Price input row
        price_layout = QHBoxLayout()
        price_layout.setSpacing(4)

        self.currency_label = QLabel("$")
        self.currency_label.setStyleSheet("color: #F0F6FC; font-size: 18px; font-weight: bold; border: none;")
        price_layout.addWidget(self.currency_label)

        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(0, 9999.99)
        self.price_spin.setDecimals(2)
        self.price_spin.setValue(initial_value)
        self.price_spin.setReadOnly(self.readonly)
        self.price_spin.setStyleSheet(f"""
            QDoubleSpinBox {{
                background-color: {'#161B22' if self.readonly else '#21262D'};
                color: {'#6B7280' if self.readonly else '#F0F6FC'};
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 18px;
                font-weight: bold;
                min-width: 120px;
            }}
            QDoubleSpinBox:focus {{
                border-color: #C40000;
            }}
        """)
        price_layout.addWidget(self.price_spin)

        per_month = QLabel("/month")
        per_month.setStyleSheet("color: #6B7280; font-size: 12px; border: none;")
        price_layout.addWidget(per_month)

        price_layout.addStretch()
        layout.addLayout(price_layout)

    def set_currency_symbol(self, symbol: str):
        self.currency_label.setText(symbol)

    def get_value(self) -> float:
        return self.price_spin.value()

    def set_value(self, value: float):
        self.price_spin.setValue(value)


class PricingConfigDialog(QDialog):
    """
    Pricing Configuration Dialog

    Allows admin to:
    - Set monthly prices for Pro and Premium tiers
    - Configure annual discount percentage
    - Set currency and symbol
    - Add descriptions for paywall display

    Changes are saved to the server database and immediately
    reflected in the Android app's paywall.
    """

    pricing_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pricing_data: Dict[str, TierPricing] = {}

        self.setWindowTitle("Subscription Pricing Configuration")
        self.setMinimumSize(600, 700)
        self._apply_styling()
        self._setup_ui()
        self._load_pricing()

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
                padding: 10px 20px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #30363D;
            }
            QLineEdit, QTextEdit {
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 8px 12px;
            }
            QLineEdit:focus, QTextEdit:focus {
                border-color: #C40000;
            }
            QComboBox {
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 8px 12px;
                min-width: 100px;
            }
            QComboBox:focus {
                border-color: #C40000;
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
        layout.setContentsMargins(24, 24, 24, 24)

        # Header
        header = QLabel("Subscription Pricing Configuration")
        header.setFont(QFont("Segoe UI", 18, QFont.Bold))
        header.setStyleSheet("color: #F0F6FC;")
        layout.addWidget(header)

        subtitle = QLabel("Configure prices that will be displayed in the Android app paywall")
        subtitle.setStyleSheet("color: #8B949E; font-size: 12px;")
        layout.addWidget(subtitle)

        # Tier Pricing Group
        pricing_group = QGroupBox("Tier Pricing (Monthly)")
        pricing_layout = QVBoxLayout(pricing_group)
        pricing_layout.setSpacing(12)

        # Free tier (always $0, readonly)
        self.free_price = PriceInput("Free Tier", 0.0, readonly=True)
        pricing_layout.addWidget(self.free_price)

        # Pro tier
        self.pro_price = PriceInput("Pro Tier", 0.0)
        pricing_layout.addWidget(self.pro_price)

        # Premium tier
        self.premium_price = PriceInput("Premium Tier", 0.0)
        pricing_layout.addWidget(self.premium_price)

        layout.addWidget(pricing_group)

        # Annual Discount Group
        discount_group = QGroupBox("Annual Discount")
        discount_layout = QFormLayout(discount_group)
        discount_layout.setSpacing(12)

        discount_row = QHBoxLayout()
        self.annual_discount = QSpinBox()
        self.annual_discount.setRange(0, 50)
        self.annual_discount.setValue(20)
        self.annual_discount.setSuffix(" %")
        self.annual_discount.setStyleSheet("""
            QSpinBox {
                background-color: #21262D;
                color: #F0F6FC;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
                min-width: 100px;
            }
        """)
        discount_row.addWidget(self.annual_discount)

        discount_hint = QLabel("(e.g., 20% = ~2 months free on annual)")
        discount_hint.setStyleSheet("color: #6B7280; font-size: 11px;")
        discount_row.addWidget(discount_hint)
        discount_row.addStretch()

        discount_layout.addRow("Annual discount:", discount_row)
        layout.addWidget(discount_group)

        # Currency Group
        currency_group = QGroupBox("Currency")
        currency_layout = QFormLayout(currency_group)
        currency_layout.setSpacing(12)

        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["USD", "EUR", "GBP", "CAD", "AUD", "ILS"])
        self.currency_combo.currentTextChanged.connect(self._on_currency_changed)
        currency_layout.addRow("Display currency:", self.currency_combo)

        self.currency_symbol = QLineEdit("$")
        self.currency_symbol.setMaximumWidth(60)
        self.currency_symbol.textChanged.connect(self._update_currency_symbols)
        currency_layout.addRow("Currency symbol:", self.currency_symbol)

        layout.addWidget(currency_group)

        # Descriptions Group
        desc_group = QGroupBox("Pricing Display Text (shown in Android paywall)")
        desc_layout = QFormLayout(desc_group)
        desc_layout.setSpacing(12)

        self.pro_description = QLineEdit()
        self.pro_description.setPlaceholderText("e.g., AI predictions, chat assistant, 7-day history")
        desc_layout.addRow("Pro description:", self.pro_description)

        self.premium_description = QLineEdit()
        self.premium_description.setPlaceholderText("e.g., Full fleet management, unlimited history")
        desc_layout.addRow("Premium description:", self.premium_description)

        layout.addWidget(desc_group)

        # Features Summary Group
        features_group = QGroupBox("Feature Bullet Points (for paywall)")
        features_layout = QFormLayout(features_group)
        features_layout.setSpacing(12)

        self.pro_features = QTextEdit()
        self.pro_features.setPlaceholderText("One feature per line:\nAI-powered predictions\nChat assistant\n7-day trip history")
        self.pro_features.setMaximumHeight(80)
        features_layout.addRow("Pro features:", self.pro_features)

        self.premium_features = QTextEdit()
        self.premium_features.setPlaceholderText("One feature per line:\nAll Pro features\nGuardian fleet mode\n365-day history")
        self.premium_features.setMaximumHeight(80)
        features_layout.addRow("Premium features:", self.premium_features)

        layout.addWidget(features_group)

        # Preview section
        preview_group = QGroupBox("Preview (as shown in app)")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_label = QLabel()
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #161B22;
                border: 1px solid #30363D;
                border-radius: 8px;
                padding: 16px;
                font-size: 12px;
            }
        """)
        self._update_preview()
        preview_layout.addWidget(self.preview_label)

        # Connect signals for live preview
        self.pro_price.price_spin.valueChanged.connect(self._update_preview)
        self.premium_price.price_spin.valueChanged.connect(self._update_preview)
        self.annual_discount.valueChanged.connect(self._update_preview)
        self.currency_symbol.textChanged.connect(self._update_preview)

        layout.addWidget(preview_group)

        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save Pricing")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #C40000;
                border-color: #C40000;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #A00000;
            }
        """)
        save_btn.clicked.connect(self._save_pricing)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

    def _on_currency_changed(self, currency: str):
        """Update currency symbol based on selected currency"""
        symbols = {
            "USD": "$",
            "EUR": "\u20AC",
            "GBP": "\u00A3",
            "CAD": "C$",
            "AUD": "A$",
            "ILS": "\u20AA"
        }
        self.currency_symbol.setText(symbols.get(currency, "$"))

    def _update_currency_symbols(self, symbol: str):
        """Update currency symbols in price inputs"""
        self.free_price.set_currency_symbol(symbol)
        self.pro_price.set_currency_symbol(symbol)
        self.premium_price.set_currency_symbol(symbol)

    def _update_preview(self):
        """Update the pricing preview"""
        symbol = self.currency_symbol.text()
        pro_monthly = self.pro_price.get_value()
        premium_monthly = self.premium_price.get_value()
        discount = self.annual_discount.value()

        # Calculate annual prices
        pro_annual = pro_monthly * 12 * (1 - discount / 100)
        premium_annual = premium_monthly * 12 * (1 - discount / 100)

        preview_text = f"""
<b>Pro Plan</b><br>
Monthly: {symbol}{pro_monthly:.2f}/month<br>
Annual: {symbol}{pro_annual:.2f}/year ({discount}% off)<br>
<br>
<b>Premium Plan</b><br>
Monthly: {symbol}{premium_monthly:.2f}/month<br>
Annual: {symbol}{premium_annual:.2f}/year ({discount}% off)
        """
        self.preview_label.setText(preview_text.strip())

    def _load_pricing(self):
        """Load current pricing from database"""
        try:
            if not DB_PATH.exists():
                logger.warning(f"Database not found: {DB_PATH}")
                return

            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Check if table exists
            cur.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='pricing_config'
            """)
            if not cur.fetchone():
                conn.close()
                logger.info("pricing_config table not found, using defaults")
                return

            # Load pricing for each tier
            cur.execute("""
                SELECT tier, price_monthly, price_annual, currency,
                       currency_symbol, description, features_summary
                FROM pricing_config
            """)

            for row in cur.fetchall():
                tier = row['tier']
                if tier == 'pro':
                    self.pro_price.set_value(row['price_monthly'] or 0)
                    self.pro_description.setText(row['description'] or "")
                    self.pro_features.setText(row['features_summary'] or "")
                    if row['currency']:
                        idx = self.currency_combo.findText(row['currency'])
                        if idx >= 0:
                            self.currency_combo.setCurrentIndex(idx)
                    if row['currency_symbol']:
                        self.currency_symbol.setText(row['currency_symbol'])
                elif tier == 'premium':
                    self.premium_price.set_value(row['price_monthly'] or 0)
                    self.premium_description.setText(row['description'] or "")
                    self.premium_features.setText(row['features_summary'] or "")

            conn.close()
            self._update_preview()

        except Exception as e:
            logger.error(f"Error loading pricing: {e}")

    def _save_pricing(self):
        """Save pricing to database"""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cur = conn.cursor()

            # Ensure table exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pricing_config (
                    id INTEGER PRIMARY KEY,
                    tier TEXT UNIQUE NOT NULL,
                    price_monthly REAL NOT NULL,
                    price_annual REAL,
                    currency TEXT DEFAULT 'USD',
                    currency_symbol TEXT DEFAULT '$',
                    description TEXT,
                    features_summary TEXT,
                    updated_at REAL,
                    updated_by INTEGER
                )
            """)

            currency = self.currency_combo.currentText()
            symbol = self.currency_symbol.text()
            discount = self.annual_discount.value()
            admin_id = 1  # Desktop admin

            # Save each tier
            tiers_data = [
                ('free', 0, 0, "Basic OBD reading", ""),
                ('pro', self.pro_price.get_value(),
                 self.pro_price.get_value() * 12 * (1 - discount / 100),
                 self.pro_description.text(),
                 self.pro_features.toPlainText()),
                ('premium', self.premium_price.get_value(),
                 self.premium_price.get_value() * 12 * (1 - discount / 100),
                 self.premium_description.text(),
                 self.premium_features.toPlainText()),
            ]

            for tier, monthly, annual, desc, features in tiers_data:
                cur.execute("""
                    INSERT INTO pricing_config
                    (tier, price_monthly, price_annual, currency, currency_symbol,
                     description, features_summary, updated_at, updated_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(tier) DO UPDATE SET
                        price_monthly = excluded.price_monthly,
                        price_annual = excluded.price_annual,
                        currency = excluded.currency,
                        currency_symbol = excluded.currency_symbol,
                        description = excluded.description,
                        features_summary = excluded.features_summary,
                        updated_at = excluded.updated_at,
                        updated_by = excluded.updated_by
                """, (tier, monthly, annual, currency, symbol, desc, features,
                      time.time(), admin_id))

            conn.commit()
            conn.close()

            QMessageBox.information(
                self,
                "Pricing Saved",
                "Subscription pricing has been updated.\n\n"
                "Changes will be reflected immediately in the Android app paywall."
            )

            self.pricing_updated.emit()
            self.accept()

        except Exception as e:
            logger.error(f"Error saving pricing: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save pricing: {e}")


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

    dialog = PricingConfigDialog()
    dialog.exec()

    sys.exit(0)
