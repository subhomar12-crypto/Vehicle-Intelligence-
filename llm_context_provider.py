"""
LLM Context Provider
Provides the LLM with comprehensive, real-time context about the system.

This module ensures the LLM:
- Has access to all relevant vehicle, driver, and prediction data
- Can explain why notifications were sent
- Responds as if it IS the AI prediction models
- Never hallucinates - all data is validated and real

Part of the PREDICT Vehicle Intelligence Platform.
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

# Import system components for data access
try:
    from notification_audit import NotificationAuditLog
    AUDIT_AVAILABLE = True
except ImportError:
    AUDIT_AVAILABLE = False

try:
    from notification_feedback import NotificationFeedbackTracker
    FEEDBACK_AVAILABLE = True
except ImportError:
    FEEDBACK_AVAILABLE = False

try:
    from customer_communication_log import CustomerCommunicationLog
    COMM_LOG_AVAILABLE = True
except ImportError:
    COMM_LOG_AVAILABLE = False


class ContextType(Enum):
    """Types of context that can be provided"""
    VEHICLE = "vehicle"
    DRIVER = "driver"
    OWNER = "owner"
    PREDICTION = "prediction"
    NOTIFICATION = "notification"
    DTC_CODE = "dtc_code"
    TRAINING = "training"
    SYSTEM = "system"
    COMMUNICATION = "communication"


@dataclass
class LLMContext:
    """Context data structure for LLM"""
    context_type: ContextType
    entity_id: str
    data: Dict[str, Any]
    summary: str
    timestamp: datetime
    confidence: float  # How confident we are in this data (1.0 = verified)


class LLMContextProvider:
    """
    Provides comprehensive context to the LLM about the entire system.

    The LLM should use this context to:
    1. Answer questions about specific vehicles, drivers, and predictions
    2. Explain why notifications were sent
    3. Provide accurate, vehicle-specific recommendations
    4. Respond as if it IS the AI prediction system
    """

    # System identity prompt - how the LLM should respond
    SYSTEM_IDENTITY = """You are the PREDICT AI - the artificial intelligence system that powers
vehicle predictive maintenance. When users ask questions, respond as if YOU are the one who:
- Analyzed the vehicle data
- Made the predictions
- Sent the notifications
- Learned from the collected data

Use first person ("I detected...", "I predicted...", "I sent this notification because...").

