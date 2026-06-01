"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Chat Tab

PREDICT Desktop AI - AI Chat Tab
Interactive chat interface with local LLM
Dark theme styling to match application
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QLabel, QScrollArea, QFrame, QComboBox, QSplitter
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont, QTextCursor
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# Dark theme colors
class ChatTheme:
    BG_PRIMARY = "#0D1117"
    BG_SECONDARY = "#161B22"
    BG_TERTIARY = "#21262D"
    TEXT_PRIMARY = "#F0F6FC"
    TEXT_SECONDARY = "#8B949E"
    ACCENT_RED = "#C40000"
    ACCENT_GREEN = "#3FB950"
    ACCENT_BLUE = "#58A6FF"
    BORDER = "#30363D"
    USER_MSG_BG = "#1F6FEB"
    AI_MSG_BG = "#21262D"
    SYSTEM_MSG = "#8B949E"
    ERROR_BG = "#F85149"


class ChatWorker(QThread):
    """Background worker for LLM chat to keep UI responsive."""
    response_ready = Signal(str)  # LLM response
    error = Signal(str)           # Error message

    def __init__(self, llm_assistant, message, context_type="general"):
        super().__init__()
        self.llm_assistant = llm_assistant
        self.message = message
        self.context_type = context_type

    def run(self):
        """Generate LLM response in background."""
        try:
            # Add context-specific prompt engineering
            if self.context_type == "dtc":
                prompt = f"As an automotive diagnostic expert: {self.message}"
            elif self.context_type == "prediction":
                prompt = f"As an AI prediction analyst: {self.message}"
            elif self.context_type == "customer":
                prompt = f"As a customer support specialist: {self.message}"
            else:
                prompt = self.message

            response = self.llm_assistant.chat(prompt, max_tokens=600, temperature=0.3)
            self.response_ready.emit(response)

        except Exception as e:
            logger.error(f"Chat error: {e}")
            self.error.emit(str(e))


class ModelSwitchWorker(QThread):
    """Background worker for switching LLM models."""
    finished = Signal(bool, str)  # success, model_name
    progress = Signal(int, str)   # progress, message

    def __init__(self, llm_assistant, model_name):
        super().__init__()
        self.llm_assistant = llm_assistant
        self.model_name = model_name

    def run(self):
        """Switch model in background."""
        try:
            def callback(progress, message):
                self.progress.emit(progress, message)

            success = self.llm_assistant.switch_model(self.model_name, callback)
            model_info = self.llm_assistant.get_current_model_info()
            self.finished.emit(success, model_info.get("name", self.model_name))

        except Exception as e:
            logger.error(f"Model switch error: {e}")
            self.finished.emit(False, str(e))


