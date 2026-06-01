"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

Info Panel Widget - Premium Automotive Dashboard
Side panel for displaying Owner/Vehicle/Driver details with luxury car UI aesthetics
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QGridLayout, QSizePolicy, QSpacerItem,
    QProgressBar, QGraphicsDropShadowEffect, QComboBox, QCheckBox,
    QSpinBox, QLineEdit, QMessageBox, QDialog, QDialogButtonBox,
    QFormLayout
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, QSize
from PySide6.QtGui import QFont, QColor, QLinearGradient, QPalette
import logging
from datetime import datetime

# Import server API client for customer management
try:
    from server_api_client import get_unified_user_client
    HAS_UNIFIED_CLIENT = True
except ImportError:
    HAS_UNIFIED_CLIENT = False
    get_unified_user_client = None

logger = logging.getLogger(__name__)


def format_timestamp(timestamp):
    """
    Convert Unix timestamp to human-readable format.

    Args:
        timestamp: Unix timestamp (float/int) or None

    Returns:
        Formatted string: "2/7/26 - 7:15PM" or "Never"
    """
    if not timestamp or timestamp <= 0:
        return "Never"

    try:
        dt = datetime.fromtimestamp(float(timestamp))

        # Format: "M/D/YY - H:MM AM/PM"
        date_str = dt.strftime("%m/%d/%y").lstrip("0").replace("/0", "/")  # Remove leading zeros
        time_str = dt.strftime("%I:%M%p").lstrip("0")   # 7:15PM not 07:15PM

        return f"{date_str} - {time_str}"
    except (ValueError, OSError) as e:
        logger.warning(f"Invalid timestamp {timestamp}: {e}")
        return "Invalid date"


class PremiumAutomotiveTheme:
    """Premium Automotive Dashboard Theme - Luxury Car Infotainment Inspired"""

    # Backgrounds - Deep charcoal layers (like Mercedes MBUX)
    BG_DEEPEST = "#08090A"       # Darkest layer
    BG_PRIMARY = "#0D0F12"       # Main background
    BG_ELEVATED = "#141820"      # Cards/panels
    BG_SURFACE = "#1C2028"       # Interactive surfaces
    BG_HOVER = "#252A35"         # Hover state

    # Accent colors - Cyan/Teal primary (BMW iDrive inspired)
    ACCENT_CYAN = "#00D4FF"      # Primary accent
    ACCENT_CYAN_DIM = "#0099CC"  # Dimmed accent
    ACCENT_CYAN_GLOW = "#00D4FF40"  # Glow effect

    # Status colors
    ACCENT_AMBER = "#FFB800"     # Warnings, highlights
    ACCENT_EMERALD = "#00E676"   # Success, healthy
    ACCENT_CRIMSON = "#FF3D3D"   # Critical, errors

    # Text hierarchy
    TEXT_PRIMARY = "#F8F9FA"     # Main text - almost white
    TEXT_SECONDARY = "#9AA0A6"   # Secondary info
    TEXT_MUTED = "#5F6368"       # Disabled/hint
    TEXT_ACCENT = "#00D4FF"      # Highlighted text

    # Borders & dividers
    BORDER_SUBTLE = "#1E2430"
    BORDER_ACCENT = "#00D4FF33"  # Cyan with transparency

    # Gradients
    GRADIENT_HEADER = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #141820, stop:1 #0D0F12)"
    GRADIENT_BUTTON = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #00D4FF, stop:1 #0099CC)"
    GRADIENT_BUTTON_HOVER = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #33DFFF, stop:1 #00B8E6)"


class HealthBar(QWidget):
    """Custom health bar with gradient fill"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(8)
        self.value = 0

    def setValue(self, value: int):
        self.value = max(0, min(100, value))
        self.update()

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QBrush, QPen

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background track
        painter.setBrush(QColor(PremiumAutomotiveTheme.BG_SURFACE))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 4, 4)

        # Filled portion with gradient
        if self.value > 0:
            fill_width = int((self.value / 100) * self.width())

            # Color based on value
            if self.value >= 80:
                color = QColor(PremiumAutomotiveTheme.ACCENT_EMERALD)
            elif self.value >= 60:
                color = QColor(PremiumAutomotiveTheme.ACCENT_AMBER)
            else:
                color = QColor(PremiumAutomotiveTheme.ACCENT_CRIMSON)

            painter.setBrush(color)
            painter.drawRoundedRect(0, 0, fill_width, self.height(), 4, 4)

        painter.end()


class InfoSection(QFrame):
    """Premium styled section within the info panel"""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("InfoSection")
        self.setStyleSheet(f"""
            QFrame#InfoSection {{
                background-color: {PremiumAutomotiveTheme.BG_ELEVATED};
                border-radius: 10px;
                border: 1px solid {PremiumAutomotiveTheme.BORDER_SUBTLE};
            }}
            QFrame#InfoSection:hover {{
                border: 1px solid {PremiumAutomotiveTheme.BORDER_ACCENT};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Section title with accent line
        title_container = QWidget()
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(8)

        # Accent bar
        accent_bar = QFrame()
        accent_bar.setFixedSize(3, 14)
        accent_bar.setStyleSheet(f"background-color: {PremiumAutomotiveTheme.ACCENT_CYAN}; border-radius: 1px;")
        title_layout.addWidget(accent_bar)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"""
            font-size: 11px;
            font-weight: 600;
            color: {PremiumAutomotiveTheme.TEXT_SECONDARY};
            letter-spacing: 1.5px;
            text-transform: uppercase;
        """)
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()

        layout.addWidget(title_container)

        # Content area
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(8)
        layout.addLayout(self.content_layout)

    def add_field(self, label: str, value: str, icon: str = ""):
        """Add a labeled field to the section"""
        row = QHBoxLayout()
        row.setSpacing(12)

        # Icon + Label
        label_text = f"{icon}  {label}" if icon else label
        label_widget = QLabel(label_text)
        label_widget.setStyleSheet(f"""
            color: {PremiumAutomotiveTheme.TEXT_MUTED};
            font-size: 12px;
            font-weight: 500;
        """)
        label_widget.setMinimumWidth(90)

        # Value
        value_widget = QLabel(str(value) if value else "—")
        value_widget.setStyleSheet(f"""
            color: {PremiumAutomotiveTheme.TEXT_PRIMARY};
            font-size: 13px;
            font-weight: 600;
        """)
        value_widget.setWordWrap(True)

        row.addWidget(label_widget)
        row.addWidget(value_widget, 1)
        self.content_layout.addLayout(row)

    def add_stat(self, label: str, value: str, color: str = None):
        """Add a stat with optional color highlight"""
        row = QHBoxLayout()
        row.setSpacing(8)

        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"""
            color: {PremiumAutomotiveTheme.TEXT_SECONDARY};
            font-size: 12px;
        """)

        value_color = color if color else PremiumAutomotiveTheme.TEXT_PRIMARY
        value_widget = QLabel(str(value))
        value_widget.setStyleSheet(f"""
            color: {value_color};
            font-size: 15px;
            font-weight: 700;
        """)

        row.addWidget(label_widget)
        row.addStretch()
        row.addWidget(value_widget)
        self.content_layout.addLayout(row)

    def add_health_bar(self, label: str, value: int):
        """Add a health/progress bar"""
        container = QVBoxLayout()
        container.setSpacing(6)

        # Label row with value
        label_row = QHBoxLayout()
        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"color: {PremiumAutomotiveTheme.TEXT_SECONDARY}; font-size: 12px;")

        # Value with color
        if value >= 80:
            color = PremiumAutomotiveTheme.ACCENT_EMERALD
            status = "EXCELLENT"
        elif value >= 60:
            color = PremiumAutomotiveTheme.ACCENT_AMBER
            status = "GOOD"
        else:
            color = PremiumAutomotiveTheme.ACCENT_CRIMSON
            status = "ATTENTION"

        value_widget = QLabel(f"{value}%  {status}")
        value_widget.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 700;")

        label_row.addWidget(label_widget)
        label_row.addStretch()
        label_row.addWidget(value_widget)
        container.addLayout(label_row)

        # Progress bar
        bar = HealthBar()
        bar.setValue(value)
        container.addWidget(bar)

        self.content_layout.addLayout(container)

    def add_widget(self, widget: QWidget):
        """Add a custom widget to the section"""
        self.content_layout.addWidget(widget)

    def clear_content(self):
        """Clear all content from the section"""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())


