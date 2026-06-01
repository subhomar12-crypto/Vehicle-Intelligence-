"""
Vehicle research service — async wrapper for VehicleResearchEngine.

Runs the synchronous research engine in a thread pool and persists
results to the vehicle_research table.
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.db.models.vehicle import VehicleResearch, VehicleProfile
from predict.core.db.session import get_db_session
from predict.core.services.websocket_service import ws_manager

logger = logging.getLogger(__name__)

# Ensure the project root is importable (vehicle_research_engine.py lives there)
_project_root = str(Path(__file__).resolve().parent.parent.parent.parent)

# Lazy-loaded singletons
_research_engine = None
_service: Optional["VehicleResearchService"] = None


def _get_research_engine():
    """Lazy-load the synchronous research engine."""
    global _research_engine
    if _research_engine is None:
        import sys
        if _project_root not in sys.path:
            sys.path.insert(0, _project_root)
        from vehicle_research_engine import VehicleResearchEngine
        _research_engine = VehicleResearchEngine()
    return _research_engine


class VehicleResearchService:
    """Production async wrapper for vehicle research."""

    # ------------------------------------------------------------------
    # Core research
    # ------------------------------------------------------------------

    async def research_vehicle(self, profile_id: int, force_fresh: bool = False) -> Dict[str, Any]:
        """Run full research for a vehicle profile (background-safe).

        Args:
            profile_id: Vehicle profile ID to research.
            force_fresh: If True, skip similarity cache (used by manual refresh).
        """
        async with get_db_session() as db:
            # 1. Fetch vehicle profile
            profile = await db.get(VehicleProfile, profile_id)
            if not profile:
                logger.error(f"Profile {profile_id} not found for research")
                return {"error": "profile_not_found"}

            if not (profile.make and profile.model and profile.year):
                logger.warning(f"Profile {profile_id} missing make/model/year — skipping research")
                return {"error": "incomplete_vehicle_info"}

            # 1b. Check similarity cache — clone if a similar vehicle was already researched
            if not force_fresh:
                similar = await self._find_similar_research(
                    db, profile.make, profile.model, profile.year,
                    getattr(profile, 'engine_type', None), profile_id
                )
                if similar:
                    logger.info(
                        f"Cloning research from profile {similar.profile_id} → {profile_id} "
                        f"({profile.make} {profile.model} {profile.year})"
                    )
                    research = await self._get_or_create_research(db, profile_id)
                    for field in [
                        'common_problems', 'failure_prone_parts', 'recalls', 'tsbs',
                        'owner_reviews_summary', 'reliability_score', 'confidence_score',
                        'sources', 'raw_search_results',
                    ]:
                        setattr(research, field, getattr(similar, field))
                    # Track clone source in ai_features
                    features = json.loads(similar.ai_features or '{}')
                    features['cloned_from_profile_id'] = similar.profile_id
                    research.ai_features = json.dumps(features)
                    research.research_status = "completed"
                    research.researched_at = time.time()
                    research.vin_status = "detected" if profile.vin else "missing"
                    await db.commit()
                    await self._notify_status(
                        profile_id, "completed",
                        reliability_score=similar.reliability_score,
                    )
                    return self._research_to_dict(research)

            # 2. Upsert VehicleResearch row → status = researching
            research = await self._get_or_create_research(db, profile_id)
            research.research_status = "researching"
            await db.commit()

            # Notify desktop
            await self._notify_status(profile_id, "researching")

        # 3. Run synchronous research engine in thread pool
        try:
            engine = _get_research_engine()
            result = await asyncio.to_thread(
                engine.research_vehicle,
                profile.make,
                profile.model,
                profile.year,
                engine_type=getattr(profile, 'engine_type', None),
                fuel_type=getattr(profile, 'fuel_type', None),
            )
            result_dict = result.to_dict()
        except Exception as e:
            logger.error(f"Research failed for profile {profile_id}: {e}")
            async with get_db_session() as db:
                research = await self._get_research(db, profile_id)
                if research:
                    research.research_status = "failed"
                    await db.commit()
            await self._notify_status(profile_id, "failed")
            return {"error": str(e)}

        # 4. Persist results
        async with get_db_session() as db:
            research = await self._get_research(db, profile_id)
            if not research:
                research = await self._get_or_create_research(db, profile_id)

            research.research_status = "completed"
            research.common_problems = json.dumps(result_dict.get("common_problems", []))
            research.failure_prone_parts = json.dumps(result_dict.get("failure_prone_parts", []))
            research.recalls = json.dumps(result_dict.get("recalls", []))
            research.tsbs = json.dumps(result_dict.get("tsbs", []))
            research.owner_reviews_summary = result_dict.get("owner_reviews_summary", "")
            research.reliability_score = result_dict.get("reliability_score", 5.0)
            research.confidence_score = result_dict.get("confidence_score", 0.5)
            research.ai_features = json.dumps(result_dict.get("ai_features", {}))
            research.raw_search_results = json.dumps(result_dict.get("sources", []))
            research.sources = json.dumps(result_dict.get("sources", []))
            research.researched_at = time.time()

            # Determine VIN status
            profile = await db.get(VehicleProfile, profile_id)
            if profile and profile.vin:
                research.vin_status = "detected"
            else:
                research.vin_status = "missing"

            await db.commit()

        # 5. Notify desktop/clients
        await self._notify_status(
            profile_id,
            "completed",
            reliability_score=result_dict.get("reliability_score"),
            problems_found=len(result_dict.get("common_problems", [])),
            recalls_found=len(result_dict.get("recalls", [])),
        )

        # 6. If VIN is missing, send a separate alert
        if research.vin_status == "missing":
            vehicle_name = f"{profile.year} {profile.make} {profile.model}" if profile else ""
            await ws_manager.broadcast({
                "type": "vin_missing_alert",
                "profile_id": profile_id,
                "vehicle_name": vehicle_name,
            })

        logger.info(f"Research completed for profile {profile_id}")
        return result_dict

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    async def get_research(self, db: AsyncSession, profile_id: int) -> Optional[Dict[str, Any]]:
        """Return parsed research data for a vehicle, or None."""
        research = await self._get_research(db, profile_id)
        if not research:
            return None
        return self._research_to_dict(research)

    async def get_research_status(self, db: AsyncSession, profile_id: int) -> Dict[str, Any]:
        """Return lightweight status dict."""
        research = await self._get_research(db, profile_id)
        if not research:
            return {"status": "none", "researched_at": None}
        return {
            "status": research.research_status,
            "researched_at": research.researched_at,
            "vin_status": research.vin_status,
        }

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    async def refresh_research(self, profile_id: int) -> Dict[str, Any]:
        """Mark existing research as stale and re-run (always fresh, no cache)."""
        async with get_db_session() as db:
            research = await self._get_research(db, profile_id)
            if research:
                research.research_status = "stale"
                await db.commit()

        return await self.research_vehicle(profile_id, force_fresh=True)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_research(self, db: AsyncSession, profile_id: int) -> Optional[VehicleResearch]:
        result = await db.execute(
            select(VehicleResearch).where(VehicleResearch.profile_id == profile_id)
        )
        return result.scalar_one_or_none()

    async def _find_similar_research(
        self, db: AsyncSession, make: str, model: str, year: int,
        engine_type: Optional[str], exclude_profile_id: int
    ) -> Optional[VehicleResearch]:
        """Find existing completed research for a similar vehicle.

        Match: same make + model (case-insensitive) + year ±2 + same engine_type.
        Used to clone research and avoid duplicate Haiku API costs.
        """
        stmt = (
            select(VehicleResearch)
            .join(VehicleProfile, VehicleResearch.profile_id == VehicleProfile.profile_id)
            .where(
                VehicleResearch.research_status == "completed",
                VehicleResearch.profile_id != exclude_profile_id,
                func.lower(VehicleProfile.make) == make.strip().lower(),
                func.lower(VehicleProfile.model) == model.strip().lower(),
                VehicleProfile.year.between(year - 2, year + 2),
            )
        )
        if engine_type:
            stmt = stmt.where(
                func.lower(VehicleProfile.engine_type) == engine_type.strip().lower()
            )
        result = await db.execute(stmt.limit(1))
        return result.scalar_one_or_none()

    async def _get_or_create_research(self, db: AsyncSession, profile_id: int) -> VehicleResearch:
        research = await self._get_research(db, profile_id)
        if research:
            return research
        research = VehicleResearch(profile_id=profile_id, research_status="pending")
        db.add(research)
        await db.flush()
        return research

    async def _notify_status(
        self,
        profile_id: int,
        status: str,
        reliability_score: float = None,
        problems_found: int = None,
        recalls_found: int = None,
    ):
        payload: Dict[str, Any] = {
            "type": "vehicle_research_update",
            "profile_id": profile_id,
            "status": status,
        }
        if reliability_score is not None:
            payload["reliability_score"] = reliability_score
        if problems_found is not None:
            payload["problems_found"] = problems_found
        if recalls_found is not None:
            payload["recalls_found"] = recalls_found

        try:
            await ws_manager.broadcast(payload)
        except Exception as e:
            logger.debug(f"WebSocket notify failed (non-critical): {e}")

    @staticmethod
    def _research_to_dict(research: VehicleResearch) -> Dict[str, Any]:
        """Convert a VehicleResearch ORM row to a JSON-safe dict."""
        def _safe_json(val):
            if not val:
                return []
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return val

        return {
            "profile_id": research.profile_id,
            "research_status": research.research_status,
            "common_problems": _safe_json(research.common_problems),
            "failure_prone_parts": _safe_json(research.failure_prone_parts),
            "recalls": _safe_json(research.recalls),
            "tsbs": _safe_json(research.tsbs),
            "owner_reviews_summary": research.owner_reviews_summary or "",
            "reliability_score": research.reliability_score,
            "confidence_score": research.confidence_score,
            "ai_features": _safe_json(research.ai_features),
            "sources": _safe_json(research.sources),
            "vin_status": research.vin_status,
            "researched_at": research.researched_at,
            "created_at": research.created_at if hasattr(research, "created_at") else None,
            "updated_at": research.updated_at if hasattr(research, "updated_at") else None,
        }


def get_research_service() -> VehicleResearchService:
    """Get or create the global research service singleton."""
    global _service
    if _service is None:
        _service = VehicleResearchService()
    return _service