class ChatTab(QWidget):
    """AI Chat interface tab with dark theme."""

    def __init__(self, llm_assistant):
        super().__init__()
        self.llm_assistant = llm_assistant
        self.chat_history = []
        self.current_worker = None
        self.pending_message = None  # For lazy loading - stores message until model loads

        self.init_ui()

    def init_ui(self):
        """Initialize chat UI with dark theme."""
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header
        header = QLabel("AI Assistant Chat")
        header.setFont(QFont("Segoe UI", 18, QFont.Bold))
        header.setStyleSheet(f"color: {ChatTheme.TEXT_PRIMARY}; padding: 8px 0;")
        layout.addWidget(header)

        # Status indicator
        self.status_label = QLabel()
        self.update_status_label()
        layout.addWidget(self.status_label)

        # Context and Model selector row
        context_layout = QHBoxLayout()

        # Context selector
        context_label = QLabel("Context:")
        context_label.setStyleSheet(f"color: {ChatTheme.TEXT_SECONDARY}; font-weight: 600;")
        context_layout.addWidget(context_label)

        combo_style = f"""
            QComboBox {{
                background-color: {ChatTheme.BG_TERTIARY};
                color: {ChatTheme.TEXT_PRIMARY};
                border: 1px solid {ChatTheme.BORDER};
                border-radius: 6px;
                padding: 8px 12px;
                min-width: 160px;
                font-size: 13px;
            }}
            QComboBox:hover {{
                border-color: {ChatTheme.ACCENT_BLUE};
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 10px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {ChatTheme.TEXT_SECONDARY};
                margin-right: 10px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {ChatTheme.BG_TERTIARY};
                color: {ChatTheme.TEXT_PRIMARY};
                border: 1px solid {ChatTheme.BORDER};
                selection-background-color: {ChatTheme.ACCENT_RED};
            }}
        """

        self.context_combo = QComboBox()
        self.context_combo.addItems([
            "General Chat",
            "DTC Diagnosis",
            "Prediction Analysis",
            "Customer Support"
        ])
        self.context_combo.setStyleSheet(combo_style)
        context_layout.addWidget(self.context_combo)

        # Model selector
        context_layout.addSpacing(20)
        model_label = QLabel("Model:")
        model_label.setStyleSheet(f"color: {ChatTheme.TEXT_SECONDARY}; font-weight: 600;")
        context_layout.addWidget(model_label)

        self.model_combo = QComboBox()
        self.model_combo.setStyleSheet(combo_style)
        self._populate_model_selector()
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        context_layout.addWidget(self.model_combo)

        # Model switch worker reference
        self.model_switch_worker = None

        context_layout.addStretch()

        layout.addLayout(context_layout)

        # Chat display area
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        # Disable text selection to prevent blue highlighting
        self.chat_display.setTextInteractionFlags(Qt.NoTextInteraction)
        self.chat_display.viewport().setCursor(Qt.ArrowCursor)
        self.chat_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: {ChatTheme.BG_SECONDARY};
                color: {ChatTheme.TEXT_PRIMARY};
                border: 1px solid {ChatTheme.BORDER};
                border-radius: 8px;
                padding: 12px;
                font-size: 14px;
                font-family: 'Segoe UI', sans-serif;
                selection-background-color: transparent;
                selection-color: {ChatTheme.TEXT_PRIMARY};
                line-height: 1.5;
            }}
            QScrollBar:vertical {{
                background-color: {ChatTheme.BG_PRIMARY};
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {ChatTheme.BORDER};
                border-radius: 5px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {ChatTheme.TEXT_SECONDARY};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        layout.addWidget(self.chat_display, stretch=1)

        # Quick actions
        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(8)

        quick_label = QLabel("Quick Actions:")
        quick_label.setStyleSheet(f"color: {ChatTheme.TEXT_SECONDARY}; font-weight: 600;")
        quick_layout.addWidget(quick_label)

        quick_btn_style = f"""
            QPushButton {{
                background-color: {ChatTheme.BG_TERTIARY};
                color: {ChatTheme.TEXT_PRIMARY};
                border: 1px solid {ChatTheme.BORDER};
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {ChatTheme.BORDER};
                border-color: {ChatTheme.ACCENT_BLUE};
            }}
            QPushButton:pressed {{
                background-color: {ChatTheme.BG_SECONDARY};
            }}
        """

        quick_dtc = QPushButton("Explain DTC")
        quick_dtc.setStyleSheet(quick_btn_style)
        quick_dtc.clicked.connect(lambda: self.insert_template("dtc"))
        quick_layout.addWidget(quick_dtc)

        quick_prediction = QPushButton("Analyze Prediction")
        quick_prediction.setStyleSheet(quick_btn_style)
        quick_prediction.clicked.connect(lambda: self.insert_template("prediction"))
        quick_layout.addWidget(quick_prediction)

        quick_customer = QPushButton("Customer Response")
        quick_customer.setStyleSheet(quick_btn_style)
        quick_customer.clicked.connect(lambda: self.insert_template("customer"))
        quick_layout.addWidget(quick_customer)

        # Failure Report template button
        failure_report_btn = QPushButton("Failure Report")
        failure_report_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ChatTheme.ACCENT_GREEN};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #45a049;
            }}
            QPushButton:pressed {{
                background-color: #2d8a32;
            }}
        """)
        failure_report_btn.clicked.connect(self._insert_failure_template)
        quick_layout.addWidget(failure_report_btn)

        quick_layout.addStretch()

        clear_btn = QPushButton("Clear Chat")
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {ChatTheme.TEXT_SECONDARY};
                border: 1px solid {ChatTheme.BORDER};
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {ChatTheme.BG_TERTIARY};
                color: {ChatTheme.TEXT_PRIMARY};
            }}
        """)
        clear_btn.clicked.connect(self.clear_chat)
        quick_layout.addWidget(clear_btn)

        layout.addLayout(quick_layout)

        # Input area
        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type your question here... (Press Enter to send)")
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                background-color: {ChatTheme.BG_TERTIARY};
                color: {ChatTheme.TEXT_PRIMARY};
                border: 2px solid {ChatTheme.BORDER};
                border-radius: 8px;
                padding: 12px 16px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border-color: {ChatTheme.ACCENT_BLUE};
            }}
            QLineEdit::placeholder {{
                color: {ChatTheme.TEXT_SECONDARY};
            }}
        """)
        self.input_field.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.input_field)

        self.send_btn = QPushButton("Send")
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ChatTheme.ACCENT_RED};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: 600;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: #E53935;
            }}
            QPushButton:pressed {{
                background-color: #A00000;
            }}
            QPushButton:disabled {{
                background-color: {ChatTheme.BG_TERTIARY};
                color: {ChatTheme.TEXT_SECONDARY};
            }}
        """)
        self.send_btn.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_btn)

        layout.addLayout(input_layout)

        self.setLayout(layout)

        # Set widget background
        self.setStyleSheet(f"background-color: {ChatTheme.BG_PRIMARY};")

        # Welcome message
        self.add_system_message("Welcome to PREDICT AI Assistant! Ask me anything about diagnostics, predictions, or vehicle issues.")

    def update_status_label(self):
        """Update LLM status indicator."""
        if self.llm_assistant.is_loaded:
            load_time = ""
            if self.llm_assistant.load_end_time and self.llm_assistant.load_start_time:
                seconds = (self.llm_assistant.load_end_time - self.llm_assistant.load_start_time).total_seconds()
                load_time = f" (loaded in {seconds:.1f}s)"

            self.status_label.setText(f"AI Assistant Ready{load_time}")
            self.status_label.setStyleSheet(f"""
                color: {ChatTheme.ACCENT_GREEN};
                background-color: rgba(63, 185, 80, 0.1);
                border: 1px solid {ChatTheme.ACCENT_GREEN};
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 600;
            """)
        else:
            self.status_label.setText("AI Assistant Not Loaded - Some features unavailable")
            self.status_label.setStyleSheet(f"""
                color: {ChatTheme.ERROR_BG};
                background-color: rgba(248, 81, 73, 0.1);
                border: 1px solid {ChatTheme.ERROR_BG};
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 600;
            """)

    def insert_template(self, template_type: str):
        """Insert a quick template into input field."""
        templates = {
            "dtc": "Explain DTC code P0420 for a 2020 Toyota Camry with 85,000 km in Qatar. Include cost estimate in QAR.",
            "prediction": "Analyze this prediction: Battery failure predicted at 78% probability, patterns: voltage drops, slow cranking. Actual: Battery was fine, alternator failed. Why was prediction wrong?",
            "customer": "Customer says: 'Your AI predicted battery failure but mechanic says battery is fine, it's the alternator. Your system is unreliable!' Generate a professional response."
        }

        self.input_field.setText(templates.get(template_type, ""))
        self.input_field.setFocus()

    def add_system_message(self, message: str):
        """Add system message to chat."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        html = f"""
        <p style='color: {ChatTheme.TEXT_SECONDARY}; font-style: italic; margin: 6px 0; font-size: 12px;'>[{timestamp}] {message}</p>
        """
        self.chat_display.append(html)
        self.scroll_to_bottom()

    def add_user_message(self, message: str):
        """Add user message to chat."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        html = f"""
        <p style='margin: 8px 0;'><b style='color: {ChatTheme.ACCENT_BLUE};'>You</b> <span style='color: {ChatTheme.TEXT_SECONDARY}; font-size: 11px;'>[{timestamp}]</span></p>
        <p style='color: white; margin: 4px 0 12px 20px;'>{message}</p>
        """
        self.chat_display.append(html)
        self.scroll_to_bottom()

        self.chat_history.append({"role": "user", "message": message, "timestamp": timestamp})

    def add_ai_message(self, message: str):
        """Add AI response to chat."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        # Replace newlines with <br> for proper HTML rendering
        message_html = message.replace('\n', '<br/>')

        html = f"""
        <p style='margin: 8px 0;'><b style='color: {ChatTheme.ACCENT_GREEN};'>AI Assistant</b> <span style='color: {ChatTheme.TEXT_SECONDARY}; font-size: 11px;'>[{timestamp}]</span></p>
        <p style='color: {ChatTheme.TEXT_PRIMARY}; margin: 4px 0 12px 20px;'>{message_html}</p>
        """
        self.chat_display.append(html)
        self.scroll_to_bottom()

        self.chat_history.append({"role": "assistant", "message": message, "timestamp": timestamp})

    def add_error_message(self, error: str):
        """Add error message to chat."""
        html = f"""
        <p style='margin: 8px 0;'><b style='color: #F85149;'>Error</b></p>
        <p style='color: #F85149; margin: 4px 0 12px 20px;'>{error}</p>
        """
        self.chat_display.append(html)
        self.scroll_to_bottom()

    def scroll_to_bottom(self):
        """Scroll chat display to bottom."""
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def send_message(self):
        """Send message to AI."""
        message = self.input_field.text().strip()

        if not message:
            return

        # Check if this is a failure report template
        if self.llm_assistant.is_failure_template(message):
            self.add_user_message("[Failure Report Template]")
            self.input_field.clear()
            self._handle_failure_template(message)
            return

        # Lazy loading: automatically load default model if not loaded
        if not self.llm_assistant.is_loaded:
            self.pending_message = message
            self.input_field.clear()
            self.add_system_message("Loading AI model for first use... This will take a moment.")

            # Trigger loading of default model (Qwen)
            self.model_combo.setEnabled(False)
            self.input_field.setEnabled(False)
            self.send_btn.setEnabled(False)

            self.model_switch_worker = ModelSwitchWorker(self.llm_assistant, "qwen")
            self.model_switch_worker.finished.connect(self._on_model_switched)
            self.model_switch_worker.start()
            return

        # Add user message to chat
        self.add_user_message(message)

        # Clear input
        self.input_field.clear()

        # Send to LLM
        self._send_to_llm(message)

    def _send_to_llm(self, message: str):
        """Send message to LLM (helper for both normal send and lazy loading)."""
        # Disable input while processing
        self.input_field.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.send_btn.setText("Thinking...")

        # Add thinking indicator
        self.add_system_message("AI is thinking... (this may take 5-15 seconds)")

        # Get context type
        context_map = {
            "General Chat": "general",
            "DTC Diagnosis": "dtc",
            "Prediction Analysis": "prediction",
            "Customer Support": "customer"
        }
        context = context_map.get(self.context_combo.currentText(), "general")

        # Start background worker
        self.current_worker = ChatWorker(self.llm_assistant, message, context)
        self.current_worker.response_ready.connect(self.handle_response)
        self.current_worker.error.connect(self.handle_error)
        self.current_worker.start()

    def handle_response(self, response: str):
        """Handle AI response."""
        self.add_ai_message(response)

        # Re-enable input
        self.input_field.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.send_btn.setText("Send")
        self.input_field.setFocus()

    def handle_error(self, error: str):
        """Handle error."""
        self.add_error_message(f"Failed to generate response: {error}")

        # Re-enable input
        self.input_field.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.send_btn.setText("Send")

    def clear_chat(self):
        """Clear chat history."""
        self.chat_display.clear()
        self.chat_history = []
        self.add_system_message("Chat cleared. How can I help you?")

    def export_chat(self):
        """Export chat history to file (future feature)."""
        pass

    # ==================== MODEL SELECTION ====================

    def _populate_model_selector(self):
        """Populate model selector with available models."""
        self.model_combo.blockSignals(True)
        self.model_combo.clear()

        available_models = self.llm_assistant.get_available_models()
        current_model = self.llm_assistant.get_current_model_info()

        for model in available_models:
            display_text = f"{model['name']} - {model['description']}"
            self.model_combo.addItem(display_text, model['id'])

        # Select current model
        if current_model.get("loaded"):
            for i in range(self.model_combo.count()):
                if self.model_combo.itemData(i) == current_model.get("id"):
                    self.model_combo.setCurrentIndex(i)
                    break

        self.model_combo.blockSignals(False)

    def _on_model_changed(self, index):
        """Handle model selection change."""
        if index < 0:
            return

        model_id = self.model_combo.itemData(index)
        current_info = self.llm_assistant.get_current_model_info()

        # Skip if same model already loaded
        if current_info.get("id") == model_id and current_info.get("loaded"):
            return

        model_name = self.model_combo.currentText().split(" - ")[0]
        self.add_system_message(f"Switching to {model_name}... This may take a moment.")

        # Disable controls during switch
        self.model_combo.setEnabled(False)
        self.input_field.setEnabled(False)
        self.send_btn.setEnabled(False)

        # Start background worker
        self.model_switch_worker = ModelSwitchWorker(self.llm_assistant, model_id)
        self.model_switch_worker.finished.connect(self._on_model_switched)
        self.model_switch_worker.start()

    def _on_model_switched(self, success: bool, model_name: str):
        """Handle model switch completion."""
        # Re-enable controls
        self.model_combo.setEnabled(True)
        self.input_field.setEnabled(True)
        self.send_btn.setEnabled(True)

        if success:
            self.add_system_message(f"Now using {model_name}")
            self.update_status_label()
            self._populate_model_selector()  # Update dropdown to show loaded model

            # Send pending message if there was one (lazy loading)
            if self.pending_message:
                message = self.pending_message
                self.pending_message = None
                # Add user message and send it
                self.add_user_message(message)
                self._send_to_llm(message)
        else:
            self.add_error_message(f"Failed to switch to {model_name}")
            # Clear pending message on failure
            self.pending_message = None
            # Revert combo to actual loaded model
            self._populate_model_selector()

    # ==================== FAILURE REPORT TEMPLATE ====================

    def _insert_failure_template(self):
        """Insert failure report template into input field."""
        template = """---FAILURE REPORT---
Profile Name:
Car Number:
Phone:
Customer Issue:
Mechanic Analysis:
Confirmed Failure: yes/no
AI Predicted This: yes/no
Date:
Notes:
---END REPORT---"""

        self.input_field.setText(template)
        self.input_field.setFocus()
        self.add_system_message("Failure report template inserted. Fill in the fields and press Send.")

    def _handle_failure_template(self, template_text: str):
        """Handle failure report template submission."""
        # Parse template
        data = self.llm_assistant.parse_failure_template(template_text)

        # Validate required fields
        if not data.get('profile_name') or not data.get('car_number'):
            self.add_error_message("Missing required fields: Profile Name and Car Number are required.")
            return False

        # Show confirmation
        confirm_msg = f"""Saving Failure Report:
- Customer: {data.get('profile_name', 'N/A')}
- Car: {data.get('car_number', 'N/A')}
- Customer reported: {data.get('customer_issue', 'N/A')}
- Actual problem: {data.get('mechanic_analysis', 'N/A')}
- AI predicted this: {'Yes' if data.get('ai_predicted') else 'No'}
- Confirmed failure: {'Yes' if data.get('confirmed') else 'No'}

This data will be saved to improve AI training."""

        self.add_system_message(confirm_msg)

        # TODO: Save to feedback_collector when integrated
        # For now, just acknowledge
        self.add_ai_message(f"Failure report received for {data.get('profile_name')} (Car #{data.get('car_number')}). "
                           f"This feedback helps improve our prediction accuracy. Thank you!")

        return True
