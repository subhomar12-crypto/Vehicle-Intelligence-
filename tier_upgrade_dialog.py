"""
PREDICT - Vehicle Intelligence Platform
Copyright 2026 PREDICT
All rights reserved.

Tier Upgrade Dialog - Premium UI for subscription tier selection
Shows tier comparison, features unlocked, and handles upgrade requests.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QGridLayout, QWidget, QButtonGroup,
    QRadioButton, QTextEdit, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QColor, QIcon
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class PremiumDialogTheme:
    """Premium theme for upgrade dialog"""

    # Backgrounds
    BG_DIALOG = "#0D0F12"
    BG_CARD = "#141820"
    BG_CARD_SELECTED = "#1A2530"
    BG_CARD_HOVER = "#1C2028"

    # Tier colors
    TIER_FREE = "#6E7681"
    TIER_BASIC = "#4CAF50"
    TIER_PREMIUM = "#FFD700"
    TIER_ENTERPRISE = "#DC3545"

    # Accents
    ACCENT_CYAN = "#00D4FF"
    ACCENT_EMERALD = "#00E676"

    # Text
    TEXT_PRIMARY = "#F8F9FA"
    TEXT_SECONDARY = "#9AA0A6"
    TEXT_MUTED = "#5F6368"

    # Borders
    BORDER_DEFAULT = "#1E2430"
    BORDER_SELECTED = "#00D4FF"


class TierCard(QFrame):
    """Individual tier selection card"""

    clicked = Signal(str)  # tier_key

    def __init__(self, tier_key: str, tier_info: Dict[str, Any], is_current: bool = False, parent=None):
        super().__init__(parent)
        self.tier_key = tier_key
        self.tier_info = tier_info
        self.is_current = is_current
        self.is_selected = False

        self.setObjectName("TierCard")
        self.setCursor(Qt.PointingHandCursor if not is_current else Qt.ArrowCursor)
        self.setMinimumWidth(200)
        self.setMinimumHeight(280)

        self._setup_ui()
        self._update_style()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(12)

        # Tier badge / header
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        # Tier name with color
        tier_color = self.tier_info.get('color', PremiumDialogTheme.TEXT_PRIMARY)
        name_label = QLabel(self.tier_info.get('name', 'Unknown').upper())
        name_label.setStyleSheet(f"""
            font-size: 18px;
            font-weight: 800;
            color: {tier_color};
            letter-spacing: 2px;
        """)
        header_layout.addWidget(name_label)

        # Price
        price_label = QLabel(self.tier_info.get('price', 'Free'))
        price_label.setStyleSheet(f"""
            font-size: 14px;
            font-weight: 600;
            color: {PremiumDialogTheme.TEXT_SECONDARY};
        """)
        header_layout.addWidget(price_label)

        # Current badge if applicable
        if self.is_current:
            current_badge = QLabel("CURRENT PLAN")
            current_badge.setStyleSheet(f"""
                background-color: {PremiumDialogTheme.ACCENT_CYAN}33;
                color: {PremiumDialogTheme.ACCENT_CYAN};
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1px;
            """)
            current_badge.setAlignment(Qt.AlignCenter)
            header_layout.addWidget(current_badge)

        layout.addWidget(header)

        # Description
        desc_label = QLabel(self.tier_info.get('description', ''))
        desc_label.setStyleSheet(f"""
            font-size: 12px;
            color: {PremiumDialogTheme.TEXT_MUTED};
            padding: 8px 0;
        """)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Divider
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {PremiumDialogTheme.BORDER_DEFAULT};")
        layout.addWidget(divider)

        # Features list
        features_widget = QWidget()
        features_layout = QVBoxLayout(features_widget)
        features_layout.setContentsMargins(0, 8, 0, 0)
        features_layout.setSpacing(6)

        features = self.tier_info.get('features', [])
        feature_labels = {
            'vehicle_data': 'Vehicle Monitoring',
            'diagnostic': 'DTC Diagnostics',
            'predict': 'AI Predictions',
            'llm_chat': 'AI Chat Assistant',
            'reports': 'PDF Reports',
            'guardian': 'Guardian Mode',
            'admin': 'Admin Access',
            'api_access': 'API Access'
        }

        for feature in features:
            feature_name = feature_labels.get(feature, feature.replace('_', ' ').title())
            feature_item = QLabel(f"  {feature_name}")
            feature_item.setStyleSheet(f"""
                font-size: 11px;
                color: {PremiumDialogTheme.ACCENT_EMERALD};
            """)
            features_layout.addWidget(feature_item)

        layout.addWidget(features_widget)

        # Limits info
        limits = self.tier_info.get('limits', {})
        predictions = limits.get('predictions', 0)
        if predictions == -1:
            limit_text = "Unlimited predictions"
        elif predictions == 0:
            limit_text = "No predictions"
        else:
            limit_text = f"{predictions} predictions/month"

        limit_label = QLabel(limit_text)
        limit_label.setStyleSheet(f"""
            font-size: 11px;
            color: {PremiumDialogTheme.TEXT_MUTED};
            font-style: italic;
            padding-top: 8px;
        """)
        layout.addWidget(limit_label)

        layout.addStretch()

    def _update_style(self):
        if self.is_current:
            bg_color = PremiumDialogTheme.BG_CARD
            border_color = PremiumDialogTheme.ACCENT_CYAN
            border_width = 2
        elif self.is_selected:
            bg_color = PremiumDialogTheme.BG_CARD_SELECTED
            border_color = PremiumDialogTheme.BORDER_SELECTED
            border_width = 2
        else:
            bg_color = PremiumDialogTheme.BG_CARD
            border_color = PremiumDialogTheme.BORDER_DEFAULT
            border_width = 1

        self.setStyleSheet(f"""
            QFrame#TierCard {{
                background-color: {bg_color};
                border: {border_width}px solid {border_color};
                border-radius: 12px;
            }}
            QFrame#TierCard:hover {{
                background-color: {PremiumDialogTheme.BG_CARD_HOVER};
            }}
        """)

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self._update_style()

    def mousePressEvent(self, event):
        if not self.is_current:
            self.clicked.emit(self.tier_key)
        super().mousePressEvent(event)


class TierUpgradeDialog(QDialog):
    """
    Premium dialog for tier selection and upgrade request.

    Shows all available tiers with feature comparison,
    allows selection of a higher tier, and submits upgrade request.
    """

    # Signals
    upgrade_requested = Signal(str, str, dict)  # (owner_id, new_tier, request_data)

    # Tier definitions
    TIER_FEATURES = {
        "free": {
            "name": "Free",
            "color": PremiumDialogTheme.TIER_FREE,
            "price": "QAR 0/month",
            "features": ["vehicle_data", "diagnostic"],
            "description": "Basic vehicle monitoring and diagnostics. Perfect for getting started.",
            "limits": {"predictions": 0, "api_access": False}
        },
        "basic": {
            "name": "Basic",
            "color": PremiumDialogTheme.TIER_BASIC,
            "price": "QAR 49/month",
            "features": ["vehicle_data", "diagnostic", "predict"],
            "description": "Add AI predictions to anticipate maintenance needs.",
            "limits": {"predictions": 3, "api_access": False}
        },
        "premium": {
            "name": "Premium",
            "color": PremiumDialogTheme.TIER_PREMIUM,
            "price": "QAR 149/month",
            "features": ["vehicle_data", "diagnostic", "predict", "llm_chat", "reports", "api_access"],
            "description": "Unlimited predictions, AI chat, and PDF reports. Full access.",
            "limits": {"predictions": -1, "api_access": True}
        },
        "enterprise": {
            "name": "Enterprise",
            "color": PremiumDialogTheme.TIER_ENTERPRISE,
            "price": "Contact Sales",
            "features": ["vehicle_data", "diagnostic", "predict", "llm_chat", "reports", "guardian", "admin", "api_access"],
            "description": "Multi-user support, Guardian mode, and priority support.",
            "limits": {"predictions": -1, "api_access": True, "multi_user": True}
        }
    }

    TIER_ORDER = ["free", "basic", "premium", "enterprise"]

    def __init__(self, owner_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.owner_data = owner_data
        self.owner_id = owner_data.get('owner_id')
        self.current_tier = owner_data.get('tier', 'free').lower()
        self.selected_tier = None
        self.tier_cards: Dict[str, TierCard] = {}

        self.setWindowTitle("Upgrade Subscription Tier")
        self.setMinimumSize(900, 600)
        self.setModal(True)

        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {PremiumDialogTheme.BG_DIALOG};
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)

        # Header
        header = self._create_header()
        main_layout.addWidget(header)

        # Tier cards container
        cards_container = QWidget()
        cards_layout = QHBoxLayout(cards_container)
        cards_layout.setSpacing(16)

        current_tier_idx = self.TIER_ORDER.index(self.current_tier) if self.current_tier in self.TIER_ORDER else 0

        for i, tier_key in enumerate(self.TIER_ORDER):
            tier_info = self.TIER_FEATURES[tier_key]
            is_current = (tier_key == self.current_tier)

            card = TierCard(tier_key, tier_info, is_current)
            card.clicked.connect(self._on_tier_selected)

            # Disable cards for lower tiers
            if i < current_tier_idx:
                card.setEnabled(False)
                card.setCursor(Qt.ForbiddenCursor)
                card.setStyleSheet(f"""
                    QFrame#TierCard {{
                        background-color: {PremiumDialogTheme.BG_CARD};
                        border: 1px solid {PremiumDialogTheme.BORDER_DEFAULT};
                        border-radius: 12px;
                        opacity: 0.5;
                    }}
                """)

            self.tier_cards[tier_key] = card
            cards_layout.addWidget(card)

        main_layout.addWidget(cards_container)

        # Selected tier info
        self.selection_info = QLabel("Select a tier to upgrade to")
        self.selection_info.setStyleSheet(f"""
            font-size: 14px;
            color: {PremiumDialogTheme.TEXT_SECONDARY};
            padding: 12px;
            background-color: {PremiumDialogTheme.BG_CARD};
            border-radius: 8px;
        """)
        self.selection_info.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.selection_info)

        # Action buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(44)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PremiumDialogTheme.BG_CARD};
                color: {PremiumDialogTheme.TEXT_PRIMARY};
                border: 1px solid {PremiumDialogTheme.BORDER_DEFAULT};
                padding: 12px 32px;
                font-size: 14px;
                font-weight: 600;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background-color: {PremiumDialogTheme.BG_CARD_HOVER};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)

        self.upgrade_btn = QPushButton("Request Upgrade")
        self.upgrade_btn.setMinimumHeight(44)
        self.upgrade_btn.setCursor(Qt.PointingHandCursor)
        self.upgrade_btn.setEnabled(False)
        self.upgrade_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {PremiumDialogTheme.ACCENT_CYAN},
                    stop:1 #0099CC);
                color: {PremiumDialogTheme.BG_DIALOG};
                border: none;
                padding: 12px 32px;
                font-size: 14px;
                font-weight: 700;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #33DFFF,
                    stop:1 #00B8E6);
            }}
            QPushButton:disabled {{
                background-color: {PremiumDialogTheme.BG_CARD};
                color: {PremiumDialogTheme.TEXT_MUTED};
            }}
        """)
        self.upgrade_btn.clicked.connect(self._on_upgrade_clicked)

        buttons_layout.addStretch()
        buttons_layout.addWidget(cancel_btn)
        buttons_layout.addWidget(self.upgrade_btn)

        main_layout.addLayout(buttons_layout)

    def _create_header(self) -> QWidget:
        header = QWidget()
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Title
        title = QLabel("Upgrade Your Subscription")
        title.setStyleSheet(f"""
            font-size: 24px;
            font-weight: 800;
            color: {PremiumDialogTheme.TEXT_PRIMARY};
            letter-spacing: 1px;
        """)
        layout.addWidget(title)

        # Subtitle with current user info
        owner_name = self.owner_data.get('name', 'Unknown')
        subtitle = QLabel(f"Owner: {owner_name}  |  Current Tier: {self.current_tier.upper()}")
        subtitle.setStyleSheet(f"""
            font-size: 14px;
            color: {PremiumDialogTheme.TEXT_SECONDARY};
        """)
        layout.addWidget(subtitle)

        return header

    def _on_tier_selected(self, tier_key: str):
        """Handle tier card selection"""
        # Deselect all cards
        for key, card in self.tier_cards.items():
            card.set_selected(key == tier_key)

        self.selected_tier = tier_key
        tier_info = self.TIER_FEATURES[tier_key]

        # Update selection info
        self.selection_info.setText(
            f"Upgrade to {tier_info['name'].upper()} tier - {tier_info['price']}"
        )
        self.selection_info.setStyleSheet(f"""
            font-size: 14px;
            color: {tier_info['color']};
            padding: 12px;
            background-color: {PremiumDialogTheme.BG_CARD};
            border: 1px solid {tier_info['color']}44;
            border-radius: 8px;
        """)

        # Enable upgrade button
        self.upgrade_btn.setEnabled(True)

    def _on_upgrade_clicked(self):
        """Handle upgrade request"""
        if not self.selected_tier:
            return

        tier_info = self.TIER_FEATURES[self.selected_tier]

        # Confirmation dialog
        reply = QMessageBox.question(
            self,
            "Confirm Upgrade Request",
            f"Request upgrade to {tier_info['name'].upper()} tier?\n\n"
            f"Price: {tier_info['price']}\n\n"
            "An admin will review and approve your request.\n"
            "You will receive a new API key via email upon approval.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            request_data = {
                'owner_id': self.owner_id,
                'owner_name': self.owner_data.get('name'),
                'owner_email': self.owner_data.get('email'),
                'current_tier': self.current_tier,
                'requested_tier': self.selected_tier,
                'requested_at': datetime.now().isoformat(),
                'tier_features': tier_info['features'],
                'tier_price': tier_info['price']
            }

            self.upgrade_requested.emit(self.owner_id, self.selected_tier, request_data)

            QMessageBox.information(
                self,
                "Request Submitted",
                f"Your upgrade request to {tier_info['name'].upper()} has been submitted.\n\n"
                "An administrator will review your request and you will be notified via email.",
                QMessageBox.Ok
            )

            self.accept()


# Convenience function
def show_tier_upgrade_dialog(owner_data: Dict[str, Any], parent=None) -> Optional[Dict[str, Any]]:
    """
    Show the tier upgrade dialog and return the result.

    Returns:
        Dict with upgrade request data if submitted, None if cancelled
    """
    dialog = TierUpgradeDialog(owner_data, parent)
    result_data = None

    def on_upgrade_requested(owner_id, new_tier, request_data):
        nonlocal result_data
        result_data = request_data

    dialog.upgrade_requested.connect(on_upgrade_requested)

    if dialog.exec() == QDialog.Accepted:
        return result_data
    return None
