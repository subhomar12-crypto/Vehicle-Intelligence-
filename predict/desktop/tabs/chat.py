"""
AI Chat tab for conversational vehicle diagnostics.

Interface for chatting with the AI assistant about vehicle issues.
"""

import logging
import time
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit,
    QFrame,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

from predict.desktop.theme import PredictTheme

logger = logging.getLogger(__name__)


class ChatWorker(QThread):
    """Background worker for AI chat requests."""
    
    response_ready = Signal(str)
    error = Signal(str)
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.message = message
        self.context = context or {}
    
    def run(self) -> None:
        """Process chat message in background."""
        try:
            # Simulate AI processing
            time.sleep(1.5)
            
            # Generate response based on message keywords
            msg_lower = self.message.lower()
            
            if "check engine" in msg_lower or "dtc" in msg_lower:
                response = (
                    "Based on the diagnostic trouble codes (P0171 - System Too Lean), "
                    "I recommend checking the following:\n\n"
                    "1. **Vacuum leaks** - Inspect all vacuum hoses and intake manifold gaskets\n"
                    "2. **MAF sensor** - Clean or replace if contaminated\n"
                    "3. **Fuel pressure** - Verify fuel pump is delivering proper pressure\n"
                    "4. **O2 sensors** - Check front O2 sensor operation\n\n"
                    "The fuel trim value of +22% indicates the ECU is adding significant fuel "
                    "to compensate for a lean condition. This is typically caused by unmetered air."
                )
            elif "battery" in msg_lower or "voltage" in msg_lower:
                response = (
                    "Your battery voltage readings show normal operation at 14.2V while running, "
                    "which indicates the alternator is charging properly.\n\n"
                    "However, I noticed a declining trend over the past week:\n"
                    "- 7 days ago: 14.4V\n"
                    "- Today: 14.2V\n\n"
                    "This slight decrease could indicate early alternator wear. "
                    "I recommend monitoring this trend. If it drops below 13.8V, "
                    "consider having the alternator tested."
                )
            elif "oil" in msg_lower:
                response = (
                    "Based on your vehicle's maintenance history and current mileage, "
                    "your next oil change is due in approximately 1,200 miles or 2 months.\n\n"
                    "Current oil life: 68%\n"
                    "Last service: 3,800 miles ago\n\n"
                    "I recommend using 5W-30 synthetic oil as specified for your vehicle."
                )
            elif "maintenance" in msg_lower or "service" in msg_lower:
                response = (
                    "Here's your upcoming maintenance schedule:\n\n"
                    "**Due Soon (within 1,000 miles):**\n"
                    "- Oil change\n"
                    "- Tire rotation\n\n"
                    "**Due in 3,000 miles:**\n"
                    "- Air filter replacement\n"
                    "- Brake inspection\n\n"
                    "**Due in 6,000 miles:**\n"
                    "- Spark plug replacement\n"
                    "- Transmission fluid check\n\n"
                    "Would you like me to add any of these to your calendar?"
                )
            else:
                response = (
                    "I'm analyzing your vehicle data. Based on the current sensor readings, "
                    "your vehicle appears to be operating within normal parameters.\n\n"
                    "Key observations:\n"
                    "- Engine temperature: Normal (92°C)\n"
                    "- Battery voltage: Good (14.2V)\n"
                    "- Engine load: Light (15%)\n\n"
                    "Is there a specific concern you'd like me to investigate?"
                )
            
            self.response_ready.emit(response)
        
        except Exception as e:
            self.error.emit(str(e))


