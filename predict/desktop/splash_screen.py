"""
Splash screen for PREDICT Desktop application.

Shows loading progress during application startup.
"""

import logging
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QCoreApplication
from PySide6.QtGui import QFont, QColor, QPixmap

from predict.core.version import APP_NAME, APP_VERSION

logger = logging.getLogger(__name__)


class SplashScreen(QWidget):
    """
    Frameless loading screen with animated progress bar.
    
    Dark background with purple accent (#7c3aed).
    """
    
    # Colors
    BG_COLOR = "#1e1e2e"
    ACCENT_COLOR = "#7c3aed"
    TEXT_COLOR = "#cdd6f4"
    SECONDARY_TEXT = "#6c7086"
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self._setup_window()
        self._setup_ui()
        self._setup_animations()
        
        logger.debug("SplashScreen initialized")
    
    def _setup_window(self) -> None:
        """Configure window properties."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Fixed size
        self.setFixedSize(500, 300)
        
        # Center on screen
        screen = self.screen()
        if screen:
            center = screen.geometry().center()
            self.move(center.x() - 250, center.y() - 150)
    
    def _setup_ui(self) -> None:
        """Setup UI components."""
        # Main container with background
        self.container = QWidget(self)
        self.container.setGeometry(0, 0, 500, 300)
        self.container.setStyleSheet(f"""
            QWidget {{
                background-color: {self.BG_COLOR};
                border-radius: 16px;
            }}
        """)
        
        # Add drop shadow
        shadow = QGraphicsDropShadowEffect(self.container)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(shadow)
        
        # Layout
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        
        # App name
        self.name_label = QLabel(APP_NAME)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setStyleSheet(f"""
            QLabel {{
                color: {self.TEXT_COLOR};
                background: transparent;
            }}
        """)
        font = QFont("Segoe UI", 36, QFont.Weight.Bold)
        self.name_label.setFont(font)
        layout.addWidget(self.name_label)
        
        # Version
        self.version_label = QLabel(f"Version {APP_VERSION}")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.version_label.setStyleSheet(f"""
            QLabel {{
                color: {self.SECONDARY_TEXT};
                background: transparent;
            }}
        """)
        font = QFont("Segoe UI", 11)
        self.version_label.setFont(font)
        layout.addWidget(self.version_label)
        
        # Spacer
        layout.addStretch()
        
        # Status message
        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {self.SECONDARY_TEXT};
                background: transparent;
            }}
        """)
        font = QFont("Segoe UI", 10)
        self.status_label.setFont(font)
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #313244;
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {self.ACCENT_COLOR};
                border-radius: 3px;
            }}
        """)
        layout.addWidget(self.progress_bar)
    
    def _setup_animations(self) -> None:
        """Setup fade animations."""
        # Fade in animation
        self.fade_in = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in.setDuration(300)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        # Fade out animation
        self.fade_out = QPropertyAnimation(self, b"windowOpacity")
        self.fade_out.setDuration(300)
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)
        self.fade_out.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.fade_out.finished.connect(self.close)
    
    def showEvent(self, event) -> None:
        """Handle show event with fade in."""
        super().showEvent(event)
        self.fade_in.start()
    
    def update_status(self, message: str, progress: int) -> None:
        """
        Update status message and progress bar.
        
        Args:
            message: Status text to display
            progress: Progress value (0-100)
        """
        self.status_label.setText(message)
        self.progress_bar.setValue(max(0, min(100, progress)))
        
        # Process events to update UI
        QCoreApplication.processEvents()
        
        logger.debug(f"Splash status: {message} ({progress}%)")
    
    def finish(self) -> None:
        """Fade out and close the splash screen."""
        logger.debug("Closing splash screen")
        self.fade_out.start()
    
    def set_progress(self, value: int) -> None:
        """Set progress bar value only."""
        self.progress_bar.setValue(max(0, min(100, value)))
    
    def set_message(self, message: str) -> None:
        """Set status message only."""
        self.status_label.setText(message)
