"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Help/About Tab

Help Tab - Documentation, changelog, and about information
"""

import os
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGroupBox, QTabWidget,
    QTextEdit, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QFont, QDesktopServices, QTextCursor

try:
    from config import get_config
    CONFIG = get_config()
except ImportError:
    CONFIG = None


class HelpTab(QWidget):
    """
    Help and About Tab
    
    Provides:
    - Documentation links
    - Changelog
    - About information
    - License information
    - Contact support
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_content()

    def _setup_ui(self):
        """Build the help UI with tabbed interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ==================== HEADER ====================
        header = QFrame()
        header.setStyleSheet("background-color: #161B22; border-bottom: 1px solid #30363D;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 15, 20, 15)
        header_layout.setSpacing(15)

        title = QLabel("❓ Help & About")
        title.setFont(QFont("Segoe UI", 24, QFont.Bold))
        title.setStyleSheet("color: #F0F6FC;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Contact support button
        contact_btn = QPushButton("📧 Contact Support")
        contact_btn.setStyleSheet(self._get_button_style('secondary'))
        contact_btn.clicked.connect(self._contact_support)
        header_layout.addWidget(contact_btn)

        layout.addWidget(header)

        # ==================== TAB WIDGET ====================
        self.help_tabs = QTabWidget()
        self.help_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #0D1117;
            }
            QTabBar::tab {
                background-color: #161B22;
                color: #8B949E;
                padding: 12px 24px;
                border: none;
                border-bottom: 2px solid transparent;
                font-size: 13px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background-color: #0D1117;
                color: #F0F6FC;
                border-bottom: 2px solid #C40000;
            }
            QTabBar::tab:hover {
                color: #F0F6FC;
            }
        """)

        # Create tabs
        self.documentation_tab = self._create_documentation_tab()
        self.help_tabs.addTab(self.documentation_tab, "📚 Documentation")

        self.changelog_tab = self._create_changelog_tab()
        self.help_tabs.addTab(self.changelog_tab, "📝 Changelog")

        self.about_tab = self._create_about_tab()
        self.help_tabs.addTab(self.about_tab, "ℹ️ About")

        layout.addWidget(self.help_tabs)

    def _create_documentation_tab(self) -> QWidget:
        """Create documentation tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(25)

        # Quick Start
        quick_start_card = self._create_card("🚀 Quick Start", "#0DCAF0")
        quick_start_content = QVBoxLayout(quick_start_card)
        quick_start_content.setSpacing(15)

        quick_start_text = QLabel(
            "1. Connect your OBD-II adapter to your vehicle\n"
            "2. Launch PREDICT and connect to the adapter\n"
            "3. Allow the AI to learn your vehicle's baseline (7 days recommended)\n"
            "4. Review predictions and alerts in the Dashboard\n"
            "5. Generate reports from the Reports tab"
        )
        quick_start_text.setWordWrap(True)
        quick_start_text.setStyleSheet("color: #F0F6FC; font-size: 14px; line-height: 1.6;")
        quick_start_content.addWidget(quick_start_text)

        layout.addWidget(quick_start_card)

        # Features
        features_card = self._create_card("✨ Features", "#4CAF50")
        features_content = QVBoxLayout(features_card)
        features_content.setSpacing(10)

        features = [
            "• AI-Powered Predictions - Predict vehicle failures before they happen",
            "• Real-Time Monitoring - Live OBD-II data streaming",
            "• Fuel Tracking - Track fuel consumption and costs",
            "• Driving Score - Monitor and improve driving habits",
            "• Geofencing - Set up location-based alerts",
            "• Maintenance Reminders - Never miss a service interval",
            "• Recall Alerts - Stay informed about safety recalls",
            "• Multi-Vehicle Support - Manage multiple vehicles",
            "• Cloud Sync - Access data from anywhere",
            "• PDF Reports - Generate professional vehicle reports"
        ]

        for feature in features:
            label = QLabel(feature)
            label.setStyleSheet("color: #F0F6FC; font-size: 13px;")
            features_content.addWidget(label)

        layout.addWidget(features_card)

        # Links
        links_card = self._create_card("🔗 Helpful Links", "#FFC107")
        links_content = QVBoxLayout(links_card)
        links_content.setSpacing(12)

        self._add_link_button(links_content, "📖 User Guide", "https://docs.predict.ai/user-guide")
        self._add_link_button(links_content, "🔧 Troubleshooting", "https://docs.predict.ai/troubleshooting")
        self._add_link_button(links_content, "💡 Tips & Tricks", "https://docs.predict.ai/tips")
        self._add_link_button(links_content, "🎥 Video Tutorials", "https://docs.predict.ai/videos")
        self._add_link_button(links_content, "🌐 Community Forum", "https://community.predict.ai")

        layout.addWidget(links_card)

        layout.addStretch()
        return widget

    def _create_changelog_tab(self) -> QWidget:
        """Create changelog tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(25)

        # Changelog content
        changelog_card = self._create_card("📝 Version History", "#0DCAF0")
        changelog_content = QVBoxLayout(changelog_card)
        changelog_content.setSpacing(15)

        self.changelog_text = QTextEdit()
        self.changelog_text.setReadOnly(True)
        self.changelog_text.setStyleSheet("""
            QTextEdit {
                background-color: #21262D;
                color: #F0F6FC;
                border: none;
                border-radius: 8px;
                padding: 15px;
                font-size: 13px;
                font-family: 'Segoe UI', 'Consolas', monospace;
            }
        """)
        self.changelog_text.setMaximumHeight(500)
        changelog_content.addWidget(self.changelog_text)

        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh Changelog")
        refresh_btn.setStyleSheet(self._get_button_style('secondary'))
        refresh_btn.clicked.connect(self._load_changelog)
        changelog_content.addWidget(refresh_btn)

        layout.addWidget(changelog_card)

        layout.addStretch()
        return widget

    def _create_about_tab(self) -> QWidget:
        """Create about tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(25)

        # About PREDICT
        about_card = self._create_card("ℹ️ About PREDICT", "#0DCAF0")
        about_content = QVBoxLayout(about_card)
        about_content.setSpacing(20)
        about_content.setAlignment(Qt.AlignCenter)

        # Logo placeholder
        logo_label = QLabel("🚗 PREDICT")
        logo_label.setFont(QFont("Segoe UI", 48, QFont.Bold))
        logo_label.setStyleSheet("color: #C40000;")
        about_content.addWidget(logo_label, 0, Qt.AlignCenter)

        # Version
        version = self._get_version()
        version_label = QLabel(f"Version {version}")
        version_label.setFont(QFont("Segoe UI", 16))
        version_label.setStyleSheet("color: #F0F6FC;")
        about_content.addWidget(version_label, 0, Qt.AlignCenter)

        # Description
        desc_label = QLabel(
            "PREDICT is an AI-powered vehicle intelligence platform that "
            "predicts failures, monitors performance, and helps you maintain "
            "your vehicle proactively."
        )
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setStyleSheet("color: #8B949E; font-size: 14px; max-width: 500px;")
        about_content.addWidget(desc_label, 0, Qt.AlignCenter)

        layout.addWidget(about_card)

        # System Info
        info_card = self._create_card("💻 System Information", "#4CAF50")
        info_content = QVBoxLayout(info_card)
        info_content.setSpacing(10)

        self._add_info_row(info_content, "Platform:", self._get_platform())
        self._add_info_row(info_content, "Python Version:", self._get_python_version())
        self._add_info_row(info_content, "Qt Version:", self._get_qt_version())
        self._add_info_row(info_content, "Installation:", self._get_installation_path())

        layout.addWidget(info_card)

        # License
        license_card = self._create_card("⚖️ License", "#FFC107")
        license_content = QVBoxLayout(license_card)
        license_content.setSpacing(15)

        license_text = QLabel(
            "PREDICT - Vehicle Intelligence Platform\n"
            "Copyright © 2026 PREDICT. All rights reserved.\n\n"
            "This software is proprietary and confidential. "
            "Unauthorized copying, modification, distribution, or use is strictly prohibited."
        )
        license_text.setWordWrap(True)
        license_text.setStyleSheet("color: #F0F6FC; font-size: 13px; line-height: 1.6;")
        license_content.addWidget(license_text)

        # View license button
        view_license_btn = QPushButton("📄 View Full License")
        view_license_btn.setStyleSheet(self._get_button_style('secondary'))
        view_license_btn.clicked.connect(self._view_full_license)
        license_content.addWidget(view_license_btn)

        layout.addWidget(license_card)

        # Credits
        credits_card = self._create_card("🙏 Credits", "#FFC107")
        credits_content = QVBoxLayout(credits_card)
        credits_content.setSpacing(10)

        credits_text = QLabel(
            "Developed by PREDICT Team\n\n"
            "Special thanks to:\n"
            "• The open-source community\n"
            "• PySide6 developers\n"
            "• obd-python library contributors\n"
            "• All our beta testers and users"
        )
        credits_text.setWordWrap(True)
        credits_text.setStyleSheet("color: #F0F6FC; font-size: 13px; line-height: 1.6;")
        credits_content.addWidget(credits_text)

        layout.addWidget(credits_card)

        layout.addStretch()
        return widget

    def _create_card(self, title: str, color: str) -> QFrame:
        """Create a consistent card/frame"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #161B22;
                border: 1px solid {color};
                border-radius: 12px;
                padding: 20px;
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Card title
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title_label.setStyleSheet(f"color: {color};")
        layout.addWidget(title_label)

        return card

    def _add_link_button(self, layout: QVBoxLayout, text: str, url: str):
        """Add a link button to the layout"""
        btn = QPushButton(text)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #21262D;
                color: #0DCAF0;
                border: 1px solid #30363D;
                border-radius: 6px;
                padding: 10px 15px;
                font-size: 13px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #30363D;
                border-color: #0DCAF0;
            }
        """)
        btn.clicked.connect(lambda: self._open_url(url))
        layout.addWidget(btn)

    def _add_info_row(self, layout: QVBoxLayout, label: str, value: str):
        """Add an information row"""
        row = QHBoxLayout()
        row.setSpacing(10)

        label_widget = QLabel(label)
        label_widget.setStyleSheet("color: #8B949E; font-size: 13px; font-weight: 600;")
        label_widget.setFixedWidth(150)
        row.addWidget(label_widget)

        value_widget = QLabel(value)
        value_widget.setStyleSheet("color: #F0F6FC; font-size: 13px;")
        row.addWidget(value_widget, 1)

        layout.addLayout(row)

    def _get_button_style(self, style_type: str = 'primary') -> str:
        """Get button stylesheet"""
        styles = {
            'primary': """
                QPushButton {
                    background-color: #C40000;
                    color: #FFFFFF;
                    border: none;
                    padding: 10px 20px;
                    font-size: 13px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #E53935;
                }
            """,
            'secondary': """
                QPushButton {
                    background-color: #21262D;
                    color: #F0F6FC;
                    border: 1px solid #30363D;
                    padding: 10px 20px;
                    font-size: 13px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #30363D;
                    border-color: #8B949E;
                }
            """
        }
        return styles.get(style_type, styles['primary'])

    def _load_content(self):
        """Load all content"""
        self._load_changelog()

    def _load_changelog(self):
        """Load changelog from file"""
        changelog_file = "./CHANGELOG.md"
        
        if os.path.exists(changelog_file):
            try:
                with open(changelog_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.changelog_text.setPlainText(content)
            except Exception as e:
                self.changelog_text.setPlainText(f"Failed to load changelog: {e}")
        else:
            # Default changelog
            default_changelog = """# Changelog