class ChatTab(QWidget):
    """
    Tab for AI chat interface.
    
    Features:
    - Chat history display with HTML formatting
    - Message input with send button
    - Clear chat functionality
    - AI model status indicator
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._messages: List[Dict[str, str]] = []
        self._worker: Optional[ChatWorker] = None
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Setup the tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("AI Assistant")
        title.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY};")
        font = QFont(PredictTheme.FONT_FAMILY, 18, QFont.Weight.Bold)
        title.setFont(font)
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Model status
        self.status_label = QLabel("Model: Qwen3.5-2B ●")
        self.status_label.setStyleSheet(f"color: {PredictTheme.SUCCESS};")
        header_layout.addWidget(self.status_label)
        
        # Clear button
        clear_btn = QPushButton("Clear Chat")
        clear_btn.clicked.connect(self._clear_chat)
        header_layout.addWidget(clear_btn)
        
        layout.addLayout(header_layout)
        
        # Chat history
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setStyleSheet(f"""
            QTextEdit {{
                background-color: {PredictTheme.BG_SECONDARY};
                color: {PredictTheme.TEXT_PRIMARY};
                border: 1px solid {PredictTheme.BORDER};
                border-radius: 8px;
                padding: 15px;
            }}
        """)
        layout.addWidget(self.chat_history)
        
        # Input area
        input_layout = QHBoxLayout()
        
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Ask about your vehicle...")
        self.message_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {PredictTheme.BG_SECONDARY};
                color: {PredictTheme.TEXT_PRIMARY};
                border: 1px solid {PredictTheme.BORDER};
                border-radius: 6px;
                padding: 10px 15px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border-color: {PredictTheme.PRIMARY};
            }}
        """)
        self.message_input.returnPressed.connect(self._send_message)
        input_layout.addWidget(self.message_input)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("primary")
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PredictTheme.PRIMARY};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 25px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #E00000;
            }}
        """)
        self.send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(self.send_btn)
        
        layout.addLayout(input_layout)
        
        # Welcome message
        self._add_system_message(
            "Welcome to PREDICT AI Assistant! I can help you understand diagnostic codes, "
            "interpret sensor readings, and provide maintenance recommendations. "
            "What would you like to know about your vehicle?"
        )
    
    def _add_user_message(self, text: str) -> None:
        """Add user message to chat."""
        # Use time.strftime for display formatting
        timestamp_display = time.strftime("%H:%M", time.localtime())
        
        html = f"""
        <div style="margin: 10px 0; text-align: right;">
            <div style="display: inline-block; background-color: {PredictTheme.PRIMARY}; 
                        color: white; padding: 10px 15px; border-radius: 15px 15px 0 15px;
                        max-width: 80%; text-align: left;">
                {text}
            </div>
            <div style="font-size: 10px; color: {PredictTheme.TEXT_MUTED}; margin-top: 5px;">
                You • {timestamp_display}
            </div>
        </div>
        """
        
        self.chat_history.append(html)
        self._scroll_to_bottom()
        
        self._messages.append({"role": "user", "content": text, "time": timestamp_display})
    
    def _add_ai_message(self, text: str) -> None:
        """Add AI message to chat."""
        timestamp_display = time.strftime("%H:%M", time.localtime())
        
        # Convert newlines to HTML breaks
        formatted_text = text.replace("\n", "<br>")
        
        html = f"""
        <div style="margin: 10px 0;">
            <div style="display: inline-block; background-color: {PredictTheme.CARD_BG}; 
                        color: {PredictTheme.TEXT_PRIMARY}; padding: 10px 15px; 
                        border-radius: 15px 15px 15px 0; max-width: 80%;
                        border: 1px solid {PredictTheme.BORDER};">
                <b style="color: {PredictTheme.ACCENT_CYAN};">PREDICT AI</b><br><br>
                {formatted_text}
            </div>
            <div style="font-size: 10px; color: {PredictTheme.TEXT_MUTED}; margin-top: 5px;">
                AI • {timestamp_display}
            </div>
        </div>
        """
        
        self.chat_history.append(html)
        self._scroll_to_bottom()
        
        self._messages.append({"role": "assistant", "content": text, "time": timestamp_display})
    
    def _add_system_message(self, text: str) -> None:
        """Add system message to chat."""
        html = f"""
        <div style="margin: 10px 0; text-align: center;">
            <div style="display: inline-block; background-color: {PredictTheme.BG_SECONDARY}; 
                        color: {PredictTheme.TEXT_SECONDARY}; padding: 8px 15px; 
                        border-radius: 15px; font-size: 12px;">
                {text}
            </div>
        </div>
        """
        
        self.chat_history.append(html)
        self._scroll_to_bottom()
    
    def _scroll_to_bottom(self) -> None:
        """Scroll chat to bottom."""
        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _send_message(self) -> None:
        """Send user message and get AI response."""
        message = self.message_input.text().strip()
        if not message:
            return
        
        # Add user message
        self._add_user_message(message)
        self.message_input.clear()
        
        # Disable input during processing
        self.message_input.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.send_btn.setText("Thinking...")
        
        # Start AI worker
        self._worker = ChatWorker(message)
        self._worker.response_ready.connect(self._on_response)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()
    
    def _on_response(self, response: str) -> None:
        """Handle AI response."""
        self._add_ai_message(response)
    
    def _on_error(self, error: str) -> None:
        """Handle chat error."""
        logger.error(f"Chat error: {error}")
        self._add_system_message(f"Error: {error}")
    
    def _on_finished(self) -> None:
        """Handle worker completion."""
        self.message_input.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.send_btn.setText("Send")
        self.message_input.setFocus()
    
    def _clear_chat(self) -> None:
        """Clear chat history."""
        self.chat_history.clear()
        self._messages = []
        self._add_system_message("Chat history cleared.")
