"""
AI & LLM Tab - Chat interface, training control, and AI Intelligence Dashboard.

Tab 3 of 6 in the PREDICT Desktop GUI.
"""

import json
import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QTextEdit, QTabWidget, QGroupBox, QFormLayout,
    QTimeEdit, QCheckBox, QProgressBar, QTableWidget, QTableWidgetItem,
    QSplitter, QHeaderView, QScrollArea, QGridLayout, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, QTime
from PySide6.QtGui import QColor

from predict.desktop.theme import PredictTheme, get_table_stylesheet
from predict.desktop.workers import APIWorker, PollingWorker
from predict.desktop.api_client import PredictAPIClient
from predict.core.config import get_config

logger = logging.getLogger(__name__)

# The 9 AI model types used in the v3 intelligence engine
AI_MODEL_NAMES = [
    "health_lstm", "anomaly_autoencoder", "rul_predictor",
    "dtc_classifier", "fuel_efficiency", "driving_pattern",
    "component_wear", "sensor_correlation", "failure_predictor",
]


class AILLMTab(QWidget):
    """Tab for AI chat, LLM training control, and AI Intelligence Dashboard."""

    def __init__(self, api_client: PredictAPIClient, parent=None):
        super().__init__(parent)
        self._api = api_client
        self._status_worker = None
        self._dashboard_worker = None
        self._dashboard_data = {}  # cached ai-dashboard response

        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI layout."""
        layout = QVBoxLayout(self)

        # Sub-tabs
        self._tabs = QTabWidget()

        # Chat tab
        self._chat_tab = self._create_chat_tab()
        self._tabs.addTab(self._chat_tab, "LLM Chat")

        # Training tab
        self._training_tab = self._create_training_tab()
        self._tabs.addTab(self._training_tab, "AI Training")

        # AI Intelligence Dashboard tab (NEW - Task 24)
        self._intelligence_tab = self._create_intelligence_tab()
        self._tabs.addTab(self._intelligence_tab, "AI Intelligence")

        layout.addWidget(self._tabs)
        self.setLayout(layout)

    # =========================================================================
    # Chat Tab
    # =========================================================================

    def _create_chat_tab(self) -> QWidget:
        """Create the chat sub-tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        # Status bar
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Model:"))
        self._model_label = QLabel("Qwen 2.5-7B")
        self._model_label.setStyleSheet(f"font-weight: bold; color: {PredictTheme.PRIMARY}")
        status_layout.addWidget(self._model_label)

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(f"color: {PredictTheme.SUCCESS}; font-size: 14px")
        status_layout.addWidget(self._status_dot)

        self._status_text = QLabel("Ready")
        status_layout.addWidget(self._status_text)
        status_layout.addStretch()

        layout.addLayout(status_layout)

        # Chat display
        self._chat_display = QTextEdit()
        self._chat_display.setReadOnly(True)
        self._chat_display.setStyleSheet(
            f"background-color: {PredictTheme.BG_SECONDARY}; "
            f"color: {PredictTheme.TEXT_PRIMARY};"
        )
        layout.addWidget(self._chat_display)

        # Input area
        input_layout = QHBoxLayout()
        self._chat_input = QLineEdit()
        self._chat_input.setPlaceholderText("Type your message...")
        self._chat_input.returnPressed.connect(self._on_send_message)

        self._send_btn = QPushButton("Send")
        self._send_btn.setStyleSheet(
            f"background-color: {PredictTheme.PRIMARY}; color: white;"
        )
        self._send_btn.clicked.connect(self._on_send_message)

        input_layout.addWidget(self._chat_input)
        input_layout.addWidget(self._send_btn)
        layout.addLayout(input_layout)

        return tab

    # =========================================================================
    # Training Tab
    # =========================================================================

    def _create_training_tab(self) -> QWidget:
        """Create the training control sub-tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)

        # Schedule group
        schedule_group = QGroupBox("Training Schedule")
        schedule_layout = QFormLayout(schedule_group)

        self._start_time = QTimeEdit()
        self._start_time.setDisplayFormat("HH:mm")
        self._end_time = QTimeEdit()
        self._end_time.setDisplayFormat("HH:mm")
        self._auto_train = QCheckBox("Auto-train enabled")
        self._save_schedule_btn = QPushButton("Save Schedule")
        self._save_schedule_btn.clicked.connect(self._on_save_schedule)

        schedule_layout.addRow("Start Time:", self._start_time)
        schedule_layout.addRow("End Time:", self._end_time)
        schedule_layout.addRow(self._auto_train)
        schedule_layout.addRow(self._save_schedule_btn)

        layout.addWidget(schedule_group)

        # Load existing schedule
        self._load_schedule()

        # Status group
        status_group = QGroupBox("Training Status")
        status_layout = QVBoxLayout(status_group)

        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("State:"))
        self._training_state = QLabel("Idle")
        self._training_state.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {PredictTheme.SUCCESS}"
        )
        status_row.addWidget(self._training_state)
        status_row.addStretch()
        status_layout.addLayout(status_row)

        self._training_progress = QProgressBar()
        self._training_progress.setRange(0, 100)
        self._training_progress.setValue(0)
        status_layout.addWidget(self._training_progress)

        # Metrics grid
        metrics_layout = QHBoxLayout()
        self._metric_loss = QLabel("Loss: --")
        self._metric_acc = QLabel("Accuracy: --")
        self._metric_epoch = QLabel("Epoch: --")
        self._metric_eta = QLabel("ETA: --")

        metrics_layout.addWidget(self._metric_loss)
        metrics_layout.addWidget(self._metric_acc)
        metrics_layout.addWidget(self._metric_epoch)
        metrics_layout.addWidget(self._metric_eta)
        status_layout.addLayout(metrics_layout)

        layout.addWidget(status_group)

        # Controls
        controls_layout = QHBoxLayout()
        self._start_train_btn = QPushButton("Start Training Now")
        self._stop_train_btn = QPushButton("Stop Training")
        self._start_train_btn.clicked.connect(self._on_start_training)
        self._stop_train_btn.clicked.connect(self._on_stop_training)

        controls_layout.addWidget(self._start_train_btn)
        controls_layout.addWidget(self._stop_train_btn)
        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        # History table
        history_group = QGroupBox("Training History")
        history_layout = QVBoxLayout(history_group)

        self._history_table = QTableWidget()
        self._history_table.setColumnCount(4)
        self._history_table.setHorizontalHeaderLabels(
            ["Date", "Duration", "Accuracy", "Loss"]
        )
        history_layout.addWidget(self._history_table)

        layout.addWidget(history_group)
        layout.addStretch()

        return tab

    # =========================================================================
    # AI Intelligence Dashboard Tab (Task 24)
    # =========================================================================

    def _create_intelligence_tab(self) -> QWidget:
        """Create the AI Intelligence Dashboard sub-tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        # Header row with refresh + train-all buttons
        header_layout = QHBoxLayout()
        header_label = QLabel("Fleet AI Intelligence Overview")
        header_label.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {PredictTheme.TEXT_PRIMARY};"
        )
        header_layout.addWidget(header_label)
        header_layout.addStretch()

        self._dashboard_refresh_btn = QPushButton("Refresh")
        self._dashboard_refresh_btn.clicked.connect(self._load_ai_dashboard)
        header_layout.addWidget(self._dashboard_refresh_btn)

        self._train_all_btn = QPushButton("Train All Eligible")
        self._train_all_btn.setStyleSheet(
            f"background-color: {PredictTheme.PRIMARY}; color: white;"
        )
        self._train_all_btn.clicked.connect(self._on_train_all_eligible)
        header_layout.addWidget(self._train_all_btn)

        layout.addLayout(header_layout)

        # Fleet summary cards
        summary_layout = QHBoxLayout()
        self._summary_total = self._make_summary_card("Total Vehicles", "0")
        self._summary_phase1 = self._make_summary_card("Cold Start", "0")
        self._summary_phase2 = self._make_summary_card("Baseline", "0")
        self._summary_phase3 = self._make_summary_card("ML Active", "0")
        self._summary_eligible = self._make_summary_card("Train-Eligible", "0")

        summary_layout.addWidget(self._summary_total)
        summary_layout.addWidget(self._summary_phase1)
        summary_layout.addWidget(self._summary_phase2)
        summary_layout.addWidget(self._summary_phase3)
        summary_layout.addWidget(self._summary_eligible)
        layout.addLayout(summary_layout)

        # Scroll area for tables
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(16)

        # --- Vehicle AI Overview Table ---
        overview_group = QGroupBox("Vehicle AI Status")
        overview_layout = QVBoxLayout(overview_group)

        self._overview_table = QTableWidget()
        self._overview_table.setColumnCount(7)
        self._overview_table.setHorizontalHeaderLabels([
            "Vehicle", "Phase", "Data Points", "Active Models",
            "Intelligence Level", "Last Trained", "Actions",
        ])
        self._overview_table.setStyleSheet(get_table_stylesheet())
        self._overview_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._overview_table.horizontalHeader().setStretchLastSection(True)
        self._overview_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        overview_layout.addWidget(self._overview_table)
        scroll_layout.addWidget(overview_group)

        # --- Model Coverage Matrix ---
        matrix_group = QGroupBox("Model Coverage Matrix")
        matrix_layout = QVBoxLayout(matrix_group)

        legend_layout = QHBoxLayout()
        for label, color in [
            ("Trained", PredictTheme.SUCCESS),
            ("Training", PredictTheme.WARNING),
            ("Failed", PredictTheme.DANGER),
            ("Not Started", PredictTheme.TEXT_MUTED),
        ]:
            dot = QLabel(f"  {label}")
            dot.setStyleSheet(f"color: {color}; font-weight: bold;")
            legend_layout.addWidget(dot)
        legend_layout.addStretch()
        matrix_layout.addLayout(legend_layout)

        self._matrix_table = QTableWidget()
        self._matrix_table.setColumnCount(len(AI_MODEL_NAMES))
        # Shorter column headers
        short_names = [n.replace("_", "\n") for n in AI_MODEL_NAMES]
        self._matrix_table.setHorizontalHeaderLabels(short_names)
        self._matrix_table.setStyleSheet(get_table_stylesheet())
        self._matrix_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        matrix_layout.addWidget(self._matrix_table)
        scroll_layout.addWidget(matrix_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        return tab

    def _make_summary_card(self, title: str, value: str) -> QGroupBox:
        """Create a small summary metric card."""
        card = QGroupBox(title)
        card.setStyleSheet(f"""
            QGroupBox {{
                font-size: 11px; font-weight: bold;
                color: {PredictTheme.TEXT_SECONDARY};
                border: 1px solid {PredictTheme.BORDER};
                border-radius: 6px; padding: 8px;
                background-color: {PredictTheme.CARD_BG};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; left: 8px;
                padding: 0 4px;
                background-color: {PredictTheme.CARD_BG};
            }}
        """)
        layout = QVBoxLayout(card)
        lbl = QLabel(value)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {PredictTheme.PRIMARY};")
        lbl.setObjectName("value_label")
        layout.addWidget(lbl)
        return card

    @staticmethod
    def _card_value_label(card: QGroupBox) -> QLabel:
        """Get the value QLabel from a summary card."""
        return card.findChild(QLabel, "value_label")

    # -------------------------------------------------------------------------
    # Intelligence dashboard data loading
    # -------------------------------------------------------------------------

    def _load_ai_dashboard(self):
        """Fetch the fleet AI dashboard from the server."""
        self._dashboard_refresh_btn.setEnabled(False)
        worker = APIWorker(self._api.get_ai_dashboard)
        worker.finished.connect(self._on_ai_dashboard_received)
        worker.error.connect(self._on_ai_dashboard_error)
        worker.start()

    def _on_ai_dashboard_received(self, data: dict):
        """Populate the overview table and coverage matrix from server data."""
        self._dashboard_refresh_btn.setEnabled(True)
        self._dashboard_data = data

        vehicles = data.get("vehicles", [])

        # --- Summary cards ---
        total = len(vehicles)
        phase_counts = {"cold_start": 0, "baseline": 0, "ml_active": 0}
        eligible = 0
        for v in vehicles:
            phase = v.get("phase", "cold_start")
            if phase in phase_counts:
                phase_counts[phase] += 1
            else:
                phase_counts["cold_start"] += 1
            data_pts = v.get("data_points", 0)
            if data_pts >= 500:
                eligible += 1

        self._card_value_label(self._summary_total).setText(str(total))
        self._card_value_label(self._summary_phase1).setText(str(phase_counts["cold_start"]))
        self._card_value_label(self._summary_phase2).setText(str(phase_counts["baseline"]))
        self._card_value_label(self._summary_phase3).setText(str(phase_counts["ml_active"]))
        self._card_value_label(self._summary_eligible).setText(str(eligible))

        # --- Overview table ---
        self._overview_table.setRowCount(len(vehicles))
        for i, v in enumerate(vehicles):
            vid = v.get("vehicle_id", 0)
            name = v.get("vehicle_name", f"Vehicle {vid}")
            phase = v.get("phase", "cold_start")
            data_pts = v.get("data_points", 0)
            models = v.get("active_models", [])
            level = v.get("intelligence_level", "basic")
            last_trained = v.get("last_trained", "Never")

            self._overview_table.setItem(i, 0, QTableWidgetItem(name))

            phase_item = QTableWidgetItem(phase.replace("_", " ").title())
            phase_color = {
                "cold_start": PredictTheme.TEXT_MUTED,
                "baseline": PredictTheme.WARNING,
                "ml_active": PredictTheme.SUCCESS,
            }.get(phase, PredictTheme.TEXT_SECONDARY)
            phase_item.setForeground(QColor(phase_color))
            self._overview_table.setItem(i, 1, phase_item)

            self._overview_table.setItem(i, 2, QTableWidgetItem(str(data_pts)))
            self._overview_table.setItem(i, 3, QTableWidgetItem(
                str(len(models)) if isinstance(models, list) else str(models)
            ))

            level_item = QTableWidgetItem(level.replace("_", " ").title())
            level_color = {
                "basic": PredictTheme.TEXT_MUTED,
                "intermediate": PredictTheme.INFO,
                "advanced": PredictTheme.SUCCESS,
                "expert": PredictTheme.ACCENT_CYAN,
            }.get(level, PredictTheme.TEXT_SECONDARY)
            level_item.setForeground(QColor(level_color))
            self._overview_table.setItem(i, 4, level_item)

            self._overview_table.setItem(i, 5, QTableWidgetItem(str(last_trained)))

            # Train button (placed as a widget in column 6)
            train_btn = QPushButton("Train")
            train_btn.setStyleSheet(
                f"background-color: {PredictTheme.PRIMARY}; color: white; "
                f"padding: 4px 10px; border-radius: 4px;"
            )
            train_btn.setEnabled(data_pts >= 500)
            train_btn.clicked.connect(lambda checked, veh_id=vid: self._on_train_vehicle(veh_id))
            self._overview_table.setCellWidget(i, 6, train_btn)

        # --- Model Coverage Matrix ---
        self._matrix_table.setRowCount(len(vehicles))
        for i, v in enumerate(vehicles):
            vid = v.get("vehicle_id", 0)
            name = v.get("vehicle_name", f"Vehicle {vid}")

            # Set row header
            self._matrix_table.setVerticalHeaderItem(i, QTableWidgetItem(name))

            model_statuses = v.get("model_statuses", {})
            active_models = v.get("active_models", [])

            for j, model_name in enumerate(AI_MODEL_NAMES):
                status = model_statuses.get(model_name, "not_started")
                # If model_statuses not in response, infer from active_models list
                if not model_statuses and isinstance(active_models, list):
                    status = "trained" if model_name in active_models else "not_started"

                cell = QTableWidgetItem(status.replace("_", " ").title())
                cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                bg_color, fg_color = {
                    "trained": (PredictTheme.SUCCESS, "#FFFFFF"),
                    "training": (PredictTheme.WARNING, "#000000"),
                    "failed": (PredictTheme.DANGER, "#FFFFFF"),
                    "not_started": (PredictTheme.BG_SECONDARY, PredictTheme.TEXT_MUTED),
                }.get(status, (PredictTheme.BG_SECONDARY, PredictTheme.TEXT_MUTED))

                cell.setBackground(QColor(bg_color))
                cell.setForeground(QColor(fg_color))
                self._matrix_table.setItem(i, j, cell)

    def _on_ai_dashboard_error(self, error_msg: str):
        """Handle AI dashboard load error."""
        self._dashboard_refresh_btn.setEnabled(True)
        logger.error(f"AI dashboard error: {error_msg}")

    # -------------------------------------------------------------------------
    # Training triggers
    # -------------------------------------------------------------------------

    def _on_train_vehicle(self, vehicle_id: int):
        """Train the default model for a single vehicle."""
        worker = APIWorker(self._api.train_vehicle_model, vehicle_id, "health_lstm")
        worker.finished.connect(self._on_train_result)
        worker.error.connect(self._on_train_error)
        worker.start()

    def _on_train_all_eligible(self):
        """Train all vehicles that have enough data points."""
        vehicles = self._dashboard_data.get("vehicles", [])
        eligible = [v for v in vehicles if v.get("data_points", 0) >= 500]
        if not eligible:
            QMessageBox.information(
                self, "No Eligible Vehicles",
                "No vehicles have enough data points (500+) for training."
            )
            return

        reply = QMessageBox.question(
            self, "Train All Eligible",
            f"Start training for {len(eligible)} vehicle(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._train_all_btn.setEnabled(False)
        self._train_all_btn.setText(f"Training 0/{len(eligible)}...")
        self._train_all_remaining = len(eligible)
        self._train_all_total = len(eligible)

        for v in eligible:
            vid = v.get("vehicle_id", 0)
            worker = APIWorker(self._api.train_vehicle_model, vid, "health_lstm")
            worker.finished.connect(self._on_train_all_one_done)
            worker.error.connect(self._on_train_all_one_done_err)
            worker.start()

    def _on_train_all_one_done(self, result: dict):
        """One vehicle training triggered."""
        self._train_all_remaining -= 1
        done = self._train_all_total - self._train_all_remaining
        self._train_all_btn.setText(f"Training {done}/{self._train_all_total}...")
        if self._train_all_remaining <= 0:
            self._train_all_btn.setEnabled(True)
            self._train_all_btn.setText("Train All Eligible")
            self._load_ai_dashboard()

    def _on_train_all_one_done_err(self, error_msg: str):
        """One vehicle training trigger failed."""
        logger.error(f"Train-all single error: {error_msg}")
        self._on_train_all_one_done({})

    def _on_train_result(self, result: dict):
        """Handle single-vehicle train result."""
        logger.info(f"Training triggered: {result}")
        # Refresh the dashboard to show updated status
        self._load_ai_dashboard()

    def _on_train_error(self, error_msg: str):
        """Handle single-vehicle train error."""
        logger.error(f"Training error: {error_msg}")

    # =========================================================================
    # Existing methods (unchanged)
    # =========================================================================

    def _load_schedule(self):
        """Load training schedule from file."""
        try:
            config = get_config()
            schedule_path = Path(config.DATA_DIR) / "ai_schedule.json"
            if schedule_path.exists():
                with open(schedule_path, "r") as f:
                    schedule = json.load(f)

                self._start_time.setTime(
                    QTime(schedule.get("start_hour", 3), schedule.get("start_minute", 0))
                )
                self._end_time.setTime(
                    QTime(schedule.get("end_hour", 5), schedule.get("end_minute", 0))
                )
                self._auto_train.setChecked(schedule.get("enabled", False))
        except Exception as e:
            logger.debug(f"Error loading schedule: {e}")

    def _start_monitors(self):
        """Start monitoring."""
        # AI status polling
        self._status_worker = PollingWorker(self._api.get_ai_status, 5000)
        self._status_worker.data_received.connect(self._on_ai_status)
        self._status_worker.start()

        # AI dashboard polling (every 60 seconds)
        self._dashboard_worker = PollingWorker(self._api.get_ai_dashboard, 60000)
        self._dashboard_worker.data_received.connect(self._on_ai_dashboard_received)
        self._dashboard_worker.start()

    def _on_ai_status(self, data: dict):
        """Handle AI status update."""
        available = data.get("available", False)
        if available:
            self._status_dot.setStyleSheet(f"color: {PredictTheme.SUCCESS}; font-size: 14px")
            self._status_text.setText("Ready")
        else:
            self._status_dot.setStyleSheet(f"color: {PredictTheme.DANGER}; font-size: 14px")
            self._status_text.setText("Unavailable")

    def _on_send_message(self):
        """Handle send message."""
        message = self._chat_input.text().strip()
        if not message:
            return

        # Display user message
        user_html = (
            f'<div style="text-align:right;margin:8px 0;">'
            f'<span style="background:{PredictTheme.PRIMARY};color:white;'
            f'padding:8px 12px;border-radius:12px;display:inline-block;'
            f'max-width:70%;">{message}</span></div>'
        )
        self._chat_display.append(user_html)
        self._chat_input.clear()
        self._chat_input.setEnabled(False)
        self._send_btn.setEnabled(False)

        # Show thinking
        self._chat_display.append(
            '<div style="text-align:left;margin:8px 0;">'
            '<span style="color:#888;padding:8px 12px;">Thinking...</span></div>'
        )

        # Send to API
        worker = APIWorker(self._api.chat_with_ai, message)
        worker.finished.connect(self._on_chat_response)
        worker.error.connect(self._on_chat_error)
        worker.start()

    def _on_chat_response(self, result: dict):
        """Handle chat response."""
        # Remove "Thinking..." by reloading
        html = self._chat_display.toHtml()
        html = html.replace(
            '<div style="text-align:left;margin:8px 0;">'
            '<span style="color:#888;padding:8px 12px;">Thinking...</span></div>',
            ""
        )
        self._chat_display.setHtml(html)

        response = result.get("response", "No response")
        ai_html = (
            f'<div style="text-align:left;margin:8px 0;">'
            f'<span style="background:{PredictTheme.CARD_BG};color:{PredictTheme.TEXT_PRIMARY};'
            f'padding:8px 12px;border-radius:12px;display:inline-block;'
            f'max-width:70%;">{response}</span></div>'
        )
        self._chat_display.append(ai_html)

        self._chat_input.setEnabled(True)
        self._send_btn.setEnabled(True)
        self._chat_input.setFocus()

    def _on_chat_error(self, error_msg: str):
        """Handle chat error."""
        self._chat_display.append(
            f'<div style="text-align:left;margin:8px 0;">'
            f'<span style="color:{PredictTheme.DANGER};padding:8px 12px;">'
            f'Error: {error_msg}</span></div>'
        )
        self._chat_input.setEnabled(True)
        self._send_btn.setEnabled(True)

    def _on_save_schedule(self):
        """Save training schedule."""
        try:
            config = get_config()
            schedule_path = Path(config.DATA_DIR) / "ai_schedule.json"

            schedule = {
                "start_hour": self._start_time.time().hour(),
                "start_minute": self._start_time.time().minute(),
                "end_hour": self._end_time.time().hour(),
                "end_minute": self._end_time.time().minute(),
                "enabled": self._auto_train.isChecked(),
            }

            with open(schedule_path, "w") as f:
                json.dump(schedule, f, indent=2)

            self._training_state.setText("Schedule saved")
        except Exception as e:
            logger.error(f"Error saving schedule: {e}")
            self._training_state.setText(f"Error: {e}")

    def _on_start_training(self):
        """Start training."""
        self._training_state.setText("Training...")
        self._training_state.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {PredictTheme.WARNING}"
        )

    def _on_stop_training(self):
        """Stop training."""
        self._training_state.setText("Idle")
        self._training_state.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {PredictTheme.SUCCESS}"
        )
        self._training_progress.setValue(0)

    def cleanup(self):
        """Stop all background workers."""
        if self._status_worker:
            self._status_worker.stop()
            self._status_worker.wait(2000)
        if self._dashboard_worker:
            self._dashboard_worker.stop()
            self._dashboard_worker.wait(2000)

    def closeEvent(self, event):
        """Clean up on close."""
        self.cleanup()
        event.accept()
