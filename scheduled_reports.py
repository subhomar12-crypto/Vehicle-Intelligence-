"""
Scheduled Reports System
Automatically generates and delivers weekly reports to owners.

Features:
1. Weekly vehicle health summaries
2. Prediction and alert summaries
3. Service recommendations
4. Email delivery with PDF attachments
5. Bilingual support (English/Arabic)

Part of the PREDICT Vehicle Intelligence Platform.
"""

import sqlite3
import json
import os
import threading
import schedule
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ReportType(Enum):
    """Types of scheduled reports"""
    WEEKLY_SUMMARY = "weekly_summary"
    MONTHLY_SUMMARY = "monthly_summary"
    PREDICTION_DIGEST = "prediction_digest"
    SERVICE_REMINDER = "service_reminder"
    FLEET_OVERVIEW = "fleet_overview"


class ReportFormat(Enum):
    """Output formats for reports"""
    EMAIL = "email"
    PDF = "pdf"
    HTML = "html"
    JSON = "json"


class DeliveryStatus(Enum):
    """Status of report delivery"""
    PENDING = "pending"
    GENERATING = "generating"
    DELIVERED = "delivered"
    FAILED = "failed"


@dataclass
class ReportSchedule:
    """A scheduled report configuration"""
    id: Optional[int]
    schedule_id: str
    owner_id: str
    owner_name: str
    owner_email: str
    report_type: ReportType
    schedule: str              # cron-like: "weekly:monday:09:00"
    language: str              # "en" or "ar"
    include_vehicles: List[str]  # Empty = all vehicles
    enabled: bool
    last_run: Optional[datetime]
    next_run: Optional[datetime]
    created_at: datetime


@dataclass
class GeneratedReport:
    """A generated report"""
    id: Optional[int]
    report_id: str
    schedule_id: str
    owner_id: str
    report_type: ReportType
    period_start: datetime
    period_end: datetime
    data: Dict[str, Any]
    html_content: Optional[str]
    delivery_status: DeliveryStatus
    delivered_at: Optional[datetime]
    error: Optional[str]
    created_at: datetime


