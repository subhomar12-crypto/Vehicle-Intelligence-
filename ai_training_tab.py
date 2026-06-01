"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Ai Training Tab
"""

import os
import csv
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QSplitter, QHBoxLayout,
    QPushButton, QGroupBox, QPlainTextEdit, QListWidget,
    QListWidgetItem, QFormLayout, QComboBox, QFileDialog,
    QInputDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

from ui_common import ProfessionalTheme, show_error
from predictive_failure_engine import PredictiveFailureEngine
from unified_ai_module import UnifiedAIModule
from automotive_data_adapter import AutomotiveDataAdapter


class TrainingFeedbackPanel(QGroupBox):
    """
    Post-training feedback panel showing what the AI learned
    Purpose: Makes training feel real, avoids "placebo training" perception
    """

    def __init__(self, parent=None):
        super().__init__("🎓 Training Results", parent)
        self.setVisible(False)  # Hidden until training completes
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 20, 15, 15)
        layout.setSpacing(10)

        # Learned insights section
        learned_label = QLabel("AI Learned:")
        learned_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        layout.addWidget(learned_label)

        self.learned_list = QLabel()
        self.learned_list.setWordWrap(True)
        self.learned_list.setStyleSheet(f"""
            QLabel {{
                color: {ProfessionalTheme.TEXT_PRIMARY};
                padding: 5px;
                background-color: {ProfessionalTheme.CARD_BG};
                border-left: 3px solid {ProfessionalTheme.SUCCESS};
                border-radius: 3px;
            }}
        """)
        layout.addWidget(self.learned_list)

        # Expected impact section
        impact_label = QLabel("Expected Impact:")
        impact_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        layout.addWidget(impact_label)

        self.impact_text = QLabel()
        self.impact_text.setWordWrap(True)
        self.impact_text.setStyleSheet(f"""
            QLabel {{
                color: {ProfessionalTheme.TEXT_PRIMARY};
                padding: 5px;
                background-color: {ProfessionalTheme.CARD_BG};
                border-left: 3px solid {ProfessionalTheme.INFO};
                border-radius: 3px;
            }}
        """)
        layout.addWidget(self.impact_text)

    def show_feedback(self, training_result: dict):
        """
        Display training feedback based on results

        Args:
            training_result: Dict with keys:
                - models_trained: List of model names
                - metrics: Dict of model_name -> {accuracy, f1, etc.}
                - feature_importances: Dict of model -> features
                - samples_used: Int
        """
        learned_items = []
        impact_items = []

        models = training_result.get('models_trained', [])
        metrics = training_result.get('metrics', {})
        feature_imp = training_result.get('feature_importances', {})
        samples = training_result.get('samples_used', 0)

        # Extract what was learned
        if models:
            learned_items.append(f"• Trained {len(models)} prediction model(s)")

        if samples:
            learned_items.append(f"• Analyzed {samples:,} data samples")

        # Top features learned
        if feature_imp:
            for model_name, features in feature_imp.items():
                if features:
                    top_features = sorted(features.items(), key=lambda x: x[1], reverse=True)[:3]
                    feature_names = [f.replace('_', ' ').title() for f, _ in top_features]
                    learned_items.append(f"• {model_name}: Key signals - {', '.join(feature_names)}")

        # Compute confidence impact
        total_accuracy = 0
        model_count = 0
        for model_name, model_metrics in metrics.items():
            accuracy = model_metrics.get('accuracy', 0)
            total_accuracy += accuracy
            model_count += 1

        if model_count > 0:
            avg_accuracy = (total_accuracy / model_count) * 100
            if avg_accuracy >= 80:
                confidence_change = "+15-20%"
                quality = "High"
            elif avg_accuracy >= 70:
                confidence_change = "+10-15%"
                quality = "Moderate"
            else:
                confidence_change = "+5-10%"
                quality = "Developing"

            impact_items.append(f"• Prediction confidence: {quality} ({avg_accuracy:.1f}% accuracy)")
            impact_items.append(f"• Expected improvement: {confidence_change} on related predictions")

        if learned_items:
            impact_items.append(f"• AI will now recognize patterns from {samples:,} historical samples")

        # Update UI
        self.learned_list.setText("\n".join(learned_items) if learned_items else "• Training completed")
        self.impact_text.setText("\n".join(impact_items) if impact_items else "• Predictions will use trained models")

        # Show the panel
        self.setVisible(True)


class AITrainingTab(QWidget):
    """AI Training Tab for importing CSV datasets and training models with enhanced dataset configuration"""

    def __init__(self, predictive_engine: PredictiveFailureEngine, unified_ai: UnifiedAIModule, parent=None):
        super().__init__(parent)
        self.predictive_engine = predictive_engine
        self.unified_ai = unified_ai

        # Dataset storage
        self.datasets = {}  # Maps dataset_id -> {dataset_type, analysis, configured, file_path, rows_loaded}
        self.current_dataset_id = None

        self._build_ui()

    def _build_ui(self):
        """Build the enhanced AI Training tab UI with dataset configuration"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header
        title = QLabel("AI Training")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Description
        description = QLabel(
            "Import CSV datasets to train AI models for predictive failure analysis. "
            "For daily_features datasets, configure label and feature columns before training."
        )
        description.setWordWrap(True)
        description.setStyleSheet(f"color: {ProfessionalTheme.TEXT_SECONDARY};")
        layout.addWidget(description)

        # Main splitter for dataset management and configuration
        splitter = QSplitter(Qt.Horizontal)

        # Left: Dataset import and management
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # Control buttons
        controls_layout = QHBoxLayout()

        self.btn_add_csv = QPushButton("Add Dataset (CSV/Logs)...")
        self.btn_add_csv.setStyleSheet(self._get_button_style('primary'))
        self.btn_train = QPushButton("Train Models")
        self.btn_train.setStyleSheet(self._get_button_style('success'))
        self.btn_clear_log = QPushButton("Clear Log")
        self.btn_clear_log.setStyleSheet(self._get_button_style('secondary'))

        self.btn_add_csv.clicked.connect(self._on_add_csv)
        self.btn_train.clicked.connect(self._on_train_models)
        self.btn_clear_log.clicked.connect(self._on_clear_log)

        controls_layout.addWidget(self.btn_add_csv)
        controls_layout.addWidget(self.btn_train)
        controls_layout.addWidget(self.btn_clear_log)
        controls_layout.addStretch(1)

        left_layout.addLayout(controls_layout)

        # Dataset list
        dataset_group = QGroupBox("Imported Datasets")
        dataset_layout = QVBoxLayout(dataset_group)

        self.dataset_list = QListWidget()
        self.dataset_list.itemSelectionChanged.connect(self._on_dataset_selected)
        dataset_layout.addWidget(self.dataset_list)

        left_layout.addWidget(dataset_group)

        # Right: Dataset configuration
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # Dataset configuration panel
        config_group = QGroupBox("Dataset Configuration")
        config_layout = QFormLayout(config_group)

        # Dataset info
        self.dataset_info_label = QLabel("No dataset selected")
        config_layout.addRow("Dataset:", self.dataset_info_label)

        # Label selection
        self.label_combo = QComboBox()
        self.label_combo.setEnabled(False)
        config_layout.addRow("Label Column:", self.label_combo)

        # Feature selection
        feature_selection_label = QLabel("Feature Columns:")
        config_layout.addRow(feature_selection_label)

        self.feature_list = QListWidget()
        self.feature_list.setSelectionMode(QListWidget.MultiSelection)
        self.feature_list.setEnabled(False)
        config_layout.addRow(self.feature_list)

        # Configuration buttons
        config_buttons_layout = QHBoxLayout()
        self.btn_save_schema = QPushButton("Save Schema")
        self.btn_save_schema.setStyleSheet(self._get_button_style('success'))
        self.btn_auto_select = QPushButton("Auto-Select Features")
        self.btn_auto_select.setStyleSheet(self._get_button_style('info'))

        self.btn_save_schema.clicked.connect(self._on_save_schema)
        self.btn_auto_select.clicked.connect(self._on_auto_select_features)
        self.btn_save_schema.setEnabled(False)
        self.btn_auto_select.setEnabled(False)

        config_buttons_layout.addWidget(self.btn_save_schema)
        config_buttons_layout.addWidget(self.btn_auto_select)
        config_buttons_layout.addStretch(1)

        config_layout.addRow(config_buttons_layout)

        right_layout.addWidget(config_group)
        right_layout.addStretch(1)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([400, 600])

        layout.addWidget(splitter)

        # Log area
        log_group = QGroupBox("Training Log")
        log_layout = QVBoxLayout(log_group)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText(
            "Training log will appear here...\n\n"
            "The log will show:\n"
            "• CSV file names and dataset types\n"
            "• Dataset analysis and configuration\n"
            "• Models trained and their performance\n"
            "• Learned thresholds and parameters\n"
            "• Integration status with unified AI"
        )

        log_layout.addWidget(self.log_output)
        layout.addWidget(log_group)

        # Training Feedback Panel (initially hidden)
        self.feedback_panel = TrainingFeedbackPanel()
        layout.addWidget(self.feedback_panel)

        # Status bar
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready to import training data")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch(1)

        layout.addLayout(status_layout)

    # ================== Helper methods ==================

    def _get_button_style(self, style_type: str = 'primary') -> str:
        """Get consistent button stylesheet based on style type."""
        styles = {
            'primary': """
                QPushButton {
                    background-color: #C40000;
                    color: #FFFFFF;
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
                    background-color: #A00000;
                }
                QPushButton:disabled {
                    background-color: #30363D;
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
                }
                QPushButton:disabled {
                    background-color: #161B22;
                    color: #8B949E;
                }
            """,
            'danger': """
                QPushButton {
                    background-color: #C40000;
                    color: #FFFFFF;
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
                    background-color: #A00000;
                }
                QPushButton:disabled {
                    background-color: #30363D;
                    color: #8B949E;
                }
            """,
            'success': """
                QPushButton {
                    background-color: #4CAF50;
                    color: #FFFFFF;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
                QPushButton:pressed {
                    background-color: #388E3C;
                }
                QPushButton:disabled {
                    background-color: #30363D;
                    color: #8B949E;
                }
            """,
            'warning': """
                QPushButton {
                    background-color: #FFC107;
                    color: #FFFFFF;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #FFD54F;
                }
                QPushButton:pressed {
                    background-color: #FFA000;
                }
                QPushButton:disabled {
                    background-color: #30363D;
                    color: #8B949E;
                }
            """,
            'info': """
                QPushButton {
                    background-color: #2196F3;
                    color: #FFFFFF;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #1976D2;
                }
                QPushButton:pressed {
                    background-color: #0D47A1;
                }
                QPushButton:disabled {
                    background-color: #30363D;
                    color: #8B949E;
                }
            """
        }
        return styles.get(style_type, styles['primary'])

    def _log_message(self, message: str):
        """Add a timestamped message to the log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_output.appendPlainText(f"[{timestamp}] {message}")

    def _update_dataset_list(self):
        """Update the dataset list widget"""
        self.dataset_list.clear()

        for dataset_id, dataset_info in self.datasets.items():
            status = "✓" if dataset_info.get("configured", False) else "⚙️"
            dataset_type = dataset_info.get("dataset_type", "unknown")
            rows = dataset_info.get("rows_loaded", 0)

            item_text = f"{status} {dataset_id} ({dataset_type}, {rows} rows)"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, dataset_id)

            # Color code by configuration status
            if dataset_info.get("configured", False):
                item.setBackground(QColor(ProfessionalTheme.SUCCESS))
                item.setForeground(QColor(ProfessionalTheme.BACKGROUND))
            elif dataset_type == "daily_features":
                item.setBackground(QColor(ProfessionalTheme.WARNING))

            self.dataset_list.addItem(item)

    def _on_dataset_selected(self):
        """Handle dataset selection"""
        selected_items = self.dataset_list.selectedItems()
        if not selected_items:
            self.current_dataset_id = None
            self._clear_configuration_ui()
            return

        dataset_id = selected_items[0].data(Qt.UserRole)
        self.current_dataset_id = dataset_id
        self._populate_configuration_ui(dataset_id)

    def _clear_configuration_ui(self):
        """Clear the configuration UI"""
        self.dataset_info_label.setText("No dataset selected")
        self.label_combo.clear()
        self.label_combo.setEnabled(False)
        self.feature_list.clear()
        self.feature_list.setEnabled(False)
        self.btn_save_schema.setEnabled(False)
        self.btn_auto_select.setEnabled(False)

    def _populate_configuration_ui(self, dataset_id: str):
        """Populate configuration UI for selected dataset"""
        if dataset_id not in self.datasets:
            return

        dataset_info = self.datasets[dataset_id]
        dataset_type = dataset_info.get("dataset_type", "unknown")
        analysis = dataset_info.get("analysis", {})
        rows_loaded = dataset_info.get("rows_loaded", 0)

        # Update dataset info
        self.dataset_info_label.setText(f"{dataset_id} ({dataset_type}, {rows_loaded} rows)")

        # Only allow configuration for daily_features
        if dataset_type != "daily_features":
            self.label_combo.clear()
            self.label_combo.setEnabled(False)
            self.feature_list.clear()
            self.feature_list.setEnabled(False)
            self.btn_save_schema.setEnabled(False)
            self.btn_auto_select.setEnabled(False)
            return

        self.label_combo.setEnabled(True)
        self.feature_list.setEnabled(True)
        self.btn_save_schema.setEnabled(True)
        self.btn_auto_select.setEnabled(True)

        # Populate label candidates
        self.label_combo.clear()
        label_candidates = analysis.get("label_candidates", [])
        columns_info = analysis.get("columns", [])

        # analysis["columns"] from your analyzer is a list of dicts
        # with 'name', 'dtype', etc. We only need names.
        column_names = [c["name"] if isinstance(c, dict) and "name" in c else c for c in columns_info]

        existing_label_names = [c.get("column", "") for c in label_candidates]

        for candidate in label_candidates:
            column_name = candidate.get("column", "")
            score = candidate.get("score", 0)
            if column_name:
                display_text = f"{column_name} ★" if score > 0.7 else column_name
                self.label_combo.addItem(display_text, column_name)

        # Add remaining columns
        for col in column_names:
            if col not in existing_label_names:
                self.label_combo.addItem(col, col)

        # Populate feature list
        self.feature_list.clear()
        numeric_features = analysis.get("numeric_feature_candidates", [])

        for feature in numeric_features:
            item = QListWidgetItem(feature)
            item.setCheckState(Qt.Checked)
            self.feature_list.addItem(item)

        # Add non-numeric/non-candidate columns as unchecked
        for col in column_names:
            if col not in numeric_features and col not in existing_label_names:
                item = QListWidgetItem(col)
                item.setCheckState(Qt.Unchecked)
                self.feature_list.addItem(item)

    def _on_auto_select_features(self):
        """Auto-select all numeric feature candidates"""
        if not self.current_dataset_id:
            return

        dataset_info = self.datasets[self.current_dataset_id]
        analysis = dataset_info.get("analysis", {})
        numeric_features = set(analysis.get("numeric_feature_candidates", []))

        for i in range(self.feature_list.count()):
            item = self.feature_list.item(i)
            if item.text() in numeric_features:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)

    def _on_save_schema(self):
        """Save dataset schema to predictive engine"""
        if not self.current_dataset_id:
            return

        dataset_info = self.datasets[self.current_dataset_id]
        if dataset_info.get("dataset_type") != "daily_features":
            return

        # Label
        label_index = self.label_combo.currentIndex()
        if label_index < 0:
            show_error(self, "Configuration Error", "Please select a label column")
            return

        label_column = self.label_combo.currentData()

        # Features
        feature_columns = []
        for i in range(self.feature_list.count()):
            item = self.feature_list.item(i)
            if item.checkState():
                feature_columns.append(item.text())

        if not feature_columns:
            show_error(self, "Configuration Error", "Please select at least one feature column")
            return

        try:
            result = self.predictive_engine.set_dataset_schema(
                dataset_id=self.current_dataset_id,
                label_column=label_column,
                feature_columns=feature_columns,
                task_type="classification",
                dataset_type="daily_features",
            )

            if result.get("success", False):
                self.datasets[self.current_dataset_id]["configured"] = True
                self._update_dataset_list()

                self._log_message(f"✅ Schema saved for {self.current_dataset_id}")
                self._log_message(f"   Label: {label_column}")
                self._log_message(f"   Features: {len(feature_columns)} columns")
                self.status_label.setText(f"Schema saved for {self.current_dataset_id}")
            else:
                error_msg = result.get("error", "Unknown error")
                self._log_message(f"❌ Failed to save schema: {error_msg}")
                show_error(self, "Schema Save Failed", f"Failed to save schema:\n{error_msg}")

        except Exception as e:
            self._log_message(f"❌ Error saving schema: {str(e)}")
            show_error(self, "Schema Save Error", f"Error saving schema:\n{str(e)}")

    def _on_add_csv(self):
        """Handle adding dataset (CSV or JSONL)"""
        try:
            file_paths, _ = QFileDialog.getOpenFileNames(
                self,
                "Select Dataset Files",
                os.path.expanduser("~"),
                "Data Files (*.csv *.jsonl);;CSV Files (*.csv);;Log Files (*.jsonl)"
            )

            if not file_paths:
                return

            total_files = 0
            total_rows = 0
            imported_files = []

            for file_path in file_paths:
                try:
                    dataset_type = self._auto_detect_dataset_type(file_path)

                    if not dataset_type:
                        self._log_message(f"❌ Could not detect dataset type for: {os.path.basename(file_path)}")
                        continue

                    self._log_message(f"📁 Importing {dataset_type} dataset: {os.path.basename(file_path)}")

                    if file_path.lower().endswith('.jsonl'):
                        summary = self.predictive_engine.import_training_jsonl(file_path, dataset_type)
                    else:
                        # Try to import CSV directly first
                        summary = self.predictive_engine.import_training_csv(file_path, dataset_type)

                        # Check if import failed due to column mismatch
                        if not summary.get("success", False):
                            error_msg = summary.get("error", "")

                            # Check if it's a column mismatch error
                            if "Missing required columns" in error_msg or "required columns" in error_msg.lower():
                                self._log_message(f"   ⚠️  Column mismatch detected - attempting auto-adaptation...")

                                # Use the data adapter
                                adapter = AutomotiveDataAdapter()

                                # Create adapted file
                                try:
                                    adapted_df, adapted_file = adapter.adapt_dataset(
                                        input_file=file_path,
                                        output_file=None,  # Auto-generate filename
                                        log_callback=self._log_message
                                    )

                                    if adapted_file and os.path.exists(adapted_file):
                                        self._log_message(f"   ✅ Dataset adapted successfully!")
                                        self._log_message(f"   📁 Using adapted file: {os.path.basename(adapted_file)}")

                                        # Try importing the adapted file
                                        summary = self.predictive_engine.import_training_csv(adapted_file, dataset_type)

                                        # Update file_path to point to adapted file for dataset tracking
                                        file_path = adapted_file
                                    else:
                                        self._log_message(f"   ❌ Adaptation failed - no output file created")
                                        summary = {"success": False, "error": "Adaptation produced no output"}
                                except Exception as adapter_error:
                                    self._log_message(f"   ❌ Adapter error: {str(adapter_error)}")
                                    summary = {"success": False, "error": str(adapter_error)}

                    if summary.get("success", False):
                        rows_loaded = summary.get("rows_loaded", 0)
                        dataset_id = summary.get("dataset_id", os.path.basename(file_path))
                        analysis = summary.get("analysis", {})
                        columns = summary.get("columns", [])

                        self.datasets[dataset_id] = {
                            "dataset_type": dataset_type,
                            "analysis": analysis,
                            "file_path": file_path,
                            "rows_loaded": rows_loaded,
                            "configured": False,
                        }

                        total_files += 1
                        total_rows += rows_loaded
                        imported_files.append((file_path, dataset_type, rows_loaded))

                        self._log_message(f"   ✅ Successfully loaded {rows_loaded} rows")

                        if dataset_type == "daily_features" and analysis:
                            label_candidates = analysis.get("label_candidates", [])
                            numeric_features = analysis.get("numeric_feature_candidates", [])

                            self._log_message(f"   📊 Analysis: {len(columns)} columns, {len(numeric_features)} numeric features")

                            if label_candidates:
                                top_labels = [c.get("column", "") for c in label_candidates[:3]]
                                self._log_message(f"   🎯 Top label candidates: {', '.join(top_labels)}")

                            self._log_message(f"   ⚙️ Please configure label and features for training")

                        for warning in summary.get("warnings", []):
                            self._log_message(f"   ⚠️ Warning: {warning}")
                    else:
                        error_msg = summary.get("error", "Unknown error")
                        self._log_message(f"   ❌ Failed to import: {error_msg}")

                except Exception as e:
                    self._log_message(f"❌ Error importing {os.path.basename(file_path)}: {str(e)}")

            self._update_dataset_list()

            if imported_files:
                self._log_message(f"\n📊 IMPORT SUMMARY: {total_files} files, {total_rows} total rows")
                for file_path, dataset_type, rows in imported_files:
                    self._log_message(f"   • {os.path.basename(file_path)} ({dataset_type}): {rows} rows")

                self.status_label.setText(f"Imported {total_files} datasets with {total_rows} rows")
            else:
                self._log_message("\n❌ No files were successfully imported")

        except Exception as e:
            self._log_message(f"❌ Error during CSV import: {str(e)}")

    def _auto_detect_dataset_type(self, file_path: str):
        """Auto-detect dataset type based on filename and column analysis"""
        filename = os.path.basename(file_path).lower()
        
        # JSONL logs from Android/Pi are usually raw time series data
        if filename.endswith('.jsonl'):
            return "time_series"

        if any(keyword in filename for keyword in ["daily", "day", "feature"]):
            return "daily_features"
        elif any(keyword in filename for keyword in ["time", "series", "obd", "live"]):
            return "time_series"
        elif any(keyword in filename for keyword in ["maint", "service", "repair"]):
            return "maintenance_history"

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    return None

                columns = [col.lower() for col in reader.fieldnames]

                daily_indicators = ["failure_within_7d", "failure_within_30d", "avg_rpm", "max_temp"]
                if any(indicator in ' '.join(columns) for indicator in daily_indicators):
                    return "daily_features"

                time_indicators = ["timestamp", "datetime", "rpm", "speed", "temp"]
                if any(indicator in ' '.join(columns) for indicator in time_indicators):
                    return "time_series"

                maint_indicators = ["service_date", "repair_type", "cost", "mileage"]
                if any(indicator in ' '.join(columns) for indicator in maint_indicators):
                    return "maintenance_history"

        except Exception:
            pass

        items = ["daily_features", "time_series", "maintenance_history"]
        item, ok = QInputDialog.getItem(
            self,
            "Select Dataset Type",
            f"Could not auto-detect dataset type for:\n{os.path.basename(file_path)}\n\nPlease select manually:",
            items,
            0,
            False
        )

        return item if ok else None

    def _on_train_models(self):
        """Handle manual model training with enhanced validation"""
        self._train_models()

    def _train_models(self):
        """Train models with enhanced workflow and validation"""
        try:
            configured_datasets = [
                dataset_id for dataset_id, info in self.datasets.items()
                if info.get("dataset_type") == "daily_features" and info.get("configured", False)
            ]

            if not configured_datasets:
                self._log_message("❌ No configured datasets found")
                self._log_message("   Please import daily_features datasets and configure label/feature columns first")
                self.status_label.setText("No configured datasets for training")
                return

            self._log_message("\n🎯 TRAINING MODELS...")
            self._log_message(f"   Using {len(configured_datasets)} configured dataset(s)")

            result = self.predictive_engine.train_models()

            models_trained = result.get("models_trained", [])
            metrics = result.get("metrics", {})
            samples_used = result.get("samples_used", 0)
            dataset_info = result.get("dataset_info", [])

            if not models_trained:
                self._log_message("❌ No models were trained")
                for warning in result.get("warnings", []):
                    self._log_message(f"   ⚠️ {warning}")
                self.status_label.setText("Training completed with no models")
                return

            learned = self.predictive_engine.export_learned_ai_parameters()
            self.unified_ai.update_from_predictive_engine(learned)

            self._log_message("✅ MODEL TRAINING COMPLETE")
            self._log_message(f"   Samples used: {samples_used}")
            self._log_message(f"   Models trained: {len(models_trained)}")

            for model_name in models_trained:
                model_metrics = metrics.get(model_name, {})
                accuracy = model_metrics.get("accuracy", 0.0)
                f1_score = model_metrics.get("f1", 0.0)
                self._log_message(f"   • {model_name}: Accuracy={accuracy:.3f}, F1={f1_score:.3f}")

            if dataset_info:
                self._log_message("\n📊 DATASET INFO:")
                for dataset in dataset_info:
                    dataset_id = dataset.get("dataset_id", "unknown")
                    features_count = len(dataset.get("features", []))
                    label = dataset.get("label", "unknown")
                    samples = dataset.get("samples", 0)
                    self._log_message(f"   • {dataset_id}: {label} → {features_count} features, {samples} samples")

            thresholds = learned.get("thresholds", {})
            if thresholds:
                self._log_message("\n📊 LEARNED THRESHOLDS:")
                for param, value in thresholds.items():
                    self._log_message(f"   • {param}: {value}")

            feature_importance = learned.get("feature_importances", {})
            if feature_importance:
                self._log_message("\n🔍 FEATURE IMPORTANCE:")
                for model_name, feats in feature_importance.items():
                    self._log_message(f"   • {model_name}:")
                    for feature, importance in feats.items():
                        self._log_message(f"      - {feature}: {importance:.3f}")

            self._log_message("\n✅ AI parameters applied to unified AI module")
            self.status_label.setText(f"Trained {len(models_trained)} models successfully")

            # Show training feedback panel
            self.feedback_panel.show_feedback({
                'models_trained': models_trained,
                'metrics': metrics,
                'feature_importances': feature_importance,
                'samples_used': samples_used
            })

        except Exception as e:
            self._log_message(f"❌ Error during model training: {str(e)}")
            self.status_label.setText("Training failed")
            self.feedback_panel.setVisible(False)  # Hide feedback on failure

    def _on_clear_log(self):
        """Clear the log output"""
        self.log_output.clear()
        self.status_label.setText("Log cleared")
