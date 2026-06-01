"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Keyboard Shortcuts

Keyboard Shortcuts Manager
==========================

Provides application-wide keyboard shortcuts for common actions.

Features:
- Configurable keyboard shortcuts
- Shortcuts for navigation, actions, and tools
- Keyboard shortcut editor dialog
- Import/Export shortcut configurations
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QLineEdit, QDialog,
    QFormLayout, QGroupBox, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QMessageBox, QCheckBox, QTabWidget,
    QDialogButtonBox, QScrollArea, QFrame, QSplitter
)
from PySide6.QtCore import Qt, QSettings, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QKeySequenceEdit

from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)


@dataclass
class Shortcut:
    """Represents a keyboard shortcut."""
    id: str
    name: str
    description: str
    default_key: str
    current_key: str
    category: str
    context: str = "global"  # global, tab-specific, or widget-specific


class KeyboardShortcutManager:
    """
    Manages all application keyboard shortcuts.
    """

    def __init__(self):
        self.shortcuts: Dict[str, Shortcut] = {}
        self.active_shortcuts: Dict[str, QShortcut] = {}
        self.action_callbacks: Dict[str, Callable] = {}
        self.config_path = CONFIG.CONFIG_DIR / "keyboard_shortcuts.json"

        # Load shortcuts from config
        self._load_shortcuts()

        # Register default shortcuts
        self._register_default_shortcuts()

    def _register_default_shortcuts(self):
        """Register default application shortcuts."""
        default_shortcuts = [
            # Global Navigation
            Shortcut("global_search", "Global Search", "Open global search dialog", "Ctrl+Shift+F", "Ctrl+Shift+F", "Navigation"),
            Shortcut("quick_connect", "Quick Connect", "Quick connect to OBD adapter", "Ctrl+K", "Ctrl+K", "Navigation"),
            Shortcut("toggle_connection", "Toggle Connection", "Toggle OBD connection", "F5", "F5", "Navigation"),

            # Tab Navigation
            Shortcut("tab_dashboard", "Dashboard Tab", "Navigate to Dashboard", "Alt+1", "Alt+1", "Navigation"),
            Shortcut("tab_live_data", "Live Data Tab", "Navigate to Live Data", "Alt+2", "Alt+2", "Navigation"),
            Shortcut("tab_diagnostics", "Diagnostics Tab", "Navigate to Diagnostics", "Alt+3", "Alt+3", "Navigation"),
            Shortcut("tab_vehicles", "Vehicles Tab", "Navigate to Vehicles", "Alt+4", "Alt+4", "Navigation"),
            Shortcut("tab_reports", "Reports Tab", "Navigate to Reports", "Alt+5", "Alt+5", "Navigation"),
            Shortcut("tab_settings", "Settings Tab", "Navigate to Settings", "Alt+6", "Alt+6", "Navigation"),

            # Actions
            Shortcut("new_vehicle", "New Vehicle", "Create new vehicle profile", "Ctrl+N", "Ctrl+N", "Actions"),
            Shortcut("save", "Save", "Save current data", "Ctrl+S", "Ctrl+S", "Actions"),
            Shortcut("export_data", "Export Data", "Export current data", "Ctrl+E", "Ctrl+E", "Actions"),
            Shortcut("import_data", "Import Data", "Import data", "Ctrl+I", "Ctrl+I", "Actions"),
            Shortcut("print_report", "Print Report", "Print current report", "Ctrl+P", "Ctrl+P", "Actions"),

            # Live Data Actions
            Shortcut("start_logging", "Start Logging", "Start data logging", "Ctrl+L", "Ctrl+L", "Live Data"),
            Shortcut("stop_logging", "Stop Logging", "Stop data logging", "Ctrl+Shift+L", "Ctrl+Shift+L", "Live Data"),
            Shortcut("clear_data", "Clear Data", "Clear live data display", "Ctrl+Delete", "Ctrl+Delete", "Live Data"),
            Shortcut("refresh_data", "Refresh Data", "Refresh data display", "F9", "F9", "Live Data"),

            # Diagnostics Actions
            Shortcut("clear_dtcs", "Clear DTCs", "Clear all DTC codes", "Ctrl+D", "Ctrl+D", "Diagnostics"),
            Shortcut("read_dtcs", "Read DTCs", "Read DTC codes", "Ctrl+R", "Ctrl+R", "Diagnostics"),
            Shortcut("scan_vehicle", "Scan Vehicle", "Perform vehicle scan", "F6", "F6", "Diagnostics"),

            # AI Actions
            Shortcut("train_model", "Train Model", "Train AI model", "Ctrl+T", "Ctrl+T", "AI"),
            Shortcut("view_predictions", "View Predictions", "View AI predictions", "Ctrl+Shift+P", "Ctrl+Shift+P", "AI"),
            Shortcut("view_feedback", "View Feedback", "View prediction feedback", "Ctrl+Shift+F", "Ctrl+Shift+F", "AI"),

            # Tools
            Shortcut("open_settings", "Open Settings", "Open settings dialog", "Ctrl+,", "Ctrl+,", "Tools"),
            Shortcut("open_help", "Open Help", "Open help documentation", "F1", "F1", "Tools"),
            Shortcut("show_shortcuts", "Show Shortcuts", "Show keyboard shortcuts", "Ctrl+/", "Ctrl+/", "Tools"),

            # Application
            Shortcut("quit", "Quit", "Quit application", "Ctrl+Q", "Ctrl+Q", "Application"),
            Shortcut("fullscreen", "Toggle Fullscreen", "Toggle fullscreen mode", "F11", "F11", "Application"),
            Shortcut("minimize", "Minimize", "Minimize window", "Ctrl+M", "Ctrl+M", "Application"),
        ]

        for shortcut in default_shortcuts:
            self.register_shortcut(shortcut)

    def register_shortcut(self, shortcut: Shortcut):
        """Register a keyboard shortcut."""
        self.shortcuts[shortcut.id] = shortcut

    def register_callback(self, shortcut_id: str, callback: Callable):
        """Register a callback function for a shortcut."""
        self.action_callbacks[shortcut_id] = callback

    def activate_shortcut(self, shortcut_id: str, parent_widget: QWidget) -> bool:
        """
        Activate a shortcut for a widget.

        Args:
            shortcut_id: ID of the shortcut to activate
            parent_widget: Parent widget to attach shortcut to

        Returns:
            True if shortcut was activated successfully
        """
        if shortcut_id not in self.shortcuts:
            logger.warning(f"Shortcut not found: {shortcut_id}")
            return False

        shortcut = self.shortcuts[shortcut_id]
        key_sequence = QKeySequence(shortcut.current_key)

        # Create QShortcut
        qshortcut = QShortcut(key_sequence, parent_widget)
        qshortcut.setAutoRepeat(False)

        # Connect to callback
        if shortcut_id in self.action_callbacks:
            qshortcut.activated.connect(self.action_callbacks[shortcut_id])
        else:
            logger.warning(f"No callback registered for shortcut: {shortcut_id}")

        self.active_shortcuts[shortcut_id] = qshortcut
        return True

    def activate_all_shortcuts(self, parent_widget: QWidget):
        """Activate all registered shortcuts for a widget."""
        for shortcut_id in self.shortcuts:
            self.activate_shortcut(shortcut_id, parent_widget)

    def deactivate_shortcut(self, shortcut_id: str):
        """Deactivate a shortcut."""
        if shortcut_id in self.active_shortcuts:
            self.active_shortcuts[shortcut_id].deleteLater()
            del self.active_shortcuts[shortcut_id]

    def deactivate_all_shortcuts(self):
        """Deactivate all shortcuts."""
        for shortcut_id in list(self.active_shortcuts.keys()):
            self.deactivate_shortcut(shortcut_id)

    def update_shortcut(self, shortcut_id: str, new_key: str):
        """Update a shortcut's key sequence."""
        if shortcut_id not in self.shortcuts:
            logger.warning(f"Shortcut not found: {shortcut_id}")
            return False

        # Validate key sequence
        try:
            key_sequence = QKeySequence(new_key)
            if key_sequence.isEmpty():
                logger.warning(f"Invalid key sequence: {new_key}")
                return False
        except Exception as e:
            logger.error(f"Error validating key sequence: {e}")
            return False

        # Update shortcut
        self.shortcuts[shortcut_id].current_key = new_key

        # Save to config
        self._save_shortcuts()

        return True

    def reset_shortcut(self, shortcut_id: str):
        """Reset a shortcut to its default key."""
        if shortcut_id not in self.shortcuts:
            logger.warning(f"Shortcut not found: {shortcut_id}")
            return False

        self.shortcuts[shortcut_id].current_key = self.shortcuts[shortcut_id].default_key
        self._save_shortcuts()
        return True

    def reset_all_shortcuts(self):
        """Reset all shortcuts to defaults."""
        for shortcut_id in self.shortcuts:
            self.shortcuts[shortcut_id].current_key = self.shortcuts[shortcut_id].default_key
        self._save_shortcuts()

    def get_shortcut(self, shortcut_id: str) -> Optional[Shortcut]:
        """Get a shortcut by ID."""
        return self.shortcuts.get(shortcut_id)

    def get_all_shortcuts(self) -> Dict[str, Shortcut]:
        """Get all shortcuts."""
        return self.shortcuts

    def get_shortcuts_by_category(self, category: str) -> List[Shortcut]:
        """Get shortcuts filtered by category."""
        return [s for s in self.shortcuts.values() if s.category == category]

    def _load_shortcuts(self):
        """Load shortcuts from configuration file."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    for shortcut_id, key in data.items():
                        # Will be applied when shortcuts are registered
                        pass
        except Exception as e:
            logger.warning(f"Could not load shortcuts config: {e}")

    def _save_shortcuts(self):
        """Save shortcuts to configuration file."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                shortcut_id: shortcut.current_key
                for shortcut_id, shortcut in self.shortcuts.items()
            }

            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved {len(data)} shortcuts to {self.config_path}")
        except Exception as e:
            logger.error(f"Error saving shortcuts config: {e}")


