"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Enhanced Ai Learning

Enhanced AI Learning System
- Learns from ALL vehicle profiles for maximum knowledge
- Provides vehicle-specific predictions
- Supports brand-specific learning (all Nissan vehicles, all Toyota, etc.)
- Continuous learning with new data
- Full persistence of models, scalers, feature ordering, and metadata
"""

import os
import json
import pickle
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import warnings
warnings.filterwarnings('ignore')

# Import portable config
try:
    from config import get_config
    _config = get_config()
    DEFAULT_AI_STORAGE_PATH = str(_config.AI_MODELS_DIR)
except ImportError:
    DEFAULT_AI_STORAGE_PATH = str(Path(__file__).parent / "PredictData" / "ai" / "models")

logger = logging.getLogger(__name__)


class EnhancedAILearning:
    """
    Advanced AI learning system that combines:
    1. Global learning (all vehicles)
    2. Brand-specific learning (all vehicles of same brand)
    3. Vehicle-specific learning (individual vehicle)
    """

    def __init__(self, model_storage_path=None):
        """Initialize enhanced AI learning system"""
        self.model_storage_path = model_storage_path or DEFAULT_AI_STORAGE_PATH
        self.ensure_storage_directory()

        # Model types
        self.global_model = None  # Learns from ALL vehicles
        self.brand_models = {}    # Per-brand models (Nissan, Toyota, etc.)
        self.vehicle_models = {}  # Per-vehicle models

        # Scalers
        self.global_scaler = StandardScaler()
        self.brand_scalers = {}
        self.vehicle_scalers = {}

        # Feature ordering (CRITICAL for consistent predictions)
        self.global_feature_columns = []
        self.brand_feature_columns = {}
        self.vehicle_feature_columns = {}

        # Normalization statistics for debugging/analysis
        self.normalization_stats = {}

        # Feature importance tracking
        self.feature_importance = {}

        # Learning history (persisted)
        self.learning_history = []

        # Load persisted history on init
        self._load_learning_history()

        logger.info(f"Enhanced AI Learning initialized (storage: {self.model_storage_path})")

    def ensure_storage_directory(self):
        """Ensure model storage directory exists"""
        os.makedirs(self.model_storage_path, exist_ok=True)
        os.makedirs(os.path.join(self.model_storage_path, 'global'), exist_ok=True)
        os.makedirs(os.path.join(self.model_storage_path, 'brand'), exist_ok=True)
        os.makedirs(os.path.join(self.model_storage_path, 'vehicle'), exist_ok=True)

    def train_global_model(self, historical_data_manager, min_samples=1000):
        """
        Train global model using data from ALL vehicles

        Args:
            historical_data_manager: HistoricalDataManager instance
            min_samples: Minimum samples required for training

        Returns:
            Dictionary with training results
        """
        try:
            logger.info("Starting global model training...")

            # Export all historical data
            csv_file = historical_data_manager.export_for_ai_training(output_format='csv')

            if not csv_file or not os.path.exists(csv_file):
                logger.warning("No historical data available for training")
                return {'success': False, 'error': 'No data'}

            # Load data
            df = pd.read_csv(csv_file)

            if len(df) < min_samples:
                logger.warning(f"Insufficient data: {len(df)} < {min_samples}")
                return {'success': False, 'error': 'Insufficient data'}

            # Prepare features and targets
            X, y_health, y_failure = self._prepare_training_data(df)

            if X is None or len(X) == 0:
                return {'success': False, 'error': 'Failed to prepare data'}

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y_health, test_size=0.2, random_state=42
            )

            # Save feature columns (CRITICAL for consistent predictions later)
            self.global_feature_columns = list(X.columns)

            # Scale features
            X_train_scaled = self.global_scaler.fit_transform(X_train)
            X_test_scaled = self.global_scaler.transform(X_test)

            # Save normalization stats
            self.normalization_stats['global'] = {
                'mean': self.global_scaler.mean_.tolist(),
                'scale': self.global_scaler.scale_.tolist(),
                'n_features': len(self.global_feature_columns),
                'feature_columns': self.global_feature_columns
            }

            # Train model
            self.global_model = GradientBoostingRegressor(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.1,
                random_state=42
            )

            self.global_model.fit(X_train_scaled, y_train)

            # Evaluate
            train_score = self.global_model.score(X_train_scaled, y_train)
            test_score = self.global_model.score(X_test_scaled, y_test)

            # Save model
            self._save_global_model()

            # Track feature importance
            self.feature_importance['global'] = dict(zip(
                X.columns,
                self.global_model.feature_importances_
            ))

            # Log training
            training_result = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'model_type': 'global',
                'samples_trained': len(X_train),
                'samples_tested': len(X_test),
                'train_score': float(train_score),
                'test_score': float(test_score),
                'features_count': len(X.columns)
            }

            self.learning_history.append(training_result)
            logger.info(f"✅ Global model trained: Train R²={train_score:.3f}, Test R²={test_score:.3f}")

            return training_result

        except Exception as e:
            logger.error(f"Error training global model: {e}")
            return {'success': False, 'error': str(e)}

    def train_brand_model(self, brand: str, historical_data_manager, min_samples=500):
        """
        Train brand-specific model (e.g., all Nissan vehicles)

        Args:
            brand: Vehicle brand (e.g., "Nissan", "Toyota")
            historical_data_manager: HistoricalDataManager instance
            min_samples: Minimum samples required

        Returns:
            Training results
        """
        try:
            logger.info(f"Training {brand}-specific model...")

            # Export all data
            csv_file = historical_data_manager.export_for_ai_training(output_format='csv')
            if not csv_file:
                return {'success': False, 'error': 'No data'}

            # Load and filter by brand
            df = pd.read_csv(csv_file)

            # Filter by brand (assuming profile folder contains brand name)
            brand_df = df[df['profile_folder'].str.contains(brand, case=False, na=False)]

            if len(brand_df) < min_samples:
                logger.warning(f"Insufficient {brand} data: {len(brand_df)} < {min_samples}")
                return {'success': False, 'error': 'Insufficient brand data'}

            # Prepare data
            X, y_health, _ = self._prepare_training_data(brand_df)

            if X is None or len(X) == 0:
                return {'success': False, 'error': 'Failed to prepare data'}

            # Split
            X_train, X_test, y_train, y_test = train_test_split(
                X, y_health, test_size=0.2, random_state=42
            )

            # Save feature columns for this brand
            self.brand_feature_columns[brand] = list(X.columns)

            # Create brand scaler
            if brand not in self.brand_scalers:
                self.brand_scalers[brand] = StandardScaler()

            X_train_scaled = self.brand_scalers[brand].fit_transform(X_train)
            X_test_scaled = self.brand_scalers[brand].transform(X_test)

            # Save normalization stats
            self.normalization_stats[f'brand_{brand}'] = {
                'mean': self.brand_scalers[brand].mean_.tolist(),
                'scale': self.brand_scalers[brand].scale_.tolist(),
                'n_features': len(self.brand_feature_columns[brand]),
                'feature_columns': self.brand_feature_columns[brand]
            }

            # Train brand model
            brand_model = GradientBoostingRegressor(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.1,
                random_state=42
            )

            brand_model.fit(X_train_scaled, y_train)

            # Evaluate
            train_score = brand_model.score(X_train_scaled, y_train)
            test_score = brand_model.score(X_test_scaled, y_test)

            # Store model
            self.brand_models[brand] = brand_model

            # Save
            self._save_brand_model(brand)

            # Feature importance
            self.feature_importance[f'brand_{brand}'] = dict(zip(
                X.columns,
                brand_model.feature_importances_
            ))

            result = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'model_type': f'brand_{brand}',
                'brand': brand,
                'samples_trained': len(X_train),
                'samples_tested': len(X_test),
                'train_score': float(train_score),
                'test_score': float(test_score)
            }

            self.learning_history.append(result)
            logger.info(f"✅ {brand} model trained: Test R²={test_score:.3f}")

            return result

        except Exception as e:
            logger.error(f"Error training {brand} model: {e}")
            return {'success': False, 'error': str(e)}

    def train_vehicle_model(self, profile_name: str, profile_id: int,
                           historical_data_manager, min_samples=200):
        """
        Train vehicle-specific model for individual vehicle

        Args:
            profile_name: Vehicle profile name
            profile_id: Profile ID
            historical_data_manager: HistoricalDataManager instance
            min_samples: Minimum samples required

        Returns:
            Training results
        """
        try:
            logger.info(f"Training vehicle-specific model for {profile_name}...")

            # Read vehicle's historical data
            vehicle_data = historical_data_manager.read_profile_data(profile_name, profile_id)

            if len(vehicle_data) < min_samples:
                logger.warning(f"Insufficient vehicle data: {len(vehicle_data)} < {min_samples}")
                # Fall back to brand/global model
                return {'success': False, 'error': 'Insufficient vehicle data', 'fallback': True}

            # Convert to DataFrame
            df = pd.DataFrame(vehicle_data)

            # Prepare data
            X, y_health, _ = self._prepare_training_data(df)

            if X is None or len(X) == 0:
                return {'success': False, 'error': 'Failed to prepare data'}

            # Split
            X_train, X_test, y_train, y_test = train_test_split(
                X, y_health, test_size=0.2, random_state=42
            )

            # Create vehicle scaler
            vehicle_key = f"{profile_name}_{profile_id}"

            # Save feature columns for this vehicle
            self.vehicle_feature_columns[vehicle_key] = list(X.columns)

            if vehicle_key not in self.vehicle_scalers:
                self.vehicle_scalers[vehicle_key] = StandardScaler()

            X_train_scaled = self.vehicle_scalers[vehicle_key].fit_transform(X_train)
            X_test_scaled = self.vehicle_scalers[vehicle_key].transform(X_test)

            # Save normalization stats
            self.normalization_stats[f'vehicle_{vehicle_key}'] = {
                'mean': self.vehicle_scalers[vehicle_key].mean_.tolist(),
                'scale': self.vehicle_scalers[vehicle_key].scale_.tolist(),
                'n_features': len(self.vehicle_feature_columns[vehicle_key]),
                'feature_columns': self.vehicle_feature_columns[vehicle_key]
            }

            # Train vehicle model
            vehicle_model = GradientBoostingRegressor(
                n_estimators=150,
                max_depth=4,
                learning_rate=0.1,
                random_state=42
            )

            vehicle_model.fit(X_train_scaled, y_train)

            # Evaluate
            train_score = vehicle_model.score(X_train_scaled, y_train)
            test_score = vehicle_model.score(X_test_scaled, y_test)

            # Store
            self.vehicle_models[vehicle_key] = vehicle_model

            # Save
            self._save_vehicle_model(vehicle_key)

            result = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'model_type': 'vehicle',
                'profile_name': profile_name,
                'profile_id': profile_id,
                'samples_trained': len(X_train),
                'samples_tested': len(X_test),
                'train_score': float(train_score),
                'test_score': float(test_score)
            }

            self.learning_history.append(result)
            logger.info(f"✅ {profile_name} model trained: Test R²={test_score:.3f}")

            return result

        except Exception as e:
            logger.error(f"Error training vehicle model: {e}")
            return {'success': False, 'error': str(e)}

    def predict_health(self, data: Dict[str, Any], profile_name: str = None,
                      profile_id: int = None, brand: str = None) -> Dict[str, Any]:
        """
        Predict vehicle health using ensemble of models

        Priority:
        1. Vehicle-specific model (if available and enough data)
        2. Brand-specific model (if available)
        3. Global model (fallback)

        Args:
            data: Current OBD data
            profile_name: Vehicle profile name
            profile_id: Profile ID
            brand: Vehicle brand

        Returns:
            Prediction results with confidence scores
        """
        try:
            # Prepare features
            features = self._extract_features(data)

            predictions = {}
            confidences = {}

            # Try vehicle-specific model first
            if profile_name and profile_id:
                vehicle_key = f"{profile_name}_{profile_id}"
                if vehicle_key in self.vehicle_models:
                    vehicle_pred = self._predict_with_model(
                        features,
                        self.vehicle_models[vehicle_key],
                        self.vehicle_scalers.get(vehicle_key)
                    )
                    if vehicle_pred is not None:
                        predictions['vehicle'] = vehicle_pred
                        confidences['vehicle'] = 0.8  # Highest confidence

            # Try brand-specific model
            if brand and brand in self.brand_models:
                brand_pred = self._predict_with_model(
                    features,
                    self.brand_models[brand],
                    self.brand_scalers.get(brand)
                )
                if brand_pred is not None:
                    predictions['brand'] = brand_pred
                    confidences['brand'] = 0.6

            # Try global model
            if self.global_model is not None:
                global_pred = self._predict_with_model(
                    features,
                    self.global_model,
                    self.global_scaler
                )
                if global_pred is not None:
                    predictions['global'] = global_pred
                    confidences['global'] = 0.4

            # Ensemble prediction (weighted average)
            if predictions:
                total_confidence = sum(confidences.values())
                weighted_health = sum(
                    pred * confidences[key] for key, pred in predictions.items()
                ) / total_confidence

                # Get model version info
                model_versions = self._get_model_versions(predictions.keys(), profile_name, profile_id, brand)

                return {
                    'health_score': round(weighted_health, 1),
                    'predictions': predictions,
                    'confidences': confidences,
                    'model_used': list(predictions.keys())[0],  # Primary model
                    'ensemble': True if len(predictions) > 1 else False,
                    'model_version': model_versions.get('primary', 'unknown'),
                    'model_versions': model_versions,
                    'prediction_timestamp': datetime.now().isoformat()
                }

            else:
                # No models available, use rule-based fallback
                return self._rule_based_health(data)

        except Exception as e:
            logger.error(f"Error predicting health: {e}")
            return self._rule_based_health(data)

    def _prepare_training_data(self, df: pd.DataFrame) -> Tuple[Optional[pd.DataFrame], Optional[np.ndarray], Optional[np.ndarray]]:
        """Prepare features and targets from raw data"""
        try:
            # Required columns for training
            feature_columns = [
                'rpm', 'speed', 'coolant_temp', 'throttle_position',
                'engine_load', 'voltage_batt_v'
            ]

            # Optional columns
            optional_columns = [
                'intake_air_temp', 'maf', 'fuel_pressure',
                'short_fuel_trim', 'long_fuel_trim', 'oil_temp'
            ]

            # Select available features
            available_features = []
            for col in feature_columns:
                if col in df.columns:
                    available_features.append(col)

            for col in optional_columns:
                if col in df.columns:
                    available_features.append(col)

            if not available_features:
                logger.error("No valid features found in data")
                return None, None, None

            # Create feature DataFrame
            X = df[available_features].copy()

            # Fill missing values with median
            X = X.fillna(X.median())

            # Create target (health score)
            # For now, compute based on rules (later can use labeled data)
            y_health = self._compute_health_target(df)

            # Create failure prediction target
            y_failure = self._compute_failure_target(df)

            return X, y_health, y_failure

        except Exception as e:
            logger.error(f"Error preparing training data: {e}")
            return None, None, None

    def _compute_health_target(self, df: pd.DataFrame) -> np.ndarray:
        """Compute health score target for training"""
        health_scores = []

        for _, row in df.iterrows():
            score = 100.0

            # Coolant temp check
            if 'coolant_temp' in row:
                if row['coolant_temp'] > 105:
                    score -= 20
                elif row['coolant_temp'] > 100:
                    score -= 10

            # Battery voltage check
            if 'voltage_batt_v' in row:
                if row['voltage_batt_v'] < 12.0:
                    score -= 30
                elif row['voltage_batt_v'] < 13.0:
                    score -= 15

            # RPM check (if speed is 0 but RPM is high)
            if 'rpm' in row and 'speed' in row:
                if row['speed'] == 0 and row['rpm'] > 1500:
                    score -= 10

            # Engine load check
            if 'engine_load' in row:
                if row['engine_load'] > 90:
                    score -= 5

            health_scores.append(max(0, min(100, score)))

        return np.array(health_scores)

    def _compute_failure_target(self, df: pd.DataFrame) -> np.ndarray:
        """Compute failure prediction target (0=no failure, 1=failure risk)"""
        # This would ideally use labeled data
        # For now, use heuristics
        failures = []

        for _, row in df.iterrows():
            failure = 0

            if 'coolant_temp' in row and row['coolant_temp'] > 110:
                failure = 1
            if 'voltage_batt_v' in row and row['voltage_batt_v'] < 11.5:
                failure = 1

            failures.append(failure)

        return np.array(failures)

    def _extract_features(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Extract features from current OBD data"""
        features = {}

        # Core features
        core_params = [
            'rpm', 'speed', 'coolant_temp', 'throttle_position',
            'engine_load', 'voltage_batt_v', 'intake_air_temp',
            'maf', 'fuel_pressure', 'oil_temp'
        ]

        for param in core_params:
            if param in data:
                features[param] = float(data[param])

        return features

    def _predict_with_model(self, features: Dict[str, float],
                           model, scaler) -> Optional[float]:
        """Make prediction with a specific model"""
        try:
            # Convert features to DataFrame
            feature_df = pd.DataFrame([features])

            # Fill missing with 0 (or could use median from training)
            feature_df = feature_df.fillna(0)

            # Scale
            if scaler:
                features_scaled = scaler.transform(feature_df)
            else:
                features_scaled = feature_df.values

            # Predict
            prediction = model.predict(features_scaled)[0]

            return float(prediction)

        except Exception as e:
            logger.error(f"Error in model prediction: {e}")
            return None

    def _get_model_versions(self, models_used: list, profile_name: str = None,
                           profile_id: int = None, brand: str = None) -> Dict[str, Any]:
        """
        Get version information for all models used in prediction.

        Returns version identifiers that help track:
        - When the model was trained
        - How much data it was trained on
        - Which exact model file was used
        """
        versions = {}

        # Get primary model (first in list)
        primary_model = list(models_used)[0] if models_used else None

        for model_type in models_used:
            try:
                if model_type == 'global':
                    metadata_path = os.path.join(self.model_storage_path, 'global', 'metadata.json')
                    if os.path.exists(metadata_path):
                        with open(metadata_path, 'r') as f:
                            metadata = json.load(f)
                        versions['global'] = {
                            'trained_at': metadata.get('saved_at', 'unknown'),
                            'feature_count': len(metadata.get('feature_columns', [])),
                            'version_hash': self._compute_model_hash('global')
                        }
                    else:
                        versions['global'] = {'version': 'in_memory', 'trained_at': 'unknown'}

                elif model_type == 'brand' and brand:
                    metadata_path = os.path.join(self.model_storage_path, 'brand', brand, 'metadata.json')
                    if os.path.exists(metadata_path):
                        with open(metadata_path, 'r') as f:
                            metadata = json.load(f)
                        versions['brand'] = {
                            'brand': brand,
                            'trained_at': metadata.get('saved_at', 'unknown'),
                            'feature_count': len(metadata.get('feature_columns', [])),
                            'version_hash': self._compute_model_hash(f'brand/{brand}')
                        }
                    else:
                        versions['brand'] = {'version': 'in_memory', 'brand': brand}

                elif model_type == 'vehicle' and profile_name and profile_id:
                    vehicle_key = f"{profile_name}_{profile_id}"
                    metadata_path = os.path.join(self.model_storage_path, 'vehicle', vehicle_key, 'metadata.json')
                    if os.path.exists(metadata_path):
                        with open(metadata_path, 'r') as f:
                            metadata = json.load(f)
                        versions['vehicle'] = {
                            'vehicle_key': vehicle_key,
                            'trained_at': metadata.get('saved_at', 'unknown'),
                            'feature_count': len(metadata.get('feature_columns', [])),
                            'version_hash': self._compute_model_hash(f'vehicle/{vehicle_key}')
                        }
                    else:
                        versions['vehicle'] = {'version': 'in_memory', 'vehicle_key': vehicle_key}

            except Exception as e:
                logger.warning(f"Error getting version for {model_type}: {e}")
                versions[model_type] = {'error': str(e)}

        # Set primary version for convenience
        if primary_model and primary_model in versions:
            primary_version = versions[primary_model]
            versions['primary'] = primary_version.get('version_hash',
                                   primary_version.get('trained_at', 'unknown'))

        return versions

    def _compute_model_hash(self, model_path_suffix: str) -> str:
        """Compute a short hash of the model file for version tracking."""
        import hashlib
        model_file = os.path.join(self.model_storage_path, model_path_suffix, 'model.pkl')
        if not os.path.exists(model_file):
            model_file = os.path.join(self.model_storage_path, model_path_suffix.split('/')[0],
                                      model_path_suffix.split('/')[-1] if '/' in model_path_suffix else '',
                                      'global_model.pkl' if 'global' in model_path_suffix else 'model.pkl')

        try:
            if os.path.exists(model_file):
                # Get file modification time + size for quick version hash
                stat = os.stat(model_file)
                version_string = f"{stat.st_mtime:.0f}_{stat.st_size}"
                return hashlib.md5(version_string.encode()).hexdigest()[:8]
            return 'no_file'
        except Exception:
            return 'unknown'

    def get_all_model_versions(self) -> Dict[str, Any]:
        """
        Get comprehensive version information for all loaded models.

        Useful for:
        - Debugging prediction issues
        - Tracking model deployments
        - Audit trails
        """
        versions = {
            'generated_at': datetime.now().isoformat(),
            'storage_path': self.model_storage_path,
            'models': {}
        }

        # Global model
        if self.global_model is not None:
            versions['models']['global'] = {
                'loaded': True,
                'type': type(self.global_model).__name__,
                'features': len(self.global_feature_columns),
                'version': self._compute_model_hash('global')
            }
        else:
            versions['models']['global'] = {'loaded': False}

        # Brand models
        versions['models']['brands'] = {}
        for brand, model in self.brand_models.items():
            versions['models']['brands'][brand] = {
                'loaded': True,
                'type': type(model).__name__,
                'features': len(self.brand_feature_columns.get(brand, [])),
                'version': self._compute_model_hash(f'brand/{brand}')
            }

        # Vehicle models
        versions['models']['vehicles'] = {}
        for vehicle_key, model in self.vehicle_models.items():
            versions['models']['vehicles'][vehicle_key] = {
                'loaded': True,
                'type': type(model).__name__,
                'features': len(self.vehicle_feature_columns.get(vehicle_key, [])),
                'version': self._compute_model_hash(f'vehicle/{vehicle_key}')
            }

        # Learning history summary
        if self.learning_history:
            versions['learning_history'] = {
                'total_sessions': len(self.learning_history),
                'last_session': self.learning_history[-1] if self.learning_history else None
            }

        return versions

    def _rule_based_health(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback rule-based health scoring"""
        score = 100.0

        if 'coolant_temp' in data:
            if data['coolant_temp'] > 105:
                score -= 20
            elif data['coolant_temp'] > 100:
                score -= 10

        if 'voltage_batt_v' in data:
            if data['voltage_batt_v'] < 12.0:
                score -= 30
            elif data['voltage_batt_v'] < 13.0:
                score -= 15

        return {
            'health_score': max(0, min(100, score)),
            'model_used': 'rule_based',
            'ensemble': False,
            'model_version': 'rule_based_v1.0',
            'model_versions': {'rule_based': {'version': '1.0', 'type': 'heuristic'}},
            'prediction_timestamp': datetime.now().isoformat()
        }

    def _save_global_model(self):
        """Save global model to disk with all metadata"""
        try:
            global_dir = os.path.join(self.model_storage_path, 'global')
            os.makedirs(global_dir, exist_ok=True)

            model_path = os.path.join(global_dir, 'global_model.pkl')
            scaler_path = os.path.join(global_dir, 'global_scaler.pkl')
            metadata_path = os.path.join(global_dir, 'metadata.json')

            with open(model_path, 'wb') as f:
                pickle.dump(self.global_model, f)

            with open(scaler_path, 'wb') as f:
                pickle.dump(self.global_scaler, f)

            # Save feature columns and normalization stats
            metadata = {
                'feature_columns': self.global_feature_columns,
                'normalization_stats': self.normalization_stats.get('global', {}),
                'feature_importance': self.feature_importance.get('global', {}),
                'saved_at': datetime.now().isoformat(),
                'scaler_mean': self.global_scaler.mean_.tolist() if hasattr(self.global_scaler, 'mean_') else None,
                'scaler_scale': self.global_scaler.scale_.tolist() if hasattr(self.global_scaler, 'scale_') else None
            }
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            # Save learning history
            self._save_learning_history()

            logger.info("Global model saved with metadata")

        except Exception as e:
            logger.error(f"Error saving global model: {e}")

    def _save_brand_model(self, brand: str):
        """Save brand model to disk with all metadata"""
        try:
            brand_dir = os.path.join(self.model_storage_path, 'brand', brand)
            os.makedirs(brand_dir, exist_ok=True)

            model_path = os.path.join(brand_dir, f'{brand}_model.pkl')
            scaler_path = os.path.join(brand_dir, f'{brand}_scaler.pkl')
            metadata_path = os.path.join(brand_dir, 'metadata.json')

            with open(model_path, 'wb') as f:
                pickle.dump(self.brand_models[brand], f)

            with open(scaler_path, 'wb') as f:
                pickle.dump(self.brand_scalers[brand], f)

            # Save feature columns and normalization stats
            scaler = self.brand_scalers.get(brand)
            metadata = {
                'brand': brand,
                'feature_columns': self.brand_feature_columns.get(brand, []),
                'normalization_stats': self.normalization_stats.get(f'brand_{brand}', {}),
                'feature_importance': self.feature_importance.get(f'brand_{brand}', {}),
                'saved_at': datetime.now().isoformat(),
                'scaler_mean': scaler.mean_.tolist() if scaler and hasattr(scaler, 'mean_') else None,
                'scaler_scale': scaler.scale_.tolist() if scaler and hasattr(scaler, 'scale_') else None
            }
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"{brand} model saved with metadata")

        except Exception as e:
            logger.error(f"Error saving {brand} model: {e}")

    def _save_vehicle_model(self, vehicle_key: str):
        """Save vehicle model to disk with all metadata"""
        try:
            vehicle_dir = os.path.join(self.model_storage_path, 'vehicle', vehicle_key)
            os.makedirs(vehicle_dir, exist_ok=True)

            model_path = os.path.join(vehicle_dir, 'vehicle_model.pkl')
            scaler_path = os.path.join(vehicle_dir, 'vehicle_scaler.pkl')
            metadata_path = os.path.join(vehicle_dir, 'metadata.json')

            with open(model_path, 'wb') as f:
                pickle.dump(self.vehicle_models[vehicle_key], f)

            with open(scaler_path, 'wb') as f:
                pickle.dump(self.vehicle_scalers[vehicle_key], f)

            # Save feature columns and normalization stats
            scaler = self.vehicle_scalers.get(vehicle_key)
            metadata = {
                'vehicle_key': vehicle_key,
                'feature_columns': self.vehicle_feature_columns.get(vehicle_key, []),
                'normalization_stats': self.normalization_stats.get(f'vehicle_{vehicle_key}', {}),
                'saved_at': datetime.now().isoformat(),
                'scaler_mean': scaler.mean_.tolist() if scaler and hasattr(scaler, 'mean_') else None,
                'scaler_scale': scaler.scale_.tolist() if scaler and hasattr(scaler, 'scale_') else None
            }
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"Vehicle model saved with metadata: {vehicle_key}")

        except Exception as e:
            logger.error(f"Error saving vehicle model: {e}")

    def _save_learning_history(self):
        """Save learning history to disk"""
        try:
            history_path = os.path.join(self.model_storage_path, 'learning_history.json')
            with open(history_path, 'w') as f:
                json.dump(self.learning_history, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving learning history: {e}")

    def _load_learning_history(self):
        """Load learning history from disk"""
        try:
            history_path = os.path.join(self.model_storage_path, 'learning_history.json')
            if os.path.exists(history_path):
                with open(history_path, 'r') as f:
                    self.learning_history = json.load(f)
                logger.info(f"Loaded {len(self.learning_history)} training history entries")
        except Exception as e:
            logger.warning(f"Error loading learning history: {e}")
            self.learning_history = []

    def load_models(self):
        """Load all saved models from disk including metadata"""
        try:
            # Load global model
            global_dir = os.path.join(self.model_storage_path, 'global')
            global_model_path = os.path.join(global_dir, 'global_model.pkl')
            global_scaler_path = os.path.join(global_dir, 'global_scaler.pkl')
            global_metadata_path = os.path.join(global_dir, 'metadata.json')

            if os.path.exists(global_model_path):
                with open(global_model_path, 'rb') as f:
                    self.global_model = pickle.load(f)
                with open(global_scaler_path, 'rb') as f:
                    self.global_scaler = pickle.load(f)

                # Load metadata (feature columns, normalization stats)
                if os.path.exists(global_metadata_path):
                    with open(global_metadata_path, 'r') as f:
                        metadata = json.load(f)
                        self.global_feature_columns = metadata.get('feature_columns', [])
                        self.normalization_stats['global'] = metadata.get('normalization_stats', {})
                        self.feature_importance['global'] = metadata.get('feature_importance', {})

                logger.info(f"Global model loaded (features: {len(self.global_feature_columns)})")

            # Load brand models
            brand_dir = os.path.join(self.model_storage_path, 'brand')
            if os.path.exists(brand_dir):
                for brand in os.listdir(brand_dir):
                    brand_path = os.path.join(brand_dir, brand)
                    if os.path.isdir(brand_path):
                        model_file = os.path.join(brand_path, f'{brand}_model.pkl')
                        scaler_file = os.path.join(brand_path, f'{brand}_scaler.pkl')
                        metadata_file = os.path.join(brand_path, 'metadata.json')

                        if os.path.exists(model_file):
                            with open(model_file, 'rb') as f:
                                self.brand_models[brand] = pickle.load(f)
                            with open(scaler_file, 'rb') as f:
                                self.brand_scalers[brand] = pickle.load(f)

                            # Load metadata
                            if os.path.exists(metadata_file):
                                with open(metadata_file, 'r') as f:
                                    metadata = json.load(f)
                                    self.brand_feature_columns[brand] = metadata.get('feature_columns', [])
                                    self.normalization_stats[f'brand_{brand}'] = metadata.get('normalization_stats', {})
                                    self.feature_importance[f'brand_{brand}'] = metadata.get('feature_importance', {})

                            logger.info(f"{brand} model loaded")

            # Load vehicle models
            vehicle_dir = os.path.join(self.model_storage_path, 'vehicle')
            if os.path.exists(vehicle_dir):
                for vehicle_key in os.listdir(vehicle_dir):
                    vehicle_path = os.path.join(vehicle_dir, vehicle_key)
                    if os.path.isdir(vehicle_path):
                        model_file = os.path.join(vehicle_path, 'vehicle_model.pkl')
                        scaler_file = os.path.join(vehicle_path, 'vehicle_scaler.pkl')
                        metadata_file = os.path.join(vehicle_path, 'metadata.json')

                        if os.path.exists(model_file):
                            with open(model_file, 'rb') as f:
                                self.vehicle_models[vehicle_key] = pickle.load(f)
                            with open(scaler_file, 'rb') as f:
                                self.vehicle_scalers[vehicle_key] = pickle.load(f)

                            # Load metadata
                            if os.path.exists(metadata_file):
                                with open(metadata_file, 'r') as f:
                                    metadata = json.load(f)
                                    self.vehicle_feature_columns[vehicle_key] = metadata.get('feature_columns', [])
                                    self.normalization_stats[f'vehicle_{vehicle_key}'] = metadata.get('normalization_stats', {})

                            logger.info(f"Vehicle model loaded: {vehicle_key}")

            logger.info(f"Models loaded: global={self.global_model is not None}, "
                       f"brands={len(self.brand_models)}, vehicles={len(self.vehicle_models)}")

        except Exception as e:
            logger.error(f"Error loading models: {e}")

    def get_learning_statistics(self) -> Dict[str, Any]:
        """Get statistics about learning progress"""
        return {
            'global_model_trained': self.global_model is not None,
            'brand_models_count': len(self.brand_models),
            'vehicle_models_count': len(self.vehicle_models),
            'brands_trained': list(self.brand_models.keys()),
            'total_training_sessions': len(self.learning_history),
            'last_training': self.learning_history[-1] if self.learning_history else None
        }
