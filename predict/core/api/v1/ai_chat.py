"""
AI Chat API routes with float timestamps.
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from predict.core.db.session import get_db as get_db_session
from predict.core.security.auth import get_current_user, require_admin
from predict.core.middleware.rate_limiter import get_rate_limiter
from predict.core.ai.llm.assistant import get_llm_assistant, ensure_llm_loaded
from predict.core.db.models.vehicle import VehicleProfile
from predict.core.db.models.dtc import DTCCodes
from predict.core.services.vehicle_research_service import get_research_service
from predict.core.cache.redis_client import get_redis

logger = logging.getLogger(__name__)
router = APIRouter()  # No prefix here - prefix is set in router.py

# ---- Rate-limiting for chat (20 requests/hour per user) ----
_rl = get_rate_limiter()

async def _rate_limit_chat(request: Request):
    allowed, meta = await _rl.is_allowed(
        f"{_rl._get_client_ip(request)}:/ai/chat", limit=20, window_seconds=3600
    )
    if not allowed:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many chat requests. Try again later.")


# ===== Chat Memory (Redis-backed) =====

CHAT_HISTORY_TTL = 86400  # 24 hours
CHAT_MAX_MESSAGES = 10    # Keep last 5 pairs (user+assistant)


async def store_chat_message(conversation_id: str, role: str, content: str) -> None:
    """Store a chat message in Redis conversation history."""
    r = await get_redis()
    if not r:
        return
    try:
        key = f"chat:{conversation_id}"
        raw = await r.get(key)
        messages = json.loads(raw) if raw else []
        messages.append({"role": role, "content": content[:500]})
        messages = messages[-CHAT_MAX_MESSAGES:]
        await r.setex(key, CHAT_HISTORY_TTL, json.dumps(messages))
    except Exception as e:
        logger.debug(f"Chat memory store failed (non-fatal): {e}")


async def get_chat_history(conversation_id: str) -> List[Dict[str, str]]:
    """Retrieve conversation history from Redis."""
    r = await get_redis()
    if not r:
        return []
    try:
        key = f"chat:{conversation_id}"
        raw = await r.get(key)
        return json.loads(raw) if raw else []
    except Exception as e:
        logger.debug(f"Chat memory load failed (non-fatal): {e}")
        return []


# ===== Pydantic Models =====

class ChatRequest(BaseModel):
    """Request model for basic chat endpoint."""
    message: str = Field(..., description="User message")
    vehicle_id: Optional[int] = Field(default=None, description="Vehicle profile ID for context")
    profile_id: Optional[int] = Field(default=None, description="Alias for vehicle_id")
    context: Optional[str] = Field(default=None, description="Additional context")


class SmartChatRequest(BaseModel):
    """Request model for smart chat endpoint."""
    message: str = Field(..., description="User message")
    profile_id: Optional[int] = Field(default=None, description="Vehicle profile ID")
    vehicle_context: Optional[Dict[str, Any]] = Field(default=None, description="Current vehicle sensor data")
    conversation_id: Optional[str] = Field(default=None, description="Optional conversation ID for continuity")
    stream: bool = Field(default=False, description="Whether to stream the response")


class SmartChatResponse(BaseModel):
    """Response model for smart chat."""
    response: str
    sources: List[str]
    confidence: float
    alerts: List[str]
    is_final: bool
    conversation_id: str


class ChatRemainingResponse(BaseModel):
    """Response model for remaining chat messages."""
    remaining: int
    limit: int
    used: int
    tier: str
    unlimited: bool
    resets_at: float


class ModelInfo(BaseModel):
    """Information about an AI model."""
    id: str
    name: str
    description: str
    quantization: str
    size_gb: float
    loaded: bool


class ModelsResponse(BaseModel):
    """Response model for available models."""
    models: List[ModelInfo]
    current_model: str
    status: str


class ModelSwitchRequest(BaseModel):
    """Request model for switching models."""
    model_id: str = Field(..., description="Model ID to switch to")


class ModelSwitchResponse(BaseModel):
    """Response model for model switch."""
    success: bool
    message: str
    model: str


# ===== Helper Functions =====

def _get_tier_chat_limit(tier: str) -> int:
    """Get daily chat limit for a tier."""
    limits = {
        "free": 0,
        "pro": 15,
        "premium": 25,  # Per vehicle, max 4 vehicles
        "admin": -1,  # Unlimited
    }
    return limits.get(tier.lower(), 0)


def _get_next_midnight_timestamp() -> float:
    """Get timestamp of next midnight UTC (daily reset time)."""
    now = time.gmtime()
    tomorrow = time.mktime((now.tm_year, now.tm_mon, now.tm_mday + 1, 0, 0, 0, 0, 0, 0))
    return tomorrow


async def _maybe_web_search(message: str) -> tuple[Optional[str], List[str]]:
    """Run a web search if the message warrants it.

    Returns:
        (formatted_context_for_llm, source_strings) where source_strings is a list
        of "Title — URL" strings for display in the chat UI. Both are empty/None
        if no search was performed or if search failed.
    """
    try:
        import sys
        from pathlib import Path
        project_root = str(Path(__file__).resolve().parent.parent.parent.parent)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from web_search import should_search_web, get_search_engine

        if not should_search_web(message):
            return None, []

        engine = get_search_engine()
        results = await asyncio.to_thread(engine.search_automotive, message, 3)
        if results:
            formatted = engine.format_results_for_llm(results)
            sources = [
                f"{r.get('title', 'Source')} — {r.get('url', '')}"
                for r in results
                if r.get("url")
            ]
            return formatted, sources
    except Exception as e:
        logger.debug(f"Web search failed (non-critical): {e}")
    return None, []


# ===== API Endpoints =====

@router.post("/chat")
async def chat_with_ai(
    request: ChatRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
    _rl_guard: None = Depends(_rate_limit_chat),
):
    """
    Chat with the AI assistant about vehicle diagnostics.

    Accepts JSON body with message and optional vehicle_id.
    """
    start_time = time.perf_counter()
    message = request.message
    vehicle_id = request.vehicle_id or request.profile_id

    # Get vehicle context if provided
    context: Dict[str, Any] = {}
    context_sources: List[str] = []

    if vehicle_id:
        stmt = select(VehicleProfile).where(VehicleProfile.profile_id == vehicle_id)
        result = await session.execute(stmt)
        vehicle = result.scalar_one_or_none()

        if vehicle:
            context["vehicle"] = {
                "id": vehicle.profile_id,
                "make": vehicle.make,
                "model": vehicle.model,
                "year": vehicle.year,
                "engine_type": vehicle.engine_type,
                "displacement": vehicle.displacement,
                "cylinders": vehicle.cylinders,
            }
            context_sources.append("vehicle_profile")

        # Get active DTCs — include severity and description
        stmt = (
            select(DTCCodes)
            .where(DTCCodes.vehicle_id == vehicle_id)
            .where(DTCCodes.is_active == 1)
        )
        result = await session.execute(stmt)
        dtcs = result.scalars().all()

        if dtcs:
            context["dtcs"] = [
                f"{dtc.code} ({getattr(dtc, 'severity', 'unknown')}): {getattr(dtc, 'description', '')}"
                for dtc in dtcs
            ]

        # Load vehicle research data as context
        try:
            research_svc = get_research_service()
            research_data = await research_svc.get_research(session, vehicle_id)
            if research_data and research_data.get("research_status") == "completed":
                context["vehicle_research"] = {
                    "common_problems": research_data.get("common_problems", []),
                    "recalls": research_data.get("recalls", []),
                    "tsbs": research_data.get("tsbs", []),
                    "reliability_score": research_data.get("reliability_score"),
                    "owner_reviews_summary": research_data.get("owner_reviews_summary", ""),
                }
                context_sources.append("vehicle_research")
        except Exception as e:
            logger.debug(f"Failed to load vehicle research: {e}")

        # DTC Forensics for basic /chat (lightweight — only if DTCs present)
        if dtcs:
            try:
                from predict.core.ai.dtc_forensics import get_dtc_forensics
                from predict.core.db.models.vehicle import VehicleData
                from sqlalchemy import desc as _desc_basic

                _latest_rows = await session.execute(
                    select(VehicleData)
                    .where(VehicleData.profile_id == vehicle_id)
                    .order_by(_desc_basic(VehicleData.timestamp))
                    .limit(50)
                )
                _rows = _latest_rows.scalars().all()
                if _rows:
                    context_sources.append("telemetry")
                    _tel = {
                        k: v for k, v in {
                            "rpm": _rows[0].rpm, "speed": _rows[0].speed,
                            "coolant_temp": _rows[0].coolant_temp,
                            "battery_voltage": _rows[0].battery_voltage,
                            "engine_load": _rows[0].engine_load,
                            "maf_rate": _rows[0].maf_rate,
                            "intake_temp": _rows[0].intake_temp,
                            "short_term_fuel_trim": _rows[0].short_term_fuel_trim,
                            "long_term_fuel_trim": _rows[0].long_term_fuel_trim,
                        }.items() if v is not None
                    }
                    _hist = [
                        {k: v for k, v in {
                            "rpm": r.rpm, "speed": r.speed,
                            "coolant_temp": r.coolant_temp,
                            "battery_voltage": r.battery_voltage,
                            "engine_load": r.engine_load,
                            "maf_rate": r.maf_rate,
                        }.items() if v is not None}
                        for r in _rows
                    ]
                    _dtc_dicts_basic = [
                        {"code": d.code, "is_active": True,
                         "severity": getattr(d, "severity", "medium"),
                         "description": getattr(d, "description", "")}
                        for d in dtcs
                    ]
                    _forensics_basic = get_dtc_forensics().analyze(
                        dtc_codes=_dtc_dicts_basic,
                        telemetry_history=_hist,
                        latest_telemetry=_tel,
                    )
                    context["dtc_forensics"] = _forensics_basic.to_dict()
                    context_sources.append("dtc_forensics")
            except Exception as _dfe_basic:
                logger.debug(f"Basic chat DTC forensics failed: {_dfe_basic}")

    # Web search if the message warrants it
    web_search_context, web_sources = await _maybe_web_search(message)
    if web_search_context:
        context["web_search"] = web_search_context
        context_sources.append("web_search")

    # Get AI response (async — won't block event loop)
    assistant = await ensure_llm_loaded()

    if not assistant.is_available():
        raise HTTPException(
            status_code=503,
            detail="AI service temporarily unavailable",
        )

    response = await assistant.chat_async(message, context=context)

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    logger.info(f"AI chat response generated in {elapsed_ms:.2f}ms")

    return {
        "message": message,
        "response": response,
        "sources": web_sources,
        "context_sources": context_sources,
        "vehicle_id": vehicle_id,
        "processing_time_ms": elapsed_ms,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "timestamp_unix": time.time(),
    }


@router.post("/smart-chat", response_model=SmartChatResponse)
async def smart_chat(
    request: SmartChatRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
    _rl_guard: None = Depends(_rate_limit_chat),
):
    """
    Smart chat endpoint (alias for /chat) that accepts JSON body.
    
    This is the endpoint the Android app expects.
    
    Args:
        request: Smart chat request with message and optional vehicle context
        
    Returns:
        AI response with additional metadata
    """
    start_time = time.perf_counter()

    # Get or create conversation ID
    conversation_id = request.conversation_id or str(uuid.uuid4())

    # Build context from vehicle_context if provided
    context: Dict[str, Any] = {}
    context_sources: List[str] = []

    if request.vehicle_context:
        context["sensor_data"] = request.vehicle_context
        context_sources.append("telemetry")

        # Extract DTC codes if present
        dtc_codes = request.vehicle_context.get("dtc_codes", [])
        if dtc_codes:
            context["dtcs"] = dtc_codes

    # Get vehicle context if profile_id provided
    if request.profile_id:
        stmt = select(VehicleProfile).where(VehicleProfile.profile_id == request.profile_id)
        result = await session.execute(stmt)
        vehicle = result.scalar_one_or_none()

        if vehicle:
            context["vehicle"] = {
                "id": vehicle.profile_id,
                "make": vehicle.make,
                "model": vehicle.model,
                "year": vehicle.year,
                "engine_type": vehicle.engine_type,
                "displacement": vehicle.displacement,
                "cylinders": vehicle.cylinders,
            }
            context_sources.append("vehicle_profile")

        # Get active DTCs
        stmt = (
            select(DTCCodes)
            .where(DTCCodes.vehicle_id == request.profile_id)
            .where(DTCCodes.is_active == 1)
        )
        result = await session.execute(stmt)
        dtcs = result.scalars().all()

        if dtcs and "dtcs" not in context:
            context["dtcs"] = [
                f"{dtc.code} ({getattr(dtc, 'severity', 'unknown')}): {getattr(dtc, 'description', '')}"
                for dtc in dtcs
            ]

        # Load vehicle research data as context
        try:
            research_svc = get_research_service()
            research_data = await research_svc.get_research(session, request.profile_id)
            if research_data and research_data.get("research_status") == "completed":
                context["vehicle_research"] = {
                    "common_problems": research_data.get("common_problems", []),
                    "recalls": research_data.get("recalls", []),
                    "tsbs": research_data.get("tsbs", []),
                    "reliability_score": research_data.get("reliability_score"),
                    "owner_reviews_summary": research_data.get("owner_reviews_summary", ""),
                }
                context_sources.append("vehicle_research")
        except Exception as e:
            logger.debug(f"Failed to load vehicle research: {e}")

    # Run intelligence layers for richer LLM context
    if request.profile_id:
        try:
            from predict.core.ai.context_scoring import ContextAwareScorer
            from predict.core.ai.pattern_matcher import PatternMatcher
            from predict.core.ai.trend_analyzer import TrendAnalyzer
            from predict.core.db.models.vehicle import VehicleData
            from sqlalchemy import desc as _desc

            # Fetch latest telemetry + history for intelligence
            _latest_result = await session.execute(
                select(VehicleData)
                .where(VehicleData.profile_id == request.profile_id)
                .order_by(_desc(VehicleData.timestamp))
                .limit(100)
            )
            _history_records = _latest_result.scalars().all()

            if _history_records:
                _latest = _history_records[0]
                _telemetry = {
                    k: v for k, v in {
                        "rpm": _latest.rpm, "speed": _latest.speed,
                        "coolant_temp": _latest.coolant_temp,
                        "battery_voltage": _latest.battery_voltage,
                        "engine_load": _latest.engine_load,
                        "throttle_pos": _latest.throttle_pos,
                        "fuel_level": _latest.fuel_level,
                        "fuel_pressure": _latest.fuel_pressure,
                        "oil_temp": _latest.oil_temp,
                        "intake_temp": _latest.intake_temp,
                        "maf_rate": _latest.maf_rate,
                        "short_term_fuel_trim": _latest.short_term_fuel_trim,
                        "long_term_fuel_trim": _latest.long_term_fuel_trim,
                        "timing_advance": _latest.timing_advance,
                        "ambient_temp": _latest.ambient_temp,
                        "boost_pressure": _latest.boost_pressure,
                        "fuel_rate": _latest.fuel_rate,
                        "torque": _latest.torque,
                        "obd_odometer": _latest.obd_odometer,
                    }.items() if v is not None
                }
                _history = [
                    {k: v for k, v in {
                        "rpm": r.rpm, "speed": r.speed,
                        "coolant_temp": r.coolant_temp,
                        "battery_voltage": r.battery_voltage,
                        "engine_load": r.engine_load,
                        "oil_temp": r.oil_temp,
                        "intake_temp": r.intake_temp,
                        "maf_rate": r.maf_rate,
                        "boost_pressure": r.boost_pressure,
                        "fuel_rate": r.fuel_rate,
                        "torque": r.torque,
                    }.items() if v is not None}
                    for r in _history_records
                ]

                # Telemetry freshness check
                if hasattr(_latest, 'timestamp') and _latest.timestamp:
                    age_seconds = time.time() - _latest.timestamp
                    if age_seconds > 3600:
                        context["data_freshness"] = f"WARNING: Data is {age_seconds/3600:.1f} hours old"
                    else:
                        context["data_freshness"] = f"Data from {age_seconds:.0f} seconds ago"

                patterns = PatternMatcher().match(_telemetry, None, _history)
                trends = TrendAnalyzer().analyze(_history)

                intel = {}
                if patterns:
                    intel["patterns_detected"] = [
                        {"name": p.name, "display_name": p.display_name,
                         "confidence": p.confidence, "severity": p.severity,
                         "reasoning": p.reasoning, "recommendation": p.recommendation}
                        for p in patterns[:3]
                    ]
                if trends:
                    intel["trends"] = [
                        {"sensor": t.sensor, "message": t.message,
                         "severity": t.severity, "direction": t.direction}
                        for t in trends[:3]
                    ]

                # Urgency from health assessment if available
                try:
                    from predict.core.ai.cold_start_predictor import get_cold_start_predictor
                    _predictor = get_cold_start_predictor()
                    _health = await _predictor.assess_vehicle_health(
                        vehicle_id=request.profile_id,
                        latest_telemetry=_telemetry,
                        vehicle_profile=context.get("vehicle", {}),
                        dtc_codes=[],
                        telemetry_history=_history,
                        climate_region="qatar",
                    )
                    context["health_assessment"] = _health
                    # Urgency from components
                    _comps = _health.get("components", {})
                    _critical = [c for c, d in _comps.items() if d.get("health_pct", 100) < 20]
                    if _critical:
                        intel["urgency"] = {"level": "CRITICAL", "reason": f"Components at risk: {', '.join(_critical)}"}
                    elif any(d.get("health_pct", 100) < 40 for d in _comps.values()):
                        intel["urgency"] = {"level": "WARNING", "reason": "Components need attention"}
                except Exception:
                    pass

                if intel:
                    context["intelligence"] = intel

                # Per-vehicle AI baseline (learned patterns for THIS car)
                _baseline_info = None
                try:
                    from predict.core.ai.vehicle_learner import VehicleLearner
                    _learner = VehicleLearner()
                    _baseline_info = await _learner.get_baseline_info(session, request.profile_id)
                    if _baseline_info and _baseline_info.get("phase") != "collecting":
                        _anomaly_scores = await _learner.get_anomaly_scores(
                            session, request.profile_id,
                            [_telemetry] if _telemetry else []
                        )
                        context["vehicle_baseline"] = {
                            "phase": _baseline_info["phase"],
                            "trip_count": _baseline_info["trip_count"],
                            "data_points": _baseline_info["data_points"],
                            "anomalies": _anomaly_scores.get("statistical", []),
                            "trends": _anomaly_scores.get("trends", []),
                        }
                except Exception:
                    pass

                # DTC Forensics — link active DTCs to sensor anomalies
                try:
                    _dtc_stmt = (
                        select(DTCCodes)
                        .where(DTCCodes.vehicle_id == request.profile_id)
                        .where(DTCCodes.is_active == 1)
                    )
                    _dtc_result = await session.execute(_dtc_stmt)
                    _active_dtcs = _dtc_result.scalars().all()

                    if _active_dtcs and len(_history) >= 10:
                        from predict.core.ai.dtc_forensics import get_dtc_forensics
                        _dtc_dicts = [
                            {
                                "code": d.code,
                                "is_active": bool(d.is_active),
                                "is_pending": bool(d.is_pending),
                                "severity": getattr(d, "severity", "medium"),
                                "description": getattr(d, "description", ""),
                            }
                            for d in _active_dtcs
                        ]
                        _baseline_stats = None
                        if _baseline_info and _baseline_info.get("sensor_stats"):
                            _baseline_stats = _baseline_info["sensor_stats"]

                        _forensics = get_dtc_forensics()
                        _forensics_result = _forensics.analyze(
                            dtc_codes=_dtc_dicts,
                            telemetry_history=_history,
                            latest_telemetry=_telemetry,
                            baseline=_baseline_stats,
                        )
                        context["dtc_forensics"] = _forensics_result.to_dict()
                except Exception as _dfe:
                    logger.debug(f"DTC forensics context failed (non-fatal): {_dfe}")

        except Exception as e:
            logger.debug(f"Intelligence context build failed (non-fatal): {e}")

    # Web search if the message warrants it
    web_search_context, web_sources = await _maybe_web_search(request.message)
    if web_search_context:
        context["web_search"] = web_search_context

    # Load conversation history from Redis
    history = await get_chat_history(conversation_id)
    if history:
        context["conversation_history"] = history

    # Get AI response (async — won't block event loop)
    assistant = await ensure_llm_loaded()

    if not assistant.is_available():
        raise HTTPException(
            status_code=503,
            detail="AI service temporarily unavailable",
        )

    try:
        response_text = await assistant.chat_async(request.message, context=context)
    except Exception as e:
        logger.error(f"LLM chat error: {e}")
        raise HTTPException(status_code=500, detail=f"AI processing error: {str(e)}")

    # Store conversation messages in Redis (fire-and-forget)
    asyncio.create_task(store_chat_message(conversation_id, "user", request.message))
    asyncio.create_task(store_chat_message(conversation_id, "assistant", response_text))

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    logger.info(f"Smart chat response generated in {elapsed_ms:.2f}ms")

    # Use real confidence from health assessment if available
    confidence = 0.85
    health_data = context.get("health_assessment", {})
    if health_data:
        # Average component confidence
        comps = health_data.get("components", {})
        if comps:
            confs = [c.get("confidence", 0.5) for c in comps.values() if isinstance(c, dict)]
            if confs:
                confidence = sum(confs) / len(confs)

    # Build alerts from urgency
    response_alerts: List[str] = []
    intel = context.get("intelligence", {})
    urg = intel.get("urgency", {})
    if urg.get("level") in ("CRITICAL", "WARNING"):
        response_alerts.append(f"{urg['level']}: {urg.get('reason', '')}")

    return SmartChatResponse(
        response=response_text,
        sources=web_sources,
        confidence=round(confidence, 2),
        alerts=response_alerts,
        is_final=True,
        conversation_id=conversation_id,
    )


@router.get("/chat/remaining", response_model=ChatRemainingResponse)
async def get_chat_remaining(
    current_user: dict = Depends(get_current_user),
):
    """
    Get remaining chat messages for user's tier.
    
    Returns:
        Remaining messages, limit, usage stats
    """
    tier = current_user.get("tier", "free")
    limit = _get_tier_chat_limit(tier)
    
    # For unlimited (admin)
    if limit == -1:
        return ChatRemainingResponse(
            remaining=-1,
            limit=-1,
            used=0,
            tier=tier,
            unlimited=True,
            resets_at=_get_next_midnight_timestamp(),
        )
    
    # For free tier with no access
    if limit == 0:
        return ChatRemainingResponse(
            remaining=0,
            limit=0,
            used=0,
            tier=tier,
            unlimited=False,
            resets_at=_get_next_midnight_timestamp(),
        )
    
    # For pro/premium tiers, calculate based on usage
    # In production, this would query actual usage from database/cache
    # For now, return the full limit
    return ChatRemainingResponse(
        remaining=limit,
        limit=limit,
        used=0,
        tier=tier,
        unlimited=False,
        resets_at=_get_next_midnight_timestamp(),
    )


@router.get("/models", response_model=ModelsResponse)
async def get_models(
    current_user: dict = Depends(get_current_user),
):
    """
    Get available AI models.
    
    Returns:
        List of available models and current model info
    """
    # We currently only use Qwen 3.5-4B
    models = [
        ModelInfo(
            id="qwen3.5-4b",
            name="Qwen 3.5 4B Instruct",
            description="Primary diagnostic assistant",
            quantization="Q5_K_M",
            size_gb=3.1,
            loaded=True,
        )
    ]

    # Check if AI is available
    assistant = get_llm_assistant()
    status = "ready" if assistant.is_available() else "unavailable"

    return ModelsResponse(
        models=models,
        current_model="qwen3.5-4b",
        status=status,
    )


@router.post("/models/switch", response_model=ModelSwitchResponse)
async def switch_model(
    request: ModelSwitchRequest,
    current_user: dict = Depends(require_admin),
):
    """
    Switch AI model (admin only).
    
    Since we only use Qwen 3.5 now, this is mostly a no-op
    but exists for Android compatibility.
    
    Args:
        request: Model switch request with model_id
        
    Returns:
        Success confirmation
    """
    # We only support qwen3.5-4b currently
    if request.model_id != "qwen3.5-4b":
        raise HTTPException(
            status_code=400,
            detail=f"Model '{request.model_id}' not available. Only 'qwen3.5-4b' is supported.",
        )
    
    return ModelSwitchResponse(
        success=True,
        message="Model switched successfully",
        model=request.model_id,
    )


@router.post("/explain-dtc/{dtc_code}")
async def explain_dtc(
    dtc_code: str,
    current_user = Depends(get_current_user),
):
    """Get AI explanation for a DTC code."""
    assistant = await ensure_llm_loaded()

    if not assistant.is_available():
        raise HTTPException(
            status_code=503,
            detail="AI service temporarily unavailable",
        )

    # Get DTC description
    dtc_descriptions = {
        "P0171": "System Too Lean (Bank 1)",
        "P0174": "System Too Lean (Bank 2)",
        "P0300": "Random/Multiple Cylinder Misfire",
        "P0301": "Cylinder 1 Misfire",
        "P0302": "Cylinder 2 Misfire",
        "P0420": "Catalyst System Efficiency Below Threshold",
    }

    description = dtc_descriptions.get(dtc_code.upper(), "Unknown Code")

    explanation = await assistant.explain_dtc_async(dtc_code, description)
    
    return {
        "dtc_code": dtc_code.upper(),
        "description": description,
        "explanation": explanation,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "timestamp_unix": time.time(),
    }


@router.get("/status")
async def get_ai_status(
    current_user = Depends(get_current_user),
):
    """Get AI service status."""
    assistant = get_llm_assistant()
    
    return {
        "available": assistant.is_available(),
        "model": assistant.current_model_name or "none",
        "loaded": assistant.is_loaded,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "timestamp_unix": time.time(),
    }