class ShortcutEditorDialog(QDialog):
    """
    Dialog for editing keyboard shortcuts.
    """

    shortcutsChanged = Signal()

    def _get_button_style(self, style_type: str = 'primary') -> str:
        """Get consistent button style based on type."""
        styles = {
            'primary': """
                QPushButton {
                    background-color: #C40000;
                    color: #F0F6FC;
                    border: none;
                    padding: 12px 24px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #E53935;
                }
                QPushButton:pressed {
                    background-color: #B71C1C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """,
            'secondary': """
                QPushButton {
                    background-color: #21262D;
                    color: #F0F6FC;
                    border: 1px solid #30363D;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #30363D;
                    border-color: #8B949E;
                }
                QPushButton:pressed {
                    background-color: #161B22;
                }
                QPushButton:disabled {
                    background-color: #161B22;
                    color: #484F58;
                    border-color: #30363D;
                }
            """,
            'danger': """
                QPushButton {
                    background-color: #C40000;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #E53935;
                }
                QPushButton:pressed {
                    background-color: #B71C1C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """,
            'success': """
                QPushButton {
                    background-color: #4CAF50;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #66BB6A;
                }
                QPushButton:pressed {
                    background-color: #388E3C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """,
            'warning': """
                QPushButton {
                    background-color: #FFC107;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #FFB300;
                }
                QPushButton:pressed {
                    background-color: #FF8F00;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """,
            'info': """
                QPushButton {
                    background-color: #2196F3;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #42A5F5;
                }
                QPushButton:pressed {
                    background-color: #1976D2;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """
        }
        return styles.get(style_type, styles['primary'])

    def __init__(self, shortcut_manager: KeyboardShortcutManager, parent=None):
        super().__init__(parent)
        self.shortcut_manager = shortcut_manager
        self.setWindowTitle("Keyboard Shortcuts")
        self.setMinimumSize(700, 500)

        self._init_ui()
        self._load_shortcuts()

    def _init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout()

        # Search box
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        search_layout.addWidget(search_label)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search shortcuts...")
        self.search_edit.textChanged.connect(self._filter_shortcuts)
        search_layout.addWidget(self.search_edit)

        layout.addLayout(search_layout)

        # Main content
        content_splitter = QSplitter(Qt.Horizontal)

        # Categories tree
        self.category_tree = QTreeWidget()
        self.category_tree.setHeaderLabels(["Category"])
        self.category_tree.setColumnWidth(0, 200)
        self.category_tree.itemClicked.connect(self._on_category_selected)
        content_splitter.addWidget(self.category_tree)

        # Shortcuts list
        shortcuts_group = QGroupBox("Shortcuts")
        shortcuts_layout = QVBoxLayout()

        # Header
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Action"))
        header_layout.addWidget(QLabel("Shortcut"))
        header_layout.addWidget(QLabel("Default"))
        shortcuts_layout.addLayout(header_layout)

        # Shortcuts list
        self.shortcuts_list = QListWidget()
        self.shortcuts_list.itemClicked.connect(self._on_shortcut_selected)
        shortcuts_layout.addWidget(self.shortcuts_list)

        # Key sequence editor
        key_layout = QHBoxLayout()
        key_layout.addWidget(QLabel("New Shortcut:"))
        self.key_edit = QKeySequenceEdit()
        self.key_edit.setMinimumWidth(200)
        key_layout.addWidget(self.key_edit)

        self.apply_button = QPushButton("Apply")
        self.apply_button.setStyleSheet(self._get_button_style('primary'))
        self.apply_button.clicked.connect(self._apply_shortcut)
        self.apply_button.setEnabled(False)
        key_layout.addWidget(self.apply_button)

        self.reset_button = QPushButton("Reset to Default")
        self.reset_button.setStyleSheet(self._get_button_style('secondary'))
        self.reset_button.clicked.connect(self._reset_shortcut)
        self.reset_button.setEnabled(False)
        key_layout.addWidget(self.reset_button)

        shortcuts_layout.addLayout(key_layout)

        shortcuts_group.setLayout(shortcuts_layout)
        content_splitter.addWidget(shortcuts_group)

        content_splitter.setSizes([200, 500])
        layout.addWidget(content_splitter)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Reset
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.Reset).clicked.connect(self._reset_all)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def _load_shortcuts(self):
        """Load shortcuts into the UI."""
        # Clear existing
        self.category_tree.clear()
        self.shortcuts_list.clear()

        # Get categories
        categories = sorted(set(s.category for s in self.shortcut_manager.shortcuts.values()))

        # Add categories to tree
        for category in categories:
            item = QTreeWidgetItem([category])
            item.setData(0, Qt.UserRole, category)
            self.category_tree.addTopLevelItem(item)

        # Select first category
        if self.category_tree.topLevelItemCount() > 0:
            self.category_tree.setCurrentItem(self.category_tree.topLevelItem(0))
            self._on_category_selected(self.category_tree.topLevelItem(0), 0)

    def _filter_shortcuts(self, text: str):
        """Filter shortcuts by search text."""
        search_text = text.lower()

        for i in range(self.shortcuts_list.count()):
            item = self.shortcuts_list.item(i)
            shortcut_data = item.data(Qt.UserRole)
            visible = (
                search_text in shortcut_data.name.lower() or
                search_text in shortcut_data.description.lower() or
                search_text in shortcut_data.current_key.lower()
            )
            item.setHidden(not visible)

    def _on_category_selected(self, item: QTreeWidgetItem, column: int):
        """Handle category selection."""
        category = item.data(0, Qt.UserRole)
        shortcuts = self.shortcut_manager.get_shortcuts_by_category(category)

        self.shortcuts_list.clear()

        for shortcut in shortcuts:
            list_item = QListWidgetItem()
            list_item.setText(f"{shortcut.name} - {shortcut.current_key}")
            list_item.setData(Qt.UserRole, shortcut)
            list_item.setToolTip(shortcut.description)
            self.shortcuts_list.addItem(list_item)

        self._apply_filter()

    def _apply_filter(self):
        """Apply current search filter."""
        self._filter_shortcuts(self.search_edit.text())

    def _on_shortcut_selected(self, item: QListWidgetItem):
        """Handle shortcut selection."""
        shortcut = item.data(Qt.UserRole)
        self.key_edit.setKeySequence(QKeySequence(shortcut.current_key))
        self.apply_button.setEnabled(True)
        self.reset_button.setEnabled(shortcut.current_key != shortcut.default_key)

    def _apply_shortcut(self):
        """Apply new shortcut."""
        current_item = self.shortcuts_list.currentItem()
        if not current_item:
            return

        shortcut = current_item.data(Qt.UserRole)
        new_key = self.key_edit.keySequence().toString()

        if not new_key:
            QMessageBox.warning(self, "Invalid Shortcut", "Please enter a valid shortcut.")
            return

        # Check for conflicts
        for s in self.shortcut_manager.shortcuts.values():
            if s.id != shortcut.id and s.current_key == new_key:
                reply = QMessageBox.question(
                    self,
                    "Shortcut Conflict",
                    f"The shortcut '{new_key}' is already assigned to '{s.name}'.\n\n"
                    "Do you want to reassign it?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return

        # Update shortcut
        self.shortcut_manager.update_shortcut(shortcut.id, new_key)

        # Update UI
        current_item.setText(f"{shortcut.name} - {new_key}")
        self.shortcutsChanged.emit()

    def _reset_shortcut(self):
        """Reset selected shortcut to default."""
        current_item = self.shortcuts_list.currentItem()
        if not current_item:
            return

        shortcut = current_item.data(Qt.UserRole)
        self.shortcut_manager.reset_shortcut(shortcut.id)

        # Update UI
        current_item.setText(f"{shortcut.name} - {shortcut.default_key}")
        self.key_edit.setKeySequence(QKeySequence(shortcut.default_key))
        self.reset_button.setEnabled(False)
        self.shortcutsChanged.emit()

    def _reset_all(self):
        """Reset all shortcuts to defaults."""
        reply = QMessageBox.question(
            self,
            "Reset All Shortcuts",
            "Are you sure you want to reset all shortcuts to their defaults?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.shortcut_manager.reset_all_shortcuts()
            self._load_shortcuts()
            self.shortcutsChanged.emit()


class ShortcutHelpDialog(QDialog):
    """
    Dialog showing all keyboard shortcuts in a readable format.
    """

    def _get_button_style(self, style_type: str = 'primary') -> str:
        """Get consistent button style based on type."""
        styles = {
            'primary': """
                QPushButton {
                    background-color: #C40000;
                    color: #F0F6FC;
                    border: none;
                    padding: 12px 24px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #E53935;
                }
                QPushButton:pressed {
                    background-color: #B71C1C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """,
            'secondary': """
                QPushButton {
                    background-color: #21262D;
                    color: #F0F6FC;
                    border: 1px solid #30363D;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #30363D;
                    border-color: #8B949E;
                }
                QPushButton:pressed {
                    background-color: #161B22;
                }
                QPushButton:disabled {
                    background-color: #161B22;
                    color: #484F58;
                    border-color: #30363D;
                }
            """,
            'danger': """
                QPushButton {
                    background-color: #C40000;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #E53935;
                }
                QPushButton:pressed {
                    background-color: #B71C1C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """,
            'success': """
                QPushButton {
                    background-color: #4CAF50;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #66BB6A;
                }
                QPushButton:pressed {
                    background-color: #388E3C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """,
            'warning': """
                QPushButton {
                    background-color: #FFC107;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #FFB300;
                }
                QPushButton:pressed {
                    background-color: #FF8F00;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """,
            'info': """
                QPushButton {
                    background-color: #2196F3;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #42A5F5;
                }
                QPushButton:pressed {
                    background-color: #1976D2;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """
        }
        return styles.get(style_type, styles['primary'])

    def __init__(self, shortcut_manager: KeyboardShortcutManager, parent=None):
        super().__init__(parent)
        self.shortcut_manager = shortcut_manager
        self.setWindowTitle("Keyboard Shortcuts")
        self.setMinimumSize(600, 500)

        self._init_ui()

    def _init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout()

        # Search box
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        search_layout.addWidget(search_label)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search shortcuts...")
        self.search_edit.textChanged.connect(self._filter_shortcuts)
        search_layout.addWidget(self.search_edit)

        layout.addLayout(search_layout)

        # Shortcuts display
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        self.shortcuts_widget = QWidget()
        self.shortcuts_layout = QVBoxLayout(self.shortcuts_widget)

        self._display_shortcuts()

        scroll_area.setWidget(self.shortcuts_widget)
        layout.addWidget(scroll_area)

        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.close_button = QPushButton("Close")
        self.close_button.setStyleSheet(self._get_button_style('secondary'))
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _display_shortcuts(self):
        """Display all shortcuts grouped by category."""
        # Clear existing
        for i in reversed(range(self.shortcuts_layout.count())):
            self.shortcuts_layout.itemAt(i).widget().setParent(None)

        # Get categories
        categories = sorted(set(s.category for s in self.shortcut_manager.shortcuts.values()))

        for category in categories:
            # Category header
            category_label = QLabel(f"<h3>{category}</h3>")
            category_label.setStyleSheet("QLabel { color: #333; margin-top: 15px; }")
            self.shortcuts_layout.addWidget(category_label)

            # Shortcuts table
            table_widget = QTreeWidget()
            table_widget.setHeaderLabels(["Action", "Shortcut", "Description"])
            table_widget.setColumnWidth(0, 200)
            table_widget.setColumnWidth(1, 150)
            table_widget.setMaximumHeight(200)

            shortcuts = self.shortcut_manager.get_shortcuts_by_category(category)
            for shortcut in shortcuts:
                item = QTreeWidgetItem([
                    shortcut.name,
                    shortcut.current_key,
                    shortcut.description
                ])
                table_widget.addTopLevelItem(item)

            self.shortcuts_layout.addWidget(table_widget)

        self.shortcuts_layout.addStretch()

    def _filter_shortcuts(self, text: str):
        """Filter shortcuts by search text."""
        search_text = text.lower()

        # Rebuild display with filtered results
        self._display_shortcuts()

        # Hide items that don't match
        for i in range(self.shortcuts_layout.count()):
            widget = self.shortcuts_layout.itemAt(i).widget()
            if isinstance(widget, QTreeWidget):
                for j in range(widget.topLevelItemCount()):
                    item = widget.topLevelItem(j)
                    visible = (
                        search_text in item.text(0).lower() or
                        search_text in item.text(1).lower() or
                        search_text in item.text(2).lower()
                    )
                    item.setHidden(not visible)


# Global instance
_shortcut_manager_instance: Optional[KeyboardShortcutManager] = None


def get_shortcut_manager() -> KeyboardShortcutManager:
    """Get the global shortcut manager instance."""
    global _shortcut_manager_instance
    if _shortcut_manager_instance is None:
        _shortcut_manager_instance = KeyboardShortcutManager()
    return _shortcut_manager_instance


def show_shortcut_editor(parent=None) -> Optional[KeyboardShortcutManager]:
    """
    Show the shortcut editor dialog.

    Args:
        parent: Parent widget

    Returns:
        The shortcut manager instance
    """
    manager = get_shortcut_manager()
    dialog = ShortcutEditorDialog(manager, parent)
    result = dialog.exec()
    return manager if result == QDialog.Accepted else None


def show_shortcut_help(parent=None):
    """
    Show the shortcut help dialog.

    Args:
        parent: Parent widget
    """
    manager = get_shortcut_manager()
    dialog = ShortcutHelpDialog(manager, parent)
    dialog.exec()


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    manager = get_shortcut_manager()

    # Show help dialog
    dialog = ShortcutHelpDialog(manager)
    dialog.show()
    sys.exit(app.exec())
