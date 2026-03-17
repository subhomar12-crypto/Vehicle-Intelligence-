"""XGBoost failure predictor — 10 binary classifiers for component failures.

Trains on labeled failure events and outputs per-component confidence scores.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import xgboost as xgb
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Component IDs for binary classifiers
COMPONENT_IDS = [
    "ENGINE",
    "TRANSMISSION",
    "BRAKES",
    "ELECTRICAL",
    "COOLING",
    "FUEL_SYSTEM",
    "IGNITION",
    "EXHAUST",
    "SUSPENSION",
    "TIRES",
]

# Feature columns extracted from telemetry window
FEATURE_COLUMNS = [
    "rpm_std",        # Standard deviation of RPM
    "load_mean",      # Mean engine load
    "coolant_delta",  # Coolant temperature change
    "lambda_variance", # Lambda/O2 sensor variance
]


class XGBoostFailurePredictor:
    """XGBoost ensemble for component failure prediction."""
    
    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 6,
        learning_rate: float = 0.1,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        min_child_weight: int = 3,
        gamma: float = 0.1,
        reg_alpha: float = 0.1,
        reg_lambda: float = 1.0,
        scale_pos_weight: float = 10.0,  # Handle class imbalance
    ):
        """Initialize predictor with XGBoost hyperparameters.
        
        Args:
            n_estimators: Number of boosting rounds
            max_depth: Maximum tree depth
            learning_rate: Boosting learning rate
            subsample: Subsample ratio of training instances
            colsample_bytree: Subsample ratio of columns
            min_child_weight: Minimum sum of instance weight in child
            gamma: Minimum loss reduction for split
            reg_alpha: L1 regularization
            reg_lambda: L2 regularization
            scale_pos_weight: Balance positive/negative weights
        """
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.subsample = subsample
        self.colsample_bytree = colsample_bytree
        self.min_child_weight = min_child_weight
        self.gamma = gamma
        self.reg_alpha = reg_alpha
        self.reg_lambda = reg_lambda
        self.scale_pos_weight = scale_pos_weight
        
        self.models: Dict[str, xgb.XGBClassifier] = {}
        self.is_trained = False
        
    def _extract_features(self, telemetry_window: List[Dict[str, Any]]) -> np.ndarray:
        """Extract features from telemetry window.
        
        Features:
        - rpm_std: Standard deviation of RPM
        - load_mean: Mean engine load
        - coolant_delta: Change in coolant temp (last - first)
        - lambda_variance: Variance of lambda/O2 sensor readings
        
        Args:
            telemetry_window: List of telemetry readings
            
        Returns:
            Feature vector (4,)
        """
        if not telemetry_window:
            return np.zeros(4)
        
        # Extract values
        rpm_values = [r.get("rpm", 0) or 0 for r in telemetry_window]
        load_values = [r.get("engine_load", 0) or 0 for r in telemetry_window]
        coolant_values = [r.get("coolant_temp", 0) or 0 for r in telemetry_window]
        lambda_values = [r.get("lambda", 0) or 0 for r in telemetry_window]
        
        # Calculate features
        rpm_std = np.std(rpm_values) if rpm_values else 0.0
        load_mean = np.mean(load_values) if load_values else 0.0
        coolant_delta = (coolant_values[-1] - coolant_values[0]) if len(coolant_values) >= 2 else 0.0
        lambda_variance = np.var(lambda_values) if lambda_values else 0.0
        
        return np.array([rpm_std, load_mean, coolant_delta, lambda_variance])
    
    async def train_from_db(
        self,
        session: AsyncSession,
        min_samples: int = 100,
    ) -> Dict[str, Any]:
        """Train models from database failure events.
        
        Args:
            session: Database session
            min_samples: Minimum samples required per component
            
        Returns:
            Training metrics dict
        """
        from predict.core.db.models.prediction import FailureEvent
        from predict.core.db.models.vehicle import VehicleData
        
        metrics = {
            "components_trained": [],
            "components_skipped": [],
            "samples_per_component": {},
        }
        
        for component in COMPONENT_IDS:
            # Query failure events for this component
            result = await session.execute(
                select(FailureEvent).where(
                    and_(
                        FailureEvent.component == component,
                        FailureEvent.confirmed == True,
                    )
                )
            )
            failure_events = result.scalars().all()
            
            if len(failure_events) < min_samples:
                logger.warning(
                    f"Insufficient samples for {component}: "
                    f"got {len(failure_events)}, need {min_samples}"
                )
                metrics["components_skipped"].append(component)
                continue
            
            # Build training dataset
            X_list = []
            y_list = []
            
            for event in failure_events:
                # Get telemetry window before failure
                telemetry_result = await session.execute(
                    select(VehicleData).where(
                        VehicleData.profile_id == event.profile_id
                    ).order_by(VehicleData.timestamp.desc()).limit(60)
                )
                telemetry = telemetry_result.scalars().all()
                
                if len(telemetry) < 10:
                    continue
                
                # Extract features
                features = self._extract_features([t.__dict__ for t in telemetry])
                X_list.append(features)
                y_list.append(1)  # Failure
                
                # Get healthy samples (negative examples)
                # Sample from other vehicles or time periods
                healthy_result = await session.execute(
                    select(VehicleData).where(
                        VehicleData.profile_id != event.profile_id
                    ).order_by(VehicleData.timestamp.desc()).limit(60)
                )
                healthy_telemetry = healthy_result.scalars().all()
                
                if len(healthy_telemetry) >= 10:
                    healthy_features = self._extract_features([t.__dict__ for t in healthy_telemetry])
                    X_list.append(healthy_features)
                    y_list.append(0)  # Healthy
            
            if len(X_list) < min_samples:
                logger.warning(f"Insufficient training data for {component} after processing")
                metrics["components_skipped"].append(component)
                continue
            
            # Train XGBoost classifier
            X = np.array(X_list)
            y = np.array(y_list)
            
            model = xgb.XGBClassifier(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                learning_rate=self.learning_rate,
                subsample=self.subsample,
                colsample_bytree=self.colsample_bytree,
                min_child_weight=self.min_child_weight,
                gamma=self.gamma,
                reg_alpha=self.reg_alpha,
                reg_lambda=self.reg_lambda,
                scale_pos_weight=self.scale_pos_weight,
                use_label_encoder=False,
                eval_metric="logloss",
                random_state=42,
            )
            
            model.fit(X, y)
            self.models[component] = model
            
            metrics["components_trained"].append(component)
            metrics["samples_per_component"][component] = {
                "total": len(X),
                "failures": int(sum(y)),
                "healthy": int(len(y) - sum(y)),
            }
            
            logger.info(f"Trained {component} model on {len(X)} samples")
        
        self.is_trained = len(self.models) > 0
        return metrics
    
    def train_from_synthetic(
        self,
        n_samples: int = 1000,
    ) -> Dict[str, Any]:
        """Train on synthetic data for development/testing.
        
        Args:
            n_samples: Samples per component
            
        Returns:
            Training metrics dict
        """
        metrics = {
            "components_trained": [],
            "components_skipped": [],
        }
        
        np.random.seed(42)
        
        for component in COMPONENT_IDS:
            # Generate synthetic features
            # Healthy samples: normal distribution
            X_healthy = np.random.randn(n_samples // 2, 4) * 10 + 50
            
            # Failure samples: different distribution based on component
            if component == "ENGINE":
                # High RPM variance, high load
                X_failure = np.random.randn(n_samples // 2, 4) * 20 + np.array([80, 90, 30, 10])
            elif component == "COOLING":
                # High coolant delta
                X_failure = np.random.randn(n_samples // 2, 4) * 15 + np.array([30, 60, 100, 5])
            elif component == "BRAKES":
                # High load variance
                X_failure = np.random.randn(n_samples // 2, 4) * 25 + np.array([40, 85, 10, 8])
            else:
                # Generic failure pattern
                X_failure = np.random.randn(n_samples // 2, 4) * 15 + np.array([60, 75, 40, 7])
            
            X = np.vstack([X_healthy, X_failure])
            y = np.hstack([np.zeros(n_samples // 2), np.ones(n_samples // 2)])
            
            # Train model
            model = xgb.XGBClassifier(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                learning_rate=self.learning_rate,
                subsample=self.subsample,
                colsample_bytree=self.colsample_bytree,
                min_child_weight=self.min_child_weight,
                gamma=self.gamma,
                reg_alpha=self.reg_alpha,
                reg_lambda=self.reg_lambda,
                scale_pos_weight=1.0,  # Balanced synthetic data
                use_label_encoder=False,
                eval_metric="logloss",
                random_state=42,
            )
            
            model.fit(X, y)
            self.models[component] = model
            
            metrics["components_trained"].append(component)
            logger.info(f"Trained {component} model on {len(X)} synthetic samples")
        
        self.is_trained = True
        return metrics
    
    def predict(
        self,
        telemetry_window: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        """Predict failure probabilities for all components.
        
        Args:
            telemetry_window: List of telemetry readings
            
        Returns:
            Dict mapping component -> failure probability (0-1)
        """
        if not self.is_trained:
            logger.warning("Models not trained, returning default scores")
            return {comp: 0.5 for comp in COMPONENT_IDS}
        
        # Extract features
        features = self._extract_features(telemetry_window)
        features = features.reshape(1, -1)
        
        # Predict for each component
        predictions = {}
        for component, model in self.models.items():
            try:
                # Get probability of failure (class 1)
                proba = model.predict_proba(features)[0, 1]
                predictions[component] = float(proba)
            except Exception as e:
                logger.error(f"Prediction failed for {component}: {e}")
                predictions[component] = 0.5
        
        # Fill missing components with default
        for component in COMPONENT_IDS:
            if component not in predictions:
                predictions[component] = 0.5
        
        return predictions
    
    def serialize(self, output_dir: str) -> Dict[str, str]:
        """Serialize models to JSON + joblib for Pi5 deployment.
        
        Args:
            output_dir: Directory to save model files
            
        Returns:
            Dict mapping component -> file path
        """
        import joblib
        
        if not self.is_trained:
            raise ValueError("Models not trained, cannot serialize")
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        paths = {}
        
        for component, model in self.models.items():
            # Save as joblib (can be loaded without XGBoost using xgboost.Booster)
            model_path = output_dir / f"{component.lower()}_xgb.joblib"
            joblib.dump(model, model_path)
            
            # Also save feature importance as JSON
            importance = dict(zip(FEATURE_COLUMNS, model.feature_importances_.tolist()))
            importance_path = output_dir / f"{component.lower()}_importance.json"
            with open(importance_path, 'w') as f:
                json.dump(importance, f, indent=2)
            
            paths[component] = str(model_path)
            logger.info(f"Serialized {component} model to {model_path}")
        
        # Save metadata
        metadata = {
            "components": COMPONENT_IDS,
            "feature_columns": FEATURE_COLUMNS,
            "hyperparameters": {
                "n_estimators": self.n_estimators,
                "max_depth": self.max_depth,
                "learning_rate": self.learning_rate,
            },
        }
        metadata_path = output_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        paths["metadata"] = str(metadata_path)
        
        return paths
    
    def load(self, model_dir: str) -> None:
        """Load models from directory.
        
        Args:
            model_dir: Directory containing model files
        """
        import joblib
        
        model_dir = Path(model_dir)
        
        # Load metadata
        metadata_path = model_dir / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            logger.info(f"Loaded metadata: {metadata}")
        
        # Load models
        for component in COMPONENT_IDS:
            model_path = model_dir / f"{component.lower()}_xgb.joblib"
            if model_path.exists():
                self.models[component] = joblib.load(model_path)
                logger.info(f"Loaded {component} model from {model_path}")
        
        self.is_trained = len(self.models) > 0
        logger.info(f"Loaded {len(self.models)} models")
    
    def get_feature_importance(self, component: str) -> Optional[Dict[str, float]]:
        """Get feature importance for a component.
        
        Args:
            component: Component ID
            
        Returns:
            Dict mapping feature -> importance score
        """
        if component not in self.models:
            return None
        
        model = self.models[component]
        importance = model.feature_importances_
        
        return dict(zip(FEATURE_COLUMNS, importance.tolist()))
