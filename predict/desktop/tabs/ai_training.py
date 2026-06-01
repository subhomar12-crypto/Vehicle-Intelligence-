"""
AI Training tab for model training management.

Shows training statistics, model selection, and training execution.
"""

import logging
import random
import time
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QTableWidget, QTableWidgetItem,
    QProgressBar, QGroupBox, QFrame,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QColor

from predict.desktop.theme import PredictTheme

logger = logging.getLogger(__name__)


class TrainingWorker(QThread):
    """Background worker for model training."""
    
    progress = Signal(int)
    epoch_complete = Signal(dict)
    finished_training = Signal(dict)
    error = Signal(str)
    
    def __init__(self, model_name: str, epochs: int = 50):
        super().__init__()
        self.model_name = model_name
        self.epochs = epochs
    
    def run(self) -> None:
        """Run training in background."""
        try:
            start_time = time.perf_counter()

            for epoch in range(1, self.epochs + 1):
                time.sleep(0.1)  # Simulate epoch time
                
                # Simulate metrics
                loss = 1.0 / (epoch + 1) + random.uniform(0, 0.1)
                accuracy = min(0.95, 0.5 + (epoch / self.epochs) * 0.45 + random.uniform(-0.05, 0.05))
                
                self.epoch_complete.emit({
                    "epoch": epoch,
                    "loss": loss,
                    "accuracy": accuracy,
                })
                
                progress = int((epoch / self.epochs) * 100)
                self.progress.emit(progress)
            
            training_time = time.perf_counter() - start_time
            
            self.finished_training.emit({
                "model": self.model_name,
                "epochs": self.epochs,
                "final_accuracy": 0.92,
                "final_loss": 0.08,
                "training_time": training_time,
            })
        
        except Exception as e:
            self.error.emit(str(e))


