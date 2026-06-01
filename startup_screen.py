"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Startup Screen

PREDICT Desktop AI - Professional Startup Loading Screen
Shows logo and loading progress while initializing
"""

from PySide6.QtWidgets import QSplashScreen, QProgressBar, QLabel, QVBoxLayout, QWidget, QApplication
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from pathlib import Path

# Import config for path management
try:
    from config import get_config
    CONFIG = get_config()
except ImportError:
    CONFIG = None


class StartupScreen(QSplashScreen):
    """Professional startup screen with logo and progress bar."""

    # Signal emitted when loading is finished (success: bool)
    finished = Signal(bool)

    def __init__(self):
        # Load logo - use CONFIG if available, otherwise use relative path
        if CONFIG:
            logo_path = str(CONFIG.ROOT_DIR / "predict - Copy.png")
        else:
            logo_path = str(Path(__file__).parent / "predict - Copy.png")
        pixmap = QPixmap(logo_path)

        # Scale to reasonable size if needed
        if pixmap.width() > 600:
            pixmap = pixmap.scaledToWidth(600, Qt.SmoothTransformation)

        super().__init__(pixmap)

        # Set window flags
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)

        # Create overlay widget for progress bar and text
        self.overlay = QWidget(self)
        self.overlay.setStyleSheet("background: transparent;")

        layout = QVBoxLayout()
        layout.addStretch()

        # Status label
        self.status_label = QLabel("Initializing PREDICT AI...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 14px;
                font-weight: bold;
                background: rgba(0, 0, 0, 150);
                padding: 10px;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #3498db;
                border-radius: 5px;
                text-align: center;
                background: rgba(255, 255, 255, 200);
                height: 25px;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #3498db, stop: 1 #2ecc71
                );
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)

        layout.addSpacing(30)

        self.overlay.setLayout(layout)

        # Position overlay at bottom of splash screen
        self.overlay.setGeometry(0, pixmap.height() - 120, pixmap.width(), 120)

    def update_progress(self, percent: int, message: str):
        """Update progress bar and status message."""
        if percent >= 0:
            self.progress_bar.setValue(percent)
        self.status_label.setText(message)
        # Process events to update UI immediately
        QApplication.processEvents()

    def load_llm(self, llm_assistant):
        """Load LLM synchronously with progress updates."""
        try:
            # Step 1: Show loading message
            self.update_progress(10, "Loading database...")

            # Step 2: Configuration
            self.update_progress(20, "Loading configuration...")

            # Step 3: Vehicle profiles
            self.update_progress(30, "Loading vehicle profiles...")

            # Step 4: AI models metadata
            self.update_progress(40, "Initializing AI engine...")

            # Step 5: LLM model (lazy loading - will load on first use)
            self.update_progress(45, "AI assistant ready (lazy loading)...")

            # LLM will load when first used in chat tab to improve startup performance
            # No need to load at startup - saves memory and reduces lag

            # Step 6: Final initialization
            self.update_progress(95, "Finalizing startup...")

            # Done
            self.update_progress(100, "✓ Ready!")

            return True

        except Exception as e:
            self.update_progress(-1, f"Error: {str(e)}")
            return False

    def finish_loading(self, success: bool = True):
        """Called when loading is complete - emits signal and closes."""
        if success:
            self.status_label.setText("✓ Ready! Starting PREDICT AI...")
        else:
            self.status_label.setText("⚠️ Started with warnings")

        # Emit finished signal
        self.finished.emit(success)

        # Close splash screen after short delay
        QTimer.singleShot(300, self.close)
