"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Global Search

Global Search Module
===================

Provides application-wide search functionality across:
- Vehicle profiles
- DTC codes
- AI predictions
- Service records
- Alerts/Notifications
- Historical data

Features:
- Real-time search with debouncing
- Category filtering
- Result highlighting
- Quick navigation to results
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import re

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QLabel, QComboBox, QCheckBox,
    QGroupBox, QSplitter, QFrame, QScrollArea, QStackedWidget,
    QProgressBar, QMenu, QToolButton, QSizePolicy, QApplication
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QMutex
from PySide6.QtGui import QIcon, QFont, QColor, QPalette, QCursor, QAction

from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Represents a single search result."""
    category: str
    title: str
    description: str
    details: Dict[str, Any]
    relevance_score: float
    timestamp: Optional[str] = None
    icon: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'category': self.category,
            'title': self.title,
            'description': self.description,
            'details': self.details,
            'relevance_score': self.relevance_score,
            'timestamp': self.timestamp,
            'icon': self.icon
        }


class SearchWorker(QThread):
    """
    Background worker for performing searches.
    Runs searches in a separate thread to keep UI responsive.
    """

    resultsReady = Signal(list)
    searchFinished = Signal()

    def __init__(self, query: str, categories: List[str], search_context: Dict[str, Any]):
        super().__init__()
        self.query = query.lower().strip()
        self.categories = categories
        self.search_context = search_context
        self._mutex = QMutex()

    def run(self):
        """Execute search in background thread."""
        try:
            results = []

            # Search vehicles
            if 'vehicles' in self.categories:
                results.extend(self._search_vehicles())

            # Search DTC codes
            if 'dtcs' in self.categories:
                results.extend(self._search_dtcs())

            # Search predictions
            if 'predictions' in self.categories:
                results.extend(self._search_predictions())

            # Search service records
            if 'service_records' in self.categories:
                results.extend(self._search_service_records())

            # Search alerts
            if 'alerts' in self.categories:
                results.extend(self._search_alerts())

            # Sort by relevance
            results.sort(key=lambda x: x.relevance_score, reverse=True)

            self.resultsReady.emit(results)
            self.searchFinished.emit()

        except Exception as e:
            logger.error(f"Search worker error: {e}")
            self.resultsReady.emit([])
            self.searchFinished.emit()

    def _search_vehicles(self) -> List[SearchResult]:
        """Search vehicle profiles."""
        results = []

        try:
            from db_utils import DatabaseManager
            db = DatabaseManager(CONFIG.PROFILES_DB_PATH)
            profiles = db.get_all_profiles()

            for profile in profiles:
                score = 0.0
                matches = []

                # Search in name
                if self.query in profile.get('name', '').lower():
                    score += 1.0
                    matches.append(f"Name: {profile.get('name')}")

                # Search in VIN
                if self.query in profile.get('vin', '').lower():
                    score += 0.9
                    matches.append(f"VIN: {profile.get('vin')}")

                # Search in make/model
                if self.query in profile.get('make', '').lower():
                    score += 0.8
                    matches.append(f"Make: {profile.get('make')}")

                if self.query in profile.get('model', '').lower():
                    score += 0.8
                    matches.append(f"Model: {profile.get('model')}")

                # Search in year
                year_str = str(profile.get('year', ''))
                if self.query in year_str:
                    score += 0.7
                    matches.append(f"Year: {year_str}")

                if score > 0:
                    results.append(SearchResult(
                        category='Vehicles',
                        title=profile.get('name', 'Unknown'),
                        description=f"{profile.get('year', '')} {profile.get('make', '')} {profile.get('model', '')}",
                        details={
                            'profile_id': profile.get('profile_id'),
                            'vin': profile.get('vin'),
                            'matches': matches
                        },
                        relevance_score=score,
                        timestamp=profile.get('created_at'),
                        icon='🚗'
                    ))

        except Exception as e:
            logger.error(f"Error searching vehicles: {e}")

        return results

    def _search_dtcs(self) -> List[SearchResult]:
        """Search DTC codes."""
        results = []

        try:
            from dtc_lookup import DTCLookup
            dtc_lookup = DTCLookup()

            # Search in DTC code
            if self.query in dtc_lookup.codes:
                code_info = dtc_lookup.codes[self.query]
                results.append(SearchResult(
                    category='DTC Codes',
                    title=self.query.upper(),
                    description=code_info.get('description', 'Unknown'),
                    details={
                        'code': self.query.upper(),
                        'severity': code_info.get('severity', 'Unknown'),
                        'symptoms': code_info.get('symptoms', []),
                        'causes': code_info.get('causes', [])
                    },
                    relevance_score=1.0,
                    icon='⚠️'
                ))

            # Search in descriptions
            for code, info in dtc_lookup.codes.items():
                if self.query in info.get('description', '').lower():
                    results.append(SearchResult(
                        category='DTC Codes',
                        title=code,
                        description=info.get('description', 'Unknown'),
                        details={
                            'code': code,
                            'severity': info.get('severity', 'Unknown'),
                            'symptoms': info.get('symptoms', []),
                            'causes': info.get('causes', [])
                        },
                        relevance_score=0.7,
                        icon='⚠️'
                    ))

        except Exception as e:
            logger.error(f"Error searching DTCs: {e}")

        return results

    def _search_predictions(self) -> List[SearchResult]:
        """Search AI predictions."""
        results = []

        try:
            from prediction_accuracy_tracker import get_accuracy_tracker

            tracker = get_accuracy_tracker()
            # This would need to be implemented in the tracker
            # For now, we'll search in the enhanced engine history

            if 'enhanced_engine' in self.search_context:
                engine = self.search_context['enhanced_engine']
                for vehicle_id, history in engine.prediction_history.items():
                    for pred in history[-50:]:  # Last 50 predictions
                        score = 0.0
                        matches = []

                        # Search in vehicle ID
                        if self.query in vehicle_id.lower():
                            score += 0.8
                            matches.append(f"Vehicle: {vehicle_id}")

                        # Search in failure types
                        for failure in pred.failure_detections:
                            if self.query in failure.get('name', '').lower():
                                score += 0.9
                                matches.append(f"Failure: {failure.get('name')}")

                        if score > 0:
                            results.append(SearchResult(
                                category='Predictions',
                                title=f"Prediction for {vehicle_id}",
                                description=f"Health: {pred.overall_health_score}%, Issues: {len(pred.failure_detections)}",
                                details={
                                    'vehicle_id': vehicle_id,
                                    'prediction_id': pred.prediction_id,
                                    'timestamp': pred.timestamp,
                                    'health_score': pred.overall_health_score,
                                    'failures': pred.failure_detections,
                                    'matches': matches
                                },
                                relevance_score=score,
                                timestamp=pred.timestamp,
                                icon='🔮'
                            ))

        except Exception as e:
            logger.error(f"Error searching predictions: {e}")

        return results

    def _search_service_records(self) -> List[SearchResult]:
        """Search service records."""
        results = []

        try:
            from feedback_collector import get_feedback_collector

            collector = get_feedback_collector()
            records = collector.get_all_service_records()

            for record in records:
                score = 0.0
                matches = []

                # Search in description
                if self.query in record.get('description', '').lower():
                    score += 1.0
                    matches.append(f"Description: {record.get('description')}")

                # Search in component
                if self.query in record.get('component', '').lower():
                    score += 0.9
                    matches.append(f"Component: {record.get('component')}")

                # Search in failure type
                if self.query in record.get('failure_type', '').lower():
                    score += 0.8
                    matches.append(f"Failure: {record.get('failure_type')}")

                # Search in shop name
                if self.query in record.get('shop_name', '').lower():
                    score += 0.7
                    matches.append(f"Shop: {record.get('shop_name')}")

                if score > 0:
                    results.append(SearchResult(
                        category='Service Records',
                        title=f"{record.get('service_type', 'Service')} - {record.get('component', 'Unknown')}",
                        description=record.get('description', ''),
                        details={
                            'record_id': record.get('record_id'),
                            'vehicle_id': record.get('vehicle_id'),
                            'service_date': record.get('service_date'),
                            'mileage': record.get('mileage'),
                            'cost': record.get('cost'),
                            'matches': matches
                        },
                        relevance_score=score,
                        timestamp=record.get('service_date'),
                        icon='🔧'
                    ))

        except Exception as e:
            logger.error(f"Error searching service records: {e}")

        return results

    def _search_alerts(self) -> List[SearchResult]:
        """Search alerts/notifications."""
        results = []

        try:
            from alert_notifications import get_notification_manager

            manager = get_notification_manager()
            # This would need to be implemented in the notification manager
            # For now, we'll search in custom alerts

            if 'custom_alerts' in self.search_context:
                alerts = self.search_context['custom_alerts']
                for alert in alerts:
                    score = 0.0
                    matches = []

                    # Search in title
                    if self.query in alert.get('title', '').lower():
                        score += 1.0
                        matches.append(f"Title: {alert.get('title')}")

                    # Search in message
                    if self.query in alert.get('message', '').lower():
                        score += 0.9
                        matches.append(f"Message: {alert.get('message')}")

                    if score > 0:
                        results.append(SearchResult(
                            category='Alerts',
                            title=alert.get('title', 'Alert'),
                            description=alert.get('message', ''),
                            details={
                                'alert_id': alert.get('alert_id'),
                                'severity': alert.get('severity'),
                                'timestamp': alert.get('timestamp'),
                                'matches': matches
                            },
                            relevance_score=score,
                            timestamp=alert.get('timestamp'),
                            icon='🔔'
                        ))

        except Exception as e:
            logger.error(f"Error searching alerts: {e}")

        return results


class GlobalSearchWidget(QWidget):
    """
    Main global search widget with search input, filters, and results display.
    """

    # Signal emitted when a result is selected
    resultSelected = Signal(str, dict)  # category, details

    def __init__(self, parent=None, search_context: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.search_context = search_context or {}
        self.current_results = []
        self.search_worker = None
        self.debounce_timer = QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self._perform_search)

        self._init_ui()

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

    def _init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Search bar
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(10, 10, 10, 10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search vehicles, DTCs, predictions, service records...")
        self.search_input.setMinimumHeight(40)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        search_layout.addWidget(self.search_input)

        self.search_button = QPushButton("Search")
        self.search_button.setMinimumHeight(40)
        self.search_button.setStyleSheet(self._get_button_style('primary'))
        self.search_button.clicked.connect(self._perform_search)
        search_layout.addWidget(self.search_button)

        layout.addLayout(search_layout)

        # Filters
        filter_frame = QFrame()
        filter_frame.setStyleSheet("QFrame { background-color: #f5f5f5; }")
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(10, 5, 10, 5)

        filter_label = QLabel("Filter:")
        filter_layout.addWidget(filter_label)

        self.vehicle_filter = QCheckBox("Vehicles")
        self.vehicle_filter.setChecked(True)
        self.vehicle_filter.stateChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.vehicle_filter)

        self.dtc_filter = QCheckBox("DTC Codes")
        self.dtc_filter.setChecked(True)
        self.dtc_filter.stateChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.dtc_filter)

        self.prediction_filter = QCheckBox("Predictions")
        self.prediction_filter.setChecked(True)
        self.prediction_filter.stateChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.prediction_filter)

        self.service_filter = QCheckBox("Service Records")
        self.service_filter.setChecked(True)
        self.service_filter.stateChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.service_filter)

        self.alert_filter = QCheckBox("Alerts")
        self.alert_filter.setChecked(True)
        self.alert_filter.stateChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.alert_filter)

        filter_layout.addStretch()

        layout.addWidget(filter_frame)

        # Results area
        self.results_splitter = QSplitter(Qt.Vertical)

        # Results list
        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self._on_result_double_clicked)
        self.results_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.results_list.customContextMenuRequested.connect(self._show_context_menu)
        self.results_splitter.addWidget(self.results_list)

        # Details panel
        self.details_panel = QWidget()
        details_layout = QVBoxLayout(self.details_panel)

        self.details_label = QLabel("Select a result to view details")
        self.details_label.setAlignment(Qt.AlignCenter)
        self.details_label.setStyleSheet("QLabel { color: #888; font-size: 14px; }")
        details_layout.addWidget(self.details_label)

        self.details_content = QStackedWidget()
        details_layout.addWidget(self.details_content)

        self.results_splitter.addWidget(self.details_panel)
        self.results_splitter.setSizes([400, 200])

        layout.addWidget(self.results_splitter)

        # Status bar
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("QLabel { color: #888; padding: 5px 10px; }")
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def _on_search_text_changed(self, text: str):
        """Handle search text change with debouncing."""
        # Debounce search (wait 300ms after user stops typing)
        self.debounce_timer.start(300)

    def _on_filter_changed(self):
        """Handle filter change."""
        if self.search_input.text().strip():
            self._perform_search()

    def _perform_search(self):
        """Perform the search."""
        query = self.search_input.text().strip()
        if not query:
            self._clear_results()
            return

        # Get selected categories
        categories = []
        if self.vehicle_filter.isChecked():
            categories.append('vehicles')
        if self.dtc_filter.isChecked():
            categories.append('dtcs')
        if self.prediction_filter.isChecked():
            categories.append('predictions')
        if self.service_filter.isChecked():
            categories.append('service_records')
        if self.alert_filter.isChecked():
            categories.append('alerts')

        if not categories:
            self.status_label.setText("No categories selected")
            return

        # Cancel any existing search
        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.terminate()
            self.search_worker.wait()

        # Start new search
        self.status_label.setText("Searching...")
        self.search_worker = SearchWorker(query, categories, self.search_context)
        self.search_worker.resultsReady.connect(self._on_search_results)
        self.search_worker.searchFinished.connect(self._on_search_finished)
        self.search_worker.start()

    def _on_search_results(self, results: List[SearchResult]):
        """Handle search results."""
        self.current_results = results
        self._display_results(results)

    def _on_search_finished(self):
        """Handle search completion."""
        count = len(self.current_results)
        if count == 0:
            self.status_label.setText("No results found")
        else:
            self.status_label.setText(f"Found {count} result(s)")

    def _display_results(self, results: List[SearchResult]):
        """Display search results in the list."""
        self.results_list.clear()

        for result in results:
            item = QListWidgetItem()
            item.setText(result.title)
            item.setData(Qt.UserRole, result.to_dict())

            # Set icon
            icon_text = result.icon or '📄'
            item.setText(f"{icon_text} {result.title}")

            # Add category badge
            category_badge = f"[{result.category}]"
            item.setToolTip(f"{category_badge}\n{result.description}")

            self.results_list.addItem(item)

    def _clear_results(self):
        """Clear all results."""
        self.results_list.clear()
        self.current_results = []
        self.details_label.setText("Select a result to view details")
        self.status_label.setText("Ready")

    def _on_result_double_clicked(self, item: QListWidgetItem):
        """Handle result double-click."""
        result_data = item.data(Qt.UserRole)
        self.resultSelected.emit(result_data['category'], result_data['details'])

    def _show_context_menu(self, position):
        """Show context menu for selected result."""
        item = self.results_list.itemAt(position)
        if not item:
            return

        result_data = item.data(Qt.UserRole)

        menu = QMenu()
        open_action = QAction("Open", self)
        open_action.triggered.connect(lambda: self.resultSelected.emit(result_data['category'], result_data['details']))
        menu.addAction(open_action)

        copy_action = QAction("Copy Details", self)
        copy_action.triggered.connect(lambda: self._copy_result_details(result_data))
        menu.addAction(copy_action)

        menu.exec_(self.results_list.mapToGlobal(position))

    def _copy_result_details(self, result_data: Dict[str, Any]):
        """Copy result details to clipboard."""
        clipboard = QApplication.clipboard()

        details_text = f"Category: {result_data['category']}\n"
        details_text += f"Title: {result_data['title']}\n"
        details_text += f"Description: {result_data['description']}\n"

        if 'matches' in result_data['details']:
            details_text += f"\nMatches:\n"
            for match in result_data['details']['matches']:
                details_text += f"  - {match}\n"

        clipboard.setText(details_text)

    def set_search_context(self, context: Dict[str, Any]):
        """Set the search context (e.g., enhanced engine reference)."""
        self.search_context = context

    def focus_search(self):
        """Focus the search input."""
        self.search_input.setFocus()
        self.search_input.selectAll()


class GlobalSearchDialog(QWidget):
    """
    Standalone global search dialog that can be opened with a keyboard shortcut.
    """

    def __init__(self, parent=None, search_context: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.setWindowTitle("Global Search")
        self.setMinimumSize(800, 600)
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)

        layout = QVBoxLayout()

        self.search_widget = GlobalSearchWidget(self, search_context)
        self.search_widget.resultSelected.connect(self._on_result_selected)

        layout.addWidget(self.search_widget)

        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.close_button = QPushButton("Close")
        self.close_button.setStyleSheet(self._get_button_style('secondary'))
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _on_result_selected(self, category: str, details: Dict[str, Any]):
        """Handle result selection."""
        # This would typically navigate to the relevant tab/section
        # For now, just log the selection
        logger.info(f"Selected result: {category} - {details}")
        self.close()

    def show_search(self, query: str = ""):
        """Show the search dialog with optional initial query."""
        self.search_widget.focus_search()
        if query:
            self.search_widget.search_input.setText(query)
            self.search_widget._perform_search()
        self.show()
        self.raise_()
        self.activateWindow()


def show_global_search(parent=None, query: str = "", search_context: Optional[Dict[str, Any]] = None):
    """
    Convenience function to show global search dialog.

    Args:
        parent: Parent widget
        query: Initial search query
        search_context: Optional search context (e.g., enhanced engine reference)
    """
    dialog = GlobalSearchDialog(parent, search_context)
    dialog.show_search(query)


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    dialog = GlobalSearchDialog()
    dialog.show()
    sys.exit(app.exec())
