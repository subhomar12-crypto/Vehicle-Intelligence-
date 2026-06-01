"""
Centralized theme for PREDICT Desktop application.

Consolidates ProfessionalTheme (general UI) and PremiumAutomotiveTheme (panels).
"""

import logging
from typing import Optional

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor, QFont

logger = logging.getLogger(__name__)


class PredictTheme:
    """
    Consolidated color scheme for PREDICT Desktop.
    
    Combines ProfessionalTheme and PremiumAutomotiveTheme colors.
    """
    
    # General UI Colors (ProfessionalTheme)
    BG_PRIMARY = "#0D1117"
    BG_SECONDARY = "#21262D"
    CARD_BG = "#1E2329"
    CARD_BG_HOVER = "#2D333B"
    TEXT_PRIMARY = "#F0F6FC"
    TEXT_SECONDARY = "#8B949E"
    TEXT_MUTED = "#5F6368"
    BORDER = "#30363D"
    BORDER_FOCUS = "#58A6FF"
    PRIMARY = "#C40000"  # PREDICT red
    SUCCESS = "#198754"
    WARNING = "#F59E0B"
    DANGER = "#DC3545"
    INFO = "#0D6EFD"
    
    # Premium Panel Colors (PremiumAutomotiveTheme)
    PANEL_BG = "#0D0F12"
    PANEL_ELEVATED = "#141820"
    PANEL_SURFACE = "#1C2028"
    PANEL_HOVER = "#252A35"
    ACCENT_CYAN = "#00D4FF"
    ACCENT_EMERALD = "#00E676"
    ACCENT_AMBER = "#FFB800"
    ACCENT_CRIMSON = "#FF3D3D"
    BORDER_SUBTLE = "#1E2430"
    
    # Font settings
    FONT_FAMILY = "Segoe UI"
    FONT_SIZE_HEADER = 18
    FONT_SIZE_SUBHEADER = 13
    FONT_SIZE_BODY = 12
    FONT_SIZE_SMALL = 10
    
    @classmethod
    def get_stylesheet(cls) -> str:
        """Get comprehensive QSS stylesheet."""
        return f"""
            /* Main Widget */
            QWidget {{
                background-color: {cls.BG_PRIMARY};
                color: {cls.TEXT_PRIMARY};
                font-family: "{cls.FONT_FAMILY}";
                font-size: {cls.FONT_SIZE_BODY}px;
            }}
            
            /* Push Button */
            QPushButton {{
                background-color: {cls.BG_SECONDARY};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 6px;
                padding: 8px 16px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {cls.CARD_BG_HOVER};
                border-color: {cls.PRIMARY};
            }}
            QPushButton:pressed {{
                background-color: {cls.PRIMARY};
            }}
            QPushButton:disabled {{
                background-color: {cls.BG_SECONDARY};
                color: {cls.TEXT_MUTED};
                border-color: {cls.BORDER};
            }}
            
            /* Primary Button */
            QPushButton#primary {{
                background-color: {cls.PRIMARY};
                color: white;
                border: none;
            }}
            QPushButton#primary:hover {{
                background-color: #E00000;
            }}
            
            /* Line Edit */
            QLineEdit {{
                background-color: {cls.BG_SECONDARY};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 6px;
                padding: 8px 12px;
            }}
            QLineEdit:focus {{
                border-color: {cls.BORDER_FOCUS};
            }}
            
            /* Combo Box */
            QComboBox {{
                background-color: {cls.BG_SECONDARY};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 6px;
                padding: 8px 12px;
                min-width: 100px;
            }}
            QComboBox:hover {{
                border-color: {cls.PRIMARY};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {cls.CARD_BG};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                selection-background-color: {cls.PRIMARY};
            }}
            
            /* Tab Widget */
            QTabWidget::pane {{
                border: 1px solid {cls.BORDER};
                border-radius: 6px;
                background-color: {cls.BG_PRIMARY};
            }}
            QTabBar::tab {{
                background-color: {cls.BG_SECONDARY};
                color: {cls.TEXT_SECONDARY};
                border: 1px solid {cls.BORDER};
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 10px 20px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background-color: {cls.BG_PRIMARY};
                color: {cls.TEXT_PRIMARY};
                border-bottom: 2px solid {cls.PRIMARY};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {cls.CARD_BG};
                color: {cls.TEXT_PRIMARY};
            }}
            
            /* Group Box / Card */
            QGroupBox {{
                font-weight: bold;
                font-size: {cls.FONT_SIZE_SUBHEADER}px;
                color: {cls.TEXT_PRIMARY};
                border: 2px solid {cls.PRIMARY};
                border-radius: 8px;
                margin-top: 12px;
                padding: 15px;
                background-color: {cls.CARD_BG};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
                background-color: {cls.CARD_BG};
            }}
            
            /* Scroll Bar */
            QScrollBar:vertical {{
                background-color: {cls.BG_SECONDARY};
                width: 12px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {cls.TEXT_MUTED};
                border-radius: 6px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {cls.TEXT_SECONDARY};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            
            QScrollBar:horizontal {{
                background-color: {cls.BG_SECONDARY};
                height: 12px;
                border-radius: 6px;
            }}
            QScrollBar::handle:horizontal {{
                background-color: {cls.TEXT_MUTED};
                border-radius: 6px;
                min-width: 30px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background-color: {cls.TEXT_SECONDARY};
            }}
            
            /* Progress Bar */
            QProgressBar {{
                background-color: {cls.BG_SECONDARY};
                border: none;
                border-radius: 4px;
                text-align: center;
                color: {cls.TEXT_PRIMARY};
            }}
            QProgressBar::chunk {{
                background-color: {cls.PRIMARY};
                border-radius: 4px;
            }}
            
            /* Label */
            QLabel {{
                color: {cls.TEXT_PRIMARY};
                background: transparent;
            }}
            QLabel#header {{
                font-size: {cls.FONT_SIZE_HEADER}px;
                font-weight: bold;
            }}
            QLabel#subheader {{
                font-size: {cls.FONT_SIZE_SUBHEADER}px;
                font-weight: bold;
                color: {cls.TEXT_SECONDARY};
            }}
            QLabel#muted {{
                color: {cls.TEXT_MUTED};
                font-size: {cls.FONT_SIZE_SMALL}px;
            }}
        """
    
    @classmethod
    def get_table_stylesheet(cls) -> str:
        """Get table-specific stylesheet."""
        return f"""
            QTableWidget {{
                background-color: {cls.BG_PRIMARY};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 6px;
                gridline-color: {cls.BG_SECONDARY};
            }}
            QTableWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {cls.BG_SECONDARY};
            }}
            QTableWidget::item:selected {{
                background-color: {cls.PRIMARY};
                color: #FFFFFF;
            }}
            QTableWidget::item:alternate {{
                background-color: #161B22;
            }}
            QHeaderView::section {{
                background-color: {cls.BG_SECONDARY};
                color: {cls.TEXT_SECONDARY};
                font-weight: bold;
                padding: 10px;
                border: none;
                border-bottom: 2px solid {cls.PRIMARY};
            }}
        """
    
    @classmethod
    def get_card_stylesheet(cls, color: Optional[str] = None) -> str:
        """Get card/groupbox stylesheet with optional accent color."""
        accent = color or cls.PRIMARY
        return f"""
            QGroupBox {{
                font-weight: bold;
                font-size: {cls.FONT_SIZE_SUBHEADER}px;
                color: {accent};
                border: 2px solid {accent};
                border-radius: 8px;
                margin-top: 12px;
                padding: 15px;
                background-color: {cls.CARD_BG};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
                background-color: {cls.CARD_BG};
            }}
        """
    
    @classmethod
    def apply_dark_theme(cls, app: QApplication) -> None:
        """Apply dark theme to QApplication."""
        # Set stylesheet
        app.setStyleSheet(cls.get_stylesheet())
        
        # Set palette
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(cls.BG_PRIMARY))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(cls.TEXT_PRIMARY))
        palette.setColor(QPalette.ColorRole.Base, QColor(cls.BG_SECONDARY))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(cls.CARD_BG))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(cls.CARD_BG))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(cls.TEXT_PRIMARY))
        palette.setColor(QPalette.ColorRole.Text, QColor(cls.TEXT_PRIMARY))
        palette.setColor(QPalette.ColorRole.Button, QColor(cls.BG_SECONDARY))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(cls.TEXT_PRIMARY))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(cls.PRIMARY))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        app.setPalette(palette)
        
        # Set default font
        font = QFont(cls.FONT_FAMILY, cls.FONT_SIZE_BODY)
        app.setFont(font)
        
        logger.debug("Dark theme applied")


def apply_dark_theme(app: QApplication) -> None:
    """Apply dark theme to QApplication."""
    PredictTheme.apply_dark_theme(app)


def get_stylesheet() -> str:
    """Get comprehensive QSS stylesheet."""
    return PredictTheme.get_stylesheet()


def get_table_stylesheet() -> str:
    """Get table-specific stylesheet."""
    return PredictTheme.get_table_stylesheet()


def get_card_stylesheet(color: Optional[str] = None) -> str:
    """Get card stylesheet with optional accent color."""
    return PredictTheme.get_card_stylesheet(color)