## Version 5.0.0 (2026-01-10)
### Phase 4: Analytics & Reports Enhancement
- Added real-time interactive charts using pyqtgraph
- Implemented 6 chart types: Fuel Efficiency, Maintenance Costs, DTC Categories, Driving Score, Temperature History, RPM Histogram
- Enhanced dashboard with live data widgets
- Implemented global search functionality
- Added CSV export for all charts

### Phase 5: Settings & Configuration Completion
- Added comprehensive settings tab with General, OBD, Notifications, and AI sections
- Implemented settings save/load for all categories
- Added theme switching (Dark/Light)
- Added notification preferences (In-App, Email, SMS, Push)

## Version 4.0.0 (2026-01-05)
### Phase 3: Dashboard Integration & Multi-Vehicle Support
- Added vehicle switcher in main window
- Implemented multi-vehicle profile management
- Added sync status indicator
- Integrated voice command system
- Added remote command controls

### Phase 2: New Dashboard Tabs
- Created Fuel Tracking tab with MPG tracking
- Created Driving Score tab with behavior analysis
- Created Geofencing tab with zone management
- Created ESP32 Sensors tab with live readings
- Created Maintenance Reminders tab
- Created Recall Alerts tab with NHTSA integration

## Version 3.0.0 (2025-12-20)
### Phase 1: Core Infrastructure & Backend Wiring
- Wired push notification manager with Firebase/OneSignal
- Wired SMS notification manager with Twilio
- Connected maintenance history API to database
- Implemented real OBD DTC retrieval
- Connected DTC learning to alert system

