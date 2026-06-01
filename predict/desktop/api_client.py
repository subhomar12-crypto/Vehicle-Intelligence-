"""
Centralized HTTP API client for PREDICT Desktop.

All tabs use this client to communicate with the embedded FastAPI server.
Runs synchronous requests (called from QThread workers, never from GUI thread).
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

import requests

from predict.core.config import get_config
from predict.core.security.secrets_loader import get_secrets

logger = logging.getLogger(__name__)


class PredictAPIClient:
    """HTTP client for the embedded PREDICT server."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000/api"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self._setup_auth()

    def _setup_auth(self):
        """Set admin API key header from secrets."""
        try:
            secrets = get_secrets()
            api_key = secrets.ADMIN_API_KEY
            if api_key:
                self.session.headers["X-API-Key"] = api_key
            else:
                logger.warning("No ADMIN_API_KEY in .env - API calls may fail")
        except Exception as e:
            logger.warning(f"Could not load secrets for API auth: {e}")

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request and return parsed JSON."""
        url = f"{self.base_url}{path}"
        kwargs.setdefault("timeout", 20)
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            if response.content:
                return response.json()
            return {"success": True}
        except requests.exceptions.HTTPError as e:
            error_data = {}
            try:
                error_data = e.response.json()
            except Exception:
                pass
            logger.error(f"HTTP {e.response.status_code} on {method} {path}: {error_data}")
            raise
        except requests.exceptions.ConnectionError:
            logger.debug(f"Connection failed (server may not be running): {url}")
            raise
        except Exception as e:
            logger.error(f"Request failed: {method} {path}: {e}")
            raise

    def get(self, path: str, **kwargs) -> Dict[str, Any]:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> Dict[str, Any]:
        return self._request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> Dict[str, Any]:
        return self._request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs) -> Dict[str, Any]:
        return self._request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs) -> Dict[str, Any]:
        return self._request("DELETE", path, **kwargs)

    def get_raw(self, path: str, **kwargs) -> requests.Response:
        """Return raw response (for file downloads)."""
        url = f"{self.base_url}{path}"
        kwargs.setdefault("timeout", 60)
        return self.session.get(url, **kwargs)

    # =========================================================================
    # ADMIN USERS
    # =========================================================================

    def search_users(self, query: str = "", limit: int = 50, offset: int = 0) -> Dict:
        params = {"limit": limit, "offset": offset}
        if query:
            params["search"] = query
        return self.get("/admin/users", params=params)

    def get_user(self, user_id: int) -> Dict:
        return self.get(f"/admin/users/{user_id}")

    def change_user_tier(self, user_id: int, tier: str) -> Dict:
        return self.put(f"/admin/users/{user_id}/tier", json={"tier": tier})

    def update_user(self, user_id: int, **fields) -> Dict:
        return self.patch(f"/admin/users/{user_id}", json=fields)

    def delete_user(self, user_id: int, hard_delete: bool = False) -> Dict:
        return self.delete(f"/admin/users/{user_id}", params={"hard_delete": hard_delete})

    def get_user_api_keys(self, user_id: int) -> Dict:
        """Get all API keys for a user."""
        return self.get("/admin/api-keys", params={"user_id": user_id})

    def generate_api_key(self, user_id: int, name: str, expires_days: int = 365) -> Dict:
        """Generate a new API key for a user."""
        return self.post("/admin/api-key/generate", params={
            "user_id": user_id,
            "name": name,
            "expires_days": expires_days
        })

    def get_system_stats(self) -> Dict:
        return self.get("/admin/stats")

    def get_audit_log(self, limit: int = 100) -> Dict:
        return self.get("/admin/audit-log", params={"limit": limit})

    def update_entitlements(self, user_id: int, entitlements: List[Dict]) -> Dict:
        return self.put(f"/admin/users/{user_id}/entitlements",
                        json={"entitlements": entitlements})

    # =========================================================================
    # VEHICLES
    # =========================================================================

    def get_user_vehicles(self, user_id: int) -> Dict:
        result = self.get("/profile/vehicles", params={"user_id": user_id})
        # Server returns a JSON array; callers expect {"vehicles": [...]}
        if isinstance(result, list):
            return {"vehicles": result}
        return result

    def get_vehicle(self, vehicle_id: int) -> Dict:
        return self.get(f"/profile/vehicles/{vehicle_id}")

    def create_vehicle(self, **fields) -> Dict:
        return self.post("/profile/vehicles", json=fields)

    def update_vehicle(self, vehicle_id: int, **fields) -> Dict:
        return self.put(f"/profile/vehicles/{vehicle_id}", json=fields)

    def delete_vehicle(self, vehicle_id: int) -> Dict:
        return self.delete(f"/profile/vehicles/{vehicle_id}")

    def get_vehicle_research(self, vehicle_id: int) -> Dict:
        return self.get(f"/profile/vehicles/{vehicle_id}/research")

    def get_vehicle_research_status(self, vehicle_id: int) -> Dict:
        return self.get(f"/profile/vehicles/{vehicle_id}/research/status")

    def refresh_vehicle_research(self, vehicle_id: int) -> Dict:
        return self.post(f"/profile/vehicles/{vehicle_id}/research/refresh")

    # =========================================================================
    # SERVICE RECORDS
    # =========================================================================

    def get_service_records(self, vehicle_id: int) -> Dict:
        return self.get(f"/profile/vehicles/{vehicle_id}/service-records")

    # =========================================================================
    # OBD DATA
    # =========================================================================

    def get_latest_vehicle_data(self, vehicle_id: int) -> Dict:
        return self.get(f"/obd/vehicle/{vehicle_id}/data/latest")

    def get_vehicle_data_history(self, vehicle_id: int, limit: int = 100) -> Dict:
        return self.get(f"/obd/vehicle/{vehicle_id}/data/history",
                        params={"limit": limit})

    def get_vehicle_stats(self, vehicle_id: int) -> Dict:
        return self.get(f"/obd/vehicle/{vehicle_id}/stats")

    def send_vehicle_data(self, profile_id: int, data: dict) -> Dict:
        """Upload OBD sensor data to server (flat JSON format)."""
        import time as _time
        payload = {
            "profile_id": profile_id,
            "timestamp": _time.time(),
            "source": "desktop",
            **data
        }
        return self.post("/vehicle_data", json=payload)

    def report_dtc_codes(self, vehicle_id: int, codes: list, is_pending: bool = False) -> Dict:
        """Report DTC codes to server."""
        return self.post("/dtc/report", params={"vehicle_id": vehicle_id}, json={
            "codes": codes,
            "is_pending": is_pending
        })

    # =========================================================================
    # DTC
    # =========================================================================

    def get_dtc_history(self, vehicle_id: int) -> Dict:
        return self.get(f"/dtc/{vehicle_id}")

    def get_active_dtcs(self, vehicle_id: int) -> Dict:
        return self.get(f"/dtc/{vehicle_id}/active")

    def lookup_dtc(self, code: str) -> Dict:
        return self.get(f"/dtc/lookup/{code}")

    def clear_dtc(self, vehicle_id: int, dtc_id: int) -> Dict:
        return self.delete(f"/dtc/{vehicle_id}/{dtc_id}")

    def get_dtc_summary(self, vehicle_id: int) -> Dict:
        return self.get(f"/dtc/{vehicle_id}/summary")

    # =========================================================================
    # PREDICTIONS
    # =========================================================================

    def get_predictions(self, vehicle_id: int) -> Dict:
        return self.get(f"/predictions/{vehicle_id}")

    def get_prediction_history(self, vehicle_id: int, limit: int = 50) -> Dict:
        return self.get(f"/predictions/{vehicle_id}/history",
                        params={"limit": limit})

    # =========================================================================
    # AI INTELLIGENCE (v3)
    # =========================================================================

    def get_health_assessment(self, vehicle_id: int) -> Dict:
        """Get full v3 health assessment with anomalies, forensics, survival curves, SHAP."""
        return self.get(f"/predictions/{vehicle_id}/health-assessment")

    def get_vehicle_ai_status(self, vehicle_id: int) -> Dict:
        """Get AI status with intelligence level, phase, models, etc."""
        return self.get(f"/predictions/{vehicle_id}/ai-status")

    def get_ai_dashboard(self) -> Dict:
        """Get fleet-wide AI overview (admin only)."""
        return self.get("/admin/ai-dashboard")

    def train_vehicle_model(self, vehicle_id: int, model: str) -> Dict:
        """Trigger model training for a specific vehicle."""
        return self.post(f"/admin/vehicles/{vehicle_id}/train", json={"model": model})

    def get_health_history(self, vehicle_id: int, days: int = 90) -> Dict:
        """Get health score snapshots over time."""
        return self.get(f"/predictions/{vehicle_id}/health-history",
                        params={"days": days})

    # =========================================================================
    # AI CHAT
    # =========================================================================

    def chat_with_ai(self, message: str, profile_id: int = 0,
                     context: str = "") -> Dict:
        payload = {"message": message}
        if profile_id:
            payload["profile_id"] = profile_id
        if context:
            payload["context"] = context
        return self.post("/ai/chat", json=payload, timeout=120)

    def explain_dtc(self, code: str) -> Dict:
        return self.post(f"/ai/explain-dtc/{code}", timeout=120)

    def get_ai_status(self) -> Dict:
        return self.get("/ai/status")

    # =========================================================================
    # REPORTS
    # =========================================================================

    def generate_report(self, vehicle_id: int, report_type: str,
                        include_llm: bool = False) -> Dict:
        return self.post("/report/generate", json={
            "vehicle_id": vehicle_id,
            "report_type": report_type,
            "include_llm_explanations": include_llm,
        })

    def get_report_status(self, report_id: int) -> Dict:
        return self.get(f"/report/status/{report_id}")

    def download_report(self, report_id: int) -> requests.Response:
        return self.get_raw(f"/report/download/{report_id}")

    def get_report_history(self, limit: int = 50) -> Dict:
        return self.get("/report/history", params={"limit": limit})

    def delete_report(self, report_id: int) -> Dict:
        return self.delete(f"/report/{report_id}")

    # =========================================================================
    # HEALTH
    # =========================================================================

    def health_check(self) -> Dict:
        return self.get("/health")

    def detailed_health(self) -> Dict:
        return self.get("/admin/health/detailed")

    def readiness(self) -> Dict:
        return self.get("/health/ready")

    # =========================================================================
    # ADMIN OPS
    # =========================================================================

    def clear_cache(self) -> Dict:
        return self.post("/admin/maintenance/clear-cache")

    def trigger_backup(self) -> Dict:
        return self.post("/admin/backup")

    def get_job_status(self) -> Dict:
        return self.get("/admin/jobs/status")

    # =========================================================================
    # TIERS
    # =========================================================================

    def list_tiers(self) -> Dict:
        return self.get("/tiers/")

    def get_tier_features(self) -> Dict:
        return self.get("/tiers/features")

    # =========================================================================
    # DRIVING
    # =========================================================================

    def get_driving_score(self, vehicle_id: int) -> Dict:
        return self.get(f"/driver/score/{vehicle_id}")

    # =========================================================================
    # FLEET REQUESTS
    # =========================================================================

    def get_fleet_requests(self, status: str = "pending", limit: int = 50, offset: int = 0) -> Dict:
        """Get fleet access requests."""
        return self.get("/admin/fleet-requests", params={
            "status": status, "limit": limit, "offset": offset
        })

    def approve_fleet_request(self, request_id: int, vehicle_limit: int = 3, notes: str = "") -> Dict:
        """Approve fleet request — upgrades tier, sets vehicle limit, generates API key."""
        return self.put(f"/admin/fleet-requests/{request_id}/approve", json={
            "vehicle_limit": vehicle_limit, "notes": notes
        })

    def deny_fleet_request(self, request_id: int, reason: str = "") -> Dict:
        """Deny fleet request."""
        return self.put(f"/admin/fleet-requests/{request_id}/deny", json={
            "reason": reason
        })

    # =========================================================================
    # VEHICLE PHOTOS
    # =========================================================================

    def upload_vehicle_photo(self, file_path: str, make: str = "", model: str = "",
                             year: int = 0, color: str = "", vin: str = "",
                             license_plate: str = "") -> Dict:
        """Upload a vehicle photo with metadata."""
        with open(file_path, "rb") as f:
            return self._request(
                "POST", "/profile/vehicles/photos/upload-preregistered",
                files={"file": (Path(file_path).name, f, "image/jpeg")},
                data={
                    "make": make, "model": model, "year": str(year),
                    "color": color, "vin": vin, "license_plate": license_plate,
                },
            )

    def get_unmatched_photos(self) -> Dict:
        """Get list of unmatched vehicle photos."""
        return self.get("/profile/vehicles/photos/unmatched")

    def delete_vehicle_photo(self, photo_id: int) -> Dict:
        """Delete a vehicle photo."""
        return self.delete(f"/profile/vehicles/photos/{photo_id}")