class AITrainingTab(QWidget):
    """
    Tab for AI model training management.
    
    Features:
    - Training statistics display
    - Model selection
    - Training execution with progress
    - Training history
    """
    
    # Available models
    MODELS = [
        "CNN-LSTM Hybrid",
        "Attention LSTM",
        "LSTM Autoencoder",
        "Ensemble Voter",
        "Random Forest",
    ]
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._training_history: List[Dict[str, Any]] = []
        self._worker: Optional[TrainingWorker] = None
        self._setup_ui()
        self._load_sample_history()
    
    def _setup_ui(self) -> None:
        """Setup the tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("AI Model Training")
        title.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY};")
        font = QFont(PredictTheme.FONT_FAMILY, 18, QFont.Weight.Bold)
        title.setFont(font)
        layout.addWidget(title)
        
        # Top row: Stats and Training controls
        top_layout = QHBoxLayout()
        
        # Stats group
        stats_group = QGroupBox("Dataset Statistics")
        stats_group.setStyleSheet(PredictTheme.get_card_stylesheet())
        stats_layout = QGridLayout(stats_group)
        
        self.stats_labels = {}
        stats_data = [
            ("Total Records:", "125,430"),
            ("Date Range:", "2023-06-01 to 2024-01-15"),
            ("Labeled Data:", "45,230 (36%)"),
            ("Active Models:", "5"),
        ]
        
        for i, (label, value) in enumerate(stats_data):
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {PredictTheme.TEXT_SECONDARY};")
            stats_layout.addWidget(lbl, i, 0)
            
            val = QLabel(value)
            val.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY}; font-weight: bold;")
            self.stats_labels[label] = val
            stats_layout.addWidget(val, i, 1)
        
        top_layout.addWidget(stats_group)
        
        # Training controls
        train_group = QGroupBox("Training")
        train_group.setStyleSheet(PredictTheme.get_card_stylesheet())
        train_layout = QVBoxLayout(train_group)
        
        # Model selector
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(self.MODELS)
        model_layout.addWidget(self.model_combo)
        train_layout.addLayout(model_layout)
        
        # Train button
        self.train_btn = QPushButton("Train Model")
        self.train_btn.setObjectName("primary")
        self.train_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PredictTheme.SUCCESS};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #146c43;
            }}
        """)
        self.train_btn.clicked.connect(self._start_training)
        train_layout.addWidget(self.train_btn)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {PredictTheme.BG_SECONDARY};
                border: 1px solid {PredictTheme.BORDER};
                border-radius: 4px;
                text-align: center;
                color: {PredictTheme.TEXT_PRIMARY};
            }}
            QProgressBar::chunk {{
                background-color: {PredictTheme.SUCCESS};
                border-radius: 4px;
            }}
        """)
        self.progress_bar.hide()
        train_layout.addWidget(self.progress_bar)
        
        # Results
        self.results_frame = QFrame()
        results_layout = QGridLayout(self.results_frame)
        
        self.accuracy_label = QLabel("Accuracy: --")
        self.accuracy_label.setStyleSheet(f"color: {PredictTheme.SUCCESS}; font-weight: bold;")
        results_layout.addWidget(self.accuracy_label, 0, 0)
        
        self.loss_label = QLabel("Loss: --")
        self.loss_label.setStyleSheet(f"color: {PredictTheme.TEXT_PRIMARY};")
        results_layout.addWidget(self.loss_label, 0, 1)
        
        self.time_label = QLabel("Time: --")
        self.time_label.setStyleSheet(f"color: {PredictTheme.TEXT_SECONDARY};")
        results_layout.addWidget(self.time_label, 0, 2)
        
        self.results_frame.hide()
        train_layout.addWidget(self.results_frame)
        
        train_layout.addStretch()
        top_layout.addWidget(train_group)
        
        layout.addLayout(top_layout)
        
        # Training history
        history_group = QGroupBox("Training History")
        history_group.setStyleSheet(PredictTheme.get_card_stylesheet())
        history_layout = QVBoxLayout(history_group)
        
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels([
            "Date", "Model", "Accuracy", "Loss", "Epochs", "Duration"
        ])
        self.history_table.setStyleSheet(PredictTheme.get_table_stylesheet())
        history_layout.addWidget(self.history_table)
        
        layout.addWidget(history_group)
    
    def _load_sample_history(self) -> None:
        """Load sample training history."""
        # Use time.strftime for display formatting
        current_time = time.time()
        
        self._training_history = [
            {
                "date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(current_time - 86400)),
                "model": "CNN-LSTM Hybrid",
                "accuracy": 0.91,
                "loss": 0.09,
                "epochs": 50,
                "duration": "12:45",
            },
            {
                "date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(current_time - 172800)),
                "model": "Attention LSTM",
                "accuracy": 0.89,
                "loss": 0.11,
                "epochs": 50,
                "duration": "15:30",
            },
            {
                "date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(current_time - 259200)),
                "model": "Ensemble Voter",
                "accuracy": 0.93,
                "loss": 0.07,
                "epochs": 30,
                "duration": "08:15",
            },
        ]
        self._update_history_table()
    
    def _update_history_table(self) -> None:
        """Update training history table."""
        self.history_table.setRowCount(len(self._training_history))
        
        for row, entry in enumerate(self._training_history):
            items = [
                entry["date"],
                entry["model"],
                f"{entry['accuracy']:.2%}",
                f"{entry['loss']:.4f}",
                str(entry["epochs"]),
                entry["duration"],
            ]
            
            for col, value in enumerate(items):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                
                # Color accuracy
                if col == 2:
                    accuracy = entry["accuracy"]
                    if accuracy >= 0.9:
                        item.setForeground(QColor(PredictTheme.SUCCESS))
                    elif accuracy >= 0.8:
                        item.setForeground(QColor(PredictTheme.WARNING))
                    else:
                        item.setForeground(QColor(PredictTheme.DANGER))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                
                self.history_table.setItem(row, col, item)
        
        self.history_table.resizeColumnsToContents()
    
    def _start_training(self) -> None:
        """Start model training."""
        model_name = self.model_combo.currentText()
        logger.info(f"Starting training for {model_name}")
        
        # Reset UI
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.results_frame.hide()
        self.train_btn.setEnabled(False)
        
        # Start worker
        self._worker = TrainingWorker(model_name, epochs=50)
        self._worker.progress.connect(self._on_progress)
        self._worker.epoch_complete.connect(self._on_epoch)
        self._worker.finished_training.connect(self._on_training_finished)
        self._worker.error.connect(self._on_training_error)
        self._worker.start()
    
    def _on_progress(self, value: int) -> None:
        """Update progress bar."""
        self.progress_bar.setValue(value)
    
    def _on_epoch(self, metrics: Dict[str, Any]) -> None:
        """Handle epoch completion."""
        logger.debug(f"Epoch {metrics['epoch']}: loss={metrics['loss']:.4f}, accuracy={metrics['accuracy']:.4f}")
    
    def _on_training_finished(self, result: Dict[str, Any]) -> None:
        """Handle training completion."""
        logger.info(f"Training completed: {result}")
        
        # Update results
        self.accuracy_label.setText(f"Accuracy: {result['final_accuracy']:.2%}")
        self.loss_label.setText(f"Loss: {result['final_loss']:.4f}")
        self.time_label.setText(f"Time: {result['training_time']:.1f}s")
        
        self.results_frame.show()
        self.progress_bar.hide()
        self.train_btn.setEnabled(True)
        
        # Add to history
        self._training_history.insert(0, {
            "date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "model": result["model"],
            "accuracy": result["final_accuracy"],
            "loss": result["final_loss"],
            "epochs": result["epochs"],
            "duration": f"{result['training_time']:.0f}s",
        })
        self._update_history_table()
    
    def _on_training_error(self, error: str) -> None:
        """Handle training error."""
        logger.error(f"Training failed: {error}")
        self.progress_bar.hide()
        self.train_btn.setEnabled(True)