## Version 2.0.0 (2025-12-10)
### Major Updates
- AI-powered predictions with LSTM models
- Real-time OBD-II data streaming
- PDF report generation
- Cloud synchronization
- Multi-language support

## Version 1.0.0 (2025-11-15)
### Initial Release
- Basic OBD-II connection
- Live data display
- DTC code reading
- Simple dashboard
"""
            self.changelog_text.setPlainText(default_changelog)

    def _get_version(self) -> str:
        """Get application version"""
        try:
            from version import __version__
            return __version__
        except ImportError:
            return "5.0.0"

    def _get_platform(self) -> str:
        """Get platform information"""
        import platform
        return f"{platform.system()} {platform.release()}"

    def _get_python_version(self) -> str:
        """Get Python version"""
        import sys
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    def _get_qt_version(self) -> str:
        """Get Qt version"""
        from PySide6.QtCore import __version__ as qt_version
        return qt_version

    def _get_installation_path(self) -> str:
        """Get installation path"""
        return os.path.abspath(os.path.dirname(__file__))

    def _open_url(self, url: str):
        """Open URL in default browser"""
        QDesktopServices.openUrl(QUrl(url))

    def _contact_support(self):
        """Open support contact"""
        subject = f"PREDICT Support Request - Version {self._get_version()}"
        body = f"Please describe your issue or question below:\n\n"
        body += f"Platform: {self._get_platform()}\n"
        body += f"Python: {self._get_python_version()}\n\n"
        
        url = f"mailto:support@predict.ai?subject={subject}&body={body}"
        self._open_url(url)

    def _view_full_license(self):
        """View full license text"""
        license_file = "./LICENSE"
        
        if os.path.exists(license_file):
            try:
                with open(license_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Show license in dialog
                dialog = QMessageBox(self)
                dialog.setWindowTitle("PREDICT License")
                dialog.setText("PREDICT - Vehicle Intelligence Platform")
                dialog.setInformativeText("Copyright © 2026 PREDICT. All rights reserved.")
                dialog.setDetailedText(content)
                dialog.setStyleSheet("""
                    QMessageBox {
                        background-color: #0D1117;
                        color: #F0F6FC;
                    }
                    QLabel {
                        color: #F0F6FC;
                    }
                """)
                dialog.exec()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load license file: {e}")
        else:
            QMessageBox.information(
                self, 
                "License Information",
                "PREDICT - Vehicle Intelligence Platform\n"
                "Copyright © 2026 PREDICT. All rights reserved.\n\n"
                "This software is proprietary and confidential. "
                "Unauthorized copying, modification, distribution, or use is strictly prohibited."
            )


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = HelpTab()
    widget.setWindowTitle("PREDICT - Help & About")
    widget.resize(900, 700)
    widget.show()

    sys.exit(app.exec())