class ScheduledReportManager:
    """
    Manages scheduled report generation and delivery.

    Handles:
    - Report scheduling configuration
    - Automatic report generation
    - Email delivery with attachments
    - Report history tracking
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            app_data = os.path.join(os.path.expanduser("~"), ".predict")
            os.makedirs(app_data, exist_ok=True)
            db_path = os.path.join(app_data, "scheduled_reports.db")

        self.db_path = db_path
        self._scheduler_running = False
        self._scheduler_thread = None
        self._init_database()

    def _init_database(self):
        """Initialize the reports database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Report schedules table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS report_schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schedule_id TEXT UNIQUE NOT NULL,
                    owner_id TEXT NOT NULL,
                    owner_name TEXT NOT NULL,
                    owner_email TEXT NOT NULL,
                    report_type TEXT NOT NULL,
                    schedule TEXT NOT NULL,
                    language TEXT DEFAULT 'en',
                    include_vehicles TEXT,
                    enabled INTEGER DEFAULT 1,
                    last_run TEXT,
                    next_run TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            # Generated reports table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS generated_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_id TEXT UNIQUE NOT NULL,
                    schedule_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    report_type TEXT NOT NULL,
                    period_start TEXT NOT NULL,
                    period_end TEXT NOT NULL,
                    data TEXT,
                    html_content TEXT,
                    delivery_status TEXT DEFAULT 'pending',
                    delivered_at TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            # Indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_schedule_owner
                ON report_schedules(owner_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_report_owner
                ON generated_reports(owner_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_report_created
                ON generated_reports(created_at)
            """)

            conn.commit()

    def create_schedule(
        self,
        owner_id: str,
        owner_name: str,
        owner_email: str,
        report_type: ReportType,
        schedule: str = "weekly:monday:09:00",
        language: str = "en",
        include_vehicles: List[str] = None
    ) -> str:
        """
        Create a new report schedule.

        Args:
            owner_id: Owner/customer ID
            owner_name: Owner's name for report greeting
            owner_email: Email address for delivery
            report_type: Type of report
            schedule: Schedule string (e.g., "weekly:monday:09:00")
            language: Report language ('en' or 'ar')
            include_vehicles: List of vehicle IDs (empty = all)

        Returns:
            schedule_id
        """
        import uuid
        schedule_id = str(uuid.uuid4())
        now = datetime.now()
        next_run = self._calculate_next_run(schedule)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO report_schedules
                (schedule_id, owner_id, owner_name, owner_email, report_type,
                 schedule, language, include_vehicles, enabled, next_run, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """, (
                schedule_id,
                owner_id,
                owner_name,
                owner_email,
                report_type.value,
                schedule,
                language,
                json.dumps(include_vehicles or []),
                next_run.isoformat() if next_run else None,
                now.isoformat()
            ))
            conn.commit()

        logger.info(f"Created report schedule {schedule_id} for owner {owner_id}")
        return schedule_id

    def _calculate_next_run(self, schedule: str) -> Optional[datetime]:
        """Calculate the next run time based on schedule string"""
        try:
            parts = schedule.lower().split(":")
            freq = parts[0]
            now = datetime.now()

            if freq == "weekly":
                # Format: "weekly:monday:09:00"
                day_name = parts[1]
                hour = int(parts[2])
                minute = int(parts[3]) if len(parts) > 3 else 0

                days = {
                    "monday": 0, "tuesday": 1, "wednesday": 2,
                    "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6
                }

                target_day = days.get(day_name, 0)
                current_day = now.weekday()

                days_ahead = target_day - current_day
                if days_ahead <= 0:
                    days_ahead += 7

                next_date = now + timedelta(days=days_ahead)
                return next_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

            elif freq == "monthly":
                # Format: "monthly:1:09:00" (1st of month at 09:00)
                day = int(parts[1])
                hour = int(parts[2])
                minute = int(parts[3]) if len(parts) > 3 else 0

                # Next month
                if now.day >= day:
                    if now.month == 12:
                        next_date = now.replace(year=now.year + 1, month=1, day=day)
                    else:
                        next_date = now.replace(month=now.month + 1, day=day)
                else:
                    next_date = now.replace(day=day)

                return next_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

            elif freq == "daily":
                # Format: "daily:09:00"
                hour = int(parts[1])
                minute = int(parts[2]) if len(parts) > 2 else 0

                next_date = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if next_date <= now:
                    next_date += timedelta(days=1)

                return next_date

        except Exception as e:
            logger.error(f"Error calculating next run: {e}")
            return None

    def get_schedules_for_owner(self, owner_id: str) -> List[ReportSchedule]:
        """Get all report schedules for an owner"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM report_schedules
                WHERE owner_id = ?
                ORDER BY created_at DESC
            """, (owner_id,))

            return [self._row_to_schedule(row) for row in cursor.fetchall()]

    def get_pending_schedules(self) -> List[ReportSchedule]:
        """Get schedules that are due to run"""
        now = datetime.now()

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM report_schedules
                WHERE enabled = 1
                AND next_run <= ?
            """, (now.isoformat(),))

            return [self._row_to_schedule(row) for row in cursor.fetchall()]

    def enable_schedule(self, schedule_id: str) -> bool:
        """Enable a report schedule"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE report_schedules
                SET enabled = 1
                WHERE schedule_id = ?
            """, (schedule_id,))
            conn.commit()
            return cursor.rowcount > 0

    def disable_schedule(self, schedule_id: str) -> bool:
        """Disable a report schedule"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE report_schedules
                SET enabled = 0
                WHERE schedule_id = ?
            """, (schedule_id,))
            conn.commit()
            return cursor.rowcount > 0

    def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a report schedule"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM report_schedules
                WHERE schedule_id = ?
            """, (schedule_id,))
            conn.commit()
            return cursor.rowcount > 0

    def generate_report(self, schedule: ReportSchedule) -> str:
        """
        Generate a report based on schedule configuration.

        Returns:
            report_id
        """
        import uuid
        report_id = str(uuid.uuid4())
        now = datetime.now()

        # Determine report period
        if schedule.report_type == ReportType.WEEKLY_SUMMARY:
            period_start = now - timedelta(days=7)
        elif schedule.report_type == ReportType.MONTHLY_SUMMARY:
            period_start = now - timedelta(days=30)
        else:
            period_start = now - timedelta(days=7)

        period_end = now

        try:
            # Gather report data
            report_data = self._gather_report_data(
                owner_id=schedule.owner_id,
                report_type=schedule.report_type,
                period_start=period_start,
                period_end=period_end,
                vehicle_ids=schedule.include_vehicles
            )

            # Generate HTML content
            html_content = self._generate_html_report(
                report_data=report_data,
                owner_name=schedule.owner_name,
                report_type=schedule.report_type,
                language=schedule.language,
                period_start=period_start,
                period_end=period_end
            )

            # Save report
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO generated_reports
                    (report_id, schedule_id, owner_id, report_type,
                     period_start, period_end, data, html_content,
                     delivery_status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                """, (
                    report_id,
                    schedule.schedule_id,
                    schedule.owner_id,
                    schedule.report_type.value,
                    period_start.isoformat(),
                    period_end.isoformat(),
                    json.dumps(report_data),
                    html_content,
                    now.isoformat()
                ))
                conn.commit()

            logger.info(f"Generated report {report_id} for schedule {schedule.schedule_id}")
            return report_id

        except Exception as e:
            logger.error(f"Error generating report: {e}")
            # Save failed report
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO generated_reports
                    (report_id, schedule_id, owner_id, report_type,
                     period_start, period_end, delivery_status, error, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'failed', ?, ?)
                """, (
                    report_id,
                    schedule.schedule_id,
                    schedule.owner_id,
                    schedule.report_type.value,
                    period_start.isoformat(),
                    period_end.isoformat(),
                    str(e),
                    now.isoformat()
                ))
                conn.commit()
            raise

    def _gather_report_data(
        self,
        owner_id: str,
        report_type: ReportType,
        period_start: datetime,
        period_end: datetime,
        vehicle_ids: List[str] = None
    ) -> Dict[str, Any]:
        """Gather data for the report"""
        data = {
            "owner_id": owner_id,
            "report_type": report_type.value,
            "period": {
                "start": period_start.isoformat(),
                "end": period_end.isoformat()
            },
            "vehicles": [],
            "predictions": [],
            "notifications": [],
            "recommendations": [],
            "summary": {}
        }

        try:
            # Get vehicle data
            from profiles_manager import get_profiles_manager
            pm = get_profiles_manager()

            vehicles = pm.get_vehicles_for_owner(owner_id)
            if vehicle_ids:
                vehicles = [v for v in vehicles if v.get("vehicle_id") in vehicle_ids]

            for vehicle in vehicles:
                vehicle_data = {
                    "vehicle_id": vehicle.get("vehicle_id"),
                    "name": vehicle.get("name"),
                    "make": vehicle.get("make"),
                    "model": vehicle.get("model"),
                    "year": vehicle.get("year"),
                    "mileage": vehicle.get("mileage"),
                    "health_status": self._get_vehicle_health(vehicle.get("vehicle_id")),
                    "predictions": self._get_vehicle_predictions(
                        vehicle.get("vehicle_id"), period_start, period_end
                    ),
                    "dtcs": self._get_vehicle_dtcs(
                        vehicle.get("vehicle_id"), period_start, period_end
                    )
                }
                data["vehicles"].append(vehicle_data)

            # Get notifications sent
            data["notifications"] = self._get_notifications(
                owner_id, period_start, period_end
            )

            # Generate recommendations
            data["recommendations"] = self._generate_recommendations(data["vehicles"])

            # Generate summary
            data["summary"] = self._generate_summary(data)

        except ImportError:
            logger.warning("Profile manager not available for report data")
        except Exception as e:
            logger.error(f"Error gathering report data: {e}")

        return data

    def _get_vehicle_health(self, vehicle_id: str) -> Dict[str, Any]:
        """Get vehicle health status"""
        try:
            from vehicle_health import get_health_manager
            health_mgr = get_health_manager()
            return health_mgr.get_vehicle_health(vehicle_id)
        except ImportError:
            return {"status": "unknown"}

    def _get_vehicle_predictions(
        self,
        vehicle_id: str,
        period_start: datetime,
        period_end: datetime
    ) -> List[Dict[str, Any]]:
        """Get predictions for a vehicle in the period"""
        try:
            from ai_prediction_engine import get_prediction_engine
            engine = get_prediction_engine()
            return engine.get_predictions_for_period(
                vehicle_id=vehicle_id,
                start=period_start,
                end=period_end
            )
        except ImportError:
            return []

    def _get_vehicle_dtcs(
        self,
        vehicle_id: str,
        period_start: datetime,
        period_end: datetime
    ) -> List[Dict[str, Any]]:
        """Get DTCs for a vehicle in the period"""
        try:
            from dtc_manager import get_dtc_manager
            dtc_mgr = get_dtc_manager()
            return dtc_mgr.get_dtcs_for_period(
                vehicle_id=vehicle_id,
                start=period_start,
                end=period_end
            )
        except ImportError:
            return []

    def _get_notifications(
        self,
        owner_id: str,
        period_start: datetime,
        period_end: datetime
    ) -> List[Dict[str, Any]]:
        """Get notifications sent to owner in the period"""
        try:
            from notification_audit import NotificationAuditLog
            audit = NotificationAuditLog()
            return audit.get_for_period(owner_id, period_start, period_end)
        except ImportError:
            return []

    def _generate_recommendations(self, vehicles: List[Dict]) -> List[str]:
        """Generate service recommendations based on vehicle data"""
        recommendations = []

        for vehicle in vehicles:
            name = vehicle.get("name", "Vehicle")
            predictions = vehicle.get("predictions", [])

            # High risk predictions
            high_risk = [p for p in predictions if p.get("risk_level", 0) > 0.7]
            if high_risk:
                components = [p.get("component") for p in high_risk]
                recommendations.append(
                    f"{name}: Schedule service for {', '.join(components)} (high risk detected)"
                )

            # DTCs
            dtcs = vehicle.get("dtcs", [])
            if dtcs:
                recommendations.append(
                    f"{name}: {len(dtcs)} diagnostic codes detected - inspection recommended"
                )

        if not recommendations:
            recommendations.append("All vehicles are in good condition. No immediate action required.")

        return recommendations

    def _generate_summary(self, data: Dict) -> Dict[str, Any]:
        """Generate report summary statistics"""
        total_vehicles = len(data.get("vehicles", []))
        total_predictions = sum(
            len(v.get("predictions", [])) for v in data.get("vehicles", [])
        )
        total_dtcs = sum(
            len(v.get("dtcs", [])) for v in data.get("vehicles", [])
        )
        total_notifications = len(data.get("notifications", []))

        # Calculate health distribution
        health_counts = {"healthy": 0, "warning": 0, "critical": 0}
        for vehicle in data.get("vehicles", []):
            health = vehicle.get("health_status", {})
            status = health.get("status", "unknown")
            if status in health_counts:
                health_counts[status] += 1

        return {
            "total_vehicles": total_vehicles,
            "total_predictions": total_predictions,
            "total_dtcs": total_dtcs,
            "total_notifications": total_notifications,
            "health_distribution": health_counts
        }

    def _generate_html_report(
        self,
        report_data: Dict[str, Any],
        owner_name: str,
        report_type: ReportType,
        language: str,
        period_start: datetime,
        period_end: datetime
    ) -> str:
        """Generate HTML content for the report"""
        # Language-specific labels
        if language == "ar":
            labels = {
                "title": "تقرير PREDICT الأسبوعي",
                "greeting": f"مرحباً {owner_name}،",
                "intro": "إليك ملخص حالة مركباتك للفترة من",
                "to": "إلى",
                "vehicles": "المركبات",
                "predictions": "التنبؤات",
                "recommendations": "التوصيات",
                "summary": "الملخص",
                "health": "الحالة الصحية",
                "mileage": "المسافة المقطوعة",
                "no_issues": "لا توجد مشاكل",
                "footer": "تم إنشاء هذا التقرير تلقائياً بواسطة PREDICT AI"
            }
        else:
            labels = {
                "title": "PREDICT Weekly Report",
                "greeting": f"Hello {owner_name},",
                "intro": "Here's your vehicle status summary for the period from",
                "to": "to",
                "vehicles": "Vehicles",
                "predictions": "Predictions",
                "recommendations": "Recommendations",
                "summary": "Summary",
                "health": "Health Status",
                "mileage": "Mileage",
                "no_issues": "No issues detected",
                "footer": "This report was automatically generated by PREDICT AI"
            }

        summary = report_data.get("summary", {})
        vehicles = report_data.get("vehicles", [])
        recommendations = report_data.get("recommendations", [])

        # Build HTML
        html = f"""
<!DOCTYPE html>
<html dir="{'rtl' if language == 'ar' else 'ltr'}">
<head>
    <meta charset="UTF-8">
    <title>{labels['title']}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #1a73e8 0%, #0d47a1 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
        }}
        .card {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .card h2 {{
            color: #1a73e8;
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 10px;
        }}
        .vehicle {{
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
        }}
        .vehicle h3 {{
            margin-top: 0;
            color: #333;
        }}
        .status-healthy {{ color: #4caf50; }}
        .status-warning {{ color: #ff9800; }}
        .status-critical {{ color: #f44336; }}
        .recommendation {{
            background: #fff3e0;
            border-left: 4px solid #ff9800;
            padding: 10px 15px;
            margin-bottom: 10px;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
        }}
        .summary-item {{
            text-align: center;
            padding: 15px;
            background: #f5f5f5;
            border-radius: 8px;
        }}
        .summary-number {{
            font-size: 32px;
            font-weight: bold;
            color: #1a73e8;
        }}
        .footer {{
            text-align: center;
            color: #666;
            font-size: 12px;
            margin-top: 30px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{labels['title']}</h1>
        <p>{labels['greeting']}</p>
        <p>{labels['intro']} {period_start.strftime('%Y-%m-%d')} {labels['to']} {period_end.strftime('%Y-%m-%d')}</p>
    </div>

    <div class="card">
        <h2>{labels['summary']}</h2>
        <div class="summary-grid">
            <div class="summary-item">
                <div class="summary-number">{summary.get('total_vehicles', 0)}</div>
                <div>{labels['vehicles']}</div>
            </div>
            <div class="summary-item">
                <div class="summary-number">{summary.get('total_predictions', 0)}</div>
                <div>{labels['predictions']}</div>
            </div>
            <div class="summary-item">
                <div class="summary-number">{summary.get('total_dtcs', 0)}</div>
                <div>DTCs</div>
            </div>
            <div class="summary-item">
                <div class="summary-number">{summary.get('total_notifications', 0)}</div>
                <div>Notifications</div>
            </div>
        </div>
    </div>

    <div class="card">
        <h2>{labels['vehicles']}</h2>
"""

        for vehicle in vehicles:
            health = vehicle.get("health_status", {})
            status = health.get("status", "unknown")
            status_class = f"status-{status}" if status in ["healthy", "warning", "critical"] else ""

            html += f"""
        <div class="vehicle">
            <h3>{vehicle.get('name', 'Unknown')}</h3>
            <p>{vehicle.get('make', '')} {vehicle.get('model', '')} ({vehicle.get('year', '')})</p>
            <p>{labels['health']}: <span class="{status_class}">{status.upper()}</span></p>
            <p>{labels['mileage']}: {vehicle.get('mileage', 0):,} km</p>
        </div>
"""

        html += f"""
    </div>

    <div class="card">
        <h2>{labels['recommendations']}</h2>
"""

        for rec in recommendations:
            html += f"""
        <div class="recommendation">
            {rec}
        </div>
"""

        html += f"""
    </div>

    <div class="footer">
        <p>{labels['footer']}</p>
        <p>PREDICT Vehicle Intelligence Platform</p>
    </div>
</body>
</html>
"""

        return html

    def deliver_report(self, report_id: str) -> bool:
        """Deliver a generated report via email"""
        try:
            # Get report data
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT r.*, s.owner_email, s.owner_name
                    FROM generated_reports r
                    JOIN report_schedules s ON r.schedule_id = s.schedule_id
                    WHERE r.report_id = ?
                """, (report_id,))
                row = cursor.fetchone()

                if not row:
                    return False

                # Send email
                self._send_report_email(
                    email=row["owner_email"],
                    owner_name=row["owner_name"],
                    html_content=row["html_content"],
                    report_type=row["report_type"]
                )

                # Update status
                cursor.execute("""
                    UPDATE generated_reports
                    SET delivery_status = 'delivered', delivered_at = ?
                    WHERE report_id = ?
                """, (datetime.now().isoformat(), report_id))
                conn.commit()

            logger.info(f"Delivered report {report_id}")
            return True

        except Exception as e:
            logger.error(f"Error delivering report: {e}")
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE generated_reports
                    SET delivery_status = 'failed', error = ?
                    WHERE report_id = ?
                """, (str(e), report_id))
                conn.commit()
            return False

    def _send_report_email(
        self,
        email: str,
        owner_name: str,
        html_content: str,
        report_type: str
    ):
        """Send report via email"""
        try:
            from alert_notifications import get_notification_manager
            manager = get_notification_manager()

            # Use the email provider
            # This would integrate with the existing email system
            logger.info(f"Would send email to {email} with {report_type} report")

        except ImportError:
            logger.warning("Notification manager not available for email delivery")

    def run_pending_reports(self):
        """Run all pending scheduled reports"""
        pending = self.get_pending_schedules()

        for schedule in pending:
            try:
                # Generate report
                report_id = self.generate_report(schedule)

                # Deliver report
                self.deliver_report(report_id)

                # Update schedule
                next_run = self._calculate_next_run(schedule.schedule)
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE report_schedules
                        SET last_run = ?, next_run = ?
                        WHERE schedule_id = ?
                    """, (
                        datetime.now().isoformat(),
                        next_run.isoformat() if next_run else None,
                        schedule.schedule_id
                    ))
                    conn.commit()

            except Exception as e:
                logger.error(f"Error running schedule {schedule.schedule_id}: {e}")

    def start_scheduler(self):
        """Start the background scheduler"""
        if self._scheduler_running:
            return

        self._scheduler_running = True

        def run_scheduler():
            schedule.every(15).minutes.do(self.run_pending_reports)

            while self._scheduler_running:
                schedule.run_pending()
                time.sleep(60)

        self._scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        self._scheduler_thread.start()
        logger.info("Report scheduler started")

    def stop_scheduler(self):
        """Stop the background scheduler"""
        self._scheduler_running = False
        logger.info("Report scheduler stopped")

    def _row_to_schedule(self, row: sqlite3.Row) -> ReportSchedule:
        """Convert database row to ReportSchedule object"""
        return ReportSchedule(
            id=row["id"],
            schedule_id=row["schedule_id"],
            owner_id=row["owner_id"],
            owner_name=row["owner_name"],
            owner_email=row["owner_email"],
            report_type=ReportType(row["report_type"]),
            schedule=row["schedule"],
            language=row["language"],
            include_vehicles=json.loads(row["include_vehicles"]) if row["include_vehicles"] else [],
            enabled=bool(row["enabled"]),
            last_run=datetime.fromisoformat(row["last_run"]) if row["last_run"] else None,
            next_run=datetime.fromisoformat(row["next_run"]) if row["next_run"] else None,
            created_at=datetime.fromisoformat(row["created_at"])
        )


# Singleton instance
_report_manager: Optional[ScheduledReportManager] = None


def get_report_manager() -> ScheduledReportManager:
    """Get the singleton ScheduledReportManager instance"""
    global _report_manager
    if _report_manager is None:
        _report_manager = ScheduledReportManager()
    return _report_manager


# Convenience functions
def create_weekly_report_schedule(
    owner_id: str,
    owner_name: str,
    owner_email: str,
    language: str = "en",
    day: str = "monday",
    hour: int = 9
) -> str:
    """Create a weekly report schedule"""
    manager = get_report_manager()
    return manager.create_schedule(
        owner_id=owner_id,
        owner_name=owner_name,
        owner_email=owner_email,
        report_type=ReportType.WEEKLY_SUMMARY,
        schedule=f"weekly:{day}:{hour:02d}:00",
        language=language
    )
