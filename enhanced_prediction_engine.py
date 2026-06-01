"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Enhanced Prediction Engine - Central Prediction Hub

Enhanced Prediction Engine
==========================
Integrates all AI enhancement modules into a unified prediction system.

Combines:
- Advanced Feature Engineering
- Failure Correlation Rules
- RUL Estimation
- Vehicle Baseline Learning
- Confidence Scoring
- External Sensor Processing
- LSTM Deep Learning (30-60 day predictions)
- Labeled Data Collection (feedback loop)
- ESP32 External Sensor Bridge

This module serves as the central hub for all predictive maintenance capabilities.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
import json
from pathlib import Path
from config import get_config

CONFIG = get_config()

# Import all enhancement modules
from advanced_feature_engineering import AdvancedFeatureEngineering
from failure_correlation_engine import FailureCorrelationEngine, FailureDetection
from rul_estimation import RULEstimator, RULPrediction
from vehicle_baseline_learning import VehicleBaselineLearning, VehicleState
from prediction_confidence import PredictionConfidenceScorer, ConfidenceScore
from external_sensor_schema import ExternalSensorProcessor

# Import new deep learning and feedback modules
try:
    from lstm_predictor import LSTMPredictor, get_lstm_predictor, PredictionResult
    LSTM_AVAILABLE = True
except ImportError as e:
    LSTM_AVAILABLE = False
    print(f"Note: LSTM predictor not available: {e}")

try:
    from feedback_collector import FeedbackCollector, get_feedback_collector
    FEEDBACK_AVAILABLE = True
except ImportError as e:
    FEEDBACK_AVAILABLE = False
    print(f"Note: Feedback collector not available: {e}")

try:
    from esp32_sensor_bridge import ESP32SensorBridge, get_sensor_bridge
    ESP32_AVAILABLE = True
except ImportError as e:
    ESP32_AVAILABLE = False
    print(f"Note: ESP32 sensor bridge not available: {e}")

try:
    from lstm_autoencoder import get_lstm_autoencoder, LSTMAutoencoderPrediction
    AUTOENCODER_AVAILABLE = True
except ImportError as e:
    AUTOENCODER_AVAILABLE = False
    print(f"Note: LSTM Autoencoder not available: {e}")

try:
    from physics_constraints import get_physics_validator, PhysicsValidationResult
    PHYSICS_AVAILABLE = True
except ImportError as e:
    PHYSICS_AVAILABLE = False
    print(f"Note: Physics constraints not available: {e}")

# Import research feature extraction for LLM-based intelligence
try:
    from research_feature_extractor import (
        ResearchFeatures, ResearchFeatureExtractor,
        get_feature_extractor, extract_features_from_research
    )
    RESEARCH_FEATURES_AVAILABLE = True
except ImportError as e:
    RESEARCH_FEATURES_AVAILABLE = False
    print(f"Note: Research feature extractor not available: {e}")

# Import fleet learning for cross-vehicle intelligence
try:
    from fleet_learning_aggregator import (
        FleetLearningAggregator, FleetStatistics, VehicleComparison,
        get_fleet_aggregator, compare_to_fleet
    )
    FLEET_LEARNING_AVAILABLE = True
except ImportError as e:
    FLEET_LEARNING_AVAILABLE = False
    print(f"Note: Fleet learning aggregator not available: {e}")

# Import recall monitoring
try:
    from recall_monitor import (
        RecallMonitor, RecallInfo, get_recall_monitor, get_recall_summary
    )
    RECALL_MONITOR_AVAILABLE = True
except ImportError as e:
    RECALL_MONITOR_AVAILABLE = False
    print(f"Note: Recall monitor not available: {e}")

# Import driving behavior and trip analysis agents (server-side)
# These agents provide driving pattern analysis and trip insights
try:
    # Try importing from server location first
    import sys
    server_path = Path(r"C:\OBDserver\Previlium_OBD_Server")
    if server_path.exists() and str(server_path) not in sys.path:
        sys.path.insert(0, str(server_path))

    from driving_behavior_agent import (
        DrivingBehaviorAgent, DrivingBehaviorAnalysis, get_driving_behavior_agent
    )
    from trip_analysis_agent import (
        TripAnalysisAgent, TripAnalysis, TripPatternSummary, get_trip_analysis_agent
    )
    BEHAVIOR_AGENTS_AVAILABLE = True
    print("Driving behavior and trip analysis agents loaded")
except ImportError as e:
    BEHAVIOR_AGENTS_AVAILABLE = False
    print(f"Note: Driving behavior/trip analysis agents not available: {e}")

logger = logging.getLogger(__name__)


@dataclass
class EnhancedPrediction:
    """Complete enhanced prediction result."""
    vehicle_id: str
    timestamp: str
    operating_state: str

    # Health scores
    overall_health_score: float
    subsystem_scores: Dict[str, float]

    # Predictions
    failure_detections: List[Dict]
    rul_predictions: List[Dict]

    # Supporting data
    derived_features: Dict[str, Any]
    anomaly_scores: Dict[str, float]
    confidence: Dict[str, Any]

    # Recommendations
    immediate_actions: List[str]
    scheduled_maintenance: List[Dict]

    # External sensor data (if available)
    external_sensor_results: Optional[Dict] = None

    # LSTM deep learning predictions (30-60 day horizon)
    lstm_prediction: Optional[Dict] = None

    # Autoencoder anomaly detection results
    autoencoder_anomaly: Optional[Dict] = None

    # Physics validation results
    physics_validation: Optional[Dict] = None

    # Prediction ID for feedback tracking
    prediction_id: Optional[str] = None

    # Research-based intelligence (LLM-derived features)
    research_applied: bool = False
    research_multiplier: float = 1.0
    known_issues_count: int = 0
    estimated_repair_costs: Optional[Dict[str, int]] = None

    # Fleet comparison data
    fleet_comparison: Optional[Dict] = None

    # Recall alerts
    recall_warning: bool = False
    recall_severity: float = 0.0
    active_recalls: Optional[List[Dict]] = None

    # Module degradation tracking - tracks which AI modules failed or are unavailable
    # Used to apply confidence penalties when predictions are made without full AI stack
    degraded_modules: List[str] = field(default_factory=list)
    degradation_penalty: float = 0.0  # 0.0 = no penalty, up to 0.3 max

    # Driving behavior analysis (from server-side agent)
    # Provides safety scores, patterns, and coaching recommendations
    driving_behavior: Optional[Dict] = None
    driver_safety_score: Optional[int] = None
    driving_risk_factor: float = 1.0  # 1.0 = normal, >1.0 = aggressive driving increases wear

    # Trip pattern analysis (from server-side agent)
    # Provides fuel efficiency, trip patterns, and usage metrics
    trip_patterns: Optional[Dict] = None
    usage_intensity: float = 1.0  # 1.0 = normal, >1.0 = heavy usage accelerates wear


