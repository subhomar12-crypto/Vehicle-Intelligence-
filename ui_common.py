"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Ui Common
"""

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QPalette, QColor


class PredictTheme:
    """
    Predict Professional Theme - Red and Dark
    
    Primary Color: #C40000 (Predict Red)
    Secondary Color: #1A1A1A (Dark Gray/Black)
    """
    
    # Primary Colors - PREDICT RED
    PRIMARY = "#C40000"
    PRIMARY_DARK = "#A00000"
    PRIMARY_LIGHT = "#E53935"
    ACCENT = "#C40000"  # Added for compatibility
    
    # Secondary Colors - Dark
    SECONDARY = "#1A1A1A"
    SECONDARY_DARK = "#0D0D0D"
    SECONDARY_LIGHT = "#2D2D2D"
    
    # Status Colors
    SUCCESS = "#4CAF50"
    SUCCESS_LIGHT = "#81C784"
    WARNING = "#FF9800"
    WARNING_DARK = "#F57C00"
    DANGER = "#F44336"
    DANGER_DARK = "#D32F2F"
    INFO = "#2196F3"
    
    # Background Colors
    BACKGROUND = "#121212"
    BACKGROUND_SECONDARY = "#1E1E1E"
    CARD_BG = "#252525"
    CARD_BACKGROUND = "#252525"  # Alias for compatibility
    CARD_BG_HOVER = "#333333"
    
    # Text Colors
    TEXT_PRIMARY = "#FFFFFF"
    TEXT_SECONDARY = "#B3B3B3"
    TEXT_MUTED = "#757575"
    
    # Border Colors
    BORDER = "#333333"
    BORDER_LIGHT = "#444444"
    BORDER_FOCUS = "#C40000"
    
    # Gauge Colors - Modern Red Theme
    GAUGE_BG = "#1A1A1A"
    GAUGE_RING = "#333333"
    GAUGE_NORMAL = "#4CAF50"
    GAUGE_WARNING = "#FF9800"
    GAUGE_CRITICAL = "#C40000"
    GAUGE_NEEDLE = "#C40000"
    GAUGE_GLOW = "#C40000"
    
    @classmethod
    def apply_theme(cls, app: QApplication):
        """Apply Predict professional theme to the application"""
        app.setStyle("Fusion")
        
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(cls.BACKGROUND))
        palette.setColor(QPalette.WindowText, QColor(cls.TEXT_PRIMARY))
        palette.setColor(QPalette.Base, QColor(cls.CARD_BG))
        palette.setColor(QPalette.AlternateBase, QColor(cls.BACKGROUND_SECONDARY))
        palette.setColor(QPalette.ToolTipBase, QColor(cls.CARD_BG))
        palette.setColor(QPalette.ToolTipText, QColor(cls.TEXT_PRIMARY))
        palette.setColor(QPalette.Text, QColor(cls.TEXT_PRIMARY))
        palette.setColor(QPalette.PlaceholderText, QColor(cls.TEXT_MUTED))
        palette.setColor(QPalette.Button, QColor(cls.CARD_BG))
        palette.setColor(QPalette.ButtonText, QColor(cls.TEXT_PRIMARY))
        palette.setColor(QPalette.BrightText, QColor(cls.DANGER))
        palette.setColor(QPalette.Highlight, QColor(cls.PRIMARY))
        palette.setColor(QPalette.HighlightedText, QColor(cls.TEXT_PRIMARY))
        palette.setColor(QPalette.Link, QColor(cls.PRIMARY))
        palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(cls.TEXT_MUTED))
        palette.setColor(QPalette.Disabled, QPalette.Text, QColor(cls.TEXT_MUTED))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(cls.TEXT_MUTED))
        
        app.setPalette(palette)
        app.setStyleSheet(cls._get_stylesheet())
    
    @classmethod
    def _get_stylesheet(cls) -> str:
        """Get complete application stylesheet with Predict Red theme"""
        return f"""
            QWidget {{
                font-family: 'Segoe UI', 'SF Pro Display', -apple-system, sans-serif;
                font-size: 13px;
            }}
            
            QMainWindow {{
                background-color: {cls.BACKGROUND};
            }}
            
            QTabWidget::pane {{
                border: 1px solid {cls.BORDER};
                border-radius: 8px;
                background-color: {cls.BACKGROUND_SECONDARY};
                padding: 5px;
            }}
            
            QTabBar::tab {{
                background-color: {cls.CARD_BG};
                color: {cls.TEXT_SECONDARY};
                padding: 10px 18px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                border: 1px solid {cls.BORDER};
                border-bottom: none;
                font-weight: 500;
            }}
            
            QTabBar::tab:selected {{
                background-color: {cls.PRIMARY};
                color: {cls.TEXT_PRIMARY};
                font-weight: 600;
            }}
            
            QTabBar::tab:hover:!selected {{
                background-color: {cls.CARD_BG_HOVER};
                color: {cls.TEXT_PRIMARY};
            }}
            
            QGroupBox {{
                font-weight: 600;
                font-size: 14px;
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 8px;
                margin-top: 12px;
                padding: 15px;
                background-color: {cls.CARD_BG};
            }}
            
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 8px;
                background-color: {cls.CARD_BG};
                color: {cls.PRIMARY};
            }}
            
            QPushButton {{
                background-color: {cls.PRIMARY};
                color: {cls.TEXT_PRIMARY};
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 13px;
            }}
            
            QPushButton:hover {{
                background-color: {cls.PRIMARY_LIGHT};
            }}
            
            QPushButton:pressed {{
                background-color: {cls.PRIMARY_DARK};
            }}
            
            QPushButton:disabled {{
                background-color: {cls.CARD_BG_HOVER};
                color: {cls.TEXT_MUTED};
            }}
            
            QPushButton[secondary="true"] {{
                background-color: {cls.SECONDARY};
                border: 1px solid {cls.BORDER};
            }}
            
            QPushButton[secondary="true"]:hover {{
                background-color: {cls.SECONDARY_LIGHT};
            }}
            
            QLineEdit, QTextEdit, QPlainTextEdit {{
                background-color: {cls.SECONDARY};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 6px;
                padding: 8px 12px;
                selection-background-color: {cls.PRIMARY};
            }}
            
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
                border-color: {cls.PRIMARY};
            }}
            
            QComboBox {{
                background-color: {cls.SECONDARY};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 6px;
                padding: 8px 12px;
                min-width: 120px;
            }}
            
            QComboBox:focus {{
                border-color: {cls.PRIMARY};
            }}
            
            QComboBox::drop-down {{
                border: none;
                width: 30px;
            }}
            
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {cls.TEXT_SECONDARY};
                margin-right: 10px;
            }}
            
            QComboBox QAbstractItemView {{
                background-color: {cls.CARD_BG};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                selection-background-color: {cls.PRIMARY};
                outline: none;
            }}
            
            QTableWidget {{
                background-color: {cls.CARD_BG};
                alternate-background-color: {cls.BACKGROUND_SECONDARY};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 8px;
                gridline-color: {cls.BORDER};
            }}
            
            QTableWidget::item {{
                padding: 8px;
            }}
            
            QTableWidget::item:selected {{
                background-color: {cls.PRIMARY};
                color: {cls.TEXT_PRIMARY};
            }}
            
            QHeaderView::section {{
                background-color: {cls.SECONDARY};
                color: {cls.TEXT_PRIMARY};
                padding: 10px;
                border: none;
                border-bottom: 1px solid {cls.BORDER};
                font-weight: 600;
            }}
            
            QScrollBar:vertical {{
                background-color: {cls.BACKGROUND};
                width: 12px;
                margin: 0;
                border-radius: 6px;
            }}
            
            QScrollBar::handle:vertical {{
                background-color: {cls.BORDER_LIGHT};
                min-height: 30px;
                border-radius: 6px;
                margin: 2px;
            }}
            
            QScrollBar::handle:vertical:hover {{
                background-color: {cls.TEXT_MUTED};
            }}
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            
            QScrollBar:horizontal {{
                background-color: {cls.BACKGROUND};
                height: 12px;
                margin: 0;
                border-radius: 6px;
            }}
            
            QScrollBar::handle:horizontal {{
                background-color: {cls.BORDER_LIGHT};
                min-width: 30px;
                border-radius: 6px;
                margin: 2px;
            }}
            
            QScrollBar::handle:horizontal:hover {{
                background-color: {cls.TEXT_MUTED};
            }}
            
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0;
            }}
            
            QProgressBar {{
                background-color: {cls.SECONDARY};
                border: 1px solid {cls.BORDER};
                border-radius: 6px;
                text-align: center;
                color: {cls.TEXT_PRIMARY};
                height: 22px;
            }}
            
            QProgressBar::chunk {{
                background-color: {cls.PRIMARY};
                border-radius: 5px;
            }}
            
            QCheckBox {{
                color: {cls.TEXT_PRIMARY};
                spacing: 8px;
            }}
            
            QCheckBox::indicator {{
                width: 20px;
                height: 20px;
                border: 2px solid {cls.BORDER};
                border-radius: 4px;
                background-color: {cls.SECONDARY};
            }}
            
            QCheckBox::indicator:checked {{
                background-color: {cls.PRIMARY};
                border-color: {cls.PRIMARY};
            }}
            
            QCheckBox::indicator:hover {{
                border-color: {cls.PRIMARY};
            }}
            
            QRadioButton {{
                color: {cls.TEXT_PRIMARY};
                spacing: 8px;
            }}
            
            QRadioButton::indicator {{
                width: 20px;
                height: 20px;
                border: 2px solid {cls.BORDER};
                border-radius: 10px;
                background-color: {cls.SECONDARY};
            }}
            
            QRadioButton::indicator:checked {{
                background-color: {cls.PRIMARY};
                border-color: {cls.PRIMARY};
            }}
            
            QSlider::groove:horizontal {{
                background-color: {cls.SECONDARY};
                height: 8px;
                border-radius: 4px;
            }}
            
            QSlider::handle:horizontal {{
                background-color: {cls.PRIMARY};
                width: 20px;
                margin: -6px 0;
                border-radius: 10px;
            }}
            
            QSlider::handle:horizontal:hover {{
                background-color: {cls.PRIMARY_LIGHT};
            }}
            
            QSpinBox {{
                background-color: {cls.SECONDARY};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 6px;
                padding: 6px;
            }}
            
            QSpinBox:focus {{
                border-color: {cls.PRIMARY};
            }}
            
            QLabel {{
                color: {cls.TEXT_PRIMARY};
            }}
            
            QToolTip {{
                background-color: {cls.CARD_BG};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 4px;
                padding: 6px;
            }}
            
            QMessageBox {{
                background-color: {cls.BACKGROUND};
            }}
            
            QMessageBox QLabel {{
                color: {cls.TEXT_PRIMARY};
            }}
            
            QMessageBox QPushButton {{
                min-width: 80px;
            }}
            
            QMenu {{
                background-color: {cls.CARD_BG};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER};
                border-radius: 8px;
                padding: 5px;
            }}
            
            QMenu::item {{
                padding: 8px 20px;
                border-radius: 4px;
            }}
            
            QMenu::item:selected {{
                background-color: {cls.PRIMARY};
            }}
            
            QMenu::separator {{
                height: 1px;
                background-color: {cls.BORDER};
                margin: 5px 10px;
            }}
            
            QStatusBar {{
                background-color: {cls.SECONDARY};
                color: {cls.TEXT_SECONDARY};
                border-top: 1px solid {cls.BORDER};
            }}
            
            QFrame[frameShape="4"] {{
                background-color: {cls.BORDER};
                max-height: 1px;
            }}
            
            QFrame[frameShape="5"] {{
                background-color: {cls.BORDER};
                max-width: 1px;
            }}
        """


# ================================
# BUTTON STYLES
# ================================

def get_primary_button_style():
    """Get primary button style (red)"""
    return f"""
        QPushButton {{
            background-color: {PredictTheme.PRIMARY};
            color: {PredictTheme.TEXT_PRIMARY};
            border: none;
            border-radius: 6px;
            padding: 12px 24px;
            font-weight: 600;
            font-size: 14px;
        }}
        QPushButton:hover {{
            background-color: {PredictTheme.PRIMARY_LIGHT};
        }}
        QPushButton:pressed {{
            background-color: {PredictTheme.PRIMARY_DARK};
        }}
        QPushButton:disabled {{
            background-color: {PredictTheme.CARD_BG_HOVER};
            color: {PredictTheme.TEXT_MUTED};
        }}
    """


def get_secondary_button_style():
    """Get secondary button style (dark)"""
    return f"""
        QPushButton {{
            background-color: {PredictTheme.SECONDARY};
            color: {PredictTheme.TEXT_PRIMARY};
            border: 1px solid {PredictTheme.BORDER};
            border-radius: 6px;
            padding: 10px 20px;
            font-weight: 500;
            font-size: 13px;
        }}
        QPushButton:hover {{
            background-color: {PredictTheme.SECONDARY_LIGHT};
            border-color: {PredictTheme.PRIMARY};
        }}
        QPushButton:pressed {{
            background-color: {PredictTheme.SECONDARY_DARK};
        }}
    """


def get_success_button_style():
    """Get success button style (green)"""
    return f"""
        QPushButton {{
            background-color: {PredictTheme.SUCCESS};
            color: {PredictTheme.TEXT_PRIMARY};
            border: none;
            border-radius: 6px;
            padding: 10px 20px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {PredictTheme.SUCCESS_LIGHT};
        }}
    """


def get_danger_button_style():
    """Get danger button style (red)"""
    return f"""
        QPushButton {{
            background-color: {PredictTheme.DANGER};
            color: {PredictTheme.TEXT_PRIMARY};
            border: none;
            border-radius: 6px;
            padding: 10px 20px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {PredictTheme.DANGER_DARK};
        }}
    """


# ================================
# COMMON UTILITY FUNCTIONS
# ================================

def show_error(parent, title, message):
    """Show a standardized error message dialog"""
    msg_box = QMessageBox(parent)
    msg_box.setIcon(QMessageBox.Critical)
    msg_box.setWindowTitle(title)
    msg_box.setText(message)
    msg_box.setStandardButtons(QMessageBox.Ok)
    return msg_box.exec()


def show_warning(parent, title, message):
    """Show a standardized warning message dialog"""
    msg_box = QMessageBox(parent)
    msg_box.setIcon(QMessageBox.Warning)
    msg_box.setWindowTitle(title)
    msg_box.setText(message)
    msg_box.setStandardButtons(QMessageBox.Ok)
    return msg_box.exec()


def show_info(parent, title, message):
    """Show a standardized information message dialog"""
    msg_box = QMessageBox(parent)
    msg_box.setIcon(QMessageBox.Information)
    msg_box.setWindowTitle(title)
    msg_box.setText(message)
    msg_box.setStandardButtons(QMessageBox.Ok)
    return msg_box.exec()


def show_question(parent, title, message):
    """Show a standardized question dialog with Yes/No buttons"""
    msg_box = QMessageBox(parent)
    msg_box.setIcon(QMessageBox.Question)
    msg_box.setWindowTitle(title)
    msg_box.setText(message)
    msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    msg_box.setDefaultButton(QMessageBox.No)
    return msg_box.exec()


# Alias for backward compatibility
ProfessionalTheme = PredictTheme
