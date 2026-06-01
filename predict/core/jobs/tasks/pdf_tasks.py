"""
PDF generation background tasks.

The main task is `generate_enhanced_report_job` which runs the full pipeline:
  Raw Telemetry → numpy stats → Risk Classification → LLM Narrative → Charts → PDF → Email
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
from pathlib import Path

from predict.core.config import get_config

logger = logging.getLogger(__name__)

# Sensor columns on VehicleData that we extract for stats/charts
REPORT_SENSORS = [
    "rpm", "coolant_temp", "battery_voltage", "engine_load",
    "throttle_pos", "intake_temp", "oil_temp", "fuel_level",
    "maf_rate", "short_term_fuel_trim", "long_term_fuel_trim",
    "boost_pressure",
]

# Subset shown as trend charts in the PDF
CHART_SENSORS = {
    "coolant_temp": "°C",
    "battery_voltage": "V",
    "engine_load": "%",
    "rpm": "RPM",
}


async def generate_enhanced_report_job(
    ctx: Dict[str, Any],
    report_id: int,
    vehicle_id: int,
    report_type: str,
    user_id: int,
    trip_id: Optional[int] = None,
    include_ai_predictions: bool = False,
) -> Dict[str, Any]:
    """
    ARQ background job — full LLM-powered report generation pipeline.

    Steps:
    1. Fetch vehicle info + health assessment (cold-start engine)
    2. Fetch vehicle research data
    3. Fetch recent sensor data (last 7 days)
    4. TelemetryStats.compute_vehicle_summary()
    5. ReportContentGenerator.generate_diagnostic_narrative()
    6. ReportChartGenerator — health bar chart + sensor trend charts
    7. PDFService.generate_enhanced_diagnostic_report()
    8. Update Report row → status="completed"
    9. Email PDF to user
    10. FCM notification
    """
    start_time = time.perf_counter()
    logger.info(f"[Report {report_id}] Starting enhanced report generation for vehicle {vehicle_id}")

    # Lazy imports to keep worker startup fast
    from sqlalchemy import select, desc
    from predict.core.db.session import get_session_maker
    from predict.core.db.models.vehicle import VehicleProfile, VehicleData, VehicleResearch
    from predict.core.db.models.audit import Report
    from predict.core.db.models.user import User
    from predict.core.ai.cold_start_predictor import get_cold_start_predictor
    from predict.core.services.telemetry_stats import TelemetryStats
    from predict.core.services.report_content_generator import get_report_content_generator
    from predict.core.services.report_chart_generator import ReportChartGenerator
    from predict.core.services.pdf_service import PDFService
    from predict.core.services.email_service import EmailService
    from predict.core.services.fcm_service import FCMService

    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            # ---------- 1. Vehicle info ----------
            profile_result = await session.execute(
                select(VehicleProfile).where(VehicleProfile.profile_id == vehicle_id)
            )
            profile = profile_result.scalar_one_or_none()
            if not profile:
                await _fail_report(session, report_id, "Vehicle not found")
                return {"status": "failed", "reason": "vehicle_not_found"}

            vehicle_info = {
                "id": profile.profile_id,
                "name": profile.name or f"{profile.year} {profile.make} {profile.model}",
                "make": profile.make,
                "model": profile.model,
                "year": profile.year,
                "vin": profile.vin,
                "engine_type": getattr(profile, "engine_type", ""),
                "displacement": getattr(profile, "displacement", ""),
                "mileage": 0,
            }

            # ---------- 2. Health assessment (cold-start engine) ----------
            health_data = {}
            try:
                predictor = get_cold_start_predictor()

                # Latest telemetry
                latest_result = await session.execute(
                    select(VehicleData)
                    .where(VehicleData.profile_id == vehicle_id)
                    .order_by(desc(VehicleData.timestamp))
                    .limit(1)
                )
                latest_record = latest_result.scalar_one_or_none()
                latest_telemetry = _extract_telemetry(latest_record) if latest_record else {}

                # Telemetry history (100 recent)
                history_result = await session.execute(
                    select(VehicleData)
                    .where(VehicleData.profile_id == vehicle_id)
                    .order_by(desc(VehicleData.timestamp))
                    .limit(100)
                )
                history_records = history_result.scalars().all()
                telemetry_history = [_extract_telemetry(r) for r in history_records]

                vehicle_profile_dict = {
                    "make": profile.make, "model": profile.model,
                    "year": profile.year, "vin": profile.vin,
                }

                health_data = await predictor.assess_vehicle_health(
                    vehicle_id=vehicle_id,
                    latest_telemetry=latest_telemetry,
                    vehicle_profile=vehicle_profile_dict,
                    dtc_codes=[],
                    telemetry_history=telemetry_history,
                    climate_region="qatar",
                )
                logger.info(f"[Report {report_id}] Health assessment: score={health_data.get('health_score')}")
            except Exception as e:
                logger.warning(f"[Report {report_id}] Health assessment failed (continuing): {e}")
                health_data = {"health_score": 0, "components": [], "is_cold_start": True}

            # ---------- 3. Vehicle research ----------
            research_data = None
            try:
                import json as _json
                research_result = await session.execute(
                    select(VehicleResearch)
                    .where(VehicleResearch.profile_id == vehicle_id)
                    .order_by(desc(VehicleResearch.researched_at))
                    .limit(1)
                )
                research = research_result.scalar_one_or_none()
                if research and research.research_status == "completed":

                    def _parse_json_field(val):
                        if not val:
                            return []
                        if isinstance(val, list):
                            return val
                        try:
                            return _json.loads(val)
                        except (ValueError, TypeError):
                            return [val] if val else []

                    research_data = {
                        "reliability_score": research.reliability_score,
                        "common_problems": _parse_json_field(research.common_problems),
                        "recalls": _parse_json_field(research.recalls),
                        "tsbs": _parse_json_field(research.tsbs),
                        "known_issues": _parse_json_field(research.failure_prone_parts),
                        "ai_summary": research.owner_reviews_summary or "",
                    }
            except Exception as e:
                logger.warning(f"[Report {report_id}] Research fetch failed (continuing): {e}")

            # ---------- 4. Sensor data for stats + charts (last 7 days) ----------
            seven_days_ago = time.time() - (7 * 86400)
            sensor_result = await session.execute(
                select(VehicleData)
                .where(
                    VehicleData.profile_id == vehicle_id,
                    VehicleData.timestamp >= seven_days_ago,
                )
                .order_by(VehicleData.timestamp)
                .limit(5000)
            )
            sensor_records = sensor_result.scalars().all()

            # Build per-sensor reading lists
            all_sensor_data = {}
            sensor_time_series = {}  # for charts: {sensor: [{timestamp, value}]}
            for record in sensor_records:
                for sensor in REPORT_SENSORS:
                    val = getattr(record, sensor, None)
                    if val is not None:
                        all_sensor_data.setdefault(sensor, []).append(val)
                        sensor_time_series.setdefault(sensor, []).append({
                            "timestamp": record.timestamp,
                            "value": val,
                        })

            # ---------- 5. Statistical preprocessing ----------
            stats = TelemetryStats()
            stats_summary = stats.compute_vehicle_summary(all_sensor_data)
            logger.info(f"[Report {report_id}] Stats: {stats_summary.get('sensors_analyzed', 0)} sensors analyzed")

            # ---------- 5b. Normalize components format ----------
            # cold_start_predictor returns components as dict with health_pct keys;
            # chart/narrative generators expect list with health_percent keys
            raw_components = health_data.get("components", [])
            if isinstance(raw_components, dict):
                components_list = []
                for comp_id, comp_data in raw_components.items():
                    entry = {"name": comp_id, "component_id": comp_id}
                    entry.update(comp_data)
                    entry["health_percent"] = comp_data.get("health_pct", 0)
                    components_list.append(entry)
                health_data["components"] = components_list

            # ---------- 6. LLM narrative ----------
            content_gen = get_report_content_generator()
            narrative = await content_gen.generate_diagnostic_narrative(
                vehicle_info=vehicle_info,
                health_data=health_data,
                research_data=research_data,
                stats_summary=stats_summary,
            )
            logger.info(f"[Report {report_id}] Narrative generated ({len(narrative.get('executive_summary', ''))} chars)")

            # ---------- 7. Charts (Matplotlib — run in thread) ----------
            chart_gen = ReportChartGenerator()
            health_chart = None
            trend_charts = []

            components = health_data.get("components", [])
            if components:
                health_chart = await asyncio.to_thread(
                    chart_gen.generate_health_bar_chart, components
                )

            for sensor_name, unit in CHART_SENSORS.items():
                ts_data = sensor_time_series.get(sensor_name, [])
                if len(ts_data) >= 3:
                    chart_bytes = await asyncio.to_thread(
                        chart_gen.generate_sensor_trend_chart, ts_data, sensor_name, unit
                    )
                    if chart_bytes:
                        trend_charts.append(chart_bytes)

            # ---------- 7b. AI Predictions for PDF (optional) ----------
            ai_predictions_data = None
            if include_ai_predictions:
                try:
                    from predict.core.api.v1.predictions import (
                        _fetch_sensor_history, _compute_trend, _compute_projection,
                        _generate_narratives, _compute_accuracy,
                        COMPONENT_SENSOR_MAP, NORMAL_RANGES,
                    )
                    sensor_history = await _fetch_sensor_history(session, vehicle_id, days=30)
                    raw_comps = health_data.get("components", {})
                    if isinstance(raw_comps, list):
                        raw_comps = {c.get("component_id", c.get("name", "")): c for c in raw_comps}
                    comp_bundles = {}
                    for comp_id in COMPONENT_SENSOR_MAP:
                        ch = raw_comps.get(comp_id, {})
                        sensor_col = COMPONENT_SENSOR_MAP[comp_id]
                        sdata = sensor_history.get(sensor_col, [])
                        vals = [d["value"] for d in sdata]
                        trend = _compute_trend(vals)
                        nr = NORMAL_RANGES.get(sensor_col, (0, 100))
                        projection = _compute_projection(
                            trend["current"] or (vals[-1] if vals else 0),
                            trend["slope_per_day"], nr,
                        ) if trend["current"] is not None else {}
                        comp_bundles[comp_id] = {
                            "health_pct": ch.get("health_pct", ch.get("health_percent", 0)),
                            "trend": trend["direction"],
                            "current_status": {"current_value": trend["current"], "normal_min": nr[0], "normal_max": nr[1]},
                            "trend_analysis": {"slope_per_day": trend["slope_per_day"], "direction": trend["direction"]},
                            "projection": projection,
                            "headline": ch.get("recommendation", ""),
                            "status_text": "", "trend_text": "", "prediction_text": "",
                            "cross_component_text": "", "compared_to_others_text": "",
                            "recommended_action": {"priority": "MONITOR", "action": ch.get("recommendation", ""), "cost_estimate": None},
                        }
                    accuracy = _compute_accuracy(True, False, False, "none", research_data is not None, False, False, False)
                    narratives = await _generate_narratives(
                        comp_bundles, vehicle_info, research_data,
                        health_data.get("health_score", 0), accuracy, [],
                    )
                    llm_comps = narratives.get("components", {})
                    for cid, bundle in comp_bundles.items():
                        llm = llm_comps.get(cid, {})
                        if llm:
                            for f in ["headline", "status_text", "trend_text", "prediction_text", "cross_component_text", "compared_to_others_text"]:
                                if llm.get(f):
                                    bundle[f] = llm[f]
                            bundle["recommended_action"] = {
                                "priority": llm.get("action_priority", "MONITOR"),
                                "action": llm.get("action", ""),
                                "cost_estimate": llm.get("cost_estimate"),
                            }
                    ai_predictions_data = {
                        "components": comp_bundles,
                        "action_plan": narratives.get("action_plan", {}),
                    }
                    logger.info(f"[Report {report_id}] AI predictions generated for PDF")
                except Exception as e:
                    logger.warning(f"[Report {report_id}] AI predictions for PDF failed (non-fatal): {e}")

            # ---------- 7c. v3 Intelligence Sections (maintenance forecast + fleet comparison) ----------
            v3_data = None
            try:
                from predict.core.api.v1.predictions import (
                    _compute_maintenance_events, _compute_fleet_comparison,
                )
                from predict.core.db.models.vehicle import VehicleProfile as VP
                import json as _json

                # Fetch component_ages and mileage from profile
                vp_result = await session.execute(
                    select(VP).where(VP.profile_id == vehicle_id)
                )
                vp_row = vp_result.scalar_one_or_none()

                comp_ages = None
                vp_mileage = None
                vp_year = vehicle_info.get("year")
                if vp_row:
                    if vp_row.component_ages:
                        comp_ages = _json.loads(vp_row.component_ages) if isinstance(vp_row.component_ages, str) else dict(vp_row.component_ages)
                    vp_mileage = getattr(vp_row, "mileage_km", None)

                # Build component_bundles from existing data
                _pdf_bundles = {}
                if ai_predictions_data and ai_predictions_data.get("components"):
                    _pdf_bundles = ai_predictions_data["components"]
                else:
                    raw_c = health_data.get("components", {})
                    if isinstance(raw_c, list):
                        raw_c = {c.get("component_id", c.get("name", "")): c for c in raw_c}
                    for cid, cd in raw_c.items():
                        _pdf_bundles[cid] = {
                            "health_pct": cd.get("health_pct", cd.get("health_percent", 0)),
                            "trend": cd.get("trend", "stable"),
                        }

                maintenance_events = _compute_maintenance_events(
                    component_bundles=_pdf_bundles,
                    component_ages=comp_ages,
                    mileage_km=vp_mileage,
                    vehicle_year=vp_year,
                )

                fleet_comparison = await _compute_fleet_comparison(
                    session=session,
                    vehicle_id=vehicle_id,
                    health_score=health_data.get("health_score", 0),
                    component_bundles=_pdf_bundles,
                    make=vehicle_info.get("make"),
                    model=vehicle_info.get("model"),
                    year=vp_year,
                )

                # Try to load cached AI diagnostic from DB-persisted /explain
                ai_diagnostic = None
                if vp_row and getattr(vp_row, "last_explain_json", None):
                    try:
                        cached_explain = _json.loads(vp_row.last_explain_json)
                        ai_diagnostic = cached_explain.get("ai_diagnostic")
                    except (ValueError, TypeError):
                        pass

                v3_data = {
                    "maintenance_events": maintenance_events,
                    "fleet_comparison": fleet_comparison,
                    "ai_diagnostic": ai_diagnostic,
                }
                logger.info(f"[Report {report_id}] v3 data: {len(maintenance_events)} maintenance events, fleet={'yes' if fleet_comparison else 'no'}")
            except Exception as e:
                logger.warning(f"[Report {report_id}] v3 sections failed (non-fatal): {e}")

            # ---------- 8. PDF generation ----------
            pdf_service = PDFService()
            report_path = await pdf_service.generate_enhanced_diagnostic_report(
                vehicle_info=vehicle_info,
                diagnostic_results={
                    "health_score": health_data.get("health_score", 0),
                    "risk_level": "critical" if health_data.get("health_score", 0) < 50
                                  else "warning" if health_data.get("health_score", 0) < 75
                                  else "good",
                    "subsystem_scores": {
                        c.get("component_id", c.get("name", "unknown")): {
                            "score": c.get("health_percent", 0),
                            "status": "critical" if c.get("health_percent", 0) < 50
                                      else "warning" if c.get("health_percent", 0) < 75
                                      else "good",
                            "notes": c.get("recommendation", ""),
                        }
                        for c in components
                    },
                },
                narrative=narrative,
                stats_summary=stats_summary,
                health_chart=health_chart,
                trend_charts=trend_charts,
                ai_predictions=ai_predictions_data,
                v3_data=v3_data,
            )
            logger.info(f"[Report {report_id}] PDF generated: {report_path}")

            # ---------- 9. Update Report DB row ----------
            report_result = await session.execute(
                select(Report).where(Report.id == report_id)
            )
            report_row = report_result.scalar_one_or_none()
            if report_row:
                report_row.file_path = report_path
                report_row.status = "completed"
                report_row.updated_at = time.time()
                await session.commit()

            # ---------- 10. Email to user ----------
            try:
                user_result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = user_result.scalar_one_or_none()
                if user and user.email:
                    pdf_bytes = Path(report_path).read_bytes()
                    email_service = EmailService()
                    await email_service.send_report_email(
                        to_email=user.email,
                        name=user.name or "Driver",
                        vehicle_name=vehicle_info["name"],
                        report_type=report_type,
                        health_score=health_data.get("health_score", 0),
                        components_analyzed=len(components),
                        pdf_bytes=pdf_bytes,
                    )
                    logger.info(f"[Report {report_id}] Email sent to {user.email}")
            except Exception as e:
                logger.warning(f"[Report {report_id}] Email send failed (non-critical): {e}")

            # ---------- 11. FCM notification ----------
            try:
                fcm = FCMService()
                await fcm.send_to_user(
                    user_id=user_id,
                    title="Report Ready",
                    body=f"Your {report_type} report is ready for download",
                    data={
                        "type": "report_ready",
                        "report_id": str(report_id),
                        "report_type": report_type,
                        "vehicle_id": str(vehicle_id),
                    },
                )
            except Exception as e:
                logger.debug(f"[Report {report_id}] FCM failed (non-critical): {e}")

            elapsed = time.perf_counter() - start_time
            logger.info(f"[Report {report_id}] Complete in {elapsed:.1f}s")

            return {
                "status": "success",
                "report_id": report_id,
                "filepath": report_path,
                "duration_seconds": elapsed,
            }

        except Exception as e:
            logger.error(f"[Report {report_id}] Pipeline failed: {e}", exc_info=True)
            await _fail_report(session, report_id, str(e))
            raise


async def _fail_report(session, report_id: int, reason: str):
    """Mark a report as failed in the DB."""
    from predict.core.db.models.audit import Report
    from sqlalchemy import select

    try:
        result = await session.execute(select(Report).where(Report.id == report_id))
        report = result.scalar_one_or_none()
        if report:
            report.status = "failed"
            report.updated_at = time.time()
            await session.commit()
    except Exception as e:
        logger.error(f"[Report {report_id}] Failed to update status: {e}")


def _extract_telemetry(record) -> Dict[str, Any]:
    """Extract sensor values from a VehicleData row into a dict."""
    data = {}
    for field in [
        "rpm", "speed", "coolant_temp", "battery_voltage", "engine_load",
        "throttle_pos", "fuel_level", "fuel_pressure", "intake_temp",
        "maf_rate", "oil_temp", "short_term_fuel_trim", "long_term_fuel_trim",
        "timing_advance", "ambient_temp", "boost_pressure", "fuel_rate",
        "torque", "obd_odometer",
    ]:
        val = getattr(record, field, None)
        if val is not None:
            data[field] = val
    return data


# Keep old stubs for backward compatibility (existing enqueued jobs)
async def generate_health_report_pdf(
    ctx: Dict[str, Any],
    vehicle_id: int,
    report_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Legacy stub — redirects to enhanced pipeline."""
    logger.info(f"Legacy health report task for vehicle {vehicle_id}, running basic generation")
    config = get_config()
    reports_dir = config.REPORTS_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)

    filename = f"health_report_vehicle_{vehicle_id}_{int(time.time())}.pdf"
    filepath = reports_dir / filename

    try:
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(filepath))
        c.drawString(100, 700, f"Health Report for Vehicle {vehicle_id}")
        c.drawString(100, 680, f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())}")
        c.save()
    except ImportError:
        filepath = filepath.with_suffix(".txt")
        filepath.write_text(f"Health Report for Vehicle {vehicle_id}")

    return {"status": "success", "filepath": str(filepath)}


async def generate_diagnostic_report_pdf(
    ctx: Dict[str, Any],
    vehicle_id: int,
    dtc_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Legacy stub — basic diagnostic report."""
    logger.info(f"Legacy diagnostic report task for vehicle {vehicle_id}")
    config = get_config()
    reports_dir = config.REPORTS_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)

    filename = f"diagnostic_report_vehicle_{vehicle_id}_{int(time.time())}.pdf"
    filepath = reports_dir / filename

    try:
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(str(filepath))
        c.drawString(100, 700, f"Diagnostic Report for Vehicle {vehicle_id}")
        c.save()
    except ImportError:
        filepath = filepath.with_suffix(".txt")
        filepath.write_text(f"Diagnostic Report for Vehicle {vehicle_id}")

    return {"status": "success", "filepath": str(filepath)}