class InfoPanelWidget(QWidget):
    """
    Premium Automotive Info Panel - Luxury Dashboard Aesthetic
    Shows detailed information when info button is clicked on tree items.
    """

    # Signals
    closed = Signal()
    pdf_requested = Signal(str, int)  # (type, id)
    action_requested = Signal(str, dict)  # (action, data)
    tier_changed = Signal(int, str)  # (user_id, tier)
    feature_toggled = Signal(int, str, bool)  # (user_id, feature, enabled)
    rate_limit_changed = Signal(int, str, int, str)  # (user_id, feature, max_requests, period)
    api_key_regenerated = Signal(int)  # (user_id,)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("InfoPanelWidget")

        # Panel width
        self.panel_width = 400
        self.setFixedWidth(self.panel_width)
        self.setMinimumHeight(400)

        # Current displayed data
        self.current_type = None
        self.current_id = None
        self.current_data = {}
        self._pending_tier = None  # Pending tier change (saved on Save button click)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the panel UI with premium automotive styling"""
        self.setStyleSheet(f"""
            QWidget#InfoPanelWidget {{
                background-color: {PremiumAutomotiveTheme.BG_PRIMARY};
                border-left: 1px solid {PremiumAutomotiveTheme.BORDER_SUBTLE};
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header with gradient background
        header = QFrame()
        header.setObjectName("PanelHeader")
        header.setStyleSheet(f"""
            QFrame#PanelHeader {{
                background: {PremiumAutomotiveTheme.GRADIENT_HEADER};
                border-bottom: 1px solid {PremiumAutomotiveTheme.BORDER_SUBTLE};
                min-height: 56px;
            }}
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 14, 16, 14)

        # Title with icon
        self.title_label = QLabel("DETAILS")
        self.title_label.setStyleSheet(f"""
            font-size: 14px;
            font-weight: 700;
            color: {PremiumAutomotiveTheme.TEXT_PRIMARY};
            letter-spacing: 2px;
        """)

        # Close button - minimal, elegant
        close_btn = QPushButton("×")
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {PremiumAutomotiveTheme.TEXT_MUTED};
                border: none;
                font-size: 22px;
                font-weight: 300;
                border-radius: 16px;
            }}
            QPushButton:hover {{
                background-color: {PremiumAutomotiveTheme.BG_HOVER};
                color: {PremiumAutomotiveTheme.TEXT_PRIMARY};
            }}
        """)
        close_btn.clicked.connect(self._on_close)

        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(close_btn)

        main_layout.addWidget(header)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {PremiumAutomotiveTheme.BG_PRIMARY};
                width: 6px;
                border-radius: 3px;
                margin: 4px 2px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {PremiumAutomotiveTheme.BORDER_SUBTLE};
                border-radius: 3px;
                min-height: 40px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {PremiumAutomotiveTheme.ACCENT_CYAN_DIM};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        # Content widget
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(16, 20, 16, 20)
        self.content_layout.setSpacing(16)

        scroll.setWidget(self.content_widget)
        main_layout.addWidget(scroll, 1)

        # Action buttons at bottom
        self.actions_frame = QFrame()
        self.actions_frame.setObjectName("ActionsFrame")
        self.actions_frame.setStyleSheet(f"""
            QFrame#ActionsFrame {{
                background-color: {PremiumAutomotiveTheme.BG_ELEVATED};
                border-top: 1px solid {PremiumAutomotiveTheme.BORDER_SUBTLE};
            }}
        """)
        self.actions_layout = QVBoxLayout(self.actions_frame)
        self.actions_layout.setContentsMargins(16, 14, 16, 14)
        self.actions_layout.setSpacing(10)

        main_layout.addWidget(self.actions_frame)

    def _on_close(self):
        """Handle close button click"""
        self.hide()
        self.closed.emit()

    def _clear_content(self):
        """Clear all content from the panel"""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        while self.actions_layout.count():
            item = self.actions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _create_button(self, text: str, style: str = 'primary', icon: str = "") -> QPushButton:
        """Create a premium styled button"""
        btn = QPushButton(f"{icon}  {text}" if icon else text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(42)

        styles = {
            'primary': f"""
                QPushButton {{
                    background: {PremiumAutomotiveTheme.GRADIENT_BUTTON};
                    color: {PremiumAutomotiveTheme.BG_DEEPEST};
                    border: none;
                    padding: 12px 20px;
                    font-size: 13px;
                    font-weight: 700;
                    border-radius: 8px;
                    letter-spacing: 0.5px;
                }}
                QPushButton:hover {{
                    background: {PremiumAutomotiveTheme.GRADIENT_BUTTON_HOVER};
                }}
                QPushButton:pressed {{
                    background-color: {PremiumAutomotiveTheme.ACCENT_CYAN_DIM};
                }}
            """,
            'secondary': f"""
                QPushButton {{
                    background-color: {PremiumAutomotiveTheme.BG_SURFACE};
                    color: {PremiumAutomotiveTheme.TEXT_PRIMARY};
                    border: 1px solid {PremiumAutomotiveTheme.BORDER_SUBTLE};
                    padding: 10px 16px;
                    font-size: 12px;
                    font-weight: 600;
                    border-radius: 8px;
                }}
                QPushButton:hover {{
                    background-color: {PremiumAutomotiveTheme.BG_HOVER};
                    border-color: {PremiumAutomotiveTheme.ACCENT_CYAN_DIM};
                }}
            """,
            'danger': f"""
                QPushButton {{
                    background-color: {PremiumAutomotiveTheme.ACCENT_CRIMSON}22;
                    color: {PremiumAutomotiveTheme.ACCENT_CRIMSON};
                    border: 1px solid {PremiumAutomotiveTheme.ACCENT_CRIMSON}44;
                    padding: 10px 16px;
                    font-size: 12px;
                    font-weight: 600;
                    border-radius: 8px;
                }}
                QPushButton:hover {{
                    background-color: {PremiumAutomotiveTheme.ACCENT_CRIMSON}44;
                    border-color: {PremiumAutomotiveTheme.ACCENT_CRIMSON};
                }}
            """,
            'success': f"""
                QPushButton {{
                    background-color: {PremiumAutomotiveTheme.ACCENT_EMERALD}22;
                    color: {PremiumAutomotiveTheme.ACCENT_EMERALD};
                    border: 1px solid {PremiumAutomotiveTheme.ACCENT_EMERALD}44;
                    padding: 10px 16px;
                    font-size: 12px;
                    font-weight: 600;
                    border-radius: 8px;
                }}
                QPushButton:hover {{
                    background-color: {PremiumAutomotiveTheme.ACCENT_EMERALD}44;
                    border-color: {PremiumAutomotiveTheme.ACCENT_EMERALD};
                }}
            """
        }

        btn.setStyleSheet(styles.get(style, styles['secondary']))
        return btn

    def _create_title_card(self, title: str, subtitle: str = ""):
        """Create the main title card at top of panel"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {PremiumAutomotiveTheme.BG_ELEVATED},
                    stop:1 {PremiumAutomotiveTheme.BG_SURFACE});
                border-radius: 12px;
                border: 1px solid {PremiumAutomotiveTheme.BORDER_ACCENT};
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(4)

        # Main title - large, bold
        title_label = QLabel(title.upper())
        title_label.setStyleSheet(f"""
            font-size: 22px;
            font-weight: 800;
            color: {PremiumAutomotiveTheme.TEXT_PRIMARY};
            letter-spacing: 1px;
        """)
        layout.addWidget(title_label)

        # Subtitle
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setStyleSheet(f"""
                font-size: 14px;
                font-weight: 500;
                color: {PremiumAutomotiveTheme.ACCENT_CYAN};
            """)
            layout.addWidget(subtitle_label)

        return card

    def _create_customer_management_section(self, user_data: dict) -> QFrame:
        """Create the customer management section with tier, features, and API key controls"""
        section = InfoSection("CUSTOMER MANAGEMENT")

        user_id = user_data.get('user_id') or user_data.get('owner_id')
        current_tier = user_data.get('tier', 'free').lower()
        features = user_data.get('features', [])
        limits = user_data.get('limits', {})
        api_key = user_data.get('api_key', '')

        # Tier selection dropdown
        tier_row = QHBoxLayout()
        tier_row.setSpacing(12)

        tier_label = QLabel("Tier")
        tier_label.setStyleSheet(f"""
            color: {PremiumAutomotiveTheme.TEXT_MUTED};
            font-size: 12px;
            font-weight: 500;
        """)
        tier_label.setMinimumWidth(90)

        self.tier_combo = QComboBox()
        self.tier_combo.addItems(["Free", "Pro", "Premium", "Admin"])
        self.tier_combo.setCurrentText(current_tier.title())
        self.tier_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {PremiumAutomotiveTheme.BG_SURFACE};
                color: {PremiumAutomotiveTheme.TEXT_PRIMARY};
                border: 1px solid {PremiumAutomotiveTheme.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                font-weight: 600;
                min-width: 120px;
            }}
            QComboBox:hover {{
                border-color: {PremiumAutomotiveTheme.ACCENT_CYAN_DIM};
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 10px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {PremiumAutomotiveTheme.BG_ELEVATED};
                color: {PremiumAutomotiveTheme.TEXT_PRIMARY};
                selection-background-color: {PremiumAutomotiveTheme.ACCENT_CYAN_DIM};
                border: 1px solid {PremiumAutomotiveTheme.BORDER_SUBTLE};
            }}
        """)
        self.tier_combo.currentTextChanged.connect(
            lambda tier: self._on_tier_changed(user_id, tier)
        )

        tier_row.addWidget(tier_label)
        tier_row.addWidget(self.tier_combo, 1)
        section.content_layout.addLayout(tier_row)

        # Separator
        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet(f"background-color: {PremiumAutomotiveTheme.BORDER_SUBTLE};")
        section.content_layout.addWidget(separator)

        # Features section title
        features_title = QLabel("FEATURES")
        features_title.setStyleSheet(f"""
            color: {PremiumAutomotiveTheme.TEXT_SECONDARY};
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 1px;
            padding-top: 8px;
        """)
        section.content_layout.addWidget(features_title)

        # Feature checkboxes with rate limit buttons
        all_features = ['vehicle_data', 'llm_chat', 'predict', 'guardian', 'admin']
        self.feature_checks = {}
        self.limit_labels = {}

        for feature in all_features:
            feature_row = QHBoxLayout()
            feature_row.setSpacing(8)

            # Checkbox
            cb = QCheckBox(feature.replace('_', ' ').title())
            cb.setChecked(feature in features)
            cb.setStyleSheet(f"""
                QCheckBox {{
                    color: {PremiumAutomotiveTheme.TEXT_PRIMARY};
                    font-size: 12px;
                    font-weight: 500;
                    spacing: 8px;
                }}
                QCheckBox::indicator {{
                    width: 18px;
                    height: 18px;
                    border-radius: 4px;
                    border: 2px solid {PremiumAutomotiveTheme.BORDER_SUBTLE};
                    background-color: {PremiumAutomotiveTheme.BG_SURFACE};
                }}
                QCheckBox::indicator:checked {{
                    background-color: {PremiumAutomotiveTheme.ACCENT_CYAN};
                    border-color: {PremiumAutomotiveTheme.ACCENT_CYAN};
                }}
                QCheckBox::indicator:hover {{
                    border-color: {PremiumAutomotiveTheme.ACCENT_CYAN_DIM};
                }}
            """)
            cb.stateChanged.connect(
                lambda state, f=feature, uid=user_id: self._on_feature_toggled(uid, f, state == Qt.Checked)
            )
            self.feature_checks[feature] = cb
            feature_row.addWidget(cb)

            # Rate limit label
            limit_info = limits.get(feature, {})
            max_req = limit_info.get('max')
            period = limit_info.get('period', 'day')

            if max_req is None:
                limit_text = "unlimited"
            elif max_req == 0:
                limit_text = "disabled"
            else:
                limit_text = f"{max_req}/{period}"

            limit_label = QLabel(limit_text)
            limit_label.setStyleSheet(f"""
                color: {PremiumAutomotiveTheme.TEXT_MUTED};
                font-size: 11px;
                padding: 0 8px;
            """)
            self.limit_labels[feature] = limit_label
            feature_row.addWidget(limit_label)

            # Edit limit button
            edit_btn = QPushButton("Edit")
            edit_btn.setFixedSize(50, 24)
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {PremiumAutomotiveTheme.BG_HOVER};
                    color: {PremiumAutomotiveTheme.TEXT_SECONDARY};
                    border: 1px solid {PremiumAutomotiveTheme.BORDER_SUBTLE};
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background-color: {PremiumAutomotiveTheme.BG_SURFACE};
                    color: {PremiumAutomotiveTheme.TEXT_PRIMARY};
                    border-color: {PremiumAutomotiveTheme.ACCENT_CYAN_DIM};
                }}
            """)
            edit_btn.clicked.connect(
                lambda checked, f=feature, uid=user_id: self._show_rate_limit_dialog(uid, f)
            )
            feature_row.addWidget(edit_btn)

            feature_row.addStretch()
            section.content_layout.addLayout(feature_row)

        return section

    def _create_api_key_section(self, user_data: dict) -> QFrame:
        """Create the API key management section"""
        section = InfoSection("API KEY")

        user_id = user_data.get('user_id') or user_data.get('owner_id')
        api_key = user_data.get('api_key', '')
        last_used_raw = user_data.get('last_used_at', 0)
        last_used = format_timestamp(last_used_raw)  # Phase 7 fix
        created_at_raw = user_data.get('key_created_at', 0)
        created_at = format_timestamp(created_at_raw) if created_at_raw else ''  # Phase 7 fix

        # API key display (masked)
        key_row = QHBoxLayout()
        key_row.setSpacing(8)

        self.api_key_display = QLineEdit()
        self.api_key_display.setReadOnly(True)
        if api_key:
            # Show masked version
            if len(api_key) > 12:
                masked = api_key[:8] + "****" + api_key[-4:]
            else:
                masked = "****" + api_key[-4:] if len(api_key) > 4 else "****"
            self.api_key_display.setText(masked)
        else:
            self.api_key_display.setText("No API key")
        self.api_key_display.setStyleSheet(f"""
            QLineEdit {{
                background-color: {PremiumAutomotiveTheme.BG_SURFACE};
                color: {PremiumAutomotiveTheme.TEXT_PRIMARY};
                border: 1px solid {PremiumAutomotiveTheme.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 8px 12px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
            }}
        """)

        # Store full key for copy
        self._current_api_key = api_key

        # Copy button
        copy_btn = QPushButton("📋")
        copy_btn.setFixedSize(36, 36)
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setToolTip("Copy API key to clipboard")
        copy_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PremiumAutomotiveTheme.BG_HOVER};
                border: 1px solid {PremiumAutomotiveTheme.BORDER_SUBTLE};
                border-radius: 6px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {PremiumAutomotiveTheme.BG_SURFACE};
                border-color: {PremiumAutomotiveTheme.ACCENT_CYAN_DIM};
            }}
        """)
        copy_btn.clicked.connect(self._copy_api_key)

        # Toggle visibility button
        self.show_key_btn = QPushButton("👁")
        self.show_key_btn.setFixedSize(36, 36)
        self.show_key_btn.setCursor(Qt.PointingHandCursor)
        self.show_key_btn.setToolTip("Show/hide full API key")
        self.show_key_btn.setStyleSheet(copy_btn.styleSheet())
        self.show_key_btn.clicked.connect(self._toggle_api_key_visibility)
        self._key_visible = False

        key_row.addWidget(self.api_key_display, 1)
        key_row.addWidget(copy_btn)
        key_row.addWidget(self.show_key_btn)
        section.content_layout.addLayout(key_row)

        # Key metadata
        if created_at:
            section.add_field("Created", created_at, "")
        section.add_field("Last Used", last_used if last_used else "Never", "")

        # Online status
        online_status = user_data.get('online_status', 'Unknown')
        status_color = {
            'Online': PremiumAutomotiveTheme.ACCENT_EMERALD,
            'Recently active': PremiumAutomotiveTheme.ACCENT_AMBER,
            'Offline': PremiumAutomotiveTheme.TEXT_MUTED,
            'Never connected': PremiumAutomotiveTheme.TEXT_MUTED,
            'Unknown': PremiumAutomotiveTheme.TEXT_MUTED,
        }.get(online_status, PremiumAutomotiveTheme.TEXT_MUTED)
        section.add_stat("Status", online_status, status_color)

        # Action buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        # Regenerate button
        regen_btn = QPushButton("🔄 Regenerate")
        regen_btn.setCursor(Qt.PointingHandCursor)
        regen_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PremiumAutomotiveTheme.BG_SURFACE};
                color: {PremiumAutomotiveTheme.ACCENT_AMBER};
                border: 1px solid {PremiumAutomotiveTheme.ACCENT_AMBER}44;
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {PremiumAutomotiveTheme.ACCENT_AMBER}22;
                border-color: {PremiumAutomotiveTheme.ACCENT_AMBER};
            }}
        """)
        regen_btn.clicked.connect(lambda: self._regenerate_api_key(user_id))
        # Disable regenerate button per user request
        regen_btn.setEnabled(False)
        regen_btn.setToolTip("API key regeneration disabled - contact admin to enable")

        # Send email button
        email_btn = QPushButton("📧 Send Key")
        email_btn.setCursor(Qt.PointingHandCursor)
        email_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PremiumAutomotiveTheme.BG_SURFACE};
                color: {PremiumAutomotiveTheme.ACCENT_CYAN};
                border: 1px solid {PremiumAutomotiveTheme.ACCENT_CYAN}44;
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {PremiumAutomotiveTheme.ACCENT_CYAN}22;
                border-color: {PremiumAutomotiveTheme.ACCENT_CYAN};
            }}
        """)
        email_btn.clicked.connect(lambda: self._send_api_key_email(user_id))

        btn_row.addWidget(regen_btn)
        btn_row.addWidget(email_btn)
        btn_row.addStretch()
        section.content_layout.addLayout(btn_row)

        return section

    def _on_tier_changed(self, user_id: int, tier: str):
        """Handle tier change from dropdown - now just marks as pending, saves on Save button"""
        if not user_id:
            return

        # Store the pending tier change - will be applied when Save is clicked
        self._pending_tier = tier.lower()
        self.current_data['tier'] = tier.lower()
        logger.info(f"Tier selection changed to {tier} for user {user_id} (pending save)")

    def _save_pending_changes(self, user_id: int):
        """Save any pending changes (tier, features, etc.)"""
        if not HAS_UNIFIED_CLIENT or not user_id:
            QMessageBox.warning(self, "Error", "Cannot save: Server connection not available")
            return

        if not hasattr(self, '_pending_tier') or not self._pending_tier:
            QMessageBox.information(self, "No Changes", "No changes to save.")
            return

        try:
            client = get_unified_user_client()
            response = client.apply_tier(user_id, self._pending_tier)

            # ApiResponse is a dataclass with .success and .data attributes
            if response.success:
                # Get data from response
                data = response.data or {}

                # Update current data
                self.current_data['tier'] = self._pending_tier
                self.current_data['features'] = data.get('features', [])
                self.current_data['limits'] = data.get('limits', {})

                # Update feature checkboxes
                features = data.get('features', [])
                for feature, cb in self.feature_checks.items():
                    cb.blockSignals(True)
                    cb.setChecked(feature in features)
                    cb.blockSignals(False)

                # Update limit labels
                limits = data.get('limits', {})
                for feature, label in self.limit_labels.items():
                    limit_info = limits.get(feature, {})
                    max_req = limit_info.get('max')
                    period = limit_info.get('period', 'day')
                    if max_req is None:
                        label.setText("unlimited")
                    elif max_req == 0:
                        label.setText("disabled")
                    else:
                        label.setText(f"{max_req}/{period}")

                self.tier_changed.emit(user_id, self._pending_tier)
                self._pending_tier = None  # Clear pending change
                QMessageBox.information(self, "Success", f"Tier changed to {self.current_data['tier'].upper()} successfully!")
                logger.info(f"Tier saved to {self.current_data['tier']} for user {user_id}")
            else:
                error = response.error or 'Unknown error'
                QMessageBox.warning(self, "Error", f"Failed to save changes: {error}")
        except Exception as e:
            logger.error(f"Error saving changes: {e}")
            QMessageBox.warning(self, "Error", f"Failed to save changes: {str(e)}")

    def _on_feature_toggled(self, user_id: int, feature: str, enabled: bool):
        """Handle feature toggle"""
        if not HAS_UNIFIED_CLIENT or not user_id:
            return

        try:
            client = get_unified_user_client()
            response = client.set_feature(user_id, feature, enabled)

            # ApiResponse is a dataclass with .success and .error attributes
            if response.success:
                # Update current data
                features = self.current_data.get('features', [])
                if enabled and feature not in features:
                    features.append(feature)
                elif not enabled and feature in features:
                    features.remove(feature)
                self.current_data['features'] = features

                self.feature_toggled.emit(user_id, feature, enabled)
                logger.info(f"Feature {feature} {'enabled' if enabled else 'disabled'} for user {user_id}")
            else:
                error = response.error or 'Unknown error'
                QMessageBox.warning(self, "Error", f"Failed to toggle feature: {error}")
                # Revert checkbox
                cb = self.feature_checks.get(feature)
                if cb:
                    cb.blockSignals(True)
                    cb.setChecked(not enabled)
                    cb.blockSignals(False)
        except Exception as e:
            logger.error(f"Error toggling feature: {e}")
            QMessageBox.warning(self, "Error", f"Failed to toggle feature: {str(e)}")

    def _show_rate_limit_dialog(self, user_id: int, feature: str):
        """Show dialog to edit rate limit for a feature"""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Rate Limit - {feature.replace('_', ' ').title()}")
        dialog.setMinimumWidth(300)
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {PremiumAutomotiveTheme.BG_PRIMARY};
            }}
            QLabel {{
                color: {PremiumAutomotiveTheme.TEXT_PRIMARY};
            }}
        """)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel(f"Rate Limit for {feature.replace('_', ' ').title()}")
        title.setStyleSheet(f"""
            font-size: 14px;
            font-weight: 700;
            color: {PremiumAutomotiveTheme.TEXT_PRIMARY};
        """)
        layout.addWidget(title)

        # Form
        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        # Max requests spinbox
        max_spin = QSpinBox()
        max_spin.setRange(-1, 100000)  # -1 = unlimited
        max_spin.setSpecialValueText("Unlimited")
        max_spin.setValue(-1)
        max_spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: {PremiumAutomotiveTheme.BG_SURFACE};
                color: {PremiumAutomotiveTheme.TEXT_PRIMARY};
                border: 1px solid {PremiumAutomotiveTheme.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
            }}
        """)

        # Get current value
        limits = self.current_data.get('limits', {})
        limit_info = limits.get(feature, {})
        current_max = limit_info.get('max')
        if current_max is None:
            max_spin.setValue(-1)
        else:
            max_spin.setValue(current_max)

        form_layout.addRow("Max Requests:", max_spin)

        # Period dropdown
        period_combo = QComboBox()
        period_combo.addItems(["minute", "hour", "day", "month"])
        period_combo.setCurrentText(limit_info.get('period', 'day'))
        period_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {PremiumAutomotiveTheme.BG_SURFACE};
                color: {PremiumAutomotiveTheme.TEXT_PRIMARY};
                border: 1px solid {PremiumAutomotiveTheme.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
            }}
        """)
        form_layout.addRow("Period:", period_combo)

        layout.addLayout(form_layout)

        # Buttons
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.setStyleSheet(f"""
            QPushButton {{
                background-color: {PremiumAutomotiveTheme.BG_SURFACE};
                color: {PremiumAutomotiveTheme.TEXT_PRIMARY};
                border: 1px solid {PremiumAutomotiveTheme.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {PremiumAutomotiveTheme.BG_HOVER};
                border-color: {PremiumAutomotiveTheme.ACCENT_CYAN_DIM};
            }}
        """)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)

        if dialog.exec() == QDialog.Accepted:
            max_requests = max_spin.value()
            if max_requests == -1:
                max_requests = None  # Unlimited
            period = period_combo.currentText()

            self._update_rate_limit(user_id, feature, max_requests, period)

    def _update_rate_limit(self, user_id: int, feature: str, max_requests: int, period: str):
        """Update rate limit on server"""
        if not HAS_UNIFIED_CLIENT or not user_id:
            return

        try:
            client = get_unified_user_client()
            response = client.set_feature_limit(user_id, feature, max_requests, period)

            # ApiResponse is a dataclass with .success and .error attributes
            if response.success:
                # Update current data
                if 'limits' not in self.current_data:
                    self.current_data['limits'] = {}
                self.current_data['limits'][feature] = {
                    'max': max_requests,
                    'period': period
                }

                # Update label
                if feature in self.limit_labels:
                    if max_requests is None:
                        self.limit_labels[feature].setText("unlimited")
                    elif max_requests == 0:
                        self.limit_labels[feature].setText("disabled")
                    else:
                        self.limit_labels[feature].setText(f"{max_requests}/{period}")

                self.rate_limit_changed.emit(user_id, feature, max_requests or 0, period)
                logger.info(f"Rate limit updated for {feature}: {max_requests}/{period}")
            else:
                error = response.error or 'Unknown error'
                QMessageBox.warning(self, "Error", f"Failed to update rate limit: {error}")
        except Exception as e:
            logger.error(f"Error updating rate limit: {e}")
            QMessageBox.warning(self, "Error", f"Failed to update rate limit: {str(e)}")

    def _copy_api_key(self):
        """Copy API key to clipboard"""
        from PySide6.QtWidgets import QApplication

        if self._current_api_key:
            clipboard = QApplication.clipboard()
            clipboard.setText(self._current_api_key)
            # Brief visual feedback would be nice here
            logger.info("API key copied to clipboard")

    def _toggle_api_key_visibility(self):
        """Toggle API key visibility"""
        self._key_visible = not self._key_visible

        if self._key_visible:
            self.api_key_display.setText(self._current_api_key or "No API key")
            self.show_key_btn.setText("🔒")
            self.show_key_btn.setToolTip("Hide API key")
        else:
            if self._current_api_key:
                if len(self._current_api_key) > 12:
                    masked = self._current_api_key[:8] + "****" + self._current_api_key[-4:]
                else:
                    masked = "****" + self._current_api_key[-4:] if len(self._current_api_key) > 4 else "****"
                self.api_key_display.setText(masked)
            else:
                self.api_key_display.setText("No API key")
            self.show_key_btn.setText("👁")
            self.show_key_btn.setToolTip("Show full API key")

    def _regenerate_api_key(self, user_id: int):
        """Regenerate API key for user"""
        reply = QMessageBox.question(
            self,
            "Regenerate API Key",
            "Are you sure you want to regenerate this API key?\n\n"
            "The old key will stop working immediately.\n"
            "An email will be sent to the customer with the new key.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        if not HAS_UNIFIED_CLIENT or not user_id:
            QMessageBox.warning(self, "Error", "Server connection not available")
            return

        try:
            client = get_unified_user_client()
            response = client.regenerate_key(user_id)

            # ApiResponse is a dataclass with .success, .data, and .error attributes
            if response.success:
                data = response.data or {}
                new_key = data.get('api_key', '')
                self._current_api_key = new_key
                self.current_data['api_key'] = new_key

                # Update display
                if len(new_key) > 12:
                    masked = new_key[:8] + "****" + new_key[-4:]
                else:
                    masked = "****" + new_key[-4:] if len(new_key) > 4 else "****"
                self.api_key_display.setText(masked)
                self._key_visible = False
                self.show_key_btn.setText("👁")

                self.api_key_regenerated.emit(user_id)

                email_sent = data.get('email_sent', False)
                if email_sent:
                    QMessageBox.information(
                        self,
                        "Success",
                        "API key regenerated successfully!\n\n"
                        "An email has been sent to the customer with the new key."
                    )
                else:
                    QMessageBox.information(
                        self,
                        "Success",
                        "API key regenerated successfully!\n\n"
                        "Note: Email notification was not sent."
                    )
                logger.info(f"API key regenerated for user {user_id}")
            else:
                error = response.error or 'Unknown error'
                QMessageBox.warning(self, "Error", f"Failed to regenerate API key: {error}")
        except Exception as e:
            logger.error(f"Error regenerating API key: {e}")
            QMessageBox.warning(self, "Error", f"Failed to regenerate API key: {str(e)}")

    def _send_api_key_email(self, user_id: int):
        """Send API key email to customer"""
        if not self.current_data:
            QMessageBox.warning(self, "Error", "No customer data available")
            return

        email = self.current_data.get('email')
        name = self.current_data.get('name', 'Customer')
        api_key = self.current_data.get('api_key')

        if not email:
            QMessageBox.warning(self, "Error", "Customer email not found")
            return

        if not api_key:
            QMessageBox.warning(self, "Error", "Customer API key not found")
            return

        try:
            # Import email service from server
            import sys
            import os
            server_path = os.path.join(os.path.dirname(__file__), '..', 'OBDserver', 'Previlium_OBD_Server')
            if server_path not in sys.path:
                sys.path.append(server_path)

            from email_service import send_api_key_email

            # Send email with API key
            car_plate = self.current_data.get('car_plate', '')
            success, message = send_api_key_email(email, name, api_key, car_plate)

            if success:
                QMessageBox.information(
                    self,
                    "Email Sent",
                    f"API key has been sent to {email}"
                )
                logger.info(f"API key email sent to {email}")
            else:
                QMessageBox.warning(
                    self,
                    "Email Failed",
                    f"Failed to send email: {message}"
                )
                logger.error(f"Failed to send API key email to {email}: {message}")

        except ImportError as e:
            logger.error(f"Failed to import email service: {e}")
            QMessageBox.warning(
                self,
                "Error",
                "Email service not available. Please check server configuration."
            )
        except Exception as e:
            logger.error(f"Error sending API key email: {e}")
            QMessageBox.warning(
                self,
                "Error",
                f"Failed to send email: {str(e)}"
            )

    def show_owner_info(self, owner_data: dict):
        """Display owner information with premium styling and customer management"""
        self._clear_content()
        self.current_type = 'owner'
        # Prefer numeric user_id over prefixed owner_id for API calls
        # server_user_id is the numeric ID for server-registered users
        _candidate_id = owner_data.get('user_id') or owner_data.get('server_user_id') or owner_data.get('owner_id')
        # Ensure we use a numeric ID for API calls (not string IDs like "server_1")
        if isinstance(_candidate_id, str) and not _candidate_id.isdigit():
            self.current_id = owner_data.get('server_user_id')  # Try numeric fallback
        else:
            self.current_id = _candidate_id
        self.current_data = owner_data

        self.title_label.setText("CUSTOMER PROFILE")

        # Title card
        name = owner_data.get('name', 'Unknown')
        tier = owner_data.get('tier', 'free').upper()
        status = owner_data.get('status', 'active').upper()
        title_card = self._create_title_card(name, f"{tier} TIER • {status}")
        self.content_layout.addWidget(title_card)

        # Contact section
        contact_section = InfoSection("CONTACT")
        contact_section.add_field("Email", owner_data.get('email', ''), "")
        contact_section.add_field("Phone", owner_data.get('phone', ''), "")
        contact_section.add_field("Registered", owner_data.get('created_at_formatted', ''), "")
        self.content_layout.addWidget(contact_section)

        # CUSTOMER MANAGEMENT SECTION (tier, features, limits)
        # Fetch fresh user data from server if available
        # Use numeric user_id for server lookups
        user_id = owner_data.get('user_id') or owner_data.get('server_user_id')
        # Sanitize: string IDs like "server_1" can't be used for server lookups
        if isinstance(user_id, str) and not user_id.isdigit():
            user_id = None
        owner_email = owner_data.get('email', '').lower()
        if HAS_UNIFIED_CLIENT and (user_id or owner_email):
            try:
                client = get_unified_user_client()
                users_response = client.list_users()
                # ApiResponse is a dataclass with .success and .data attributes
                if users_response.success:
                    data = users_response.data or {}
                    users = data.get('users', [])
                    for user in users:
                        server_user_id = user.get('user_id')
                        user_email = user.get('email', '').lower()
                        # Match by user_id (with type coercion) or email
                        if (user_id and server_user_id == user_id) or \
                           (user_id and str(server_user_id) == str(user_id)) or \
                           (owner_email and user_email == owner_email):
                            # Merge server data into owner_data
                            owner_data['user_id'] = server_user_id  # Store the numeric ID
                            owner_data['features'] = user.get('features', [])
                            owner_data['limits'] = user.get('limits', {})
                            owner_data['api_key'] = user.get('api_key', '')
                            owner_data['tier'] = user.get('tier', owner_data.get('tier', 'free'))
                            owner_data['status'] = user.get('status', 'active')
                            owner_data['last_used_at'] = user.get('last_used_at', '')
                            owner_data['key_created_at'] = user.get('key_created_at', '')
                            owner_data['online_status'] = user.get('online_status', 'Unknown')
                            # Update current_id with the numeric ID for API calls
                            self.current_id = server_user_id
                            break
            except Exception as e:
                logger.warning(f"Could not fetch user data from server: {e}")

        # FALLBACK: If no API key yet, try direct database query
        if not owner_data.get('api_key') and user_id:
            try:
                import sqlite3
                from pathlib import Path
                server_db = Path(r"C:\OBDserver\Previlium_OBD_Server\server_database.db")
                if server_db.exists():
                    conn = sqlite3.connect(str(server_db))
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    cur.execute("SELECT api_key FROM unified_users WHERE user_id = ?", (user_id,))
                    row = cur.fetchone()
                    if row and row['api_key']:
                        owner_data['api_key'] = row['api_key']
                        logger.info(f"Retrieved API key from database for user {user_id}")
                    conn.close()
            except Exception as e:
                logger.warning(f"Could not query database directly: {e}")

        # Add customer management section
        management_section = self._create_customer_management_section(owner_data)
        self.content_layout.addWidget(management_section)

        # Add API key section
        api_key_section = self._create_api_key_section(owner_data)
        self.content_layout.addWidget(api_key_section)

        # Vehicles section
        vehicles = owner_data.get('vehicles', [])
        vehicles_section = InfoSection(f"VEHICLES  ({len(vehicles)})")
        for vehicle in vehicles:
            v_name = vehicle.get('name', 'Unknown Vehicle')
            v_info = f"{vehicle.get('make', '')} {vehicle.get('model', '')} {vehicle.get('year', '')}".strip()
            vehicles_section.add_field(v_name, v_info or "—", "")
        if not vehicles:
            no_vehicles = QLabel("No vehicles registered")
            no_vehicles.setStyleSheet(f"color: {PremiumAutomotiveTheme.TEXT_MUTED}; font-style: italic; padding: 8px 0;")
            vehicles_section.add_widget(no_vehicles)
        self.content_layout.addWidget(vehicles_section)

        # Usage stats section (if available)
        usage = owner_data.get('usage', {})
        if usage:
            usage_section = InfoSection("USAGE THIS PERIOD")
            for feature, count in usage.items():
                limit_info = owner_data.get('limits', {}).get(feature, {})
                max_req = limit_info.get('max')
                if max_req:
                    usage_section.add_stat(
                        feature.replace('_', ' ').title(),
                        f"{count} / {max_req}",
                        PremiumAutomotiveTheme.ACCENT_AMBER if count >= max_req * 0.8 else PremiumAutomotiveTheme.TEXT_PRIMARY
                    )
                else:
                    usage_section.add_stat(feature.replace('_', ' ').title(), str(count))
            self.content_layout.addWidget(usage_section)

        # Driving behavior section (if owner is also a driver)
        behavior = owner_data.get('driving_behavior', {})
        if behavior and behavior.get('total_trips', 0) > 0:
            behavior_section = InfoSection("DRIVING METRICS")

            score = behavior.get('safety_score', 0)
            behavior_section.add_health_bar("Safety Score", score)

            behavior_section.add_stat("Total Trips", str(behavior.get('total_trips', 0)))
            behavior_section.add_stat("Distance", f"{behavior.get('total_distance_km', 0):,.0f} km")

            violations = behavior.get('violations', 0)
            viol_color = PremiumAutomotiveTheme.ACCENT_CRIMSON if violations > 0 else PremiumAutomotiveTheme.ACCENT_EMERALD
            behavior_section.add_stat("Violations", str(violations), viol_color)

            self.content_layout.addWidget(behavior_section)

        # Spacer
        self.content_layout.addStretch()

        # Action buttons
        # Save button for pending changes (tier, etc.)
        save_btn = self._create_button("Save Changes", 'success', "💾")
        save_btn.clicked.connect(lambda: self._save_pending_changes(self.current_id))
        self.actions_layout.addWidget(save_btn)

        pdf_btn = self._create_button("Generate Customer Report", 'primary', "")
        pdf_btn.clicked.connect(lambda: self.pdf_requested.emit('owner', self.current_id))
        self.actions_layout.addWidget(pdf_btn)

        # Danger zone buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        suspend_btn = self._create_button("Suspend Account", 'danger')
        suspend_btn.clicked.connect(lambda: self._suspend_user(self.current_id))

        delete_btn = self._create_button("Delete Account", 'danger')
        delete_btn.clicked.connect(lambda: self._delete_user(self.current_id))

        btn_row.addWidget(suspend_btn)
        btn_row.addWidget(delete_btn)
        self.actions_layout.addLayout(btn_row)

    def _suspend_user(self, user_id: int):
        """Suspend/unsuspend user account"""
        current_status = self.current_data.get('status', 'active')
        new_status = 'suspended' if current_status == 'active' else 'active'
        action_text = 'suspend' if new_status == 'suspended' else 'reactivate'

        reply = QMessageBox.question(
            self,
            f"{action_text.title()} Account",
            f"Are you sure you want to {action_text} this account?\n\n"
            f"Customer: {self.current_data.get('name', 'Unknown')}\n\n"
            f"{'This will prevent them from using the API.' if new_status == 'suspended' else 'This will restore their API access.'}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        if not HAS_UNIFIED_CLIENT or not user_id:
            QMessageBox.warning(self, "Error", "Server connection not available")
            return

        try:
            client = get_unified_user_client()
            response = client.update_user(user_id, status=new_status)

            # ApiResponse is a dataclass with .success and .error attributes
            if response.success:
                self.current_data['status'] = new_status
                QMessageBox.information(
                    self,
                    "Success",
                    f"Account has been {action_text}d successfully."
                )
                # Refresh the panel
                self.show_owner_info(self.current_data)
            else:
                error = response.error or 'Unknown error'
                QMessageBox.warning(self, "Error", f"Failed to {action_text} account: {error}")
        except Exception as e:
            logger.error(f"Error suspending user: {e}")
            QMessageBox.warning(self, "Error", f"Failed to {action_text} account: {str(e)}")

    def _delete_user(self, user_id: int):
        """Delete user account"""
        reply = QMessageBox.warning(
            self,
            "Delete Account",
            f"⚠️ DANGER: Are you sure you want to DELETE this account?\n\n"
            f"Customer: {self.current_data.get('name', 'Unknown')}\n"
            f"Email: {self.current_data.get('email', 'Unknown')}\n\n"
            f"This action cannot be undone!\n"
            f"All API keys will be revoked immediately.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Double confirmation
        reply2 = QMessageBox.question(
            self,
            "Confirm Delete",
            "Type 'DELETE' to confirm deletion.\n\nAre you absolutely sure?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply2 != QMessageBox.Yes:
            return

        if not HAS_UNIFIED_CLIENT or not user_id:
            QMessageBox.warning(self, "Error", "Server connection not available")
            return

        try:
            client = get_unified_user_client()
            response = client.delete_user(user_id)

            # ApiResponse is a dataclass with .success and .error attributes
            if response.success:
                QMessageBox.information(
                    self,
                    "Success",
                    "Account has been deleted successfully."
                )
                # Close the panel
                self._on_close()
                # Emit action to refresh parent
                self.action_requested.emit('user_deleted', {'user_id': user_id})
            else:
                error = response.error or 'Unknown error'
                QMessageBox.warning(self, "Error", f"Failed to delete account: {error}")
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            QMessageBox.warning(self, "Error", f"Failed to delete account: {str(e)}")

    def show_vehicle_info(self, vehicle_data: dict):
        """Display vehicle information with premium styling"""
        self._clear_content()
        self.current_type = 'vehicle'
        self.current_id = vehicle_data.get('profile_id')
        self.current_data = vehicle_data

        self.title_label.setText("VEHICLE PROFILE")

        # Vehicle title card
        make = vehicle_data.get('make', '')
        model = vehicle_data.get('model', '')
        year = vehicle_data.get('year', '')
        title = f"{make} {model}".strip() or vehicle_data.get('name', 'Unknown')
        title_card = self._create_title_card(title, str(year) if year else "")
        self.content_layout.addWidget(title_card)

        # Specifications section
        specs_section = InfoSection("SPECIFICATIONS")
        specs_section.add_field("Name", vehicle_data.get('name', ''), "")
        specs_section.add_field("Plate", vehicle_data.get('license_plate', ''), "")
        specs_section.add_field("Make", make, "")
        specs_section.add_field("Model", model, "")
        specs_section.add_field("Year", str(year) if year else "—", "")
        # VIN display (Phase 7 fix: formatted for readability)
        vin = vehicle_data.get('vin', '')
        if vin and len(vin) == 17:
            # Format standard VIN: XXXX-XXXX-XXXX-XXXXX
            formatted_vin = f"{vin[:4]}-{vin[4:8]}-{vin[8:12]}-{vin[12:]}"
            specs_section.add_field("VIN", formatted_vin, "🔍")
        elif vin:
            # Non-standard VIN length, show as-is
            specs_section.add_field("VIN", vin, "🔍")
        else:
            specs_section.add_field("VIN", "Not set", "🔍")
        self.content_layout.addWidget(specs_section)

        # Engine & Drivetrain section
        engine_section = InfoSection("ENGINE & DRIVETRAIN")
        engine_section.add_field("Engine Type", vehicle_data.get('engine_type', '') or '—', "")
        engine_section.add_field("Cylinders", str(vehicle_data.get('cylinders', '')) if vehicle_data.get('cylinders') else '—', "")
        engine_section.add_field("Displacement", vehicle_data.get('displacement', '') or '—', "")
        engine_section.add_field("Fuel Type", vehicle_data.get('fuel_type', '') or '—', "")
        engine_section.add_field("Transmission", vehicle_data.get('transmission', '') or '—', "")
        engine_section.add_field("Drivetrain", vehicle_data.get('drivetrain', '') or '—', "")
        self.content_layout.addWidget(engine_section)

        # ECU Information section (Mode 09 data from OBD)
        cal_id = vehicle_data.get('calibration_id', '')
        ecu_name = vehicle_data.get('ecu_name', '')
        cvn = vehicle_data.get('cvn', '')
        if cal_id or ecu_name or cvn:
            ecu_section = InfoSection("ECU INFORMATION")
            if ecu_name:
                ecu_section.add_field("ECU Name", ecu_name, "")
            if cal_id:
                ecu_section.add_field("Calibration ID", cal_id, "")
            if cvn:
                ecu_section.add_field("CVN", cvn, "")
            self.content_layout.addWidget(ecu_section)

        # Assigned drivers section
        drivers = vehicle_data.get('drivers', [])
        driver_section = InfoSection(f"DRIVERS  ({len(drivers)})")
        for driver in drivers:
            d_name = driver.get('name', 'Unknown')
            d_type = "OWNER" if driver.get('is_owner_driver') else "ASSIGNED"
            driver_section.add_field(d_name, d_type, "")
        if not drivers:
            no_drivers = QLabel("No drivers assigned")
            no_drivers.setStyleSheet(f"color: {PremiumAutomotiveTheme.TEXT_MUTED}; font-style: italic; padding: 8px 0;")
            driver_section.add_widget(no_drivers)
        self.content_layout.addWidget(driver_section)

        # Vehicle health section
        health = vehicle_data.get('health', {})
        health_section = InfoSection("HEALTH STATUS")
        score = health.get('overall_score', 0) if health else 0
        health_section.add_health_bar("Overall Health", score)

        # Component status
        for component, status in health.get('components', {}).items():
            if status == 'Good':
                color = PremiumAutomotiveTheme.ACCENT_EMERALD
            elif status == 'Warning':
                color = PremiumAutomotiveTheme.ACCENT_AMBER
            else:
                color = PremiumAutomotiveTheme.ACCENT_CRIMSON
            health_section.add_stat(f"  {component}", status, color)

        self.content_layout.addWidget(health_section)

        # AI Predictions section
        predictions = vehicle_data.get('predictions', [])
        if predictions:
            pred_section = InfoSection("AI PREDICTIONS")
            for pred in predictions[:4]:
                component = pred.get('component', 'Unknown')
                probability = pred.get('failure_probability', 0)
                days = pred.get('estimated_days', 'N/A')

                if probability >= 50:
                    color = PremiumAutomotiveTheme.ACCENT_CRIMSON
                elif probability >= 30:
                    color = PremiumAutomotiveTheme.ACCENT_AMBER
                else:
                    color = PremiumAutomotiveTheme.TEXT_MUTED

                pred_section.add_stat(
                    component,
                    f"{probability:.0f}% in {days}d",
                    color
                )
            self.content_layout.addWidget(pred_section)

        # Fleet Comparison section
        fleet_comparison = vehicle_data.get('fleet_comparison', {})
        if fleet_comparison and fleet_comparison.get('fleet_size', 0) > 0:
            fleet_section = InfoSection("FLEET COMPARISON")

            # Health percentile
            percentile = fleet_comparison.get('health_percentile', 50)
            fleet_size = fleet_comparison.get('fleet_size', 0)

            if percentile >= 75:
                pct_color = PremiumAutomotiveTheme.ACCENT_EMERALD
            elif percentile >= 50:
                pct_color = PremiumAutomotiveTheme.TEXT_PRIMARY
            else:
                pct_color = PremiumAutomotiveTheme.ACCENT_AMBER

            fleet_section.add_stat(
                "Your Health Rank",
                f"Better than {percentile:.0f}%",
                pct_color
            )
            fleet_section.add_stat(
                "Similar Vehicles",
                f"{fleet_size} vehicles",
                PremiumAutomotiveTheme.TEXT_SECONDARY
            )

            # Risk vs fleet
            risk_vs_fleet = fleet_comparison.get('risk_vs_fleet', 'average')
            if risk_vs_fleet == 'lower':
                risk_color = PremiumAutomotiveTheme.ACCENT_EMERALD
                risk_text = "LOWER RISK"
            elif risk_vs_fleet == 'higher':
                risk_color = PremiumAutomotiveTheme.ACCENT_CRIMSON
                risk_text = "HIGHER RISK"
            else:
                risk_color = PremiumAutomotiveTheme.TEXT_SECONDARY
                risk_text = "AVERAGE"
            fleet_section.add_stat("Risk vs Fleet", risk_text, risk_color)

            # Common issues in fleet
            common_issues = fleet_comparison.get('fleet_common_issues', [])[:3]
            if common_issues:
                issues_text = ", ".join([i.replace('_', ' ').title() for i in common_issues])
                fleet_section.add_field("Common Issues", issues_text, "")

            # Recommendations from fleet data
            recommendations = fleet_comparison.get('fleet_based_recommendations', [])[:2]
            for rec in recommendations:
                rec_label = QLabel(f"  {rec}")
                rec_label.setWordWrap(True)
                rec_label.setStyleSheet(f"""
                    color: {PremiumAutomotiveTheme.TEXT_MUTED};
                    font-size: 11px;
                    font-style: italic;
                    padding: 4px 0;
                """)
                fleet_section.add_widget(rec_label)

            self.content_layout.addWidget(fleet_section)

        # Recall Alerts section
        recall_data = vehicle_data.get('recall_data', {})
        has_recalls = recall_data.get('has_recalls', False)
        if has_recalls:
            recall_section = InfoSection("RECALL ALERTS")

            total_recalls = recall_data.get('total_recalls', 0)
            critical_recalls = recall_data.get('critical_recalls', 0)

            # Show recall counts with appropriate colors
            if critical_recalls > 0:
                recall_color = PremiumAutomotiveTheme.ACCENT_CRIMSON
                recall_status = "CRITICAL"
            else:
                recall_color = PremiumAutomotiveTheme.ACCENT_AMBER
                recall_status = "ACTIVE"

            recall_section.add_stat(
                "Active Recalls",
                f"{total_recalls} {recall_status}",
                recall_color
            )

            if critical_recalls > 0:
                recall_section.add_stat(
                    "Critical",
                    str(critical_recalls),
                    PremiumAutomotiveTheme.ACCENT_CRIMSON
                )

            # Show recall details
            recalls = recall_data.get('recalls', [])[:3]
            for recall in recalls:
                component = recall.get('component', 'Unknown')
                severity = recall.get('severity', 'unknown')

                if severity == 'critical':
                    sev_color = PremiumAutomotiveTheme.ACCENT_CRIMSON
                elif severity == 'high':
                    sev_color = PremiumAutomotiveTheme.ACCENT_AMBER
                else:
                    sev_color = PremiumAutomotiveTheme.TEXT_SECONDARY

                recall_section.add_stat(component, severity.upper(), sev_color)

                # Show summary if available
                summary = recall.get('summary', '')
                if summary:
                    summary_label = QLabel(summary[:100] + "..." if len(summary) > 100 else summary)
                    summary_label.setWordWrap(True)
                    summary_label.setStyleSheet(f"""
                        color: {PremiumAutomotiveTheme.TEXT_MUTED};
                        font-size: 11px;
                        padding: 2px 0 8px 0;
                    """)
                    recall_section.add_widget(summary_label)

            # Last checked date
            last_checked = recall_data.get('last_checked')
            if last_checked:
                recall_section.add_field("Last Checked", last_checked[:10], "")

            self.content_layout.addWidget(recall_section)

        # Activity section
        activity_section = InfoSection("RECENT ACTIVITY")
        activity_section.add_field("Location", vehicle_data.get('last_location', 'Unknown'), "")
        activity_section.add_field("Last Seen", vehicle_data.get('last_seen', 'Never'), "")
        self.content_layout.addWidget(activity_section)

        # Vehicle Intelligence section (populated async via update_vehicle_intelligence())
        self._intelligence_section = InfoSection("VEHICLE INTELLIGENCE")
        loading_label = QLabel("Loading research data...")
        loading_label.setStyleSheet(f"color: {PremiumAutomotiveTheme.TEXT_MUTED}; font-style: italic; padding: 8px 0;")
        self._intelligence_section.add_widget(loading_label)
        self.content_layout.addWidget(self._intelligence_section)

        # ECU Test Results section (populated async via update_mode06_data())
        self._mode06_section = InfoSection("ECU TEST RESULTS")
        mode06_loading = QLabel("Waiting for Mode 06 data...")
        mode06_loading.setStyleSheet(f"color: {PremiumAutomotiveTheme.TEXT_MUTED}; font-style: italic; padding: 8px 0;")
        self._mode06_section.add_widget(mode06_loading)
        self.content_layout.addWidget(self._mode06_section)

        # Spacer
        self.content_layout.addStretch()

        # Action buttons
        pdf_btn = self._create_button("Generate Vehicle Report", 'primary', "")
        pdf_btn.clicked.connect(lambda: self.pdf_requested.emit('vehicle', self.current_id))
        self.actions_layout.addWidget(pdf_btn)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        trends_btn = self._create_button("View Trends", 'secondary')
        trends_btn.clicked.connect(lambda: self.action_requested.emit('view_trends', {'profile_id': self.current_id}))

        add_driver_btn = self._create_button("Add Driver", 'secondary')
        add_driver_btn.clicked.connect(lambda: self.action_requested.emit('add_driver', {'profile_id': self.current_id}))

        btn_row.addWidget(trends_btn)
        btn_row.addWidget(add_driver_btn)
        self.actions_layout.addLayout(btn_row)

        # Second row: Research & Recall buttons
        btn_row2 = QHBoxLayout()
        btn_row2.setSpacing(10)

        check_recalls_btn = self._create_button("Check Recalls", 'secondary')
        check_recalls_btn.clicked.connect(lambda: self.action_requested.emit('check_recalls', {
            'profile_id': self.current_id,
            'make': vehicle_data.get('make', ''),
            'model': vehicle_data.get('model', ''),
            'year': vehicle_data.get('year', 0)
        }))

        refresh_research_btn = self._create_button("Refresh Research", 'secondary')
        refresh_research_btn.clicked.connect(lambda: self.action_requested.emit('refresh_research', {
            'profile_id': self.current_id,
            'make': vehicle_data.get('make', ''),
            'model': vehicle_data.get('model', ''),
            'year': vehicle_data.get('year', 0)
        }))

        btn_row2.addWidget(check_recalls_btn)
        btn_row2.addWidget(refresh_research_btn)
        self.actions_layout.addLayout(btn_row2)

    def update_vehicle_intelligence(self, research_data: dict):
        """Update the Vehicle Intelligence section with fetched research data.

        Called after background API fetch completes. Rebuilds the section content
        in-place without clearing the entire panel.
        """
        if not hasattr(self, '_intelligence_section') or self._intelligence_section is None:
            return

        section = self._intelligence_section
        section.clear_content()

        status = research_data.get('research_status') or research_data.get('status', 'unknown')

        # Show VIN missing alert if applicable
        vin_status = research_data.get('vin_status', '')
        if vin_status == 'missing':
            vin_alert = QLabel("⚠  VIN not set — decode from OBD or enter manually")
            vin_alert.setWordWrap(True)
            vin_alert.setStyleSheet(f"""
                color: {PremiumAutomotiveTheme.ACCENT_AMBER};
                font-size: 11px;
                font-weight: bold;
                padding: 4px 0 8px 0;
            """)
            section.add_widget(vin_alert)

        if status == 'pending':
            pending_lbl = QLabel("Research queued — results available shortly")
            pending_lbl.setStyleSheet(f"color: {PremiumAutomotiveTheme.TEXT_MUTED}; font-style: italic; padding: 4px 0;")
            section.add_widget(pending_lbl)
            return

        if status == 'researching':
            researching_lbl = QLabel("Research in progress...")
            researching_lbl.setStyleSheet(f"color: {PremiumAutomotiveTheme.ACCENT_CYAN}; font-style: italic; padding: 4px 0;")
            section.add_widget(researching_lbl)
            return

        if status == 'failed':
            failed_lbl = QLabel("Research failed — click Refresh Research to retry")
            failed_lbl.setWordWrap(True)
            failed_lbl.setStyleSheet(f"color: {PremiumAutomotiveTheme.ACCENT_CRIMSON}; font-style: italic; padding: 4px 0;")
            section.add_widget(failed_lbl)
            return

        # Status: completed or stale
        if status == 'stale':
            section.add_stat("Status", "STALE", PremiumAutomotiveTheme.ACCENT_AMBER)
        else:
            section.add_stat("Status", "COMPLETED", PremiumAutomotiveTheme.ACCENT_EMERALD)

        # Reliability score
        reliability = research_data.get('reliability_score')
        if reliability is not None:
            try:
                score_val = float(reliability)
                # Score is 0-10 from server; health bar expects 0-100
                section.add_health_bar("Reliability Score", int(score_val * 10))
                section.add_stat(
                    "Score",
                    f"{score_val:.1f} / 10",
                    PremiumAutomotiveTheme.ACCENT_EMERALD if score_val >= 7
                    else PremiumAutomotiveTheme.ACCENT_AMBER if score_val >= 5
                    else PremiumAutomotiveTheme.ACCENT_CRIMSON
                )
            except (TypeError, ValueError):
                pass

        # Counts
        common_problems = research_data.get('common_problems') or []
        known_issues = research_data.get('failure_prone_parts') or research_data.get('known_issues') or []
        recalls = research_data.get('recalls') or []
        tsbs = research_data.get('tsbs') or []

        if common_problems:
            color = PremiumAutomotiveTheme.ACCENT_CRIMSON if len(common_problems) >= 5 \
                else PremiumAutomotiveTheme.ACCENT_AMBER if len(common_problems) >= 3 \
                else PremiumAutomotiveTheme.TEXT_SECONDARY
            section.add_stat("Common Problems", str(len(common_problems)), color)

        if known_issues:
            section.add_stat("Failure-Prone Parts", str(len(known_issues)),
                             PremiumAutomotiveTheme.ACCENT_AMBER)

        if recalls:
            section.add_stat("Known Recalls", str(len(recalls)),
                             PremiumAutomotiveTheme.ACCENT_CRIMSON if recalls else PremiumAutomotiveTheme.TEXT_SECONDARY)

        if tsbs:
            section.add_stat("TSBs", str(len(tsbs)), PremiumAutomotiveTheme.TEXT_SECONDARY)

        # AI summary preview
        ai_summary = research_data.get('owner_reviews_summary') or research_data.get('ai_summary', '')
        if ai_summary:
            preview = ai_summary[:180] + "..." if len(ai_summary) > 180 else ai_summary
            summary_lbl = QLabel(preview)
            summary_lbl.setWordWrap(True)
            summary_lbl.setStyleSheet(f"""
                color: {PremiumAutomotiveTheme.TEXT_MUTED};
                font-size: 11px;
                font-style: italic;
                padding: 6px 0 2px 0;
            """)
            section.add_widget(summary_lbl)

        # First 3 common problems as bullet list
        if common_problems:
            header_lbl = QLabel("Top Issues:")
            header_lbl.setStyleSheet(f"color: {PremiumAutomotiveTheme.TEXT_SECONDARY}; font-size: 11px; font-weight: bold; padding-top: 6px;")
            section.add_widget(header_lbl)
            for prob in common_problems[:3]:
                prob_lbl = QLabel(f"  • {prob}")
                prob_lbl.setWordWrap(True)
                prob_lbl.setStyleSheet(f"color: {PremiumAutomotiveTheme.TEXT_MUTED}; font-size: 11px; padding: 1px 0;")
                section.add_widget(prob_lbl)

    def update_mode06_data(self, mode06_data: dict):
        """Update Mode 06 ECU Test Results section with fetched data.

        Called after background API fetch completes. Rebuilds the section content
        in-place without clearing the entire panel.
        """
        if not hasattr(self, '_mode06_section') or self._mode06_section is None:
            return

        section = self._mode06_section
        section.clear_content()

        results = mode06_data.get('results', [])
        if not results:
            no_data = QLabel("No Mode 06 test data available")
            no_data.setStyleSheet(f"color: {PremiumAutomotiveTheme.TEXT_MUTED}; font-style: italic; padding: 4px 0;")
            section.add_widget(no_data)
            return

        # Use the most recent result set
        latest = results[0]
        tests = latest.get('tests', [])
        if not tests:
            no_tests = QLabel("No ECU test results recorded")
            no_tests.setStyleSheet(f"color: {PremiumAutomotiveTheme.TEXT_MUTED}; font-style: italic; padding: 4px 0;")
            section.add_widget(no_tests)
            return

        # Summary counts
        passed = sum(1 for t in tests if t.get('passed', True))
        failed = len(tests) - passed
        total = len(tests)

        if failed == 0:
            summary_color = PremiumAutomotiveTheme.ACCENT_EMERALD
            summary_text = f"ALL PASS ({total} tests)"
        else:
            summary_color = PremiumAutomotiveTheme.ACCENT_CRIMSON
            summary_text = f"{failed} FAIL / {total} tests"

        section.add_stat("ECU Verdict", summary_text, summary_color)

        # Show individual test results (up to 8)
        for test in tests[:8]:
            test_name = test.get('test_name', test.get('testName', 'Unknown'))
            is_passed = test.get('passed', True)
            value = test.get('value', test.get('test_value', 0))
            unit = test.get('unit', '')
            max_limit = test.get('max_limit', test.get('maxLimit'))

            status = "PASS" if is_passed else "FAIL"
            color = PremiumAutomotiveTheme.ACCENT_EMERALD if is_passed else PremiumAutomotiveTheme.ACCENT_CRIMSON

            # Truncate long test names
            display_name = test_name[:30] + "..." if len(test_name) > 30 else test_name

            if max_limit is not None and max_limit > 0:
                try:
                    detail = f"{status}  {float(value):.1f}/{float(max_limit):.1f} {unit}"
                except (TypeError, ValueError):
                    detail = status
            else:
                detail = status

            section.add_stat(f"  {display_name}", detail, color)

    def show_driver_info(self, driver_data: dict):
        """Display driver information with premium styling"""
        self._clear_content()
        self.current_type = 'driver'
        self.current_id = driver_data.get('driver_id')
        self.current_data = driver_data

        self.title_label.setText("DRIVER PROFILE")

        # Title card
        name = driver_data.get('name', 'Unknown')
        driver_type = "OWNER DRIVER" if driver_data.get('is_owner_driver') else "ASSIGNED DRIVER"
        title_card = self._create_title_card(name, driver_type)
        self.content_layout.addWidget(title_card)

        # Contact section
        contact_section = InfoSection("CONTACT")
        contact_section.add_field("Email", driver_data.get('email', ''), "")
        contact_section.add_field("Phone", driver_data.get('phone', ''), "")
        contact_section.add_field("Added", driver_data.get('created_at_formatted', ''), "")
        self.content_layout.addWidget(contact_section)

        # Guardian Role section
        guardian_role = driver_data.get('guardian_role', 'driver')
        role_section = InfoSection("GUARDIAN ROLE")
        # Style the role value with an appropriate color
        role_display = guardian_role.replace('_', ' ').title()
        if guardian_role == 'owner':
            role_color = PremiumAutomotiveTheme.ACCENT_AMBER
        elif guardian_role == 'co_guardian':
            role_color = PremiumAutomotiveTheme.ACCENT_CYAN
        else:
            role_color = PremiumAutomotiveTheme.TEXT_SECONDARY
        role_section.add_stat("Role", role_display, role_color)
        self.content_layout.addWidget(role_section)

        # Vehicles driven section
        vehicles = driver_data.get('vehicles', [])
        vehicles_section = InfoSection(f"VEHICLES  ({len(vehicles)})")
        for vehicle in vehicles:
            v_name = vehicle.get('name', 'Unknown')
            owner = vehicle.get('owner_name', '')
            vehicles_section.add_field(v_name, f"Owner: {owner}" if owner else "", "")
        if not vehicles:
            no_vehicles = QLabel("No vehicles assigned")
            no_vehicles.setStyleSheet(f"color: {PremiumAutomotiveTheme.TEXT_MUTED}; font-style: italic; padding: 8px 0;")
            vehicles_section.add_widget(no_vehicles)
        self.content_layout.addWidget(vehicles_section)

        # Driving behavior section
        behavior = driver_data.get('behavior', {})
        behavior_section = InfoSection("DRIVING METRICS")

        score = behavior.get('safety_score', 0)
        behavior_section.add_health_bar("Safety Score", score)

        behavior_section.add_stat("Total Trips", str(behavior.get('total_trips', 0)))
        behavior_section.add_stat("Distance", f"{behavior.get('total_distance_km', 0):,.0f} km")

        # Violations breakdown
        violations = behavior.get('violations', {})
        total_violations = sum(violations.values()) if isinstance(violations, dict) else violations
        viol_color = PremiumAutomotiveTheme.ACCENT_CRIMSON if total_violations > 0 else PremiumAutomotiveTheme.ACCENT_EMERALD
        behavior_section.add_stat("Violations", str(total_violations), viol_color)

        self.content_layout.addWidget(behavior_section)

        # Behavior breakdown section
        breakdown_section = InfoSection("PERFORMANCE")
        breakdown_section.add_stat("Avg Speed", f"{behavior.get('avg_speed', 0):.0f} km/h")

        max_speed = behavior.get('max_speed', 0)
        max_color = PremiumAutomotiveTheme.ACCENT_CRIMSON if max_speed > 120 else PremiumAutomotiveTheme.TEXT_PRIMARY
        breakdown_section.add_stat("Max Speed", f"{max_speed:.0f} km/h", max_color)

        breakdown_section.add_stat("Harsh Braking", f"{behavior.get('harsh_braking_events', 0)} events")
        breakdown_section.add_stat("Harsh Accel", f"{behavior.get('harsh_accel_events', 0)} events")
        breakdown_section.add_field("Last Active", driver_data.get('last_active', 'Never'), "")
        self.content_layout.addWidget(breakdown_section)

        # Spacer
        self.content_layout.addStretch()

        # Action buttons
        pdf_btn = self._create_button("Generate Driver Report", 'primary', "")
        pdf_btn.clicked.connect(lambda: self.pdf_requested.emit('driver', self.current_id))
        self.actions_layout.addWidget(pdf_btn)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        violations_btn = self._create_button("View Violations", 'secondary')
        violations_btn.clicked.connect(lambda: self.action_requested.emit('view_violations', {'driver_id': self.current_id}))

        # Only show remove button for non-owner drivers
        if not driver_data.get('is_owner_driver'):
            remove_btn = self._create_button("Remove Driver", 'danger')
            remove_btn.clicked.connect(lambda: self.action_requested.emit('remove_driver', {'driver_id': self.current_id}))
            btn_row.addWidget(violations_btn)
            btn_row.addWidget(remove_btn)
        else:
            btn_row.addWidget(violations_btn)
            btn_row.addStretch()

        self.actions_layout.addLayout(btn_row)
