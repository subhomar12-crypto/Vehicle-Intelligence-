"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Predictive Failure Engine - Failure Forecasting System

Hybrid predictive engine for vehicle failure forecasting.
Uses rule-based logic + trend analysis to predict 3-7 day failure risks.
"""

import time
from typing import Dict, List, Tuple, Any, Optional
from collections import deque
import statistics
import os
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score
from sklearn.ensemble import GradientBoostingClassifier, VotingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.svm import SVC
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import cross_val_score, GridSearchCV
from sklearn.metrics import precision_score, recall_score, roc_auc_score
from sklearn.feature_selection import SelectKBest, f_classif, RFE
import xgboost as xgb
import lightgbm as lgb
import warnings
from sklearn.preprocessing import StandardScaler
import joblib
import numpy as np
import json
import shutil
from datetime import datetime, timedelta

# Import centralized configuration
try:
    from config import get_config
    CONFIG = get_config()
except ImportError:
    CONFIG = None

ADVANCED_MODEL_CONFIG = {
    'random_forest': {
        'n_estimators': 200,
        'max_depth': 15,
        'min_samples_split': 5,
        'min_samples_leaf': 2,
        'random_state': 42,
        'n_jobs': -1
    },
    'xgboost': {
        'n_estimators': 200,
        'max_depth': 8,
        'learning_rate': 0.1,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'random_state': 42,
        'n_jobs': -1
    },
    'lightgbm': {
        'n_estimators': 200,
        'max_depth': 8,
        'learning_rate': 0.1,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'random_state': 42,
        'n_jobs': -1
    },
    'neural_network': {
        'hidden_layer_sizes': (100, 50),
        'activation': 'relu',
        'solver': 'adam',
        'alpha': 0.0001,
        'learning_rate': 'adaptive',
        'max_iter': 500,
        'random_state': 42
    },
    'svm': {
        'C': 1.0,
        'kernel': 'rbf',
        'gamma': 'scale',
        'probability': True,
        'random_state': 42
    }
}


class PredictiveFailureEngine:
    """
    Hybrid predictive engine for the desktop app.

    - Uses rule-based logic + trend analysis (history)
    - Later can be extended with ML (but must already have hooks for it)
    - Predicts 3–7 day failure risk for all major vehicle systems
    - Also flags immediate risks (now/soon) when patterns look dangerous
    """

    def __init__(self):
        # Placeholder for future ML models (leave it ready)
        self.csv_models = {}  # e.g. {"ensemble": trained_model} in the future
        
        # Component risk thresholds (based on automotive engineering standards)
        self.thresholds = {
            'battery_voltage': {
                'critical_max': 16.0,  # Overcharging
                'critical_min': 11.8,
                'warning_min': 12.2,
                'normal_min': 12.6
            },
            'coolant_temp': {
                'critical_max': 110,
                'warning_max': 100,
                'normal_max': 95
            },
            'engine_load': {
                'critical_min': 90,
                'warning_min': 80,
                'normal_max': 75
            },
            'rpm': {
                'critical_min': 5000,
                'warning_min': 4000,
                'normal_max': 3500
            },
            'fuel_system': {
                'pressure_warning': 2.5,  # psi deviation from normal
            }
        }

        # ML Configuration - Uses CONFIG for portability
        if CONFIG:
            self.data_dir = str(CONFIG.AI_TRAINING_SETS_DIR)
            self.models_dir = str(CONFIG.AI_MODELS_DIR)
        else:
            # Fallback for development
            self.data_dir = os.path.join(os.path.dirname(__file__), "CSV DATASETS")
            self.models_dir = os.path.join(self.data_dir, "MODELS")
        os.makedirs(self.models_dir, exist_ok=True)

        # Storage for training data (in memory) - UPDATED: dicts instead of lists
        self.daily_frames: Dict[str, pd.DataFrame] = {}         # dataset_id -> df
        self.time_series_frames: Dict[str, pd.DataFrame] = {}   # dataset_id -> df
        self.maintenance_frames: Dict[str, pd.DataFrame] = {}   # dataset_id -> df
        
        # NEW: Dataset schemas storage
        self.dataset_schemas: Dict[str, Dict[str, Any]] = {}  # dataset_id -> {label_column, feature_columns, task_type, dataset_type}
        self.dataset_analysis: Dict[str, Dict[str, Any]] = {} # dataset_id -> analysis results

        # Trained ML models and metadata
        self.models: Dict[str, Any] = {}          # e.g. {"overall_failure_7d": model, "maintenance_30d": model}
        self.model_metadata: Dict[str, Any] = {}  # e.g. {"overall_failure_7d": {"samples": ..., "accuracy": ..., "f1": ...}}

        # Learned parameters to share with unified_ai_module
        self.learned_thresholds: Dict[str, float] = {}
        self.model_feature_importances: Dict[str, Dict[str, float]] = {}

        # Hybrid AI Engine
        self.hybrid_ai = HybridAIEngine()

        # Training cancellation flag
        self._cancel_training = False

        # Attempt to load existing models from disk at startup
        self._load_existing_models()

    def _load_existing_models(self) -> None:
        """
        Load previously trained models from self.models_dir if they exist.
        This allows using ML predictions without retraining every time.
        """
        model_files = {
            "overall_failure_7d": os.path.join(self.models_dir, "overall_failure_7d.pkl"),
            "maintenance_30d": os.path.join(self.models_dir, "maintenance_30d.pkl"),
        }

        for name, path in model_files.items():
            if os.path.isfile(path):
                try:
                    self.models[name] = joblib.load(path)
                    print(f"✅ Loaded existing model: {name}")
                except Exception as e:
                    print(f"❌ Failed to load model {name}: {e}")
                    continue
        
        # Load Hybrid AI models
        hybrid_path = os.path.join(self.models_dir, "hybrid_ai")
        if self.hybrid_ai.load_models(hybrid_path):
            print("✅ Loaded existing Hybrid AI models")

        # Advanced ML attributes (ensemble, feature engineering, etc.)
        self.advanced_models = {}
        self.model_scalers = {}
        self.feature_selectors = {}
        self.model_performance = {}
        self.ensemble_model = None
        self.feature_importance_cache = {}
        self.training_history = []
        self.model_version = "2.0"
        self.last_training_time = None
        self.prediction_cache = {}
        self.feature_engineering_enabled = True
        self.cross_validation_folds = 5
        self.model_retrain_interval = 7  # days
        self.min_training_samples = 100

        # Advanced feature engineering settings
        self.feature_settings = {
            'rolling_windows': [3, 5, 10],
            'statistical_features': True,
            'frequency_features': True,
            'correlation_features': True,
            'trend_features': True
        }

    def _get_dataset_frame(self, dataset_id: str, dataset_type: str) -> Optional[pd.DataFrame]:
        """Get DataFrame for a specific dataset ID and type."""
        if dataset_type == "daily_features":
            return self.daily_frames.get(dataset_id)
        elif dataset_type == "time_series":
            return self.time_series_frames.get(dataset_id)
        elif dataset_type == "maintenance_history":
            return self.maintenance_frames.get(dataset_id)
        return None

    def request_training_cancel(self):
        """Signal that any ongoing training loop should stop ASAP."""
        self._cancel_training = True

    def reset_training_cancel(self):
        """Reset the training cancellation flag."""
        self._cancel_training = False

    def analyze_csv_structure(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze CSV structure to suggest label and feature columns.
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            Dictionary with analysis results including:
            - columns: list of column info
            - label_candidates: suggested label columns
            - numeric_feature_candidates: suggested feature columns
        """
        try:
            df = pd.read_csv(file_path)
            return self.analyze_dataframe(df, os.path.basename(file_path))
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to read CSV: {e}",
                "columns": [],
                "label_candidates": [],
                "numeric_feature_candidates": []
            }

    def analyze_dataframe(self, df: pd.DataFrame, dataset_name: str) -> Dict[str, Any]:
        """
        Analyze DataFrame structure to suggest label and feature columns.
        
        Args:
            df: pandas DataFrame
            dataset_name: name identifier for the dataset
            
        Returns:
            Dictionary with analysis results
        """
        columns_info = []
        numeric_columns = []
        label_candidates = []
        
        # Label name hints (case insensitive)
        label_hints = [
            "fail", "fault", "error", "anomaly", "maint", "maintenance", 
            "status", "condition", "break", "outage", "defect", "problem",
            "risk", "alert", "warning", "critical", "failure", "broken",
            "target", "label", "class", "outcome", "result"
        ]
        
        # ID column hints to exclude from features
        id_hints = ["id", "ID", "udi", "UDI", "product", "Product", "serial", "Serial"]
        
        for col in df.columns:
            # Get column info
            dtype = str(df[col].dtype)
            unique_count = df[col].nunique()
            sample_values = df[col].dropna().head(3).tolist() if len(df) > 0 else []
            
            col_info = {
                "name": col,
                "dtype": dtype,
                "unique_count": int(unique_count),
                "sample_values": sample_values
            }
            columns_info.append(col_info)
            
            # Check if numeric (for feature candidates)
            if pd.api.types.is_numeric_dtype(df[col]):
                numeric_columns.append(col)
            
            # Check if potential label column
            is_potential_label = False
            label_score = 0
            
            # Score based on name hints
            col_lower = col.lower()
            for hint in label_hints:
                if hint in col_lower:
                    label_score += 2
            
            # Score based on unique values (binary or small categorical)
            if unique_count == 2:
                label_score += 3  # Perfect binary label
            elif 2 <= unique_count <= 5:
                label_score += 2  # Small categorical
            elif unique_count <= 10:
                label_score += 1  # Medium categorical
            
            # Score based on data type
            if pd.api.types.is_numeric_dtype(df[col]) and unique_count <= 10:
                label_score += 1
            elif pd.api.types.is_object_dtype(df[col]) and unique_count <= 5:
                label_score += 1
            
            if label_score >= 2:
                label_candidates.append({
                    "column": col,
                    "score": label_score,
                    "dtype": dtype,
                    "unique_count": int(unique_count),
                    "reasons": self._get_label_reasons(col, label_score, unique_count)
                })
        
        # Sort label candidates by score (descending)
        label_candidates.sort(key=lambda x: x["score"], reverse=True)
        
        # Filter numeric feature candidates (exclude IDs and potential labels)
        numeric_feature_candidates = []
        for col in numeric_columns:
            # Exclude columns that look like IDs
            is_id_column = any(hint in col.lower() for hint in id_hints)
            # Exclude high cardinality columns that might be IDs
            is_high_cardinality = df[col].nunique() > len(df) * 0.8
            
            if not is_id_column and not is_high_cardinality:
                numeric_feature_candidates.append(col)
        
        return {
            "success": True,
            "dataset_name": dataset_name,
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "columns": columns_info,
            "label_candidates": label_candidates,
            "numeric_feature_candidates": numeric_feature_candidates
        }

    def import_training_jsonl(self, file_path: str, dataset_type: str) -> Dict[str, Any]:
        """
        Import a JSONL log file (from Android/Pi sessions) for training.
        """
        dataset_id = os.path.basename(file_path)
        data_points = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if entry.get('type') == 'data_point' and 'data' in entry:
                            # Data is already flattened by MobileDataBridge
                            row = entry['data']
                            if 'timestamp' not in row and 'timestamp' in entry:
                                row['timestamp'] = entry['timestamp']
                            data_points.append(row)
                    except:
                        continue
            
            if not data_points:
                return {"success": False, "error": "No valid data points found in log file", "dataset_id": dataset_id}
                
            df = pd.DataFrame(data_points)
            
            # Store based on type
            if dataset_type == "daily_features":
                self.daily_frames[dataset_id] = df
            elif dataset_type == "time_series":
                self.time_series_frames[dataset_id] = df
            elif dataset_type == "maintenance_history":
                self.maintenance_frames[dataset_id] = df
                
            # Analyze
            analysis = self.analyze_dataframe(df, dataset_id)
            self.dataset_analysis[dataset_id] = analysis
            
            return {"success": True, "dataset_type": dataset_type, "rows_loaded": len(df), "columns": list(df.columns), "analysis": analysis, "warnings": [], "dataset_id": dataset_id}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to import JSONL: {e}", "dataset_id": dataset_id}

    def _get_label_reasons(self, column: str, score: int, unique_count: int) -> List[str]:
        """Generate reasons why a column is a good label candidate."""
        reasons = []
        
        # Name-based reasons
        label_hints = [
            "fail", "fault", "error", "anomaly", "maint", "maintenance", 
            "status", "condition", "break", "outage", "defect", "problem",
            "risk", "alert", "warning", "critical", "failure", "broken"
        ]
        
        col_lower = column.lower()
        for hint in label_hints:
            if hint in col_lower:
                reasons.append(f"Name contains '{hint}'")
                break
        
        # Value-based reasons
        if unique_count == 2:
            reasons.append("Binary values (perfect for classification)")
        elif 2 <= unique_count <= 5:
            reasons.append(f"Small number of categories ({unique_count})")
        elif unique_count <= 10:
            reasons.append(f"Reasonable number of categories ({unique_count})")
        
        return reasons

    def import_training_csv(self, file_path: str, dataset_type: str) -> Dict[str, Any]:
        """
        Import a CSV file and add it to the training pool.

        Args:
            file_path: Full path to a CSV file
            dataset_type: One of:
                - "daily_features"
                - "time_series"
                - "maintenance_history"

        Behavior:
            - Load CSV via pandas.read_csv
            - Validate required columns based on dataset_type
            - Drop obviously broken rows (e.g. all NaNs in critical columns)
            - Append DataFrame to internal storage:
                self.daily_frames / self.time_series_frames / self.maintenance_frames

        Returns:
            {
              "success": True/False,
              "dataset_type": str,
              "rows_loaded": int,
              "columns": list[str],
              "analysis": analysis_results,
              "warnings": list[str],
              "dataset_id": str
            }
        """
        warnings: List[str] = []
        dataset_id = os.path.basename(file_path)

        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to read CSV: {e}",
                "dataset_type": dataset_type,
                "rows_loaded": 0,
                "columns": [],
                "warnings": warnings,
                "dataset_id": dataset_id
            }

        # NEW: Flexible handling for daily_features - no fixed required columns
        if dataset_type == "daily_features":
            # Basic cleaning: drop rows where all values are NaN
            df = df.dropna(how='all')
            
            if df.empty:
                return {
                    "success": False,
                    "error": "No valid rows after cleaning",
                    "dataset_type": dataset_type,
                    "rows_loaded": 0,
                    "columns": list(df.columns),
                    "warnings": warnings,
                    "dataset_id": dataset_id
                }

            # UPDATED: Store by dataset_id instead of appending to list
            self.daily_frames[dataset_id] = df
            
            # Store analysis results
            analysis_result = self.analyze_dataframe(df, dataset_id)
            self.dataset_analysis[dataset_id] = analysis_result
            
            return {
                "success": True,
                "dataset_type": dataset_type,
                "rows_loaded": int(len(df)),
                "columns": list(df.columns),
                "analysis": analysis_result,
                "warnings": warnings,
                "dataset_id": dataset_id
            }

        # Keep existing strict validation for other dataset types
        elif dataset_type == "time_series":
            required = [
                "timestamp",
                "vehicle_id",
                "rpm",
                "speed_kmh",
                "coolant_temp_c",
                "engine_load_pct",
                "battery_voltage_v",
                "overall_failure_7d",
            ]
        elif dataset_type == "maintenance_history":
            required = [
                "vehicle_id",
                "event_date",
                "component",
                "event_type",
                "failed_within_7d",
            ]
        else:
            return {
                "success": False,
                "error": f"Unknown dataset_type: {dataset_type}",
                "dataset_type": dataset_type,
                "rows_loaded": 0,
                "columns": list(df.columns),
                "warnings": warnings,
                "dataset_id": dataset_id
            }

        missing = [c for c in required if c not in df.columns]
        if missing:
            error_msg = f"Missing required columns: {missing}"
            return {
                "success": False,
                "error": error_msg,
                "dataset_type": dataset_type,
                "rows_loaded": 0,
                "columns": list(df.columns),
                "warnings": warnings,
                "dataset_id": dataset_id
            }

        # Basic cleaning: drop rows where all required columns are NaN
        df = df.dropna(subset=required, how="all")

        if df.empty:
            error_msg = "No valid rows after cleaning"
            return {
                "success": False,
                "error": error_msg,
                "dataset_type": dataset_type,
                "rows_loaded": 0,
                "columns": list(df.columns),
                "warnings": warnings,
                "dataset_id": dataset_id
            }

        # UPDATED: Store by dataset_id instead of appending to list
        if dataset_type == "time_series":
            self.time_series_frames[dataset_id] = df
        elif dataset_type == "maintenance_history":
            self.maintenance_frames[dataset_id] = df

        return {
            "success": True,
            "dataset_type": dataset_type,
            "rows_loaded": int(len(df)),
            "columns": list(df.columns),
            "warnings": warnings,
            "dataset_id": dataset_id
        }

    def set_dataset_schema(self, dataset_id: str, label_column: str, 
                          feature_columns: List[str], 
                          task_type: str = "classification", 
                          dataset_type: str = "daily_features") -> Dict[str, Any]:
        """
        Store user-selected schema for a dataset.
        
        Args:
            dataset_id: Identifier for the dataset (usually filename)
            label_column: Column name to use as label/target
            feature_columns: List of column names to use as features
            task_type: Type of ML task ("classification" or "regression")
            dataset_type: Type of dataset
            
        Returns:
            Dictionary with success status and any validation messages
        """
        # UPDATED: Use helper method to get the right DataFrame
        target_frame = self._get_dataset_frame(dataset_id, dataset_type)
        if target_frame is None:
            return {"success": False, "error": f"No dataset found for id={dataset_id}, type={dataset_type}"}
        
        # Validate columns exist
        if label_column not in target_frame.columns:
            return {"success": False, "error": f"Label column '{label_column}' not found in dataset"}
        
        missing_features = [col for col in feature_columns if col not in target_frame.columns]
        if missing_features:
            return {"success": False, "error": f"Feature columns not found: {missing_features}"}
        
        # Store schema
        self.dataset_schemas[dataset_id] = {
            "label_column": label_column,
            "feature_columns": feature_columns,
            "task_type": task_type,
            "dataset_type": dataset_type,
            "dataset_size": len(target_frame)
        }
        
        return {
            "success": True,
            "message": f"Schema set for {dataset_id}: label={label_column}, features={len(feature_columns)}",
            "schema": self.dataset_schemas[dataset_id]
        }

    def train_models(self) -> Dict[str, Any]:
        """
        Train ML models using all imported datasets with configured schemas.

        Steps:
          1. Find all datasets with stored schemas
          2. Combine data from compatible datasets
          3. Train models using the configured label and feature columns
          4. Save models and metadata
        """
        if not self.dataset_schemas:
            return {
                "models_trained": [],
                "metrics": {},
                "samples_used": 0,
                "warnings": ["No datasets with configured schemas found"]
            }

        trained_models = {}
        metrics = {}
        total_samples = 0
        dataset_info = []
        
        for dataset_id, schema in self.dataset_schemas.items():
            # Check for cancellation
            if self._cancel_training:
                print("⚠️ Training cancelled by user")
                break
                
            # UPDATED: Use helper method to get the right DataFrame
            df = self._get_dataset_frame(dataset_id, schema["dataset_type"])
            if df is None:
                continue

            # Extract features and label
            X = df[schema["feature_columns"]].copy()
            y = df[schema["label_column"]].copy()
            
            # Drop rows with missing label
            valid_mask = y.notna()
            X = X[valid_mask]
            y = y[valid_mask]
            
            if X.empty:
                continue

            # Clean feature data
            X_clean = X.fillna(X.median(numeric_only=True))
            
            # Convert label to numeric if needed
            if not pd.api.types.is_numeric_dtype(y):
                y = pd.factorize(y)[0]  # Convert categorical to numeric
            
            # Train/test split
            X_train, X_test, y_train, y_test = train_test_split(
                X_clean, y, test_size=0.2, random_state=42, stratify=y
            )
            
            model_name = f"custom_model_{dataset_id}"
            
            try:
                # Train model
                model = RandomForestClassifier(
                    n_estimators=100,  # Reduced for faster training
                    random_state=42,
                    n_jobs=-1,
                )
                model.fit(X_train, y_train)
                
                # Evaluate
                y_pred = model.predict(X_test)
                acc = accuracy_score(y_test, y_pred)
                f1 = f1_score(y_test, y_pred, zero_division=0)
                
                # Store model and metadata
                self.models[model_name] = model
                self.model_metadata[model_name] = {
                    "samples": int(len(X_train)),
                    "accuracy": float(acc),
                    "f1": float(f1),
                    "features": schema["feature_columns"],
                    "label": schema["label_column"],
                    "dataset_id": dataset_id
                }
                
                # Store feature importances
                self.model_feature_importances[model_name] = {
                    col: float(imp) for col, imp in zip(schema["feature_columns"], model.feature_importances_)
                }
                
                # Save model to disk
                joblib.dump(model, os.path.join(self.models_dir, f"{model_name}.pkl"))
                
                trained_models[model_name] = {
                    "accuracy": float(acc),
                    "f1": float(f1)
                }
                total_samples += len(X_clean)
                
                # Also train the legacy "overall_failure_7d" model if we have appropriate data
                if "failure" in schema["label_column"].lower() or "fail" in schema["label_column"].lower():
                    legacy_model_name = "overall_failure_7d"
                    self.models[legacy_model_name] = model
                    self.model_metadata[legacy_model_name] = self.model_metadata[model_name].copy()
                    joblib.dump(model, os.path.join(self.models_dir, f"{legacy_model_name}.pkl"))
                    trained_models[legacy_model_name] = trained_models[model_name]
                
                dataset_info.append({
                    "dataset_id": dataset_id,
                    "samples": len(X_clean),
                    "features": schema["feature_columns"],
                    "label": schema["label_column"]
                })
                
            except Exception as e:
                print(f"Error training model for {dataset_id}: {e}")
                continue
        
        # Derive learned thresholds from successful training data
        if dataset_info:
            # UPDATED: Combine data from all datasets
            combined_frames = []
            for info in dataset_info:
                dataset_id = info["dataset_id"]
                schema = self.dataset_schemas[dataset_id]
                df = self._get_dataset_frame(dataset_id, schema["dataset_type"])
                if df is not None:
                    combined_frames.append(df[info["features"]])
            
            if combined_frames:
                combined_df = pd.concat(combined_frames, ignore_index=True)
                for col in combined_df.columns:
                    if "coolant" in col.lower() or "temp" in col.lower():
                        self.learned_thresholds["coolant_critical"] = float(combined_df[col].quantile(0.9))
                        self.learned_thresholds["coolant_warning"] = float(combined_df[col].quantile(0.75))
                    elif "battery" in col.lower() or "voltage" in col.lower():
                        self.learned_thresholds["battery_critical"] = float(combined_df[col].quantile(0.1))
                        self.learned_thresholds["battery_warning"] = float(combined_df[col].quantile(0.25))
                    elif "load" in col.lower():
                        self.learned_thresholds["engine_load_danger"] = float(combined_df[col].quantile(0.9))

        return {
            "models_trained": list(trained_models.keys()),
            "metrics": trained_models,
            "samples_used": total_samples,
            "dataset_info": dataset_info
        }

    def train_hybrid_ai(self) -> Dict[str, Any]:
        """
        Train the Hybrid AI Engine with available data.
        
        Returns:
            Dictionary with training results
        """
        # Collect all available time series data for hybrid AI training
        all_time_series_data = []
        all_labels = []
        
        # Use time series frames for hybrid AI training
        for df in self.time_series_frames.values():
            # Extract relevant features for hybrid AI
            hybrid_features = ['rpm', 'engine_load_pct', 'coolant_temp_c', 'battery_voltage_v']
            available_features = [f for f in hybrid_features if f in df.columns]
            
            if available_features and len(df) > 0:
                # Use failure labels if available
                labels = None
                if 'overall_failure_7d' in df.columns:
                    labels = df['overall_failure_7d']
                
                all_time_series_data.append(df[available_features])
                if labels is not None:
                    all_labels.append(labels)
        
        if not all_time_series_data:
            return {
                "success": False,
                "message": "No time series data available for hybrid AI training",
                "samples_used": 0
            }
        
        # Combine all time series data
        combined_data = pd.concat(all_time_series_data, ignore_index=True)
        combined_labels = pd.concat(all_labels, ignore_index=True) if all_labels else None
        
        # Train hybrid AI
        try:
            self.hybrid_ai.train_hybrid_models(combined_data, combined_labels)
            
            return {
                "success": True,
                "message": "Hybrid AI models trained successfully",
                "samples_used": len(combined_data),
                "features_used": list(combined_data.columns),
                "has_supervised": self.hybrid_ai.has_supervised
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Hybrid AI training failed: {e}",
                "samples_used": 0
            }

    def export_learned_ai_parameters(self) -> Dict[str, Any]:
        """
        Export learned thresholds, feature importances, and model metadata
        so unified_ai_module can use them.
        """
        return {
            "thresholds": dict(self.learned_thresholds),
            "feature_importances": dict(self.model_feature_importances),
            "models": {
                name: {
                    "trained": True,
                    "metadata": self.model_metadata.get(name, {}),
                }
                for name in self.models.keys()
            },
        }

    def export_model_package(self, target_dir: str) -> Dict[str, Any]:
        """
        Export all trained models + learned parameters into a portable AI package.

        Steps:
          - Create target_dir if missing
          - Copy all .pkl models from self.models_dir to target_dir
          - Create ai_metadata.json containing:
                thresholds
                model_metadata
                feature_importances
                export timestamp

        Returns:
          {
            "export_path": target_dir,
            "models_copied": [...],
            "metadata_file": "ai_metadata.json"
          }
        """
        os.makedirs(target_dir, exist_ok=True)
        
        models_copied = []
        
        # Copy all model files
        for model_name in self.models.keys():
            source_path = os.path.join(self.models_dir, f"{model_name}.pkl")
            target_path = os.path.join(target_dir, f"{model_name}.pkl")
            
            if os.path.exists(source_path):
                shutil.copy2(source_path, target_path)
                models_copied.append(model_name)
        
        # Create metadata file
        metadata = {
            "thresholds": dict(self.learned_thresholds),
            "model_metadata": dict(self.model_metadata),
            "feature_importances": dict(self.model_feature_importances),
            "export_timestamp": datetime.now().isoformat(),
            "models_copied": models_copied
        }
        
        metadata_file = os.path.join(target_dir, "ai_metadata.json")
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return {
            "export_path": target_dir,
            "models_copied": models_copied,
            "metadata_file": "ai_metadata.json"
        }

    def get_model_info(self) -> Dict[str, Any]:
        """
        Return status of loaded models for diagnostics or UI.
        """
        return {
            "models": {
                name: {
                    "metadata": self.model_metadata.get(name, {}),
                    "feature_importances": self.model_feature_importances.get(name, {}),
                }
                for name in self.models.keys()
            },
            "thresholds": dict(self.learned_thresholds),
            "dataset_schemas": self.dataset_schemas,
        }

    def export_model_to_onnx(self, model_name: str, onnx_path: str) -> Dict[str, Any]:
        """
        Export a trained scikit-learn model to ONNX for fast inference.
        Requires skl2onnx to be installed.
        """
        try:
            from skl2onnx import convert_sklearn
            from skl2onnx.common.data_types import FloatTensorType

            model = self.models.get(model_name)
            if model is None:
                return {"success": False, "error": f"Model '{model_name}' not found"}

            first_metadata = self.model_metadata.get(model_name, {})
            n_features = len(first_metadata.get("features", []))
            initial_type = [('float_input', FloatTensorType([None, n_features]))]

            onnx_model = convert_sklearn(model, initial_types=initial_type)
            with open(onnx_path, "wb") as f:
                f.write(onnx_model.SerializeToString())

            return {"success": True, "path": onnx_path}
        except ImportError:
            return {"success": False, "error": "Install skl2onnx to use ONNX export"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_training_job_to_cloud(self, api_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Stub for future: send training job to cloud server."""
        try:
            import requests
            resp = requests.post(api_url, json=payload, timeout=60)
            return resp.json()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _compute_max_coolant(self, history: list, latest_data: dict) -> float:
        """Compute max coolant temperature from history and latest data"""
        if not history:
            return float(latest_data.get('coolant_temp', 85))
        
        coolant_values = [h.get('coolant_temp', 85) for h in history]
        coolant_values.append(latest_data.get('coolant_temp', 85))
        return float(max(coolant_values))

    def _compute_min_battery(self, history: list, latest_data: dict) -> float:
        """Compute min battery voltage from history and latest data"""
        if not history:
            return float(latest_data.get('battery_voltage', 12.6))
        
        battery_values = [h.get('battery_voltage', 12.6) for h in history]
        battery_values.append(latest_data.get('battery_voltage', 12.6))
        return float(min(battery_values))

    def predict_from_csv_model(self, features: dict, model_name: str = "ensemble"):
        """
        For future integration with ML models.

        Args:
            features: dict[str, float] – feature_name -> value
            model_name: which model to use inside self.csv_models

        Returns:
            (prediction, probability, explanation)

            prediction: int 0=GOOD, 1=WARNING, 2=CRITICAL
            probability: float 0.0–1.0
            explanation: short human-readable string

        For now, implements simple heuristic based on key features.
        """
        # Simple heuristic-based prediction (to be replaced with ML)
        risk_score = 0
        risk_factors = []
        
        # Battery voltage analysis
        voltage = features.get('battery_voltage', features.get('voltage', 12.6))
        if voltage < self.thresholds['battery_voltage']['critical_min']:
            risk_score += 2
            risk_factors.append("Critical battery voltage")
        elif voltage < self.thresholds['battery_voltage']['warning_min']:
            risk_score += 1
            risk_factors.append("Low battery voltage")
            
        # Coolant temperature analysis
        coolant_temp = features.get('coolant_temp', features.get('coolant', 85))
        if coolant_temp > self.thresholds['coolant_temp']['critical_max']:
            risk_score += 2
            risk_factors.append("Critical coolant temperature")
        elif coolant_temp > self.thresholds['coolant_temp']['warning_max']:
            risk_score += 1
            risk_factors.append("High coolant temperature")
            
        # Engine load analysis
        engine_load = features.get('engine_load', features.get('load', 50))
        if engine_load > self.thresholds['engine_load']['critical_min']:
            risk_score += 2
            risk_factors.append("Critical engine load")
        elif engine_load > self.thresholds['engine_load']['warning_min']:
            risk_score += 1
            risk_factors.append("High engine load")
            
        # Determine final prediction
        if risk_score >= 3:
            prediction = 2  # CRITICAL
            probability = min(0.95, 0.6 + (risk_score - 3) * 0.1)
        elif risk_score >= 1:
            prediction = 1  # WARNING
            probability = min(0.8, 0.3 + risk_score * 0.2)
        else:
            prediction = 0  # GOOD
            probability = 0.1
            
        explanation = " | ".join(risk_factors) if risk_factors else "All systems normal"
        
        return prediction, probability, explanation
        
    def _validate_input_data(self, data: dict) -> Tuple[bool, List[str]]:
        """
        Sanity check input data to prevent AI hallucinations on sensor glitches.
        Returns (is_valid, list_of_issues)
        """
        issues = []
        
        # Physical impossibility checks
        if data.get('rpm', 0) > 10000:
            issues.append("RPM sensor glitch (>10k)")
        if data.get('battery_voltage', 0) > 18.0:
            issues.append("Voltage sensor glitch (>18V)")
        if data.get('coolant_temp', 0) > 150:
            issues.append("Temp sensor glitch (>150C)")
        if data.get('coolant_temp', 0) < -50:
            issues.append("Temp sensor glitch (<-50C)")
            
        return len(issues) == 0, issues

    def analyze_failure_risk(
        self,
        vehicle_profile: dict,
        latest_data: dict,
        history: list[dict],
        horizon_days: tuple[int, int] = (3, 7),
    ) -> dict:
        """
        Main API used by the desktop Failure Forecast tab.

        Inputs:
            vehicle_profile: dict with basic info (make, model, year, etc.). Can be empty.
            latest_data: MOST RECENT live snapshot from OBD (dict of PIDs -> values).
            history: list of recent historical snapshots (each like latest_data, plus timestamp if available).
            horizon_days: 2-tuple, default (3, 7) = forecast window.

        Output:
            A dict with structured risk assessment, failure predictions, and expert insights.
        """
        # 1. Data Sanity Check (Reliability Layer)
        current_values_raw = self._extract_parameters(latest_data)
        is_valid, data_issues = self._validate_input_data(current_values_raw)
        
        if not is_valid:
            return {
                "risk_assessment": {"overall_risk": "UNKNOWN", "score": 0, "probability": 0.0},
                "failure_predictions": {},
                "expert_insights": [f"⚠️ Analysis paused: {issue}" for issue in data_issues],
                "hybrid_ai_analysis": {"ai_status": "Data Error", "risk_score": 0.0}
            }

        # Extract and normalize data
        current_values = self._extract_parameters(latest_data)
        historical_values = [self._extract_parameters(h) for h in history if h]
        
        # Calculate component risks
        component_risks = self._assess_component_risks(current_values, historical_values, horizon_days)
        
        # Calculate overall risk
        overall_risk = self._calculate_overall_risk(component_risks)
        
        # Generate expert insights
        expert_insights = self._generate_expert_insights(component_risks, current_values, historical_values)
        
        # ML Integration - NEW: Combine ML predictions with rule-based logic
        ml_risk_data = self._get_ml_risk_prediction(current_values, historical_values, latest_data, history)
        
        # Hybrid AI Integration - NEW: Get hybrid AI risk assessment
        hybrid_risk_data = self.hybrid_ai.predict_hybrid_risk(current_values)
        
        if ml_risk_data and "probability" in ml_risk_data:
            # Combine ML probability with rule-based probability
            ml_prob = ml_risk_data["probability"]
            rule_prob = overall_risk.get("probability", 0.1)
            
            # Use weighted average (favor ML if available)
            combined_prob = (ml_prob * 0.7) + (rule_prob * 0.3)
            overall_risk["probability"] = float(combined_prob)
            
            # Update risk level based on combined probability
            if combined_prob >= 0.75:
                overall_risk["overall_risk"] = "🔴 CRITICAL"
            elif combined_prob >= 0.6:
                overall_risk["overall_risk"] = "🟠 HIGH"
            elif combined_prob >= 0.4:
                overall_risk["overall_risk"] = "🟡 MEDIUM"
            elif combined_prob >= 0.2:
                overall_risk["overall_risk"] = "🔵 LOW"
            else:
                overall_risk["overall_risk"] = "🟢 NORMAL"
            
            # Add ML insights to expert insights
            if ml_risk_data.get("explanation"):
                expert_insights.insert(0, f"🤖 ML Insight: {ml_risk_data['explanation']}")
        
        # Add Hybrid AI insights
        if hybrid_risk_data["ai_status"] == "Active":
            hybrid_insight = f"🧠 Hybrid AI: {hybrid_risk_data['risk_status']} "
            hybrid_insight += f"(Anomaly: {hybrid_risk_data['anomaly_score']}, "
            hybrid_insight += f"Failure: {hybrid_risk_data['known_failure_prob']})"
            expert_insights.insert(0, hybrid_insight)
            
            # If hybrid AI detects high risk but traditional methods don't, escalate
            if (hybrid_risk_data["risk_status"] in ["WARNING", "CRITICAL"] and 
                overall_risk["overall_risk"] in ["🟢 NORMAL", "🔵 LOW"]):
                overall_risk["overall_risk"] = "🟡 MEDIUM"
                overall_risk["probability"] = max(overall_risk["probability"], 0.5)
                expert_insights.insert(0, "⚠️ AI Alert: Anomaly detected in system behavior")
        
        return {
            "risk_assessment": overall_risk,
            "failure_predictions": component_risks,
            "expert_insights": expert_insights,
            "hybrid_ai_analysis": hybrid_risk_data
        }

    def _get_ml_risk_prediction(self, current: dict, history: list, latest_data: dict, full_history: list) -> Optional[Dict[str, Any]]:
        """Get ML-based risk prediction if models are available"""
        if "overall_failure_7d" not in self.models:
            return None

        try:
            meta = self.model_metadata.get("overall_failure_7d", {})
            feature_cols = meta.get("features", [])
            
            if not feature_cols:
                return None

            # Build feature vector from current data and history
            feature_vector = []
            for col in feature_cols:
                if col == "max_coolant_temp_c":
                    value = self._compute_max_coolant(full_history, latest_data)
                elif col == "min_battery_voltage_v":
                    value = self._compute_min_battery(full_history, latest_data)
                elif col == "avg_coolant_temp_c":
                    # Use current coolant temp as approximation
                    value = float(current.get('coolant_temp', 85))
                elif col == "pct_time_high_load":
                    # Estimate from history
                    if full_history:
                        high_load_count = sum(1 for h in full_history if h.get('engine_load', 0) > 80)
                        value = (high_load_count / len(full_history)) * 100
                    else:
                        value = 0.0
                elif col == "pct_time_high_coolant":
                    # Estimate from history
                    if full_history:
                        high_coolant_count = sum(1 for h in full_history if h.get('coolant_temp', 0) > 95)
                        value = (high_coolant_count / len(full_history)) * 100
                    else:
                        value = 0.0
                elif col == "dtc_events_today":
                    # Assume no DTC events for real-time prediction
                    value = 0
                else:
                    # Try to get from current data with fallback
                    value = float(current.get(col, 0.0))
                feature_vector.append(value)

            X_current = np.array([feature_vector])
            p_fail = self.models["overall_failure_7d"].predict_proba(X_current)[0, 1]
            
            # Generate explanation based on feature importances
            explanation_parts = []
            importances = self.model_feature_importances.get("overall_failure_7d", {})
            
            for feature, importance in sorted(importances.items(), key=lambda x: x[1], reverse=True)[:2]:
                if importance > 0.1:  # Only mention significant contributors
                    idx = feature_cols.index(feature)
                    value = feature_vector[idx]
                    explanation_parts.append(f"{feature}: {value:.1f}")
            
            explanation = f"Failure probability {p_fail:.1%}"
            if explanation_parts:
                explanation += f" (key factors: {', '.join(explanation_parts)})"
            
            return {
                "probability": float(p_fail),
                "explanation": explanation
            }
            
        except Exception as e:
            print(f"ML prediction error: {e}")
            return None

    def _extract_parameters(self, data: dict) -> dict:
        """Extract and normalize parameters from raw OBD data."""
        extracted = {}
        
        # Battery voltage (multiple possible keys)
        extracted['battery_voltage'] = float(data.get('battery_voltage') or 
                                           data.get('voltage') or 
                                           data.get('battery') or 
                                           data.get('0142', 12.6))
        
        # Coolant temperature  
        extracted['coolant_temp'] = float(data.get('coolant_temp') or 
                                        data.get('coolant') or 
                                        data.get('engine_coolant_temp') or 
                                        data.get('0105', 85))
        
        # Engine load
        extracted['engine_load'] = float(data.get('engine_load') or 
                                       data.get('calculated_engine_load') or 
                                       data.get('load') or 
                                       data.get('0104', 50))
        
        # RPM
        extracted['rpm'] = float(data.get('rpm') or 
                               data.get('engine_rpm') or 
                               data.get('010C', 800))
        
        # Vehicle speed
        extracted['speed'] = float(data.get('speed') or 
                                 data.get('vehicle_speed') or 
                                 data.get('010D', 0))
        
        # Fuel level
        extracted['fuel_level'] = float(data.get('fuel_level') or 
                                      data.get('fuel_level_input') or 
                                      data.get('012F', 50))
        
        # Intake air temperature
        extracted['intake_temp'] = float(data.get('intake_air_temp') or 
                                       data.get('010F', 25))
        
        # MAF rate
        extracted['maf_rate'] = float(data.get('maf_rate') or 
                                    data.get('0110', 0))
        
        return extracted

    def _assess_component_risks(self, current: dict, history: list, horizon_days: tuple) -> dict:
        """Assess risks for all major vehicle components."""
        return {
            "engine": self._assess_engine_risk(current, history, horizon_days),
            "battery": self._assess_battery_risk(current, history, horizon_days),
            "cooling_system": self._assess_cooling_risk(current, history, horizon_days),
            "electrical_system": self._assess_electrical_risk(current, history, horizon_days),
            "transmission": self._assess_transmission_risk(current, history, horizon_days),
            "fuel_system": self._assess_fuel_risk(current, history, horizon_days),
            "braking_system": self._assess_braking_risk(current, history, horizon_days),
            "turbo_or_intake": self._assess_turbo_risk(current, history, horizon_days),
            "sensors": self._assess_sensor_risk(current, history, horizon_days),
        }

    def _assess_engine_risk(self, current: dict, history: list, horizon_days: tuple) -> dict:
        """Assess engine failure risk."""
        risk_level = "LOW"
        probability = 0.1
        signals = []
        actions = []
        immediate_risk = False
        
        # Use learned thresholds if available
        load_danger = self.learned_thresholds.get("engine_load_danger", 90.0)
        
        # High load analysis
        if current['engine_load'] > load_danger:
            risk_level = "CRITICAL"
            probability = 0.85
            signals.append(f"Engine load critically high ({current['engine_load']:.0f}%)")
            actions.append("Reduce engine load immediately - avoid hard acceleration")
            immediate_risk = True
        elif current['engine_load'] > self.thresholds['engine_load']['warning_min']:
            if risk_level != "CRITICAL":
                risk_level = "HIGH"
                probability = 0.65
            signals.append(f"Sustained high engine load ({current['engine_load']:.0f}%)")
            actions.append("Monitor engine load patterns and reduce aggressive driving")
        
        # RPM pattern analysis
        if current['rpm'] > self.thresholds['rpm']['critical_min']:
            if risk_level != "CRITICAL":
                risk_level = "HIGH"
                probability = max(probability, 0.7)
            signals.append(f"Critical RPM level ({current['rpm']:.0f} RPM)")
            actions.append("Avoid redline RPM operation")
            immediate_risk = True
        elif current['rpm'] > self.thresholds['rpm']['warning_min']:
            if risk_level not in ["CRITICAL", "HIGH"]:
                risk_level = "MEDIUM"
                probability = max(probability, 0.5)
            signals.append(f"High RPM operation ({current['rpm']:.0f} RPM)")
            actions.append("Shift to lower gear to reduce RPM")
        
        # Temperature correlation
        coolant_warn = self.learned_thresholds.get("coolant_warning", 100.0)
        if (current['engine_load'] > 80 and 
            current['coolant_temp'] > coolant_warn):
            risk_level = "HIGH"
            probability = max(probability, 0.75)
            signals.append("High load with elevated coolant temperature")
            actions.append("Allow engine to cool down before further operation")
        
        # Trend analysis from history
        if len(history) > 10:
            recent_loads = [h['engine_load'] for h in history[-10:]]
            if statistics.mean(recent_loads) > 75:
                risk_level = "MEDIUM" if risk_level == "LOW" else risk_level
                probability = max(probability, 0.4)
                signals.append("Consistently high engine load in recent operation")
        
        return {
            "risk_level": risk_level,
            "probability": probability,
            "horizon_days": list(horizon_days),
            "immediate_risk": immediate_risk,
            "signals": signals,
            "recommended_actions": actions
        }

    def _assess_battery_risk(self, current: dict, history: list, horizon_days: tuple) -> dict:
        """Assess battery failure risk."""
        risk_level = "LOW"
        probability = 0.1
        signals = []
        actions = []
        immediate_risk = False
        
        voltage = current['battery_voltage']
        
        # Use learned thresholds if available
        batt_crit = self.learned_thresholds.get("battery_critical", 11.8)
        batt_warn = self.learned_thresholds.get("battery_warning", 12.2)
        
        # Voltage threshold analysis
        if voltage < batt_crit:
            risk_level = "CRITICAL"
            probability = 0.9
            signals.append(f"Critical battery voltage ({voltage:.1f}V)")
            actions.append("Immediate battery replacement required")
            actions.append("Test alternator output")
            immediate_risk = True
        elif voltage < batt_warn:
            risk_level = "HIGH"
            probability = 0.7
            signals.append(f"Low battery voltage ({voltage:.1f}V)")
            actions.append("Battery load test recommended within 3 days")
            actions.append("Check charging system")
        
        # Overvoltage protection
        elif voltage > self.thresholds['battery_voltage']['critical_max']:
            risk_level = "CRITICAL"
            probability = 0.8
            signals.append(f"Overcharging detected ({voltage:.1f}V)")
            actions.append("Immediate alternator/regulator inspection")
            immediate_risk = True
        
        # Trend analysis
        if len(history) > 5:
            recent_voltages = [h['battery_voltage'] for h in history[-5:]]
            min_voltage = min(recent_voltages)
            voltage_trend = self._calculate_trend(recent_voltages)
            
            if voltage_trend < -0.1:  # Decreasing trend
                risk_level = "MEDIUM" if risk_level == "LOW" else risk_level
                probability = max(probability, 0.5)
                signals.append("Battery voltage showing decreasing trend")
                actions.append("Monitor voltage during engine start")
        
        return {
            "risk_level": risk_level,
            "probability": probability,
            "horizon_days": list(horizon_days),
            "immediate_risk": immediate_risk,
            "signals": signals,
            "recommended_actions": actions
        }

    def _assess_cooling_risk(self, current: dict, history: list, horizon_days: tuple) -> dict:
        """Assess cooling system failure risk."""
        risk_level = "LOW"
        probability = 0.1
        signals = []
        actions = []
        immediate_risk = False
        
        temp = current['coolant_temp']
        
        # Use learned thresholds if available
        coolant_crit = self.learned_thresholds.get("coolant_critical", 110.0)
        coolant_warn = self.learned_thresholds.get("coolant_warning", 100.0)
        
        # Temperature threshold analysis
        if temp > coolant_crit:
            risk_level = "CRITICAL"
            probability = 0.95
            signals.append(f"Critical coolant temperature ({temp:.0f}°C)")
            actions.append("Stop engine immediately to prevent damage")
            actions.append("Check coolant level and circulation")
            immediate_risk = True
        elif temp > coolant_warn:
            risk_level = "HIGH"
            probability = 0.75
            signals.append(f"High coolant temperature ({temp:.0f}°C)")
            actions.append("Monitor temperature closely")
            actions.append("Inspect radiator and cooling fans")
        
        # Trend analysis
        if len(history) > 8:
            recent_temps = [h['coolant_temp'] for h in history[-8:]]
            max_temp = max(recent_temps)
            temp_trend = self._calculate_trend(recent_temps)
            
            if temp_trend > 0.5:  # Rising trend
                risk_level = "MEDIUM" if risk_level == "LOW" else risk_level
                probability = max(probability, 0.6)
                signals.append("Coolant temperature showing rising trend")
                actions.append("Check thermostat operation")
            
            if max_temp > coolant_warn:
                risk_level = "MEDIUM" if risk_level == "LOW" else risk_level
                probability = max(probability, 0.55)
                signals.append("Recent high temperature events detected")
        
        return {
            "risk_level": risk_level,
            "probability": probability,
            "horizon_days": list(horizon_days),
            "immediate_risk": immediate_risk,
            "signals": signals,
            "recommended_actions": actions
        }

    def _assess_electrical_risk(self, current: dict, history: list, horizon_days: tuple) -> dict:
        """Assess electrical system risk (primarily based on battery analysis)."""
        battery_risk = self._assess_battery_risk(current, history, horizon_days)
        
        # Electrical system inherits battery risk but with different focus
        risk_level = battery_risk["risk_level"]
        probability = battery_risk["probability"] * 0.8  # Slightly lower probability for general electrical
        
        signals = battery_risk["signals"].copy()
        actions = [
            "Check alternator belt tension",
            "Inspect electrical connections",
            "Test voltage regulator"
        ]
        
        # Add electrical-specific signals
        voltage = current['battery_voltage']
        if 13.5 < voltage < 14.5:
            signals.append("Charging system operating normally")
        elif voltage > 14.5:
            signals.append("Possible voltage regulator issue")
            risk_level = "MEDIUM" if risk_level == "LOW" else risk_level
            probability = max(probability, 0.5)
        
        return {
            "risk_level": risk_level,
            "probability": probability,
            "horizon_days": list(horizon_days),
            "immediate_risk": battery_risk["immediate_risk"],
            "signals": signals,
            "recommended_actions": actions
        }

    def _assess_transmission_risk(self, current: dict, history: list, horizon_days: tuple) -> dict:
        """Assess transmission failure risk."""
        risk_level = "LOW"
        probability = 0.1
        signals = []
        actions = []
        immediate_risk = False
        
        # Transmission risk based on driving patterns
        high_rpm_count = sum(1 for h in history if h['rpm'] > self.thresholds['rpm']['warning_min'])
        high_load_count = sum(1 for h in history if h['engine_load'] > self.thresholds['engine_load']['warning_min'])
        
        if high_rpm_count > len(history) * 0.3:  # 30% of time at high RPM
            risk_level = "MEDIUM"
            probability = 0.5
            signals.append("Frequent high-RPM operation detected")
            actions.append("Consider more gradual acceleration")
        
        if high_load_count > len(history) * 0.4:  # 40% of time at high load
            risk_level = "MEDIUM" if risk_level == "LOW" else "HIGH"
            probability = max(probability, 0.6)
            signals.append("Sustained high engine load affecting transmission")
            actions.append("Allow transmission to cool during extended driving")
        
        # Current high load + RPM combination
        if (current['engine_load'] > 85 and current['rpm'] > 3500):
            risk_level = "HIGH"
            probability = max(probability, 0.7)
            signals.append("High stress on transmission system")
            actions.append("Avoid aggressive shifting under load")
        
        return {
            "risk_level": risk_level,
            "probability": probability,
            "horizon_days": list(horizon_days),
            "immediate_risk": immediate_risk,
            "signals": signals,
            "recommended_actions": actions
        }

    def _assess_fuel_risk(self, current: dict, history: list, horizon_days: tuple) -> dict:
        """Assess fuel system risk."""
        risk_level = "LOW"
        probability = 0.1
        signals = []
        actions = ["Regular fuel system maintenance recommended"]
        
        fuel_level = current['fuel_level']
        
        if fuel_level < 15:
            risk_level = "MEDIUM"
            probability = 0.4
            signals.append("Low fuel level may affect fuel pump cooling")
            actions.append("Maintain fuel level above 1/4 tank")
        
        # Basic fuel system monitoring
        if len(history) > 5:
            fuel_levels = [h['fuel_level'] for h in history[-5:]]
            if any(level < 10 for level in fuel_levels):
                risk_level = "MEDIUM"
                probability = 0.45
                signals.append("Frequent operation with very low fuel")
        
        return {
            "risk_level": risk_level,
            "probability": probability,
            "horizon_days": list(horizon_days),
            "immediate_risk": False,
            "signals": signals,
            "recommended_actions": actions
        }

    def _assess_braking_risk(self, current: dict, history: list, horizon_days: tuple) -> dict:
        """Assess braking system risk (limited data from OBD)."""
        # Braking system has limited OBD parameters, so conservative assessment
        risk_level = "LOW"
        probability = 0.05
        signals = ["Brake system monitoring requires additional sensors"]
        actions = ["Regular brake inspection recommended", "Check brake fluid level"]
        
        return {
            "risk_level": risk_level,
            "probability": probability,
            "horizon_days": list(horizon_days),
            "immediate_risk": False,
            "signals": signals,
            "recommended_actions": actions
        }

    def _assess_turbo_risk(self, current: dict, history: list, horizon_days: tuple) -> dict:
        """Assess turbocharger/intake system risk."""
        risk_level = "LOW"
        probability = 0.1
        signals = []
        actions = []
        
        # Turbo risk based on intake temperature and load patterns
        intake_temp = current['intake_temp']
        maf_rate = current['maf_rate']
        
        if intake_temp > 60:  # High intake air temperature
            risk_level = "MEDIUM"
            probability = 0.5
            signals.append(f"High intake air temperature ({intake_temp:.0f}°C)")
            actions.append("Check intercooler efficiency")
        
        if maf_rate > 200 and current['engine_load'] > 80:  # High airflow under load
            risk_level = "MEDIUM"
            probability = 0.55
            signals.append("High mass airflow under heavy load")
            actions.append("Allow turbo to cool after hard driving")
        
        return {
            "risk_level": risk_level,
            "probability": probability,
            "horizon_days": list(horizon_days),
            "immediate_risk": False,
            "signals": signals,
            "recommended_actions": actions
        }

    def _assess_sensor_risk(self, current: dict, history: list, horizon_days: tuple) -> dict:
        """Assess sensor system risk based on data consistency."""
        risk_level = "LOW"
        probability = 0.1
        signals = []
        actions = ["Regular sensor diagnostics recommended"]
        
        # Check for sensor outliers or inconsistent readings
        if len(history) > 3:
            coolant_temps = [h['coolant_temp'] for h in history[-3:]]
            voltage_readings = [h['battery_voltage'] for h in history[-3:]]
            
            coolant_std = statistics.stdev(coolant_temps) if len(coolant_temps) > 1 else 0
            voltage_std = statistics.stdev(voltage_readings) if len(voltage_readings) > 1 else 0
            
            if coolant_std > 10:  # High temperature variation
                risk_level = "MEDIUM"
                probability = 0.4
                signals.append("Unusual coolant temperature fluctuations")
                actions.append("Inspect coolant temperature sensor")
            
            if voltage_std > 0.8:  # High voltage variation
                risk_level = "MEDIUM"
                probability = 0.45
                signals.append("Voltage reading instability")
                actions.append("Check electrical connections and sensors")
        
        return {
            "risk_level": risk_level,
            "probability": probability,
            "horizon_days": list(horizon_days),
            "immediate_risk": False,
            "signals": signals,
            "recommended_actions": actions
        }

    def _calculate_overall_risk(self, component_risks: dict) -> dict:
        """Calculate overall vehicle risk based on component assessments."""
        risk_weights = {
            "CRITICAL": 4,
            "HIGH": 3,
            "MEDIUM": 2,
            "LOW": 1
        }
        
        # Calculate weighted risk score
        total_weight = 0
        max_possible = 0
        
        for component, risk_data in component_risks.items():
            weight = risk_weights[risk_data["risk_level"]]
            total_weight += weight
            max_possible += 4  # Maximum weight per component
        
        overall_score = (total_weight / max_possible) * 100 if max_possible > 0 else 0
        
        # Determine overall risk level
        if overall_score >= 75:
            risk_level = "🔴 CRITICAL"
            probability = 0.85
        elif overall_score >= 60:
            risk_level = "🟠 HIGH"
            probability = 0.65
        elif overall_score >= 40:
            risk_level = "🟡 MEDIUM"
            probability = 0.45
        elif overall_score >= 20:
            risk_level = "🔵 LOW"
            probability = 0.25
        else:
            risk_level = "🟢 NORMAL"
            probability = 0.1
        
        return {
            "overall_risk": risk_level,
            "score": int(overall_score),
            "probability": probability,
            "horizon_days": [3, 7]
        }

    def _calculate_trend(self, values: list) -> float:
        """Calculate simple linear trend from values."""
        if len(values) < 2:
            return 0.0
        
        try:
            x = list(range(len(values)))
            slope = statistics.covariance(x, values) / statistics.variance(x) if statistics.variance(x) > 0 else 0
            return slope
        except:
            return 0.0

    def _generate_expert_insights(self, component_risks: dict, current: dict, history: list) -> list:
        """Generate expert insights based on risk assessment and patterns."""
        insights = []
        
        # Critical risks first
        critical_components = [comp for comp, risk in component_risks.items() 
                             if risk["risk_level"] in ["CRITICAL", "HIGH"]]
        
        if critical_components:
            insights.append(f"⚠ HIGH PRIORITY — Focus on {', '.join(critical_components)} systems")
        
        # Battery insights
        batt_risk = component_risks["battery"]
        if batt_risk["risk_level"] in ["CRITICAL", "HIGH"]:
            insights.append("⚠ Battery voltage instability detected - possible charging system failure")
        
        # Cooling system insights
        cool_risk = component_risks["cooling_system"]
        if cool_risk["risk_level"] in ["CRITICAL", "HIGH"]:
            insights.append("🚨 Cooling system operating at dangerous temperatures - immediate attention required")
        
        # Engine insights
        engine_risk = component_risks["engine"]
        if engine_risk["risk_level"] in ["CRITICAL", "HIGH"]:
            insights.append("⚙️ Engine operating under extreme conditions - reduce load to prevent damage")
        
        # General maintenance insights
        if len(history) > 20:
            avg_load = statistics.mean([h['engine_load'] for h in history[-20:]])
            if avg_load > 70:
                insights.append("📊 Driving pattern shows consistently high engine load - consider smoother acceleration")
        
        # Add positive insights when risks are low
        low_risk_count = sum(1 for risk in component_risks.values() if risk["risk_level"] == "LOW")
        if low_risk_count >= 6:
            insights.append("✅ Majority of systems operating within normal parameters")
        
        # Ensure we have at least some insights
        if not insights:
            insights.append("📈 System monitoring active - all parameters within expected ranges")
            insights.append("🔍 Continue regular operation with scheduled maintenance")
        
        return insights


# --- ADDED FOR HYBRID AI CAPABILITIES ---
class HybridAIEngine:
    """
    Hybrid Brain: Combines Rule-based, Random Forest (Supervised), 
    and Isolation Forest (Unsupervised/Anomaly Detection).
    """
    def __init__(self):
        self.rf_model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.iso_model = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
        self.scaler = StandardScaler()
        self.is_fitted = False
        self.has_supervised = False
        
    def save_models(self, path_prefix: str):
        """Save hybrid models to disk"""
        if self.is_fitted:
            try:
                joblib.dump(self.rf_model, f"{path_prefix}_rf.pkl")
                joblib.dump(self.iso_model, f"{path_prefix}_iso.pkl")
                joblib.dump(self.scaler, f"{path_prefix}_scaler.pkl")
            except Exception as e:
                print(f"Error saving hybrid models: {e}")
            
    def load_models(self, path_prefix: str) -> bool:
        """Load hybrid models from disk"""
        try:
            if os.path.exists(f"{path_prefix}_rf.pkl"):
                self.rf_model = joblib.load(f"{path_prefix}_rf.pkl")
                self.iso_model = joblib.load(f"{path_prefix}_iso.pkl")
                self.scaler = joblib.load(f"{path_prefix}_scaler.pkl")
                self.is_fitted = True
                # Assume supervised capability if RF model exists
                self.has_supervised = True 
                return True
        except Exception as e:
            print(f"Error loading hybrid models: {e}")
        return False
        
    def train_hybrid_models(self, historical_data_df, labels=None):
        """
        historical_data_df: DataFrame of sensor readings (RPM, Load, Temp, etc.)
        labels: Optional Series of failure labels (0=Good, 1=Fail) for Random Forest.
        """
        # Select numeric features for AI
        features = ['rpm', 'engine_load', 'coolant_temp', 'battery_voltage', 'intake_temp', 'maf_rate']
        available_features = [f for f in features if f in historical_data_df.columns]
        
        if not available_features:
            print("⚠️ No compatible features found for Hybrid AI training")
            return

        valid_data = historical_data_df[available_features].dropna()
        
        if len(valid_data) < 50:
            print("⚠️ Not enough data to train Hybrid AI (Need 50+ samples)")
            return

        X = self.scaler.fit_transform(valid_data)

        # 1. Train Isolation Forest (Unsupervised - learns "Normal")
        self.iso_model.fit(X)
        
        # 2. Train Random Forest (Supervised - learns "Patterns")
        if labels is not None and len(labels) == len(valid_data):
            valid_labels = labels.iloc[valid_data.index]  # Align labels with valid data
            self.rf_model.fit(X, valid_labels)
            self.has_supervised = True
        else:
            self.has_supervised = False
            
        self.is_fitted = True
        print("✅ Hybrid AI Models Trained (Isolation Forest + Random Forest)")

    def predict_hybrid_risk(self, current_snapshot: dict) -> dict:
        """
        Returns a risk assessment combining Anomaly Score and Failure Probability.
        """
        if not self.is_fitted:
            return {"ai_status": "Not Trained", "risk_score": 0.0}

        # Prepare input vector using available features
        features = ['rpm', 'engine_load', 'coolant_temp', 'battery_voltage', 'intake_temp', 'maf_rate']
        available_features = [f for f in features if f in current_snapshot]
        
        if not available_features:
            return {"ai_status": "No Features", "risk_score": 0.0}

        vector = np.array([[current_snapshot.get(f, 0) for f in features]])
        vector_scaled = self.scaler.transform(vector)

        # 1. Anomaly Detection (Isolation Forest)
        # decision_function: lower = more anomalous. We invert it for a "Risk Score".
        anomaly_score = -1 * self.iso_model.decision_function(vector_scaled)[0]
        # Normalize roughly to 0-1 (positive values are anomalies)
        anomaly_risk = 1.0 if anomaly_score > 0 else 0.0 

        # 2. Failure Prediction (Random Forest)
        known_failure_prob = 0.0
        if self.has_supervised:
            # Class 1 is "Failure"
            known_failure_prob = self.rf_model.predict_proba(vector_scaled)[0][1]

        # 3. Hybrid Logic
        # If specific failure is detected, trust RF. 
        # If RF is low but Anomaly is high, flag as "Unknown System Stress".
        total_risk = max(known_failure_prob, anomaly_risk * 0.8) # Anomaly is slightly weighted down
        
        status = "Normal"
        if total_risk > 0.8: 
            status = "CRITICAL"
        elif total_risk > 0.5: 
            status = "WARNING"
        
        return {
            "ai_status": "Active",
            "anomaly_score": round(float(anomaly_score), 4),
            "known_failure_prob": round(float(known_failure_prob), 4),
            "total_risk_score": round(float(total_risk), 4),
            "risk_status": status,
            "description": "Anomaly Detected" if anomaly_risk > known_failure_prob and status != "Normal" else "Known Failure Pattern"
        }

    def engineer_advanced_features(self, df):
        """Engineer advanced features from raw vehicle data."""
        try:
            if df is None or df.empty:
                return df

            engineered_df = df.copy()

            # Time-based features
            if 'timestamp' in engineered_df.columns:
                engineered_df['timestamp'] = pd.to_datetime(engineered_df['timestamp'])
                engineered_df['hour'] = engineered_df['timestamp'].dt.hour
                engineered_df['day_of_week'] = engineered_df['timestamp'].dt.dayofweek
                engineered_df['month'] = engineered_df['timestamp'].dt.month
                engineered_df['quarter'] = engineered_df['timestamp'].dt.quarter
                engineered_df['is_weekend'] = (engineered_df['timestamp'].dt.dayofweek >= 5).astype(int)

                # Cyclical encoding for time features
                engineered_df['hour_sin'] = np.sin(2 * np.pi * engineered_df['hour'] / 24)
                engineered_df['hour_cos'] = np.cos(2 * np.pi * engineered_df['hour'] / 24)
                engineered_df['day_sin'] = np.sin(2 * np.pi * engineered_df['day_of_week'] / 7)
                engineered_df['day_cos'] = np.cos(2 * np.pi * engineered_df['day_of_week'] / 7)

            # Rolling window features
            for col in ['rpm', 'speed', 'coolant_temp', 'battery_voltage', 'engine_load']:
                if col in engineered_df.columns:
                    for window in self.feature_settings.get('rolling_windows', [3, 5, 10]):
                        engineered_df[f'{col}_rolling_mean_{window}'] = engineered_df[col].rolling(window=window, min_periods=1).mean()
                        engineered_df[f'{col}_rolling_std_{window}'] = engineered_df[col].rolling(window=window, min_periods=1).std()
                        engineered_df[f'{col}_rolling_min_{window}'] = engineered_df[col].rolling(window=window, min_periods=1).min()
                        engineered_df[f'{col}_rolling_max_{window}'] = engineered_df[col].rolling(window=window, min_periods=1).max()
                        engineered_df[f'{col}_rolling_range_{window}'] = engineered_df[f'{col}_rolling_max_{window}'] - engineered_df[f'{col}_rolling_min_{window}']

            # Statistical features
            if self.feature_settings.get('statistical_features', True):
                for col in ['rpm', 'speed', 'coolant_temp', 'battery_voltage', 'engine_load']:
                    if col in engineered_df.columns:
                        col_mean = engineered_df[col].mean()
                        col_std = engineered_df[col].std()
                        if col_std and col_std > 0:
                            engineered_df[f'{col}_zscore'] = (engineered_df[col] - col_mean) / col_std

                        engineered_df[f'{col}_percentile_25'] = engineered_df[col].rolling(window=50, min_periods=1).quantile(0.25)
                        engineered_df[f'{col}_percentile_75'] = engineered_df[col].rolling(window=50, min_periods=1).quantile(0.75)

            # Ratio and interaction features
            if 'rpm' in engineered_df.columns and 'speed' in engineered_df.columns:
                engineered_df['rpm_speed_ratio'] = engineered_df['rpm'] / (engineered_df['speed'] + 1)
                engineered_df['rpm_speed_product'] = engineered_df['rpm'] * engineered_df['speed']

            if 'coolant_temp' in engineered_df.columns and 'intake_temp' in engineered_df.columns:
                engineered_df['temp_diff'] = engineered_df['coolant_temp'] - engineered_df['intake_temp']
                engineered_df['temp_ratio'] = engineered_df['coolant_temp'] / (engineered_df['intake_temp'] + 1)

            if 'engine_load' in engineered_df.columns and 'rpm' in engineered_df.columns:
                engineered_df['load_rpm_interaction'] = engineered_df['engine_load'] * engineered_df['rpm'] / 1000.0

            # Change rate features
            for col in ['rpm', 'speed', 'coolant_temp', 'battery_voltage']:
                if col in engineered_df.columns:
                    engineered_df[f'{col}_change_rate'] = engineered_df[col].diff()
                    engineered_df[f'{col}_pct_change'] = engineered_df[col].pct_change()

            # Performance efficiency features
            if 'engine_load' in engineered_df.columns and 'speed' in engineered_df.columns:
                engineered_df['efficiency_score'] = engineered_df['speed'] / (engineered_df['engine_load'] + 1)

            if 'fuel_consumption' in engineered_df.columns and 'speed' in engineered_df.columns:
                engineered_df['fuel_efficiency'] = engineered_df['speed'] / (engineered_df['fuel_consumption'] + 1)

            engineered_df = engineered_df.fillna(method='ffill').fillna(0)
            return engineered_df

        except Exception as e:
            print(f"Error in feature engineering: {e}")
            return df

    def select_best_features(self, X, y, method: str = 'univariate', k: int = 20):
        """Select best features for model training."""
        try:
            if X is None or y is None or X.empty:
                return list(X.columns) if X is not None else [], None

            if method == 'univariate':
                selector = SelectKBest(score_func=f_classif, k=min(k, X.shape[1]))
                selector.fit(X, y)
                selected_features = X.columns[selector.get_support()].tolist()

            elif method == 'rfe':
                rf = RandomForestClassifier(n_estimators=100, random_state=42)
                selector = RFE(estimator=rf, n_features_to_select=min(k, X.shape[1]))
                selector.fit(X, y)
                selected_features = X.columns[selector.get_support()].tolist()

            elif method == 'importance':
                rf = RandomForestClassifier(n_estimators=100, random_state=42)
                rf.fit(X, y)
                importance_scores = rf.feature_importances_
                feature_importance = dict(zip(X.columns, importance_scores))
                selected_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:k]
                selected_features = [f[0] for f in selected_features]
                selector = rf
            else:
                return list(X.columns), None

            return selected_features, selector

        except Exception as e:
            print(f"Error in feature selection: {e}")
            return list(X.columns), None

    def _prepare_advanced_training_data(self, training_data, target_column: str):
        """Prepare data for advanced model training."""
        try:
            if isinstance(training_data, list):
                df = pd.DataFrame(training_data)
            else:
                df = training_data.copy()

            if df is None or df.empty:
                return None, None

            if target_column not in df.columns:
                df[target_column] = self._create_synthetic_target(df)

            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            if target_column not in numeric_cols:
                numeric_cols.append(target_column)

            feature_cols = [c for c in numeric_cols if c != target_column]
            X = df[feature_cols]
            y = df[target_column]

            X = X.fillna(X.median(numeric_only=True))
            y = y.fillna(0)

            if X.shape[1] > 1:
                selector = SelectKBest(score_func=f_classif, k='all')
                selector.fit(X, y)
                mask = selector.get_support()
                X = X.loc[:, mask]

            return X, y

        except Exception as e:
            print(f"Error preparing training data: {e}")
            return None, None

    def _create_synthetic_target(self, df: pd.DataFrame):
        """Create synthetic target variable when no explicit label is present."""
        try:
            conditions = []

            if 'coolant_temp' in df.columns:
                conditions.append(df['coolant_temp'] > 105)
            if 'battery_voltage' in df.columns:
                conditions.append(df['battery_voltage'] < 11.5)
            if 'engine_load' in df.columns:
                conditions.append(df['engine_load'] > 90)
            if 'rpm' in df.columns:
                conditions.append(df['rpm'] > 5000)
            if 'oil_pressure' in df.columns:
                conditions.append(df['oil_pressure'] < 15)

            if conditions:
                failure_condition = conditions[0]
                for cond in conditions[1:]:
                    failure_condition = failure_condition | cond
                return failure_condition.astype(int)
            else:
                return pd.Series([0] * len(df))

        except Exception as e:
            print(f"Error creating synthetic target: {e}")
            return pd.Series([0] * len(df))

    def _evaluate_model(self, model, X_test, y_test):
        """Evaluate model performance on test data."""
        try:
            if X_test is None or X_test.shape[0] == 0:
                return {
                    'accuracy': 0.0,
                    'f1': 0.0,
                    'precision': 0.0,
                    'recall': 0.0,
                    'auc': 0.0,
                }

            y_pred = model.predict(X_test)
            y_proba = model.predict_proba(X_test) if hasattr(model, 'predict_proba') else None

            accuracy = accuracy_score(y_test, y_pred)
            f1 = f1_score(y_test, y_pred, average='weighted')
            precision = precision_score(y_test, y_pred, average='weighted', zero_division=0)
            recall = recall_score(y_test, y_pred, average='weighted', zero_division=0)

            auc = 0.0
            if y_proba is not None and len(np.unique(y_test)) == 2:
                try:
                    auc = roc_auc_score(y_test, y_proba[:, 1])
                except Exception:
                    auc = 0.0

            return {
                'accuracy': float(accuracy),
                'f1': float(f1),
                'precision': float(precision),
                'recall': float(recall),
                'auc': float(auc),
            }

        except Exception as e:
            print(f"Error evaluating model: {e}")
            return {
                'accuracy': 0.0,
                'f1': 0.0,
                'precision': 0.0,
                'recall': 0.0,
                'auc': 0.0,
            }

    def _calculate_ensemble_feature_importance(self, models: dict, selected_features: list):
        """Calculate average feature importance across tree-based models."""
        try:
            feature_importance = {}
            tree_models = ['random_forest', 'xgboost', 'lightgbm']

            for name in tree_models:
                model = models.get(name)
                if model is not None and hasattr(model, 'feature_importances_'):
                    importances = model.feature_importances_
                    for i, feat in enumerate(selected_features):
                        if i < len(importances):
                            feature_importance.setdefault(feat, []).append(importances[i])

            averaged = {}
            for feat, vals in feature_importance.items():
                if vals:
                    averaged[feat] = float(np.mean(vals))

            return averaged

        except Exception as e:
            print(f"Error calculating ensemble feature importance: {e}")
            return {}

    def train_advanced_ensemble(self, training_data, target_column: str = 'failure_within_7d'):
        """Train advanced ensemble model for failure prediction."""
        try:
            print("🚀 Training advanced ensemble model...")
            start_time = time.time()

            X, y = self._prepare_advanced_training_data(training_data, target_column)
            if X is None or y is None:
                return {'success': False, 'error': 'Insufficient training data'}

            X_engineered = self.engineer_advanced_features(X)

            selected_features, feature_selector = self.select_best_features(
                X_engineered, y, k=min(30, X_engineered.shape[1])
            )
            X_selected = X_engineered[selected_features]

            X_train, X_test, y_train, y_test = train_test_split(
                X_selected, y, test_size=0.2, random_state=42, stratify=y
            )

            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            models = {}
            model_performance = {}

            rf_model = RandomForestClassifier(**ADVANCED_MODEL_CONFIG['random_forest'])
            rf_model.fit(X_train_scaled, y_train)
            models['random_forest'] = rf_model
            model_performance['random_forest'] = self._evaluate_model(rf_model, X_test_scaled, y_test)

            xgb_model = xgb.XGBClassifier(**ADVANCED_MODEL_CONFIG['xgboost'])
            xgb_model.fit(X_train_scaled, y_train)
            models['xgboost'] = xgb_model
            model_performance['xgboost'] = self._evaluate_model(xgb_model, X_test_scaled, y_test)

            lgb_model = lgb.LGBMClassifier(**ADVANCED_MODEL_CONFIG['lightgbm'])
            lgb_model.fit(X_train_scaled, y_train)
            models['lightgbm'] = lgb_model
            model_performance['lightgbm'] = self._evaluate_model(lgb_model, X_test_scaled, y_test)

            nn_model = MLPClassifier(**ADVANCED_MODEL_CONFIG['neural_network'])
            nn_model.fit(X_train_scaled, y_train)
            models['neural_network'] = nn_model
            model_performance['neural_network'] = self._evaluate_model(nn_model, X_test_scaled, y_test)

            svm_model = SVC(**ADVANCED_MODEL_CONFIG['svm'])
            svm_model.fit(X_train_scaled, y_train)
            models['svm'] = svm_model
            model_performance['svm'] = self._evaluate_model(svm_model, X_test_scaled, y_test)

            ensemble_model = VotingClassifier(
                estimators=[
                    ('rf', models['random_forest']),
                    ('xgb', models['xgboost']),
                    ('lgb', models['lightgbm']),
                    ('nn', models['neural_network']),
                ],
                voting='soft',
            )
            ensemble_model.fit(X_train_scaled, y_train)
            models['ensemble'] = ensemble_model
            model_performance['ensemble'] = self._evaluate_model(ensemble_model, X_test_scaled, y_test)

            self.advanced_models = models
            self.model_scalers['ensemble'] = scaler
            self.feature_selectors['ensemble'] = feature_selector
            self.model_performance = model_performance
            self.last_training_time = datetime.now()

            feature_importance = self._calculate_ensemble_feature_importance(models, selected_features)
            self.feature_importance_cache = feature_importance

            training_record = {
                'timestamp': self.last_training_time.isoformat(),
                'model_type': 'advanced_ensemble',
                'samples': int(len(X_train)),
                'features': int(len(selected_features)),
                'performance': model_performance,
            }
            self.training_history.append(training_record)

            training_time = time.time() - start_time

            results = {
                'success': True,
                'training_time': float(training_time),
                'samples_used': int(len(X_train)),
                'features_used': int(len(selected_features)),
                'selected_features': selected_features,
                'model_performance': model_performance,
                'feature_importance': feature_importance,
                'ensemble_accuracy': model_performance['ensemble']['accuracy'],
                'ensemble_f1': model_performance['ensemble']['f1'],
                'ensemble_auc': model_performance['ensemble']['auc'],
            }

            print(f"✅ Advanced ensemble trained in {training_time:.2f}s")
            print(f"📊 Ensemble Accuracy: {results['ensemble_accuracy']:.3f}")
            print(f"📊 Ensemble F1: {results['ensemble_f1']:.3f}")
            print(f"📊 Ensemble AUC: {results['ensemble_auc']:.3f}")

            return results

        except Exception as e:
            print(f"❌ Error training advanced ensemble: {e}")
            return {'success': False, 'error': str(e)}

    def predict_with_advanced_ensemble(self, current_data, historical_data=None):
        """Make predictions using advanced ensemble model."""
        try:
            if 'ensemble' not in self.advanced_models:
                return self._fallback_prediction(current_data)

            features_df = self._prepare_advanced_prediction_features(current_data, historical_data)
            if features_df is None or features_df.empty:
                return self._fallback_prediction(current_data)

            features_engineered = self.engineer_advanced_features(features_df)

            if 'ensemble' in self.feature_selectors and self.feature_selectors['ensemble'] is not None:
                selector = self.feature_selectors['ensemble']
                if hasattr(selector, 'get_support'):
                    mask = selector.get_support()
                    selected_cols = [c for c, m in zip(features_engineered.columns, mask) if m]
                    features_selected = features_engineered[selected_cols]
                else:
                    features_selected = features_engineered
            else:
                features_selected = features_engineered

            if 'ensemble' in self.model_scalers:
                scaler = self.model_scalers['ensemble']
                features_scaled = scaler.transform(features_selected)
            else:
                features_scaled = features_selected

            ensemble_model = self.advanced_models['ensemble']
            prediction = int(ensemble_model.predict(features_scaled)[0])

            if hasattr(ensemble_model, 'predict_proba'):
                probabilities = ensemble_model.predict_proba(features_scaled)[0]
            else:
                probabilities = np.array([0.0, 1.0]) if prediction == 1 else np.array([1.0, 0.0])

            confidence = float(probabilities.max())
            explanation = self._generate_advanced_explanation(features_selected, prediction, probabilities)

            individual_predictions = {}
            for name, model in self.advanced_models.items():
                if name == 'ensemble':
                    continue
                try:
                    pred = int(model.predict(features_scaled)[0])
                    if hasattr(model, 'predict_proba'):
                        proba = model.predict_proba(features_scaled)[0]
                        conf = float(proba.max())
                        probs_list = proba.tolist()
                    else:
                        conf = 0.0
                        probs_list = [0.0, 0.0]
                    individual_predictions[name] = {
                        'prediction': pred,
                        'confidence': conf,
                        'probabilities': probs_list,
                    }
                except Exception:
                    individual_predictions[name] = {
                        'prediction': 0,
                        'confidence': 0.0,
                        'probabilities': [0.0, 0.0],
                    }

            return {
                'prediction': prediction,
                'confidence': confidence,
                'probabilities': probabilities.tolist(),
                'explanation': explanation,
                'individual_predictions': individual_predictions,
                'model_type': 'advanced_ensemble',
                'feature_count': int(features_selected.shape[1]),
                'prediction_timestamp': datetime.now().isoformat(),
            }

        except Exception as e:
            print(f"Error in advanced prediction: {e}")
            return self._fallback_prediction(current_data)

    def _prepare_advanced_prediction_features(self, current_data, historical_data=None):
        """Prepare features for advanced prediction."""
        try:
            if isinstance(current_data, dict):
                df = pd.DataFrame([current_data])
            else:
                df = current_data.copy()

            if historical_data:
                hist_df = pd.DataFrame(historical_data)
                for col in ['rpm', 'speed', 'coolant_temp', 'battery_voltage', 'engine_load']:
                    if col in hist_df.columns:
                        recent = hist_df[col].tail(5)
                        df[f'{col}_recent_avg'] = recent.mean()
                        df[f'{col}_recent_std'] = recent.std()

            return df

        except Exception as e:
            print(f"Error preparing prediction features: {e}")
            return None

    def _generate_advanced_explanation(self, features_df, prediction: int, probabilities):
        """Generate human-readable explanation for advanced prediction."""
        try:
            parts = []

            if prediction == 0:
                parts.append("System operating normally")
            elif prediction == 1:
                parts.append("Warning: Potential issues detected")
            else:
                parts.append("Critical: Immediate attention required")

            confidence = float(probabilities.max())
            if confidence > 0.8:
                parts.append("High confidence prediction")
            elif confidence > 0.6:
                parts.append("Moderate confidence prediction")
            else:
                parts.append("Low confidence prediction")

            if getattr(self, 'feature_importance_cache', None):
                top_features = sorted(
                    self.feature_importance_cache.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:3]

                contrib = []
                for feat, imp in top_features:
                    if feat in features_df.columns:
                        val = features_df[feat].iloc[0]
                        try:
                            contrib.append(f"{feat}: {float(val):.2f}")
                        except Exception:
                            contrib.append(f"{feat}: {val}")
                if contrib:
                    parts.append("Key factors: " + ", ".join(contrib))

            return " | ".join(parts)

        except Exception:
            return f"Prediction: {prediction} with {float(probabilities.max()):.2%} confidence"

    def _fallback_prediction(self, current_data: dict):
        """Fallback rule-based prediction when ML models are unavailable."""
        try:
            risk_score = 0

            if current_data.get('coolant_temp', 0) > 100:
                risk_score += 2
            if current_data.get('battery_voltage', 12.6) < 12.0:
                risk_score += 2
            if current_data.get('engine_load', 0) > 85:
                risk_score += 1
            if current_data.get('rpm', 0) > 4000:
                risk_score += 1

            if risk_score >= 3:
                prediction = 2
                confidence = 0.8
            elif risk_score >= 1:
                prediction = 1
                confidence = 0.6
            else:
                prediction = 0
                confidence = 0.7

            return {
                'prediction': prediction,
                'confidence': confidence,
                'explanation': f"Rule-based prediction: risk_score={risk_score}",
                'model_type': 'rule_based_fallback',
                'prediction_timestamp': datetime.now().isoformat(),
            }

        except Exception as e:
            return {
                'prediction': 0,
                'confidence': 0.5,
                'explanation': f"Prediction error: {str(e)}",
                'model_type': 'error',
            }

    def save_advanced_models(self, model_dir: str = None):
        if CONFIG:
            model_dir = model_dir if model_dir else str(CONFIG.AI_MODELS_DIR)
        else:
            model_dir = model_dir if model_dir else os.path.join(os.path.dirname(__file__), "CSV DATASETS", "MODELS")
        """Save advanced models, scalers, selectors, and metadata to disk."""
        try:
            os.makedirs(model_dir, exist_ok=True)

            for name, model in self.advanced_models.items():
                model_path = os.path.join(model_dir, f"advanced_{name}.pkl")
                joblib.dump(model, model_path)

            scaler_path = os.path.join(model_dir, "advanced_scalers.pkl")
            joblib.dump(self.model_scalers, scaler_path)

            selector_path = os.path.join(model_dir, "advanced_selectors.pkl")
            joblib.dump(self.feature_selectors, selector_path)

            metadata = {
                'model_version': self.model_version,
                'last_training_time': self.last_training_time.isoformat() if self.last_training_time else None,
                'model_performance': self.model_performance,
                'feature_importance': self.feature_importance_cache,
                'training_history': self.training_history[-10:],
                'feature_settings': self.feature_settings,
            }

            metadata_path = os.path.join(model_dir, "advanced_metadata.json")
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Save Hybrid AI models
            hybrid_path = os.path.join(model_dir, "hybrid_ai")
            self.hybrid_ai.save_models(hybrid_path)

            print(f"✅ Advanced models saved to {model_dir}")
            return True

        except Exception as e:
            print(f"❌ Error saving advanced models: {e}")
            return False

    def load_advanced_models(self, model_dir: str = None):
        if CONFIG:
            model_dir = model_dir if model_dir else str(CONFIG.AI_MODELS_DIR)
        else:
            model_dir = model_dir if model_dir else os.path.join(os.path.dirname(__file__), "CSV DATASETS", "MODELS")
        """Load advanced models, scalers, selectors, and metadata from disk."""
        try:
            model_files = {
                'random_forest': "advanced_random_forest.pkl",
                'xgboost': "advanced_xgboost.pkl",
                'lightgbm': "advanced_lightgbm.pkl",
                'neural_network': "advanced_neural_network.pkl",
                'svm': "advanced_svm.pkl",
                'ensemble': "advanced_ensemble.pkl",
            }

            for name, fname in model_files.items():
                path = os.path.join(model_dir, fname)
                if os.path.exists(path):
                    self.advanced_models[name] = joblib.load(path)
                    print(f"✅ Loaded {name} model")

            scaler_path = os.path.join(model_dir, "advanced_scalers.pkl")
            if os.path.exists(scaler_path):
                self.model_scalers = joblib.load(scaler_path)
                print("✅ Loaded advanced scalers")

            selector_path = os.path.join(model_dir, "advanced_selectors.pkl")
            if os.path.exists(selector_path):
                self.feature_selectors = joblib.load(selector_path)
                print("✅ Loaded advanced selectors")

            metadata_path = os.path.join(model_dir, "advanced_metadata.json")
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                self.model_performance = metadata.get('model_performance', {})
                self.feature_importance_cache = metadata.get('feature_importance', {})
                self.training_history = metadata.get('training_history', [])
                last_time = metadata.get('last_training_time')
                if last_time:
                    self.last_training_time = datetime.fromisoformat(last_time)
                print("✅ Loaded advanced metadata")

            return True

        except Exception as e:
            print(f"❌ Error loading advanced models: {e}")
            return False

    def get_advanced_model_info(self):
        """Return information and diagnostics for advanced models."""
        return {
            'models_loaded': list(self.advanced_models.keys()),
            'model_performance': self.model_performance,
            'feature_importance': self.feature_importance_cache,
            'last_training_time': self.last_training_time.isoformat() if self.last_training_time else None,
            'model_version': self.model_version,
            'training_history_count': len(self.training_history),
            'feature_settings': self.feature_settings,
        }

    def should_retrain_models(self) -> bool:
        """Check if advanced models should be retrained based on time interval."""
        if not self.last_training_time:
            return True
        days = (datetime.now() - self.last_training_time).days
        return days >= self.model_retrain_interval

    def update_model_with_new_data(self, new_data, target_column: str = 'failure_within_7d'):
        """Update advanced models with new data (simplified online learning)."""
        try:
            if new_data is None:
                return False

            if isinstance(new_data, list):
                new_df = pd.DataFrame(new_data)
            else:
                new_df = pd.DataFrame([new_data]) if isinstance(new_data, dict) else new_data.copy()

            if new_df is None or new_df.empty:
                return False

            if target_column not in new_df.columns:
                new_df[target_column] = self._create_synthetic_target(new_df)

            if self.training_history:
                existing_data = self.training_history[-1].get('training_data')
                if isinstance(existing_data, pd.DataFrame):
                    combined = pd.concat([existing_data, new_df], ignore_index=True)
                else:
                    combined = new_df
            else:
                combined = new_df

            result = self.train_advanced_ensemble(combined, target_column=target_column)
            return bool(result.get('success'))

        except Exception as e:
            print(f"Error updating models with new data: {e}")
            return False