CRITICAL RULES:
1. NEVER make up or guess data - only use the context provided
2. If you don't have information, say "I don't have that data available"
3. Be specific with vehicle names, dates, and numbers from the context
4. When explaining predictions, reference the actual data that led to them
5. Be professional and helpful, but also honest about limitations"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            app_data = os.path.join(os.path.expanduser("~"), ".predict")
            os.makedirs(app_data, exist_ok=True)
            db_path = os.path.join(app_data, "llm_context.db")

        self.db_path = db_path

        # Initialize sub-components
        self.audit_log = NotificationAuditLog() if AUDIT_AVAILABLE else None
        self.feedback_tracker = NotificationFeedbackTracker() if FEEDBACK_AVAILABLE else None
        self.comm_log = CustomerCommunicationLog() if COMM_LOG_AVAILABLE else None

        self._init_database()

    def _init_database(self):
        """Initialize context cache database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Cache for frequently accessed context
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS context_cache (
                    cache_key TEXT PRIMARY KEY,
                    context_type TEXT NOT NULL,
                    entity_id TEXT,
                    data TEXT NOT NULL,
                    summary TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
            """)

            # Context request log for analytics
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS context_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_type TEXT NOT NULL,
                    entity_id TEXT,
                    user_id TEXT,
                    requested_at TEXT NOT NULL,
                    response_size INTEGER
                )
            """)

            conn.commit()

    def get_system_identity(self) -> str:
        """Get the system identity prompt for the LLM"""
        return self.SYSTEM_IDENTITY

    def build_context_for_query(
        self,
        query: str,
        user_id: str = None,
        profile_id: str = None,
        vehicle_id: str = None,
        driver_id: str = None,
        notification_id: str = None,
        include_history: bool = True,
        max_context_items: int = 20
    ) -> Dict[str, Any]:
        """
        Build comprehensive context for an LLM query.

        Args:
            query: The user's question
            user_id: The user asking the question
            profile_id: Specific profile to focus on
            vehicle_id: Specific vehicle to focus on
            driver_id: Specific driver to focus on
            notification_id: Specific notification being asked about
            include_history: Include communication/interaction history
            max_context_items: Maximum number of context items to include

        Returns:
            Dictionary with all relevant context for the LLM
        """
        context = {
            "system_identity": self.SYSTEM_IDENTITY,
            "current_time": datetime.now().isoformat(),
            "query": query,
            "entities": {},
            "predictions": [],
            "notifications": [],
            "communications": [],
            "ai_status": {},
            "warnings": []
        }

        # If asking about a specific notification
        if notification_id:
            notification_context = self._get_notification_context(notification_id)
            if notification_context:
                context["notifications"].append(notification_context)
                # Extract related IDs from notification
                if not vehicle_id and notification_context.get("vehicle_id"):
                    vehicle_id = notification_context["vehicle_id"]
                if not profile_id and notification_context.get("profile_id"):
                    profile_id = notification_context["profile_id"]

        # Get vehicle context
        if vehicle_id:
            vehicle_context = self._get_vehicle_context(vehicle_id)
            if vehicle_context:
                context["entities"]["vehicle"] = vehicle_context

        # Get driver context
        if driver_id:
            driver_context = self._get_driver_context(driver_id)
            if driver_context:
                context["entities"]["driver"] = driver_context

        # Get profile/owner context
        if profile_id:
            profile_context = self._get_profile_context(profile_id)
            if profile_context:
                context["entities"]["profile"] = profile_context

        # Get recent predictions for relevant entities
        predictions = self._get_recent_predictions(
            profile_id=profile_id,
            vehicle_id=vehicle_id,
            limit=max_context_items
        )
        context["predictions"] = predictions

        # Get recent notifications
        if not notification_id:  # Only if not already focusing on one
            notifications = self._get_recent_notifications(
                profile_id=profile_id,
                vehicle_id=vehicle_id,
                limit=max_context_items
            )
            context["notifications"].extend(notifications)

        # Get communication history if requested
        if include_history and profile_id:
            communications = self._get_communication_history(profile_id)
            context["communications"] = communications

        # Get AI training status
        context["ai_status"] = self._get_ai_training_status()

        # Add data validation warnings
        context["warnings"] = self._validate_context(context)

        # Log the context request
        self._log_context_request(
            request_type="query_context",
            entity_id=vehicle_id or profile_id,
            user_id=user_id,
            response_size=len(json.dumps(context))
        )

        return context

    def _get_notification_context(self, notification_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed context about a specific notification"""
        if not self.audit_log:
            return None

        try:
            # Get from audit log
            audit_entry = self.audit_log.get_by_id(notification_id)
            if not audit_entry:
                return None

            context = {
                "notification_id": notification_id,
                "title": audit_entry.title,
                "message": audit_entry.message,
                "priority": audit_entry.priority,
                "sent_at": audit_entry.sent_at.isoformat() if audit_entry.sent_at else None,
                "trigger_type": audit_entry.trigger_type.value if audit_entry.trigger_type else None,
                "trigger_data": audit_entry.trigger_data,
                "vehicle_id": audit_entry.vehicle_id,
                "profile_id": audit_entry.profile_id,
                "driver_id": audit_entry.driver_id,
                "delivery_status": audit_entry.delivery_status,
                "read_at": audit_entry.read_at.isoformat() if audit_entry.read_at else None,
            }

            # Build explanation for why this notification was sent
            explanation = self.audit_log.build_explanation_context(notification_id)
            context["explanation"] = explanation

            # Get feedback if available
            if self.feedback_tracker:
                feedback = self.feedback_tracker.get_feedback_summary_for_llm(notification_id)
                context["user_feedback"] = feedback

            return context

        except Exception as e:
            return {"error": str(e), "notification_id": notification_id}

    def _get_vehicle_context(self, vehicle_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive context about a vehicle"""
        # This would typically query the vehicle database
        # For now, return a structured template
        try:
            from profiles_manager import get_profiles_manager
            pm = get_profiles_manager()

            # Get vehicle data from profiles
            vehicle_data = pm.get_vehicle_by_id(vehicle_id)
            if not vehicle_data:
                return None

            context = {
                "vehicle_id": vehicle_id,
                "name": vehicle_data.get("name", "Unknown"),
                "make": vehicle_data.get("make"),
                "model": vehicle_data.get("model"),
                "year": vehicle_data.get("year"),
                "vin": vehicle_data.get("vin"),
                "mileage": vehicle_data.get("mileage"),
                "last_service": vehicle_data.get("last_service"),
                "status": vehicle_data.get("status", "unknown"),
            }

            # Get recent DTCs
            dtcs = self._get_vehicle_dtcs(vehicle_id)
            if dtcs:
                context["recent_dtcs"] = dtcs

            # Get health metrics
            health = self._get_vehicle_health(vehicle_id)
            if health:
                context["health_metrics"] = health

            return context

        except ImportError:
            return {"vehicle_id": vehicle_id, "error": "Profile manager not available"}
        except Exception as e:
            return {"vehicle_id": vehicle_id, "error": str(e)}

    def _get_driver_context(self, driver_id: str) -> Optional[Dict[str, Any]]:
        """Get context about a driver"""
        try:
            from profiles_manager import get_profiles_manager
            pm = get_profiles_manager()

            driver_data = pm.get_driver_by_id(driver_id)
            if not driver_data:
                return None

            context = {
                "driver_id": driver_id,
                "name": driver_data.get("name", "Unknown"),
                "license_number": driver_data.get("license_number"),
                "assigned_vehicles": driver_data.get("assigned_vehicles", []),
            }

            # Get driving behavior metrics
            behavior = self._get_driver_behavior(driver_id)
            if behavior:
                context["driving_behavior"] = behavior

            return context

        except ImportError:
            return {"driver_id": driver_id, "error": "Profile manager not available"}
        except Exception as e:
            return {"driver_id": driver_id, "error": str(e)}

    def _get_profile_context(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Get context about an owner/profile"""
        try:
            from profiles_manager import get_profiles_manager
            pm = get_profiles_manager()

            profile_data = pm.get_profile(profile_id)
            if not profile_data:
                return None

            context = {
                "profile_id": profile_id,
                "name": profile_data.get("name", "Unknown"),
                "company": profile_data.get("company"),
                "vehicles_count": len(profile_data.get("vehicles", [])),
                "drivers_count": len(profile_data.get("drivers", [])),
                "subscription_status": profile_data.get("subscription_status"),
            }

            return context

        except ImportError:
            return {"profile_id": profile_id, "error": "Profile manager not available"}
        except Exception as e:
            return {"profile_id": profile_id, "error": str(e)}

    def _get_recent_predictions(
        self,
        profile_id: str = None,
        vehicle_id: str = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent predictions for display"""
        try:
            from ai_prediction_engine import get_prediction_engine
            engine = get_prediction_engine()

            predictions = engine.get_recent_predictions(
                profile_id=profile_id,
                vehicle_id=vehicle_id,
                limit=limit
            )

            formatted = []
            for pred in predictions:
                formatted.append({
                    "prediction_id": pred.get("id"),
                    "component": pred.get("component"),
                    "risk_level": pred.get("risk_level"),
                    "confidence": pred.get("confidence"),
                    "prediction_date": pred.get("created_at"),
                    "days_until_failure": pred.get("days_until_failure"),
                    "factors": pred.get("contributing_factors", []),
                    "recommendation": pred.get("recommendation"),
                })

            return formatted

        except ImportError:
            return []
        except Exception as e:
            return [{"error": str(e)}]

    def _get_recent_notifications(
        self,
        profile_id: str = None,
        vehicle_id: str = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent notifications"""
        if not self.audit_log:
            return []

        try:
            entries = self.audit_log.get_recent(
                profile_id=profile_id,
                limit=limit
            )

            formatted = []
            for entry in entries:
                formatted.append({
                    "notification_id": entry.notification_id,
                    "title": entry.title,
                    "message": entry.message,
                    "priority": entry.priority,
                    "sent_at": entry.sent_at.isoformat() if entry.sent_at else None,
                    "trigger_type": entry.trigger_type.value if entry.trigger_type else None,
                    "read": entry.read_at is not None,
                })

            return formatted

        except Exception as e:
            return [{"error": str(e)}]

    def _get_communication_history(
        self,
        profile_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get communication history for a customer"""
        if not self.comm_log:
            return []

        try:
            context = self.comm_log.get_llm_context_for_customer(profile_id, max_entries=limit)
            return context.get("recent_summaries", [])

        except Exception as e:
            return [{"error": str(e)}]

    def _get_ai_training_status(self) -> Dict[str, Any]:
        """Get AI training status for context"""
        try:
            from ai_prediction_engine import get_prediction_engine
            engine = get_prediction_engine()

            status = engine.get_training_status()
            return {
                "last_training": status.get("last_training_time"),
                "models_count": status.get("models_count"),
                "total_data_points": status.get("total_data_points"),
                "model_accuracy": status.get("accuracy"),
                "next_scheduled_training": status.get("next_training"),
            }

        except ImportError:
            return {"status": "Training engine not available"}
        except Exception as e:
            return {"error": str(e)}

    def _get_vehicle_dtcs(self, vehicle_id: str) -> List[Dict[str, Any]]:
        """Get recent DTCs for a vehicle"""
        try:
            from dtc_manager import get_dtc_manager
            dtc_mgr = get_dtc_manager()

            dtcs = dtc_mgr.get_recent_dtcs(vehicle_id, limit=5)
            return [
                {
                    "code": dtc.get("code"),
                    "description": dtc.get("description"),
                    "severity": dtc.get("severity"),
                    "detected_at": dtc.get("detected_at"),
                    "status": dtc.get("status"),
                }
                for dtc in dtcs
            ]

        except ImportError:
            return []
        except Exception as e:
            return [{"error": str(e)}]

    def _get_vehicle_health(self, vehicle_id: str) -> Optional[Dict[str, Any]]:
        """Get vehicle health metrics"""
        try:
            from vehicle_health import get_health_manager
            health_mgr = get_health_manager()

            health = health_mgr.get_vehicle_health(vehicle_id)
            return health

        except ImportError:
            return None
        except Exception as e:
            return {"error": str(e)}

    def _get_driver_behavior(self, driver_id: str) -> Optional[Dict[str, Any]]:
        """Get driver behavior metrics"""
        try:
            from driver_behavior import get_behavior_analyzer
            analyzer = get_behavior_analyzer()

            behavior = analyzer.get_driver_summary(driver_id)
            return behavior

        except ImportError:
            return None
        except Exception as e:
            return {"error": str(e)}

    def _validate_context(self, context: Dict[str, Any]) -> List[str]:
        """Validate context data and return any warnings"""
        warnings = []

        # Check for missing critical data
        if not context.get("entities"):
            warnings.append("No entity data available - responses may be limited")

        if not context.get("predictions"):
            warnings.append("No prediction data available")

        # Check for stale data
        if context.get("ai_status", {}).get("last_training"):
            try:
                last_training = datetime.fromisoformat(context["ai_status"]["last_training"])
                if datetime.now() - last_training > timedelta(days=7):
                    warnings.append("AI models haven't been trained in over 7 days")
            except:
                pass

        return warnings

    def _log_context_request(
        self,
        request_type: str,
        entity_id: str = None,
        user_id: str = None,
        response_size: int = 0
    ):
        """Log context request for analytics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO context_requests
                    (request_type, entity_id, user_id, requested_at, response_size)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    request_type,
                    entity_id,
                    user_id,
                    datetime.now().isoformat(),
                    response_size
                ))
                conn.commit()
        except Exception:
            pass  # Don't fail on logging errors

    def format_context_for_prompt(self, context: Dict[str, Any]) -> str:
        """
        Format context dictionary into a string suitable for LLM prompt injection.

        This creates a structured, readable context that the LLM can reference.
        """
        parts = []

        # System identity
        parts.append("=== SYSTEM IDENTITY ===")
        parts.append(context.get("system_identity", self.SYSTEM_IDENTITY))
        parts.append("")

        # Current time
        parts.append(f"Current Time: {context.get('current_time', datetime.now().isoformat())}")
        parts.append("")

        # Entity context
        if context.get("entities"):
            parts.append("=== ENTITY CONTEXT ===")

            if "vehicle" in context["entities"]:
                v = context["entities"]["vehicle"]
                parts.append(f"Vehicle: {v.get('name', 'Unknown')}")
                parts.append(f"  - Make/Model: {v.get('make', 'N/A')} {v.get('model', 'N/A')} ({v.get('year', 'N/A')})")
                parts.append(f"  - Mileage: {v.get('mileage', 'N/A')} km")
                parts.append(f"  - Status: {v.get('status', 'Unknown')}")
                if v.get("recent_dtcs"):
                    parts.append(f"  - Recent DTCs: {len(v['recent_dtcs'])} codes detected")
                parts.append("")

            if "driver" in context["entities"]:
                d = context["entities"]["driver"]
                parts.append(f"Driver: {d.get('name', 'Unknown')}")
                if d.get("driving_behavior"):
                    behavior = d["driving_behavior"]
                    parts.append(f"  - Driving Score: {behavior.get('score', 'N/A')}")
                parts.append("")

            if "profile" in context["entities"]:
                p = context["entities"]["profile"]
                parts.append(f"Owner/Profile: {p.get('name', 'Unknown')}")
                parts.append(f"  - Company: {p.get('company', 'N/A')}")
                parts.append(f"  - Vehicles: {p.get('vehicles_count', 0)}")
                parts.append(f"  - Drivers: {p.get('drivers_count', 0)}")
                parts.append("")

        # Predictions
        if context.get("predictions"):
            parts.append("=== RECENT PREDICTIONS ===")
            for pred in context["predictions"][:5]:
                parts.append(f"- {pred.get('component', 'Unknown')}: {pred.get('risk_level', 0):.0%} risk")
                parts.append(f"  Confidence: {pred.get('confidence', 0):.0%}")
                if pred.get("days_until_failure"):
                    parts.append(f"  Estimated failure in: {pred['days_until_failure']} days")
                if pred.get("recommendation"):
                    parts.append(f"  Recommendation: {pred['recommendation']}")
            parts.append("")

        # Notifications
        if context.get("notifications"):
            parts.append("=== RECENT NOTIFICATIONS ===")
            for notif in context["notifications"][:5]:
                parts.append(f"- [{notif.get('priority', 'N/A').upper()}] {notif.get('title', 'No title')}")
                parts.append(f"  {notif.get('message', '')}")
                if notif.get("explanation"):
                    parts.append(f"  Why sent: {notif['explanation']}")
                parts.append(f"  Sent: {notif.get('sent_at', 'N/A')}")
            parts.append("")

        # AI Status
        if context.get("ai_status"):
            status = context["ai_status"]
            parts.append("=== AI SYSTEM STATUS ===")
            parts.append(f"Last Training: {status.get('last_training', 'N/A')}")
            parts.append(f"Model Accuracy: {status.get('model_accuracy', 'N/A')}")
            parts.append(f"Total Data Points: {status.get('total_data_points', 'N/A')}")
            parts.append("")

        # Warnings
        if context.get("warnings"):
            parts.append("=== WARNINGS ===")
            for warning in context["warnings"]:
                parts.append(f"- {warning}")
            parts.append("")

        return "\n".join(parts)

    def get_notification_explanation(self, notification_id: str) -> str:
        """
        Get a natural language explanation of why a notification was sent.

        This is specifically for when users call asking "Why did I get this notification?"
        """
        if not self.audit_log:
            return "Notification audit system not available. Cannot retrieve explanation."

        try:
            explanation = self.audit_log.build_explanation_context(notification_id)

            if not explanation:
                return f"I don't have detailed records for notification {notification_id}."

            # Format into natural language
            parts = []

            if explanation.get("trigger_explanation"):
                parts.append(f"I sent this notification because: {explanation['trigger_explanation']}")

            if explanation.get("prediction_context"):
                pred = explanation["prediction_context"]
                parts.append(f"My prediction model detected a {pred.get('risk_level', 0):.0%} risk "
                           f"for the {pred.get('component', 'component')}.")
                if pred.get("contributing_factors"):
                    parts.append(f"Contributing factors: {', '.join(pred['contributing_factors'])}")

            if explanation.get("vehicle_context"):
                vehicle = explanation["vehicle_context"]
                parts.append(f"This is for vehicle: {vehicle.get('name', 'Unknown')}")

            if explanation.get("delivery_info"):
                delivery = explanation["delivery_info"]
                parts.append(f"The notification was sent via {', '.join(delivery.get('channels', []))} "
                           f"at {delivery.get('sent_at', 'unknown time')}.")

            return " ".join(parts) if parts else "No detailed explanation available."

        except Exception as e:
            return f"Error retrieving explanation: {str(e)}"


# Singleton instance
_context_provider: Optional[LLMContextProvider] = None


def get_context_provider() -> LLMContextProvider:
    """Get the singleton LLMContextProvider instance"""
    global _context_provider
    if _context_provider is None:
        _context_provider = LLMContextProvider()
    return _context_provider


def build_llm_prompt_context(
    query: str,
    user_id: str = None,
    profile_id: str = None,
    vehicle_id: str = None,
    notification_id: str = None
) -> str:
    """
    Convenience function to build formatted context for an LLM prompt.

    Returns a formatted string ready for injection into the LLM system prompt.
    """
    provider = get_context_provider()
    context = provider.build_context_for_query(
        query=query,
        user_id=user_id,
        profile_id=profile_id,
        vehicle_id=vehicle_id,
        notification_id=notification_id
    )
    return provider.format_context_for_prompt(context)