class EnhancedPredictionEngine:
    """
    Main integration point for all enhanced AI capabilities.
    Coordinates all modules to provide comprehensive predictions.
    """

    def __init__(self, config=None):
        """Initialize the enhanced prediction engine."""
        self.config = config

        # Initialize all component modules
        logger.info("Initializing Enhanced Prediction Engine components...")

        self.feature_engineering = AdvancedFeatureEngineering(config)
        self.failure_correlator = FailureCorrelationEngine(config)
        self.rul_estimator = RULEstimator(config)
        self.baseline_learner = VehicleBaselineLearning(config)
        self.confidence_scorer = PredictionConfidenceScorer(config)
        self.sensor_processor = ExternalSensorProcessor(config)

        # Initialize LSTM deep learning predictor
        self.lstm_predictor: Optional[LSTMPredictor] = None
        if LSTM_AVAILABLE:
            try:
                self.lstm_predictor = get_lstm_predictor()
                logger.info("LSTM predictor initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize LSTM predictor: {e}")

        # Initialize feedback collector for labeled data
        self.feedback_collector: Optional[FeedbackCollector] = None
        if FEEDBACK_AVAILABLE:
            try:
                self.feedback_collector = get_feedback_collector()
                logger.info("Feedback collector initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize feedback collector: {e}")

        # Initialize ESP32 sensor bridge
        self.esp32_bridge: Optional[ESP32SensorBridge] = None
        if ESP32_AVAILABLE:
            try:
                self.esp32_bridge = get_sensor_bridge()
                logger.info("ESP32 sensor bridge initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize ESP32 bridge: {e}")

        # Initialize LSTM Autoencoder for anomaly detection
        self.autoencoder = None
        if AUTOENCODER_AVAILABLE:
            try:
                from lstm_autoencoder import get_lstm_autoencoder
                self.autoencoder = get_lstm_autoencoder()
                logger.info("LSTM Autoencoder initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize LSTM Autoencoder: {e}")

        # Initialize Physics Constraints Validator
        self.physics_validator = None
        if PHYSICS_AVAILABLE:
            try:
                from physics_constraints import get_physics_validator
                self.physics_validator = get_physics_validator()
                logger.info("Physics Constraints Validator initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Physics Validator: {e}")

        # Storage path for integrated results
        self.storage_path = CONFIG.AI_PREDICTIONS_DIR
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Prediction history
        self.prediction_history: Dict[str, List[EnhancedPrediction]] = {}

        # OBD data buffer for LSTM sequences (per vehicle)
        self.obd_sequence_buffer: Dict[str, List[Dict]] = {}
        self.sequence_buffer_size = 100  # Keep last 100 readings for LSTM

        # Module degradation tracking - tracks which modules are unavailable or failed
        # This allows confidence penalties when predictions lack full AI stack
        self.module_status: Dict[str, bool] = {
            'lstm_predictor': self.lstm_predictor is not None,
            'feedback_collector': self.feedback_collector is not None,
            'esp32_bridge': self.esp32_bridge is not None,
            'autoencoder': self.autoencoder is not None,
            'physics_validator': self.physics_validator is not None,
        }
        self._log_module_status()

        # Integration with existing modules (set externally)
        self.unified_ai = None
        self.predictive_engine = None

        # Initialize Research Feature Extractor for LLM-based intelligence
        self.research_extractor: Optional[ResearchFeatureExtractor] = None
        if RESEARCH_FEATURES_AVAILABLE:
            try:
                self.research_extractor = get_feature_extractor()
                logger.info("Research feature extractor initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize research extractor: {e}")

        # Initialize Fleet Learning Aggregator
        self.fleet_aggregator: Optional[FleetLearningAggregator] = None
        if FLEET_LEARNING_AVAILABLE:
            try:
                self.fleet_aggregator = get_fleet_aggregator()
                logger.info("Fleet learning aggregator initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize fleet aggregator: {e}")

        # Initialize Recall Monitor
        self.recall_monitor: Optional[RecallMonitor] = None
        if RECALL_MONITOR_AVAILABLE:
            try:
                self.recall_monitor = get_recall_monitor()
                logger.info("Recall monitor initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize recall monitor: {e}")

        # Update module status after all modules initialized
        self.module_status.update({
            'research_extractor': self.research_extractor is not None,
            'fleet_aggregator': self.fleet_aggregator is not None,
            'recall_monitor': self.recall_monitor is not None,
        })

        logger.info("Enhanced Prediction Engine initialized successfully")
        logger.info(f"  - LSTM: {'enabled' if self.lstm_predictor else 'disabled'}")
        logger.info(f"  - Feedback: {'enabled' if self.feedback_collector else 'disabled'}")
        logger.info(f"  - ESP32: {'enabled' if self.esp32_bridge else 'disabled'}")
        logger.info(f"  - Autoencoder: {'enabled' if self.autoencoder else 'disabled'}")
        logger.info(f"  - Physics: {'enabled' if self.physics_validator else 'disabled'}")
        logger.info(f"  - Research: {'enabled' if self.research_extractor else 'disabled'}")
        logger.info(f"  - Fleet Learning: {'enabled' if self.fleet_aggregator else 'disabled'}")
        logger.info(f"  - Recall Monitor: {'enabled' if self.recall_monitor else 'disabled'}")

        # Log any degraded modules
        degraded = self._get_degraded_modules()
        if degraded:
            penalty = self._calculate_degradation_penalty(degraded)
            logger.warning(f"  - Degradation penalty: {penalty:.1%} (modules unavailable: {', '.join(degraded)})")

    def set_unified_ai(self, unified_ai):
        """Set reference to UnifiedAIModule for integration."""
        self.unified_ai = unified_ai

    def set_predictive_engine(self, predictive_engine):
        """Set reference to PredictiveFailureEngine for integration."""
        self.predictive_engine = predictive_engine

    def _log_module_status(self):
        """Log the status of all AI modules for transparency."""
        available = sum(1 for v in self.module_status.values() if v)
        total = len(self.module_status)
        logger.info(f"AI Module Status: {available}/{total} modules active")
        for module, status in self.module_status.items():
            if not status:
                logger.warning(f"  - {module}: UNAVAILABLE (predictions may be less accurate)")

    def _get_degraded_modules(self) -> List[str]:
        """Get list of currently degraded/unavailable modules."""
        degraded = [name for name, available in self.module_status.items() if not available]
        # Also check runtime module failures
        if self.research_extractor is None:
            degraded.append('research_extractor')
        if self.fleet_aggregator is None:
            degraded.append('fleet_aggregator')
        if self.recall_monitor is None:
            degraded.append('recall_monitor')
        return degraded

    def _calculate_degradation_penalty(self, degraded_modules: List[str]) -> float:
        """
        Calculate confidence penalty based on unavailable modules.

        Critical modules have higher penalty weights:
        - lstm_predictor: 0.10 (critical for long-term predictions)
        - autoencoder: 0.08 (important for anomaly detection)
        - physics_validator: 0.05 (validation layer)
        - research_extractor: 0.04 (LLM-based intelligence)
        - fleet_aggregator: 0.03 (cross-vehicle learning)

        Returns: penalty value 0.0 to 0.3 (capped)
        """
        PENALTY_WEIGHTS = {
            'lstm_predictor': 0.10,
            'autoencoder': 0.08,
            'physics_validator': 0.05,
            'research_extractor': 0.04,
            'fleet_aggregator': 0.03,
            'recall_monitor': 0.02,
            'feedback_collector': 0.02,
            'esp32_bridge': 0.01,
        }

        total_penalty = 0.0
        for module in degraded_modules:
            total_penalty += PENALTY_WEIGHTS.get(module, 0.02)

        # Cap at 30% max penalty to avoid completely discrediting predictions
        return min(0.30, total_penalty)

    def _get_vehicle_id(self, profile: Optional[Dict]) -> str:
        """Extract vehicle ID from profile."""
        if not profile:
            return "unknown"
        return str(profile.get('profile_id', profile.get('vin', profile.get('name', 'unknown'))))

    def process_snapshot(
        self,
        obd_data: Dict[str, Any],
        profile: Optional[Dict] = None,
        active_dtcs: List[str] = None,
        external_sensor_data: Dict[str, Any] = None,
        current_mileage: int = None,
        research_features: Optional['ResearchFeatures'] = None,
        research_data: Optional[Dict[str, Any]] = None
    ) -> EnhancedPrediction:
        """
        Process a data snapshot through all enhancement modules.

        Args:
            obd_data: Current OBD-II sensor readings
            profile: Vehicle profile dictionary
            active_dtcs: List of active DTC codes
            external_sensor_data: Data from ESP32 sensors (optional)
            current_mileage: Current vehicle mileage (optional)
            research_features: Pre-extracted ResearchFeatures from LLM research (optional)
            research_data: Raw research data dict to extract features from (optional)

        Returns:
            EnhancedPrediction with comprehensive analysis
        """
        vehicle_id = self._get_vehicle_id(profile)
        timestamp = datetime.now()
        active_dtcs = active_dtcs or []

        # Generate unique prediction ID for feedback tracking
        prediction_id = f"PRED_{vehicle_id}_{timestamp.strftime('%Y%m%d%H%M%S%f')}"

        # Step 0: Add OBD data to sequence buffer for LSTM
        self._add_to_sequence_buffer(vehicle_id, obd_data, timestamp)

        # Step 0.5: Extract or use research features from LLM research
        if research_features is None and research_data is not None and self.research_extractor:
            try:
                research_features = self.research_extractor.extract_features(research_data)
                logger.debug(f"Extracted research features for {vehicle_id}")
            except Exception as e:
                logger.warning(f"Failed to extract research features: {e}")

        # Step 1: Process through feature engineering
        processed_data = self.feature_engineering.process_snapshot(obd_data, profile)
        derived_features = processed_data.get('derived_features', {})

        # Step 2: Add to baseline learning
        learning_status = self.baseline_learner.add_sample(obd_data, profile)

        # Step 3: Get anomaly scores against baseline
        anomaly_scores = self.baseline_learner.get_anomaly_score(obd_data, profile)

        # Step 4: Detect failures through correlation engine
        failure_detections = self.failure_correlator.analyze(
            obd_data, derived_features, active_dtcs
        )

        # Step 5: Estimate RUL for components
        rul_predictions = self.rul_estimator.estimate_all_components(
            vehicle_id, obd_data, current_mileage
        )

        # Step 6: Get ESP32 external sensor data if bridge is active
        external_results = None
        if self.esp32_bridge and not external_sensor_data:
            # Try to get recent data from ESP32 bridge
            try:
                esp32_features = self.esp32_bridge.get_features_for_prediction(vehicle_id)
                if esp32_features:
                    external_sensor_data = esp32_features
            except Exception as e:
                logger.debug(f"No ESP32 data available: {e}")

        # Process external sensor data if available
        if external_sensor_data:
            external_results = self.sensor_processor.process_packet(external_sensor_data)
            # Add external anomalies to failure detections
            for anomaly in external_results.get('anomalies', []):
                failure_detections.append(FailureDetection(
                    rule_id=f"external_{anomaly.get('type', 'unknown')}",
                    name=anomaly.get('type', 'Unknown Anomaly'),
                    description=anomaly.get('message', ''),
                    category='sensors',
                    severity=3,
                    confidence=0.75,
                    evidence=[anomaly.get('message', '')],
                    repair_urgency='soon',
                    typical_repair='Inspect component',
                    estimated_cost=(50, 200),
                    timestamp=timestamp.isoformat()
                ))

        # Step 7: Run LSTM deep learning prediction (30-60 day horizon)
        lstm_prediction = None
        if self.lstm_predictor:
            try:
                sequence = self.obd_sequence_buffer.get(vehicle_id, [])
                if len(sequence) >= 10:  # Need minimum sequence length
                    lstm_result = self.lstm_predictor.predict(sequence)
                    if lstm_result:
                        lstm_prediction = {
                            'failure_probability': lstm_result.failure_probability,
                            'failure_type': lstm_result.failure_type,
                            'days_to_failure': lstm_result.days_to_failure,
                            'confidence': lstm_result.confidence,
                            'contributing_features': lstm_result.contributing_features,
                            'model_version': lstm_result.model_version
                        }

                        # If LSTM predicts high failure probability, add to failure detections
                        if lstm_result.failure_probability > 0.7:
                            failure_detections.append(FailureDetection(
                                rule_id=f"lstm_{lstm_result.failure_type}",
                                name=f"LSTM: {lstm_result.failure_type.replace('_', ' ').title()} Risk",
                                description=f"Deep learning predicts {lstm_result.failure_probability*100:.0f}% chance of {lstm_result.failure_type} failure in {lstm_result.days_to_failure} days",
                                category='prediction',
                                severity=4 if lstm_result.failure_probability > 0.85 else 3,
                                confidence=lstm_result.confidence,
                                evidence=[f"LSTM model v{lstm_result.model_version}"],
                                repair_urgency='soon' if lstm_result.days_to_failure < 30 else 'scheduled',
                                typical_repair=f"Inspect {lstm_result.failure_type}",
                                estimated_cost=(100, 500),
                                timestamp=timestamp.isoformat()
                            ))
            except Exception as e:
                logger.debug(f"LSTM prediction failed: {e}")

        # Step 7.5: Run Autoencoder Anomaly Detection
        autoencoder_result = None
        if self.autoencoder:
            try:
                sequence = self.obd_sequence_buffer.get(vehicle_id, [])
                if len(sequence) >= 10:  # Need minimum sequence length
                    autoencoder_result = self.autoencoder.detect_anomalies(sequence)
                    if autoencoder_result:
                        autoencoder_result = {
                            'anomaly_detected': autoencoder_result.anomaly_detected,
                            'anomaly_score': autoencoder_result.anomaly_score,
                            'anomaly_type': autoencoder_result.anomaly_type,
                            'confidence': autoencoder_result.confidence,
                            'reconstruction_error': autoencoder_result.reconstruction_error,
                            'feature_anomalies': autoencoder_result.feature_anomalies,
                            'model_version': autoencoder_result.model_version
                        }

                        # If autoencoder detects anomaly, add to failure detections
                        if autoencoder_result['anomaly_detected']:
                            failure_detections.append(FailureDetection(
                                rule_id=f"autoencoder_{autoencoder_result['anomaly_type']}",
                                name=f"Autoencoder: {autoencoder_result['anomaly_type'].replace('_', ' ').title()}",
                                description=f"Anomaly detection model found {autoencoder_result['anomaly_type']} with score {autoencoder_result['anomaly_score']:.3f}",
                                category='anomaly',
                                severity=3 if autoencoder_result['anomaly_score'] < 0.8 else 4,
                                confidence=autoencoder_result['confidence'],
                                evidence=[f"Autoencoder v{autoencoder_result['model_version']}"],
                                repair_urgency='soon' if autoencoder_result['anomaly_score'] > 0.7 else 'scheduled',
                                typical_repair="Investigate anomaly source",
                                estimated_cost=(50, 200),
                                timestamp=timestamp.isoformat()
                            ))
            except Exception as e:
                logger.debug(f"Autoencoder anomaly detection failed: {e}")

        # Step 7.6: Run Physics Validation
        physics_result = None
        if self.physics_validator:
            try:
                # Get recent readings for physics validation
                recent_readings = self.obd_sequence_buffer.get(vehicle_id, [])[-10:]  # Last 10 readings
                if recent_readings:
                    physics_validation = self.physics_validator.validate_snapshot(
                        obd_data, recent_readings
                    )
                    physics_result = {
                        'is_valid': physics_validation.is_valid,
                        'overall_confidence': physics_validation.overall_confidence,
                        'physics_consistency_score': physics_validation.physics_consistency_score,
                        'domain_scores': {domain.value: score for domain, score in physics_validation.domain_scores.items()},
                        'violations': [
                            {
                                'domain': v.domain.value,
                                'constraint': v.constraint_name,
                                'severity': v.severity.value,
                                'description': v.description,
                                'violation_score': v.violation_score
                            } for v in physics_validation.violations[:5]  # Top 5 violations
                        ],
                        'violation_count': len(physics_validation.violations)
                    }

                    # Add physics violations as failure detections
                    for violation in physics_validation.violations:
                        if violation.severity in [ConstraintSeverity.CRITICAL, ConstraintSeverity.IMPOSSIBLE]:
                            failure_detections.append(FailureDetection(
                                rule_id=f"physics_{violation.domain.value}_{violation.constraint_name}",
                                name=f"Physics: {violation.constraint_name.replace('_', ' ').title()}",
                                description=violation.description,
                                category='physics',
                                severity=4 if violation.severity == ConstraintSeverity.IMPOSSIBLE else 3,
                                confidence=min(0.9, violation.violation_score + 0.1),
                                evidence=[f"Physics validation: {violation.domain.value}"],
                                repair_urgency='immediate' if violation.severity == ConstraintSeverity.IMPOSSIBLE else 'soon',
                                typical_repair="Check sensor readings and system calibration",
                                estimated_cost=(0, 100),
                                timestamp=timestamp.isoformat()
                            ))
            except Exception as e:
                logger.debug(f"Physics validation failed: {e}")

        # Step 8: Calculate subsystem health scores
        subsystem_scores = self._calculate_subsystem_scores(
            obd_data, derived_features, anomaly_scores, failure_detections
        )

        # Step 8.5: Apply research-based intelligence adjustments
        research_applied = False
        research_multiplier = 1.0
        known_issues_count = 0
        estimated_repair_costs = None
        fleet_comparison_data = None
        recall_warning = False
        recall_severity = 0.0
        active_recalls_list = None

        if research_features is not None:
            research_applied = True
            research_multiplier = research_features.known_issue_multiplier
            known_issues_count = len(research_features.common_failure_parts)
            estimated_repair_costs = research_features.avg_part_costs if research_features.avg_part_costs else None

            # Apply failure probability boosts to matching failure detections
            # CRITICAL FIX: Cap boost to prevent confidence inflation from LLM hallucinations
            MAX_RESEARCH_BOOST = 0.3  # Max 30% confidence increase
            MAX_BOOSTED_CONFIDENCE = 0.85  # Cap boosted confidence to prevent false certainty
            MIN_BASE_CONFIDENCE = 0.3  # Don't boost very weak signals

            for detection in failure_detections:
                component_name = detection.name.lower() if hasattr(detection, 'name') else str(detection.get('name', '')).lower()
                # Normalize component name
                if self.research_extractor:
                    normalized = self.research_extractor._normalize_part_name(component_name)
                    raw_boost = research_features.failure_probability_boost.get(normalized, 0)
                    # Clamp boost to safe range to prevent LLM-derived inflation
                    boost = max(0.0, min(MAX_RESEARCH_BOOST, float(raw_boost)))

                    if boost > 0:
                        # Only boost if base confidence is meaningful
                        if hasattr(detection, 'confidence'):
                            if detection.confidence >= MIN_BASE_CONFIDENCE:
                                detection.confidence = min(MAX_BOOSTED_CONFIDENCE, detection.confidence * (1 + boost))
                        elif isinstance(detection, dict):
                            base_conf = detection.get('confidence', 0.5)
                            if base_conf >= MIN_BASE_CONFIDENCE:
                                detection['confidence'] = min(MAX_BOOSTED_CONFIDENCE, base_conf * (1 + boost))
                        logger.debug(f"Applied capped research boost of {boost} (raw: {raw_boost}) to {normalized}")

            # Apply DTC severity adjustments
            for dtc in active_dtcs:
                prefix = dtc[:3] if len(dtc) >= 3 else dtc
                adjustment = research_features.dtc_severity_adjustments.get(prefix, 1.0)
                if adjustment > 1.0:
                    # Find related failure detections and boost their severity
                    for detection in failure_detections:
                        if hasattr(detection, 'severity'):
                            detection.severity = min(5, int(detection.severity * adjustment))

            # Handle recall warnings
            if research_features.has_active_recalls:
                recall_warning = True
                recall_severity = research_features.recall_severity

        # Step 8.6: Get fleet comparison data if available
        if self.fleet_aggregator and profile:
            try:
                make = profile.get('make', '')
                model = profile.get('model', '')
                year = profile.get('year', 0)
                if make and model and year:
                    vehicle_data = {
                        'vehicle_id': vehicle_id,
                        'make': make,
                        'model': model,
                        'year': year,
                        'health_score': sum(subsystem_scores.values()) / len(subsystem_scores) if subsystem_scores else 0,
                        'component_health': subsystem_scores
                    }
                    comparison = self.fleet_aggregator.compare_vehicle_to_fleet(vehicle_data)
                    if comparison.fleet_size > 0:
                        fleet_comparison_data = comparison.to_dict()
            except Exception as e:
                logger.debug(f"Fleet comparison failed: {e}")

        # Step 8.7: Check for recalls if profile has make/model/year
        if self.recall_monitor and profile:
            try:
                make = profile.get('make', '')
                model = profile.get('model', '')
                year = profile.get('year', 0)
                if make and model and year:
                    recall_summary = self.recall_monitor.get_recall_summary_for_vehicle(make, model, year)
                    if recall_summary.get('has_recalls'):
                        recall_warning = True
                        recall_severity = max(recall_severity, recall_summary.get('critical_recalls', 0) * 0.3)
                        active_recalls_list = recall_summary.get('recalls', [])
            except Exception as e:
                logger.debug(f"Recall check failed: {e}")

        # Step 9: Calculate overall health score
        overall_health = self._calculate_overall_health(
            subsystem_scores, failure_detections, rul_predictions
        )

        # Apply research reliability factor to overall health
        if research_features is not None:
            # Lower reliability = lower health (reliability_factor > 1.0 means less reliable)
            health_adjustment = 2 - research_features.reliability_factor  # 0.8-1.2
            overall_health = max(0, min(100, overall_health * health_adjustment))

        # Step 10: Calculate confidence for this prediction
        confidence = self._calculate_prediction_confidence(
            vehicle_id, len(derived_features), anomaly_scores,
            failure_detections, active_dtcs
        )

        # Step 11: Determine operating state
        operating_state = self._determine_state(obd_data)

        # Step 12: Generate recommendations
        immediate_actions = self._generate_immediate_actions(failure_detections)
        scheduled_maintenance = self._generate_maintenance_schedule(
            rul_predictions, failure_detections
        )

        # Step 13: Calculate module degradation penalty
        degraded_modules = self._get_degraded_modules()
        degradation_penalty = self._calculate_degradation_penalty(degraded_modules)

        # Apply degradation penalty to confidence scores
        if degradation_penalty > 0 and isinstance(confidence, ConfidenceScore):
            # Reduce overall confidence when modules are unavailable
            adjusted_overall = max(0.1, confidence.overall_confidence - degradation_penalty)
            confidence.overall_confidence = adjusted_overall
            logger.debug(f"Applied {degradation_penalty:.1%} degradation penalty. "
                        f"Unavailable modules: {degraded_modules}")

        # -------------------------------------------------
        # DRIVING BEHAVIOR & TRIP ANALYSIS INTEGRATION
        # -------------------------------------------------
        # These agents run on the server and provide driving pattern analysis
        # to adjust component wear predictions based on driver behavior
        driving_behavior_data = None
        driver_safety_score = None
        driving_risk_factor = 1.0
        trip_patterns_data = None
        usage_intensity = 1.0

        if BEHAVIOR_AGENTS_AVAILABLE:
            try:
                # Get database path for agents
                agent_db_path = str(Path(r"C:\OBDserver\Previlium_OBD_Server\data\obd_data.db"))

                # Try to get driving behavior if a driver is associated with this vehicle
                try:
                    behavior_agent = get_driving_behavior_agent(agent_db_path)
                    # Use vehicle_id to find associated driver and analyze behavior
                    behavior_analysis = behavior_agent.analyze_driver(
                        driver_id=vehicle_id,  # May also serve as driver ID
                        vehicle_id=vehicle_id,
                        days=7  # Short-term for immediate risk assessment
                    )

                    if behavior_analysis.confidence >= 0.3:
                        driving_behavior_data = behavior_analysis.to_dict()
                        driver_safety_score = behavior_analysis.overall_safety_score

                        # Calculate driving risk factor based on safety score
                        # Low score = aggressive driving = higher wear rate
                        if driver_safety_score < 50:
                            driving_risk_factor = 1.15  # 15% increased wear for aggressive drivers
                        elif driver_safety_score < 70:
                            driving_risk_factor = 1.08  # 8% increased wear
                        elif driver_safety_score >= 90:
                            driving_risk_factor = 0.95  # 5% reduced wear for smooth drivers

                        logger.debug(f"Driving behavior: score={driver_safety_score}, "
                                    f"risk_factor={driving_risk_factor}")
                except Exception as e:
                    logger.debug(f"Driving behavior analysis not available: {e}")

                # Get trip patterns for usage intensity
                try:
                    trip_agent = get_trip_analysis_agent(agent_db_path)
                    trip_summary = trip_agent.get_pattern_summary(vehicle_id, days=7)

                    if trip_summary.confidence >= 0.3:
                        trip_patterns_data = trip_summary.to_dict()

                        # Calculate usage intensity based on trip frequency
                        if trip_summary.avg_trips_per_day > 5:
                            usage_intensity = 1.15  # Heavy usage - 15% faster wear
                        elif trip_summary.avg_trips_per_day > 3:
                            usage_intensity = 1.08  # Moderate-high usage
                        elif trip_summary.avg_trips_per_day < 0.5:
                            usage_intensity = 0.95  # Light usage - slower wear

                        logger.debug(f"Trip patterns: avg_trips/day={trip_summary.avg_trips_per_day:.1f}, "
                                    f"usage_intensity={usage_intensity}")
                except Exception as e:
                    logger.debug(f"Trip pattern analysis not available: {e}")

                # Apply driving behavior adjustments to predictions
                if driving_risk_factor != 1.0 or usage_intensity != 1.0:
                    combined_factor = driving_risk_factor * usage_intensity

                    # Adjust RUL predictions
                    for rul in rul_predictions:
                        if hasattr(rul, 'estimated_days'):
                            rul.estimated_days = int(rul.estimated_days / combined_factor)

                    # Adjust failure detection probabilities for wear-related components
                    wear_components = ['brake_pads', 'tires', 'transmission', 'clutch',
                                      'suspension', 'cv_joints', 'wheel_bearings']
                    for detection in failure_detections:
                        component = getattr(detection, 'name', '').lower()
                        if any(wc in component for wc in wear_components):
                            if hasattr(detection, 'confidence'):
                                original_prob = detection.confidence
                                detection.confidence = min(0.95, original_prob * combined_factor)
                                if combined_factor > 1.0:
                                    detection.notes = getattr(detection, 'notes', [])
                                    if isinstance(detection.notes, list):
                                        detection.notes.append(f"Adjusted +{(combined_factor-1)*100:.0f}% for driving behavior")

                    logger.debug(f"Applied combined behavior/usage factor: {combined_factor:.2f}")

            except Exception as e:
                logger.warning(f"Driving behavior/trip integration error: {e}")
                degraded_modules.append("behavior_agents")

        # Create prediction result
        prediction = EnhancedPrediction(
            vehicle_id=vehicle_id,
            timestamp=timestamp.isoformat(),
            operating_state=operating_state,
            overall_health_score=round(overall_health, 1),
            subsystem_scores=subsystem_scores,
            failure_detections=[self._detection_to_dict(d) for d in failure_detections],
            rul_predictions=[self._rul_to_dict(r) for r in rul_predictions],
            derived_features=derived_features,
            anomaly_scores=anomaly_scores,
            confidence=asdict(confidence) if hasattr(confidence, '__dict__') else confidence,
            immediate_actions=immediate_actions,
            scheduled_maintenance=scheduled_maintenance,
            external_sensor_results=external_results,
            lstm_prediction=lstm_prediction,
            autoencoder_anomaly=autoencoder_result,
            physics_validation=physics_result,
            prediction_id=prediction_id,
            # Research-based intelligence
            research_applied=research_applied,
            research_multiplier=research_multiplier,
            known_issues_count=known_issues_count,
            estimated_repair_costs=estimated_repair_costs,
            # Fleet comparison
            fleet_comparison=fleet_comparison_data,
            # Recall alerts
            recall_warning=recall_warning,
            recall_severity=recall_severity,
            active_recalls=active_recalls_list,
            # Module degradation tracking
            degraded_modules=degraded_modules,
            degradation_penalty=degradation_penalty,
            # Driving behavior analysis (from server-side agent)
            driving_behavior=driving_behavior_data,
            driver_safety_score=driver_safety_score,
            driving_risk_factor=driving_risk_factor,
            # Trip pattern analysis (from server-side agent)
            trip_patterns=trip_patterns_data,
            usage_intensity=usage_intensity
        )

        # Store in history
        if vehicle_id not in self.prediction_history:
            self.prediction_history[vehicle_id] = []
        self.prediction_history[vehicle_id].append(prediction)
        if len(self.prediction_history[vehicle_id]) > 1000:
            self.prediction_history[vehicle_id] = self.prediction_history[vehicle_id][-500:]

        # Update RUL readings for trending
        self._update_rul_readings(vehicle_id, obd_data, current_mileage)

        # Register prediction for feedback tracking
        if self.feedback_collector and lstm_prediction:
            try:
                sequence_start = self.obd_sequence_buffer[vehicle_id][0].get('timestamp', timestamp.isoformat())
                self.feedback_collector.register_prediction(
                    prediction_id=prediction_id,
                    vehicle_id=vehicle_id,
                    prediction_type=lstm_prediction['failure_type'],
                    predicted_component=lstm_prediction['failure_type'],
                    predicted_failure_date=(timestamp + timedelta(days=lstm_prediction['days_to_failure'])).isoformat(),
                    confidence_score=lstm_prediction['confidence'],
                    sequence_start_date=sequence_start
                )
            except Exception as e:
                logger.debug(f"Failed to register prediction for feedback: {e}")

        return prediction

    def _add_to_sequence_buffer(self, vehicle_id: str, obd_data: Dict, timestamp: datetime):
        """Add OBD reading to sequence buffer for LSTM."""
        if vehicle_id not in self.obd_sequence_buffer:
            self.obd_sequence_buffer[vehicle_id] = []

        # Add timestamp to data
        data_with_ts = dict(obd_data)
        data_with_ts['timestamp'] = timestamp.isoformat()

        self.obd_sequence_buffer[vehicle_id].append(data_with_ts)

        # Keep buffer size limited
        if len(self.obd_sequence_buffer[vehicle_id]) > self.sequence_buffer_size:
            self.obd_sequence_buffer[vehicle_id] = self.obd_sequence_buffer[vehicle_id][-self.sequence_buffer_size:]

    def _calculate_subsystem_scores(
        self,
        data: Dict,
        derived: Dict,
        anomalies: Dict,
        failures: List
    ) -> Dict[str, float]:
        """Calculate health scores for each vehicle subsystem.

        CRITICAL FIX: Scores now start at a neutral baseline (70%) rather than 100%.
        This prevents the system from reporting "perfect health" when there's
        simply no data or no detected issues. Positive evidence increases scores,
        negative evidence decreases them.
        """
        # Start at neutral baseline - absence of evidence != perfect health
        NEUTRAL_BASELINE = 70.0
        scores = {
            'engine': NEUTRAL_BASELINE,
            'cooling': NEUTRAL_BASELINE,
            'electrical': NEUTRAL_BASELINE,
            'fuel_system': NEUTRAL_BASELINE,
            'transmission': NEUTRAL_BASELINE,
            'emissions': NEUTRAL_BASELINE
        }

        # Boost scores slightly for each sensor with normal readings
        # This rewards having actual data vs. assuming perfect health
        sensor_to_subsystem = {
            'rpm': 'engine',
            'engine_load': 'engine',
            'coolant_temp': 'cooling',
            'battery_voltage': 'electrical',
            'fuel_trim_short': 'fuel_system',
            'fuel_trim_long': 'fuel_system',
            'speed': 'transmission'
        }

        # Award points for having data with normal z-scores
        for sensor, z_score in anomalies.items():
            subsystem = sensor_to_subsystem.get(sensor)
            if subsystem:
                if z_score < 1.5:
                    # Normal reading - boost confidence in health
                    scores[subsystem] = min(100, scores[subsystem] + 5)
                elif z_score < 2:
                    # Slightly elevated but ok
                    scores[subsystem] = min(100, scores[subsystem] + 2)

        # Deduct from anomaly scores
        sensor_to_subsystem = {
            'rpm': 'engine',
            'engine_load': 'engine',
            'coolant_temp': 'cooling',
            'battery_voltage': 'electrical',
            'fuel_trim_short': 'fuel_system',
            'fuel_trim_long': 'fuel_system',
            'speed': 'transmission'
        }

        for sensor, z_score in anomalies.items():
            subsystem = sensor_to_subsystem.get(sensor)
            if subsystem and z_score > 2:
                # Deduct points based on z-score
                deduction = min(30, (z_score - 2) * 10)
                scores[subsystem] = max(0, scores[subsystem] - deduction)

        # Deduct from failure detections
        for failure in failures:
            category = failure.category if hasattr(failure, 'category') else failure.get('category', '')
            severity = failure.severity if hasattr(failure, 'severity') else failure.get('severity', 1)

            if category in scores:
                deduction = severity * 10
                scores[category] = max(0, scores[category] - deduction)

        # Round all scores
        return {k: round(v, 1) for k, v in scores.items()}

    def _calculate_overall_health(
        self,
        subsystem_scores: Dict[str, float],
        failures: List,
        rul_predictions: List
    ) -> float:
        """Calculate overall vehicle health score."""
        # Weighted average of subsystem scores
        weights = {
            'engine': 0.25,
            'cooling': 0.15,
            'electrical': 0.15,
            'fuel_system': 0.20,
            'transmission': 0.15,
            'emissions': 0.10
        }

        weighted_sum = sum(
            subsystem_scores.get(sys, 100) * weight
            for sys, weight in weights.items()
        )

        # Deduct for critical failures
        for failure in failures:
            severity = failure.severity if hasattr(failure, 'severity') else failure.get('severity', 1)
            if severity >= 4:
                weighted_sum -= 10
            elif severity >= 3:
                weighted_sum -= 5

        # Deduct for low RUL
        for rul in rul_predictions:
            health = rul.current_health_pct if hasattr(rul, 'current_health_pct') else rul.get('current_health_pct', 100)
            if health < 30:
                weighted_sum -= 5
            elif health < 50:
                weighted_sum -= 2

        return max(0, min(100, weighted_sum))

    def _calculate_prediction_confidence(
        self,
        vehicle_id: str,
        feature_count: int,
        anomalies: Dict,
        failures: List,
        dtcs: List
    ) -> ConfidenceScore:
        """Calculate confidence for the overall prediction."""
        baseline = self.baseline_learner.get_baseline(vehicle_id)
        has_baseline = baseline is not None

        max_z = max(anomalies.values()) if anomalies else 0

        return self.confidence_scorer.calculate_confidence(
            prediction_type='vehicle_health',
            data_points=feature_count * 10,  # Approximate
            supporting_evidence=len(failures),
            contradicting_evidence=0,
            pattern_strength=0.7,
            data_age_hours=0,
            baseline_z_score=max_z,
            related_dtcs=len(dtcs),
            vehicle_has_baseline=has_baseline
        )

    def _determine_state(self, data: Dict) -> str:
        """Determine vehicle operating state."""
        rpm = self._get_value(data, ['rpm', 'engine_rpm'])
        speed = self._get_value(data, ['speed', 'vehicle_speed'])
        load = self._get_value(data, ['engine_load', 'calculated_engine_load'])

        if rpm is None or rpm < 100:
            return 'off'
        if speed is not None and speed < 5:
            if load is not None and load < 30:
                return 'idle'
            return 'warming_up'
        if load is not None and load > 80:
            return 'high_load'
        if speed is not None and speed > 30:
            return 'cruising'

        return 'unknown'

    def _get_value(self, data: Dict, keys: List[str]) -> Optional[float]:
        """Get value from data trying multiple keys."""
        for key in keys:
            if key in data and data[key] is not None:
                try:
                    return float(data[key])
                except (ValueError, TypeError):
                    pass
        return None

    def _generate_immediate_actions(self, failures: List) -> List[str]:
        """Generate list of immediate actions based on detected failures."""
        actions = []

        for failure in failures:
            severity = failure.severity if hasattr(failure, 'severity') else failure.get('severity', 1)
            urgency = failure.repair_urgency if hasattr(failure, 'repair_urgency') else failure.get('repair_urgency', '')
            name = failure.name if hasattr(failure, 'name') else failure.get('name', 'Unknown')
            repair = failure.typical_repair if hasattr(failure, 'typical_repair') else failure.get('typical_repair', '')

            if severity >= 4 or urgency == 'immediate':
                actions.append(f"CRITICAL: {name} - {repair}")
            elif severity >= 3 or urgency == 'soon':
                actions.append(f"URGENT: {name} - {repair}")

        return actions

    def _generate_maintenance_schedule(
        self,
        rul_predictions: List,
        failures: List
    ) -> List[Dict]:
        """Generate scheduled maintenance items."""
        schedule = []

        # From RUL predictions
        for rul in rul_predictions:
            health = rul.current_health_pct if hasattr(rul, 'current_health_pct') else rul.get('current_health_pct', 100)
            name = rul.component_name if hasattr(rul, 'component_name') else rul.get('component_name', 'Unknown')
            rul_miles = rul.predicted_rul_miles if hasattr(rul, 'predicted_rul_miles') else rul.get('predicted_rul_miles')
            rul_days = rul.predicted_rul_days if hasattr(rul, 'predicted_rul_days') else rul.get('predicted_rul_days')
            recommendation = rul.recommendation if hasattr(rul, 'recommendation') else rul.get('recommendation', '')

            if health < 80:
                schedule.append({
                    'component': name,
                    'health_pct': health,
                    'rul_miles': rul_miles,
                    'rul_days': rul_days,
                    'recommendation': recommendation,
                    'priority': 'high' if health < 50 else 'medium'
                })

        # From failure detections (non-critical)
        for failure in failures:
            severity = failure.severity if hasattr(failure, 'severity') else failure.get('severity', 1)
            urgency = failure.repair_urgency if hasattr(failure, 'repair_urgency') else failure.get('repair_urgency', '')

            if urgency == 'scheduled':
                name = failure.name if hasattr(failure, 'name') else failure.get('name', 'Unknown')
                repair = failure.typical_repair if hasattr(failure, 'typical_repair') else failure.get('typical_repair', '')
                cost = failure.estimated_cost if hasattr(failure, 'estimated_cost') else failure.get('estimated_cost', (0, 0))

                schedule.append({
                    'component': name,
                    'action': repair,
                    'estimated_cost': cost,
                    'priority': 'low'
                })

        return schedule

    def _update_rul_readings(self, vehicle_id: str, data: Dict, mileage: int = None):
        """Update RUL estimation with current readings."""
        # Battery voltage for battery/alternator RUL
        voltage = self._get_value(data, ['battery_voltage', 'control_module_voltage'])
        rpm = self._get_value(data, ['rpm', 'engine_rpm'])

        if voltage is not None:
            # Resting voltage (engine off) goes to battery
            if rpm is None or rpm < 100:
                self.rul_estimator.add_reading(
                    vehicle_id, 'battery', voltage, mileage
                )
            else:
                # Running voltage goes to alternator
                self.rul_estimator.add_reading(
                    vehicle_id, 'alternator', voltage, mileage
                )

        # Fuel trim for MAF/fuel system
        ltft = self._get_value(data, ['long_term_fuel_trim_1', 'fuel_trim_long'])
        if ltft is not None:
            self.rul_estimator.add_reading(
                vehicle_id, 'maf_sensor', abs(ltft), mileage
            )

    def _detection_to_dict(self, detection) -> Dict:
        """Convert FailureDetection to dictionary."""
        if hasattr(detection, '__dict__'):
            return {k: v for k, v in detection.__dict__.items() if not k.startswith('_')}
        return detection

    def _rul_to_dict(self, rul) -> Dict:
        """Convert RULPrediction to dictionary."""
        if hasattr(rul, '__dict__'):
            return {k: v for k, v in rul.__dict__.items() if not k.startswith('_')}
        return rul

    def get_prediction_summary(self, vehicle_id: str) -> Dict[str, Any]:
        """Get summary of recent predictions for a vehicle."""
        history = self.prediction_history.get(vehicle_id, [])

        if not history:
            return {
                'vehicle_id': vehicle_id,
                'has_data': False,
                'message': 'No prediction history available'
            }

        recent = history[-1]

        return {
            'vehicle_id': vehicle_id,
            'has_data': True,
            'last_prediction': recent.timestamp,
            'overall_health': recent.overall_health_score,
            'subsystem_scores': recent.subsystem_scores,
            'active_issues': len(recent.failure_detections),
            'immediate_actions': recent.immediate_actions,
            'prediction_count': len(history)
        }

    def get_learning_status(self, vehicle_id: str) -> Dict[str, Any]:
        """Get learning status for a vehicle."""
        return {
            'baseline': self.baseline_learner.get_learning_status(vehicle_id),
            'feature_engineering': self.feature_engineering.get_feature_summary(vehicle_id),
            'confidence_calibration': self.confidence_scorer.get_calibration_status()
        }

    def save_all_data(self):
        """Save all module data to disk."""
        self.feature_engineering._save_baselines()
        self.rul_estimator.save_data()
        self.confidence_scorer._save_data()
        logger.info("All enhanced prediction data saved")

    def process_feedback(self, vehicle_id: str, prediction_id: str,
                          prediction_type: str, was_correct: bool,
                          actual_outcome: str = None) -> Dict[str, Any]:
        """
        Record feedback on a prediction's accuracy.

        Args:
            vehicle_id: Vehicle ID
            prediction_id: ID of the prediction being rated
            prediction_type: Type of prediction
            was_correct: Whether the prediction was correct
            actual_outcome: What actually happened

        Returns:
            Feedback recording result
        """
        # Find the prediction in history
        history = self.prediction_history.get(vehicle_id, [])

        # Get confidence at time of prediction
        confidence_at_prediction = 0.5  # Default
        for pred in history:
            if pred.timestamp == prediction_id:
                confidence_at_prediction = pred.confidence.get('overall_confidence', 0.5)
                break

        return self.confidence_scorer.record_feedback(
            prediction_id=prediction_id,
            prediction_type=prediction_type,
            predicted_outcome='issue_detected' if not was_correct else 'correct',
            actual_outcome=actual_outcome or ('correct' if was_correct else 'incorrect'),
            confidence_at_prediction=confidence_at_prediction
        )

    # =========================================================================
    # Service History & Feedback Management
    # =========================================================================

    def add_service_record(
        self,
        vehicle_id: str,
        service_date: str,
        mileage: int,
        service_type: str,
        component: str,
        description: str,
        failure_type: Optional[str] = None,
        cost: float = 0.0,
        shop_name: Optional[str] = None,
        parts_replaced: Optional[List[str]] = None,
        dtc_codes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Add a service record for feedback learning.

        This automatically links to pending predictions and creates
        labeled training data for LSTM.
        """
        if not self.feedback_collector:
            return {'success': False, 'error': 'Feedback collector not available'}

        record_id = self.feedback_collector.add_service_record(
            vehicle_id=vehicle_id,
            service_date=service_date,
            mileage=mileage,
            service_type=service_type,
            component=component,
            description=description,
            failure_type=failure_type,
            cost=cost,
            shop_name=shop_name,
            parts_replaced=parts_replaced,
            dtc_codes=dtc_codes
        )

        return {'success': True, 'record_id': record_id}

    def confirm_prediction(
        self,
        prediction_id: str,
        was_correct: bool,
        actual_outcome: str,
        confirmation_source: str = 'manual_user',
        actual_failure_date: Optional[str] = None,
        user_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Confirm whether a prediction was correct.
        Used to build labeled training data for LSTM.
        """
        if not self.feedback_collector:
            return {'success': False, 'error': 'Feedback collector not available'}

        return self.feedback_collector.confirm_prediction(
            prediction_id=prediction_id,
            was_correct=was_correct,
            actual_outcome=actual_outcome,
            confirmation_source=confirmation_source,
            actual_failure_date=actual_failure_date,
            user_notes=user_notes
        )

    def get_pending_predictions(self, vehicle_id: Optional[str] = None) -> List[Dict]:
        """Get predictions awaiting feedback confirmation."""
        if not self.feedback_collector:
            return []
        return self.feedback_collector.get_pending_predictions(vehicle_id)

    def get_service_records(
        self,
        vehicle_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        failure_only: bool = False
    ) -> List[Dict]:
        """Get service records for a vehicle."""
        if not self.feedback_collector:
            return []
        return self.feedback_collector.get_service_records(
            vehicle_id, start_date, end_date, failure_only
        )

    def get_feedback_statistics(self) -> Dict[str, Any]:
        """Get statistics on prediction feedback and training data."""
        if not self.feedback_collector:
            return {'available': False}

        stats = self.feedback_collector.get_statistics()
        stats['available'] = True
        return stats

    # =========================================================================
    # LSTM Training Management
    # =========================================================================

    def train_lstm_model(self, min_samples: int = 50) -> Dict[str, Any]:
        """
        Train or retrain the LSTM model using collected labeled data.

        Args:
            min_samples: Minimum labeled sequences required to train

        Returns:
            Training result
        """
        if not self.lstm_predictor:
            return {'success': False, 'error': 'LSTM predictor not available'}

        if not self.feedback_collector:
            return {'success': False, 'error': 'Feedback collector not available (needed for labeled data)'}

        # Get labeled sequences
        sequences = self.feedback_collector.get_labeled_sequences(min_length_days=7)

        if len(sequences) < min_samples:
            return {
                'success': False,
                'error': f'Insufficient training data: {len(sequences)} sequences (need {min_samples}+)',
                'current_samples': len(sequences)
            }

        # Prepare training data
        training_data = []
        for seq in sequences:
            # Get OBD data for this sequence period
            # In production, this would query historical data storage
            training_data.append({
                'sequence': [],  # Would be filled with actual OBD readings
                'label': {
                    'failure_occurred': seq['failure_occurred'],
                    'failure_type': seq['failure_type'],
                    'days_to_failure': seq['days_to_failure']
                }
            })

        # Train model
        result = self.lstm_predictor.train(training_data)

        # Mark sequences as exported
        if result.get('success'):
            self.feedback_collector.mark_sequences_exported(
                [s['sequence_id'] for s in sequences]
            )

        return result

    def get_lstm_status(self) -> Dict[str, Any]:
        """Get LSTM model status and training info."""
        if not self.lstm_predictor:
            return {
                'available': False,
                'reason': 'LSTM predictor not initialized (TensorFlow may not be installed)'
            }

        info = self.lstm_predictor.get_model_info()
        info['available'] = True
        return info

    # =========================================================================
    # ESP32 Sensor Bridge Management
    # =========================================================================

    def start_esp32_bridge(self) -> Dict[str, Any]:
        """Start the ESP32 sensor bridge server."""
        if not self.esp32_bridge:
            return {'success': False, 'error': 'ESP32 bridge not available'}

        try:
            self.esp32_bridge.start()
            return {
                'success': True,
                'http_port': self.esp32_bridge.http_port,
                'message': 'ESP32 sensor bridge started'
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def stop_esp32_bridge(self) -> Dict[str, Any]:
        """Stop the ESP32 sensor bridge server."""
        if not self.esp32_bridge:
            return {'success': False, 'error': 'ESP32 bridge not available'}

        try:
            self.esp32_bridge.stop()
            return {'success': True, 'message': 'ESP32 sensor bridge stopped'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_esp32_status(self, vehicle_id: Optional[str] = None) -> Dict[str, Any]:
        """Get ESP32 sensor bridge status and sensor health."""
        if not self.esp32_bridge:
            return {'available': False}

        result = {
            'available': True,
            'running': self.esp32_bridge.running,
            'http_port': self.esp32_bridge.http_port,
            'sensor_count': len(self.esp32_bridge.sensors),
            'sensor_health': {
                sid: {
                    'is_online': h.is_online,
                    'last_reading': h.last_reading,
                    'readings_count': h.readings_count,
                    'avg_quality': h.avg_quality
                }
                for sid, h in self.esp32_bridge.sensor_health.items()
            }
        }

        if vehicle_id:
            result['vehicle_summary'] = self.esp32_bridge.get_sensor_summary(vehicle_id)

        return result

    def get_external_sensor_data(
        self,
        vehicle_id: str,
        sensor_type: Optional[str] = None,
        hours: int = 24
    ) -> List[Dict]:
        """Get external sensor data for a vehicle."""
        if not self.esp32_bridge:
            return []
        return self.esp32_bridge.get_recent_data(vehicle_id, sensor_type, hours)

    # =========================================================================
    # DTC-Based Automatic Confirmation
    # =========================================================================

    def process_dtc_codes(self, vehicle_id: str, dtc_codes: List[str]) -> Dict[str, Any]:
        """
        Process DTC codes detected from the vehicle.
        Automatically confirms pending predictions if DTCs match predicted failures.

        Args:
            vehicle_id: Vehicle identifier
            dtc_codes: List of DTC codes (e.g., ['P0301', 'P0420'])

        Returns:
            Dictionary with processing results and any confirmed predictions
        """
        if not dtc_codes:
            return {'success': True, 'codes_processed': 0, 'confirmations': []}

        # Store DTCs in current snapshot for correlation analysis
        result = {
            'success': True,
            'codes_processed': len(dtc_codes),
            'confirmations': [],
            'new_alerts': []
        }

        # Check if DTCs confirm any pending predictions via feedback collector
        if self.feedback_collector:
            try:
                confirmations = self.feedback_collector.check_dtc_confirmations(
                    vehicle_id, dtc_codes
                )
                result['confirmations'] = confirmations or []
                if confirmations:
                    logger.info(f"DTCs {dtc_codes} confirmed {len(confirmations)} predictions for {vehicle_id}")
            except Exception as e:
                logger.error(f"Error checking DTC confirmations: {e}")
                result['confirmation_error'] = str(e)

        # Add DTCs to baseline learning as anomaly indicators
        for dtc in dtc_codes:
            # Track DTC occurrence for pattern learning
            if hasattr(self.baseline_learner, 'record_dtc_occurrence'):
                self.baseline_learner.record_dtc_occurrence(vehicle_id, dtc)

        # Create alerts for critical DTCs
        critical_dtcs = [dtc for dtc in dtc_codes if dtc.startswith(('P030', 'P050', 'P060'))]
        if critical_dtcs:
            result['new_alerts'] = [{
                'type': 'dtc_critical',
                'vehicle_id': vehicle_id,
                'codes': critical_dtcs,
                'severity': 'critical',
                'message': f"Critical DTC codes detected: {', '.join(critical_dtcs)}"
            }]

        return result

    def get_dtc_pattern_analysis(self, vehicle_id: str) -> Dict[str, Any]:
        """
        Analyze DTC patterns for a vehicle to identify recurring issues.

        Returns:
            Analysis of DTC patterns including frequency, correlations, and recommendations
        """
        if not self.feedback_collector:
            return {'available': False}

        # Get service records with DTCs
        records = self.feedback_collector.get_service_records(vehicle_id, failure_only=True)

        # Analyze DTC frequency
        dtc_counts = {}
        for record in records:
            dtc_codes = record.get('dtc_codes', [])
            if isinstance(dtc_codes, str):
                import json
                try:
                    dtc_codes = json.loads(dtc_codes)
                except:
                    dtc_codes = []
            for dtc in dtc_codes:
                dtc_counts[dtc] = dtc_counts.get(dtc, 0) + 1

        # Find recurring patterns
        recurring = [dtc for dtc, count in dtc_counts.items() if count >= 2]

        return {
            'available': True,
            'vehicle_id': vehicle_id,
            'total_dtc_occurrences': sum(dtc_counts.values()),
            'unique_dtcs': len(dtc_counts),
            'dtc_frequency': dtc_counts,
            'recurring_dtcs': recurring,
            'service_records_analyzed': len(records)
        }

    # =========================================================================
    # Combined Status & Diagnostics
    # =========================================================================

    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive status of all AI systems."""
        return {
            'enhanced_engine': {
                'active': True,
                'prediction_history_vehicles': len(self.prediction_history),
                'sequence_buffers': len(self.obd_sequence_buffer)
            },
            'lstm': self.get_lstm_status(),
            'feedback': self.get_feedback_statistics(),
            'esp32': self.get_esp32_status(),
            'autoencoder': {
                'available': self.autoencoder is not None,
                'trained': self.autoencoder.is_trained if self.autoencoder else False,
                'model_version': self.autoencoder.model_version if self.autoencoder else None
            } if AUTOENCODER_AVAILABLE else {'available': False},
            'physics': {
                'available': PHYSICS_AVAILABLE,
                'validator_active': self.physics_validator is not None
            },
            'baseline_learning': {
                'vehicles_with_baseline': len(self.baseline_learner.baselines)
                if hasattr(self.baseline_learner, 'baselines') else 0
            },
            'confidence_calibration': self.confidence_scorer.get_calibration_status(),
            # Research-based intelligence
            'research_features': {
                'available': RESEARCH_FEATURES_AVAILABLE,
                'extractor_active': self.research_extractor is not None
            },
            # Fleet learning
            'fleet_learning': {
                'available': FLEET_LEARNING_AVAILABLE,
                'aggregator_active': self.fleet_aggregator is not None
            },
            # Recall monitoring
            'recall_monitor': {
                'available': RECALL_MONITOR_AVAILABLE,
                'monitor_active': self.recall_monitor is not None
            }
        }

    # =========================================================================
    # Research & Fleet Learning Methods
    # =========================================================================

    def get_research_status(self, vehicle_id: str, profile: Optional[Dict] = None) -> Dict[str, Any]:
        """Get research-based intelligence status for a vehicle."""
        if not RESEARCH_FEATURES_AVAILABLE or not self.research_extractor:
            return {'available': False}

        result = {
            'available': True,
            'extractor_ready': True
        }

        # If profile provided, try to get fleet comparison
        if profile and self.fleet_aggregator:
            make = profile.get('make', '')
            model = profile.get('model', '')
            year = profile.get('year', 0)

            if make and model and year:
                fleet_summary = self.fleet_aggregator.get_fleet_summary_for_display(make, model, year)
                result['fleet_data'] = fleet_summary

        return result

    def get_fleet_comparison(
        self,
        vehicle_id: str,
        health_score: float,
        component_health: Dict[str, float],
        profile: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """Get fleet comparison for a vehicle."""
        if not self.fleet_aggregator or not profile:
            return None

        try:
            vehicle_data = {
                'vehicle_id': vehicle_id,
                'make': profile.get('make', ''),
                'model': profile.get('model', ''),
                'year': profile.get('year', 0),
                'health_score': health_score,
                'component_health': component_health
            }
            comparison = self.fleet_aggregator.compare_vehicle_to_fleet(vehicle_data)
            return comparison.to_dict() if comparison.fleet_size > 0 else None
        except Exception as e:
            logger.error(f"Fleet comparison failed: {e}")
            return None

    def check_vehicle_recalls(
        self,
        make: str,
        model: str,
        year: int,
        force: bool = False
    ) -> Dict[str, Any]:
        """Check for recalls for a specific vehicle make/model/year."""
        if not self.recall_monitor:
            return {'available': False}

        try:
            result = self.recall_monitor.check_vehicle_recalls(make, model, year, force)
            return result.to_dict()
        except Exception as e:
            logger.error(f"Recall check failed: {e}")
            return {'available': True, 'success': False, 'error': str(e)}

    def aggregate_fleet_data(self, make: str, model: str, year: int) -> Dict[str, Any]:
        """Aggregate fleet data for a make/model/year."""
        if not self.fleet_aggregator:
            return {'available': False}

        try:
            stats = self.fleet_aggregator.aggregate_fleet_data(make, model, year)
            return stats.to_dict()
        except Exception as e:
            logger.error(f"Fleet aggregation failed: {e}")
            return {'available': True, 'success': False, 'error': str(e)}


# Factory function for easy initialization
def create_enhanced_engine(config=None) -> EnhancedPredictionEngine:
    """Create and return an initialized EnhancedPredictionEngine."""
    return EnhancedPredictionEngine(config)
