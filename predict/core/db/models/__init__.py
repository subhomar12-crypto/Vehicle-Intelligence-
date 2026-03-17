"""
Import all models so Alembic can discover them via Base.metadata.
"""

from predict.core.db.models.user import (
    User, ApiKey, Entitlement, RateLimit, UsageCounter,
    TierPreset, DriverAssignment, UserFeatureOverride, PricingConfig,
)
from predict.core.db.models.vehicle import (
    VehicleProfile, VehicleData, OBDRecord, TelemetryRecord, ServiceRecord,
)
from predict.core.db.models.dtc import DTCCodes, DTCHistory
from predict.core.db.models.guardian import (
    Guardian, VehicleGuardian, Alert, GuardianCommand,
    LocationRequest, ConsentRecord, GuardianTelemetry, DrivingEvent,
)
from predict.core.db.models.trip import (
    Trip, TripEvent, Driver, VehicleDriver, DriverSession,
    DriverInviteCode, DriverBehaviorSummary, GuardianTrip,
)
from predict.core.db.models.prediction import (
    Prediction, MLTrainingLabel, MLAggregatedFeature,
    FleetBaseline, OBDSensorConfig,
)
from predict.core.db.models.subscription import (
    FleetInvite, Geofence, GeofenceEvent,
    TierUpgradeRequest, SubscriptionAuditLog,
)
from predict.core.db.models.audit import (
    Report, AuditLog, VerificationCode, VerificationSession,
    IdempotencyCache, FailedOperation, DataExportConfig, ExportHistory,
)
from predict.core.db.models.pid_atlas import PIDAtlas
from predict.core.db.models.prediction_feedback import (
    PredictionSnapshot, PredictionAccuracy, PredictionFeedback,
    FleetPattern, FleetLearningAdjustment,
    ComponentAccuracyStats, FleetPenaltyAdjustment,
)
from predict.core.db.models.pricing import PartsPrice, ServicePrice
from predict.core.db.models.model_registry import (
    ModelVersion, BaseModelEntry, TrainingJob,
)

__all__ = [
    # User domain
    "User", "ApiKey", "Entitlement", "RateLimit", "UsageCounter",
    "TierPreset", "DriverAssignment", "UserFeatureOverride", "PricingConfig",
    # Vehicle domain
    "VehicleProfile", "VehicleData", "OBDRecord", "TelemetryRecord", "ServiceRecord",
    # DTC domain
    "DTCCodes", "DTCHistory",
    # Guardian domain
    "Guardian", "VehicleGuardian", "Alert", "GuardianCommand",
    "LocationRequest", "GuardianTelemetry", "DrivingEvent",
    # Trip domain
    "Trip", "TripEvent", "Driver", "VehicleDriver", "DriverSession",
    "DriverInviteCode", "DriverBehaviorSummary", "GuardianTrip",
    # Prediction domain
    "Prediction", "MLTrainingLabel", "MLAggregatedFeature",
    "FleetBaseline", "OBDSensorConfig",
    # Subscription domain
    "FleetInvite", "Geofence", "GeofenceEvent",
    "TierUpgradeRequest", "SubscriptionAuditLog",
    # Audit domain
    "Report", "AuditLog", "VerificationCode", "VerificationSession",
    "IdempotencyCache", "FailedOperation", "DataExportConfig", "ExportHistory",
    "ConsentRecord",
    # PID Atlas
    "PIDAtlas",
    # Prediction Feedback
    "PredictionSnapshot", "PredictionAccuracy", "PredictionFeedback",
    "FleetPattern", "FleetLearningAdjustment",
    "ComponentAccuracyStats", "FleetPenaltyAdjustment",
    # Pricing domain
    "PartsPrice", "ServicePrice",
    # Model registry
    "ModelVersion", "BaseModelEntry", "TrainingJob",
]
