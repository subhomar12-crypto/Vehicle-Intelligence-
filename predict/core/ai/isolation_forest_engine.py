"""Isolation Forest engine — anomaly detection with JSON serialization for Pi5 deployment."""

import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AnomalyResult:
    """Anomaly detection result."""
    timestamp: float
    anomaly_score: float
    sensors: List[str]
    severity: str  # "low", "medium", "high"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class IsolationForestEngine:
    """Isolation Forest anomaly detection with JSON serialization."""
    
    def __init__(self, contamination: float = 0.1, n_estimators: int = 100):
        """Initialize engine.
        
        Args:
            contamination: Expected proportion of outliers
            n_estimators: Number of trees in forest
        """
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.model = None
        self.threshold = None
        
    def train_from_baseline(self, baseline_data: np.ndarray) -> Dict[str, Any]:
        """Train Isolation Forest and return JSON-serializable model.
        
        Args:
            baseline_data: (N, features) array of normal readings
            
        Returns:
            JSON-serializable model dictionary
        """
        from sklearn.ensemble import IsolationForest
        
        if len(baseline_data) < 50:
            raise ValueError(f"Need at least 50 baseline samples, got {len(baseline_data)}")
        
        # Train model
        self.model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(baseline_data)
        
        # Compute threshold from training data
        scores = self.model.score_samples(baseline_data)
        self.threshold = np.percentile(scores, self.contamination * 100)
        
        # Serialize to JSON
        model_dict = self.serialize_model(self.model)
        model_dict["threshold"] = float(self.threshold)
        model_dict["contamination"] = self.contamination
        
        logger.info(f"Trained Isolation Forest on {len(baseline_data)} samples, "
                   f"threshold={self.threshold:.3f}")
        
        return model_dict
    
    def serialize_model(self, model) -> Dict[str, Any]:
        """Serialize sklearn IsolationForest to JSON.
        
        Extracts tree structure for pure-Python inference on Pi5.
        
        Returns:
            Dictionary with tree structures
        """
        trees = []
        
        for estimator in model.estimators_:
            tree = estimator.tree_
            n_nodes = tree.node_count
            
            # Extract tree structure
            tree_dict = {
                "n_nodes": n_nodes,
                "children_left": tree.children_left.tolist(),
                "children_right": tree.children_right.tolist(),
                "feature": tree.feature.tolist(),
                "threshold": tree.threshold.tolist(),
                "value": tree.value[:, 0, 0].tolist() if hasattr(tree, 'value') else [],
            }
            trees.append(tree_dict)
        
        return {
            "n_estimators": len(trees),
            "trees": trees,
            "n_features": model.n_features_in_,
        }
    
    def load_model(self, model_dict: Dict[str, Any]) -> None:
        """Load model from JSON serialization.
        
        Args:
            model_dict: Model dictionary from serialize_model()
        """
        self.model = model_dict
        self.threshold = model_dict.get("threshold", -0.5)
        self.contamination = model_dict.get("contamination", 0.1)
        logger.info(f"Loaded Isolation Forest model with {model_dict['n_estimators']} trees")
    
    def detect_anomalies(
        self, 
        readings: List[Dict[str, Any]],
        feature_columns: List[str],
    ) -> List[AnomalyResult]:
        """Detect anomalies in readings.
        
        Args:
            readings: List of telemetry readings
            feature_columns: List of feature names to use
            
        Returns:
            List of anomaly results
        """
        if self.model is None:
            logger.warning("No model loaded, cannot detect anomalies")
            return []
        
        if len(readings) == 0:
            return []
        
        # Extract features
        features = []
        timestamps = []
        
        for reading in readings:
            row = []
            for col in feature_columns:
                val = reading.get(col)
                if val is None:
                    row.append(0.0)
                else:
                    try:
                        row.append(float(val))
                    except (TypeError, ValueError):
                        row.append(0.0)
            features.append(row)
            timestamps.append(reading.get("timestamp", 0.0))
        
        features = np.array(features)
        
        # Check feature count matches model
        if isinstance(self.model, dict):
            expected_features = self.model.get("n_features", features.shape[1])
        else:
            expected_features = getattr(self.model, "n_features_in_", features.shape[1])
        
        if features.shape[1] != expected_features:
            logger.warning(f"Feature mismatch: model expects {expected_features}, got {features.shape[1]}")
            return []
        
        # Score samples
        if isinstance(self.model, dict):
            # Use JSON model (pure Python)
            scores = self._score_samples_json(features)
        else:
            # Use sklearn model
            scores = self.model.score_samples(features)
        
        # Detect anomalies
        anomalies = []
        for i, score in enumerate(scores):
            if score < self.threshold:
                # Determine severity
                deviation = self.threshold - score
                if deviation > 0.5:
                    severity = "high"
                elif deviation > 0.3:
                    severity = "medium"
                else:
                    severity = "low"
                
                # Find most anomalous sensors (highest values)
                sensor_values = list(zip(feature_columns, features[i]))
                sensor_values.sort(key=lambda x: abs(x[1]), reverse=True)
                top_sensors = [s for s, _ in sensor_values[:3]]
                
                anomalies.append(AnomalyResult(
                    timestamp=float(timestamps[i]),
                    anomaly_score=float(score),
                    sensors=top_sensors,
                    severity=severity,
                ))
        
        return anomalies
    
    def _score_samples_json(self, features: np.ndarray) -> np.ndarray:
        """Score samples using JSON-serialized model (pure Python).
        
        This allows inference on Pi5 without sklearn.
        
        Args:
            features: (N, n_features) array
            
        Returns:
            Array of anomaly scores (lower = more anomalous)
        """
        n_samples = len(features)
        n_trees = self.model["n_estimators"]
        trees = self.model["trees"]
        
        scores = np.zeros(n_samples)
        
        for tree in trees:
            depths = self._traverse_tree(features, tree)
            scores += depths
        
        # Average depth across trees
        scores /= n_trees
        
        # Convert to anomaly score (lower = more anomalous)
        # Using average path length normalization
        scores = -scores
        
        return scores
    
    def _traverse_tree(
        self, 
        features: np.ndarray, 
        tree: Dict[str, Any]
    ) -> np.ndarray:
        """Traverse tree for all samples and return depths.
        
        Args:
            features: (N, n_features) array
            tree: Tree dictionary
            
        Returns:
            Array of depths for each sample
        """
        n_samples = len(features)
        depths = np.zeros(n_samples)
        
        # Start at root for all samples
        node_indices = np.zeros(n_samples, dtype=int)
        active = np.ones(n_samples, dtype=bool)
        current_depth = np.zeros(n_samples)
        
        children_left = np.array(tree["children_left"])
        children_right = np.array(tree["children_right"])
        feature = np.array(tree["feature"])
        threshold = np.array(tree["threshold"])
        
        while np.any(active):
            # Process active samples
            current_nodes = node_indices[active]
            
            # Check which are leaves
            is_leaf = (children_left[current_nodes] == children_right[current_nodes])
            
            # Mark leaves as done
            leaf_mask = active.copy()
            leaf_mask[active] = is_leaf
            depths[leaf_mask] = current_depth[leaf_mask]
            active[leaf_mask] = False
            
            if not np.any(active):
                break
            
            # Process internal nodes
            current_nodes = node_indices[active]
            feat_idx = feature[current_nodes]
            thresh = threshold[current_nodes]
            
            # Get feature values for active samples
            active_indices = np.where(active)[0]
            feat_values = features[active_indices, feat_idx]
            
            # Go left or right
            go_left = feat_values <= thresh
            
            next_nodes = np.where(
                go_left,
                children_left[current_nodes],
                children_right[current_nodes]
            )
            
            node_indices[active] = next_nodes
            current_depth[active] += 1
        
        return depths
    
    def export_for_pi5(self, filepath: str) -> None:
        """Export model to JSON file for Pi5 deployment.
        
        Args:
            filepath: Path to save JSON file
        """
        if self.model is None:
            raise ValueError("No model to export")
        
        if isinstance(self.model, dict):
            model_dict = self.model
        else:
            model_dict = self.serialize_model(self.model)
            model_dict["threshold"] = float(self.threshold) if self.threshold else -0.5
            model_dict["contamination"] = self.contamination
        
        with open(filepath, 'w') as f:
            json.dump(model_dict, f, indent=2)
        
        logger.info(f"Exported model to {filepath}")
    
    def import_from_pi5(self, filepath: str) -> None:
        """Import model from JSON file (from Pi5 or server).
        
        Args:
            filepath: Path to JSON file
        """
        with open(filepath, 'r') as f:
            model_dict = json.load(f)
        
        self.load_model(model_dict)
