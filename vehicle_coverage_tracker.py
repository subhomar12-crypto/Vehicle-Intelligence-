"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Vehicle Coverage Tracker

Vehicle Coverage Tracker
========================
Tracks and documents which vehicles are covered by the AI model.
Critical for transparency about model limitations.

This module:
1. Tracks all vehicles in training data
2. Documents coverage by make/model/year
3. Identifies unsupported vehicles
4. Generates coverage reports for users
5. Provides warnings when predicting on unsupported vehicles
"""

import sqlite3
import json
import logging
from typing import Dict, Any, Optional, List, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum
import hashlib

logger = logging.getLogger(__name__)


# =============================================================================
# COVERAGE LEVELS
# =============================================================================

class CoverageLevel(Enum):
    """Level of model coverage for a vehicle."""
    FULL = "full"                  # Extensively tested, high confidence
    PARTIAL = "partial"            # Some data, moderate confidence
    MINIMAL = "minimal"            # Very limited data
    UNSUPPORTED = "unsupported"    # No training data
    UNKNOWN = "unknown"            # Cannot determine


# Coverage thresholds (number of training samples)
COVERAGE_THRESHOLDS = {
    CoverageLevel.FULL: 500,       # 500+ samples = full coverage
    CoverageLevel.PARTIAL: 100,    # 100-499 samples = partial
    CoverageLevel.MINIMAL: 10,     # 10-99 samples = minimal
    CoverageLevel.UNSUPPORTED: 0,  # <10 samples = unsupported
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class VehicleInfo:
    """Information about a specific vehicle type."""
    make: str
    model: str
    year_start: int
    year_end: int
    engine_types: List[str] = field(default_factory=list)
    transmission_types: List[str] = field(default_factory=list)


@dataclass
class VehicleCoverage:
    """Coverage information for a vehicle type."""
    vehicle_id: str  # Hash of make+model+year_range
    make: str
    model: str
    year_start: int
    year_end: int
    coverage_level: CoverageLevel
    sample_count: int
    failure_count: int
    last_updated: str
    notes: str = ""
    accuracy_on_vehicle: Optional[float] = None
    known_issues: List[str] = field(default_factory=list)


@dataclass
class CoverageWarning:
    """Warning about coverage limitations."""
    warning_type: str
    severity: str  # 'critical', 'warning', 'info'
    message: str
    recommendation: str


@dataclass
class CoverageReport:
    """Complete coverage report."""
    report_id: str
    generated_at: str
    total_vehicles: int
    coverage_by_level: Dict[str, int]
    coverage_by_make: Dict[str, Dict[str, Any]]
    warnings: List[CoverageWarning]
    summary: Dict[str, Any]


# =============================================================================
# VEHICLE COVERAGE TRACKER
# =============================================================================

class VehicleCoverageTracker:
    """
    Tracks and reports vehicle coverage for the AI model.

    CRITICAL: Users must be informed when their vehicle has limited
    or no coverage. Predictions on unsupported vehicles should carry
    prominent warnings.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize coverage tracker."""
        self.db_path = db_path or Path("ai_data/vehicle_coverage.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_database()

        # Cache for quick lookups
        self._coverage_cache: Dict[str, VehicleCoverage] = {}

        logger.info("Vehicle Coverage Tracker initialized")

    def _init_database(self):
        """Initialize SQLite database."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vehicle_coverage (
                vehicle_id TEXT PRIMARY KEY,
                make TEXT NOT NULL,
                model TEXT NOT NULL,
                year_start INTEGER NOT NULL,
                year_end INTEGER NOT NULL,
                coverage_level TEXT NOT NULL,
                sample_count INTEGER NOT NULL DEFAULT 0,
                failure_count INTEGER NOT NULL DEFAULT 0,
                last_updated TEXT NOT NULL,
                notes TEXT,
                accuracy_on_vehicle REAL,
                known_issues TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_vehicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vin_hash TEXT,
                make TEXT NOT NULL,
                model TEXT NOT NULL,
                year INTEGER NOT NULL,
                engine_type TEXT,
                transmission_type TEXT,
                sample_count INTEGER NOT NULL DEFAULT 1,
                failure_count INTEGER NOT NULL DEFAULT 0,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS coverage_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                vehicle_id TEXT,
                details TEXT
            )
        """)

        conn.commit()
        conn.close()

    def register_training_vehicle(
        self,
        make: str,
        model: str,
        year: int,
        sample_count: int = 1,
        failure_count: int = 0,
        vin_hash: Optional[str] = None,
        engine_type: Optional[str] = None,
        transmission_type: Optional[str] = None
    ):
        """
        Register a vehicle used in training data.

        Args:
            make: Vehicle make (e.g., "Toyota")
            model: Vehicle model (e.g., "Camry")
            year: Model year
            sample_count: Number of samples from this vehicle
            failure_count: Number of failure samples
            vin_hash: Hash of VIN for unique identification
            engine_type: Engine type if known
            transmission_type: Transmission type if known
        """
        make = make.strip().upper()
        model = model.strip().upper()

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        # Check if vehicle exists
        cursor.execute("""
            SELECT id, sample_count, failure_count FROM training_vehicles
            WHERE make = ? AND model = ? AND year = ?
        """, (make, model, year))

        existing = cursor.fetchone()

        if existing:
            # Update existing
            cursor.execute("""
                UPDATE training_vehicles
                SET sample_count = sample_count + ?,
                    failure_count = failure_count + ?,
                    last_seen = ?
                WHERE id = ?
            """, (sample_count, failure_count, now, existing[0]))
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO training_vehicles
                (vin_hash, make, model, year, engine_type, transmission_type,
                 sample_count, failure_count, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (vin_hash, make, model, year, engine_type, transmission_type,
                  sample_count, failure_count, now, now))

        conn.commit()
        conn.close()

        # Update coverage summary
        self._update_coverage_summary(make, model)

    def _update_coverage_summary(self, make: str, model: str):
        """Update coverage summary for a make/model."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Get aggregate data for this make/model
        cursor.execute("""
            SELECT MIN(year), MAX(year), SUM(sample_count), SUM(failure_count)
            FROM training_vehicles
            WHERE make = ? AND model = ?
        """, (make, model))

        row = cursor.fetchone()
        if not row or row[0] is None:
            conn.close()
            return

        year_start, year_end, total_samples, total_failures = row

        # Determine coverage level
        coverage_level = self._determine_coverage_level(total_samples)

        # Create vehicle ID
        vehicle_id = self._make_vehicle_id(make, model, year_start, year_end)

        now = datetime.now().isoformat()

        # Update or insert coverage
        cursor.execute("""
            INSERT OR REPLACE INTO vehicle_coverage
            (vehicle_id, make, model, year_start, year_end, coverage_level,
             sample_count, failure_count, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (vehicle_id, make, model, year_start, year_end,
              coverage_level.value, total_samples, total_failures, now))

        conn.commit()
        conn.close()

        # Invalidate cache
        self._coverage_cache.pop(vehicle_id, None)

    def _determine_coverage_level(self, sample_count: int) -> CoverageLevel:
        """Determine coverage level based on sample count."""
        if sample_count >= COVERAGE_THRESHOLDS[CoverageLevel.FULL]:
            return CoverageLevel.FULL
        elif sample_count >= COVERAGE_THRESHOLDS[CoverageLevel.PARTIAL]:
            return CoverageLevel.PARTIAL
        elif sample_count >= COVERAGE_THRESHOLDS[CoverageLevel.MINIMAL]:
            return CoverageLevel.MINIMAL
        else:
            return CoverageLevel.UNSUPPORTED

    def _make_vehicle_id(self, make: str, model: str, year_start: int, year_end: int) -> str:
        """Create unique vehicle ID."""
        key = f"{make}:{model}:{year_start}:{year_end}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def get_coverage(
        self,
        make: str,
        model: str,
        year: int
    ) -> Tuple[CoverageLevel, VehicleCoverage, List[CoverageWarning]]:
        """
        Get coverage information for a specific vehicle.

        Args:
            make: Vehicle make
            model: Vehicle model
            year: Model year

        Returns:
            Tuple of (coverage_level, coverage_info, warnings)
        """
        make = make.strip().upper()
        model = model.strip().upper()

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Find matching coverage
        cursor.execute("""
            SELECT * FROM vehicle_coverage
            WHERE make = ? AND model = ? AND ? BETWEEN year_start AND year_end
        """, (make, model, year))

        row = cursor.fetchone()
        conn.close()

        warnings = []

        if row:
            coverage = VehicleCoverage(
                vehicle_id=row[0],
                make=row[1],
                model=row[2],
                year_start=row[3],
                year_end=row[4],
                coverage_level=CoverageLevel(row[5]),
                sample_count=row[6],
                failure_count=row[7],
                last_updated=row[8],
                notes=row[9] or "",
                accuracy_on_vehicle=row[10],
                known_issues=json.loads(row[11]) if row[11] else []
            )

            # Generate warnings based on coverage level
            if coverage.coverage_level == CoverageLevel.MINIMAL:
                warnings.append(CoverageWarning(
                    warning_type="limited_coverage",
                    severity="warning",
                    message=f"Limited training data for {make} {model} ({coverage.sample_count} samples)",
                    recommendation="Predictions should be verified by a professional"
                ))
            elif coverage.coverage_level == CoverageLevel.PARTIAL:
                warnings.append(CoverageWarning(
                    warning_type="partial_coverage",
                    severity="info",
                    message=f"Moderate training data for {make} {model} ({coverage.sample_count} samples)",
                    recommendation="Consider professional verification for critical predictions"
                ))

            return coverage.coverage_level, coverage, warnings
        else:
            # No coverage found
            coverage = VehicleCoverage(
                vehicle_id="",
                make=make,
                model=model,
                year_start=year,
                year_end=year,
                coverage_level=CoverageLevel.UNSUPPORTED,
                sample_count=0,
                failure_count=0,
                last_updated=datetime.now().isoformat(),
                notes="No training data available"
            )

            warnings.append(CoverageWarning(
                warning_type="unsupported_vehicle",
                severity="critical",
                message=f"NO training data for {year} {make} {model}",
                recommendation="Predictions may be unreliable. Professional inspection strongly recommended."
            ))

            return CoverageLevel.UNSUPPORTED, coverage, warnings

    def check_prediction_coverage(
        self,
        make: str,
        model: str,
        year: int
    ) -> Dict[str, Any]:
        """
        Check coverage before making a prediction.

        Returns a dict with coverage info and mandatory warnings.
        """
        level, coverage, warnings = self.get_coverage(make, model, year)

        result = {
            'coverage_level': level.value,
            'sample_count': coverage.sample_count,
            'is_supported': level not in [CoverageLevel.UNSUPPORTED, CoverageLevel.UNKNOWN],
            'confidence_modifier': self._get_confidence_modifier(level),
            'warnings': [
                {
                    'type': w.warning_type,
                    'severity': w.severity,
                    'message': w.message,
                    'recommendation': w.recommendation
                }
                for w in warnings
            ],
            'must_display_warning': level in [CoverageLevel.UNSUPPORTED, CoverageLevel.MINIMAL],
            'disclaimer': self._get_coverage_disclaimer(level, make, model, year)
        }

        return result

    def _get_confidence_modifier(self, level: CoverageLevel) -> float:
        """Get confidence modifier based on coverage level."""
        modifiers = {
            CoverageLevel.FULL: 1.0,
            CoverageLevel.PARTIAL: 0.85,
            CoverageLevel.MINIMAL: 0.6,
            CoverageLevel.UNSUPPORTED: 0.3,
            CoverageLevel.UNKNOWN: 0.4,
        }
        return modifiers.get(level, 0.5)

    def _get_coverage_disclaimer(
        self,
        level: CoverageLevel,
        make: str,
        model: str,
        year: int
    ) -> str:
        """Get mandatory disclaimer text based on coverage."""
        if level == CoverageLevel.UNSUPPORTED:
            return (
                f"⚠️ WARNING: The {year} {make} {model} is NOT in our training database. "
                f"Predictions for this vehicle are based on general patterns and may not be accurate. "
                f"Professional inspection is STRONGLY RECOMMENDED before taking any action."
            )
        elif level == CoverageLevel.MINIMAL:
            return (
                f"⚠️ NOTICE: Limited data available for {year} {make} {model}. "
                f"Prediction confidence is reduced. Verify with a qualified technician."
            )
        elif level == CoverageLevel.PARTIAL:
            return (
                f"ℹ️ This vehicle has moderate coverage in our training data. "
                f"For safety-critical predictions, professional verification is recommended."
            )
        else:
            return ""

    def generate_coverage_report(self) -> CoverageReport:
        """Generate comprehensive coverage report."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Get all coverage data
        cursor.execute("SELECT * FROM vehicle_coverage ORDER BY make, model")
        rows = cursor.fetchall()

        # Count by level
        coverage_by_level = {level.value: 0 for level in CoverageLevel}
        coverage_by_make: Dict[str, Dict[str, Any]] = {}

        for row in rows:
            level = row[5]
            coverage_by_level[level] = coverage_by_level.get(level, 0) + 1

            make = row[1]
            if make not in coverage_by_make:
                coverage_by_make[make] = {
                    'total_models': 0,
                    'total_samples': 0,
                    'models': []
                }

            coverage_by_make[make]['total_models'] += 1
            coverage_by_make[make]['total_samples'] += row[6]
            coverage_by_make[make]['models'].append({
                'model': row[2],
                'years': f"{row[3]}-{row[4]}",
                'level': row[5],
                'samples': row[6]
            })

        conn.close()

        # Generate warnings
        warnings = []
        if coverage_by_level.get(CoverageLevel.UNSUPPORTED.value, 0) > 0:
            warnings.append(CoverageWarning(
                warning_type="unsupported_vehicles_exist",
                severity="info",
                message=f"{coverage_by_level[CoverageLevel.UNSUPPORTED.value]} vehicle types have insufficient coverage",
                recommendation="Consider expanding training data"
            ))

        # Summary
        total_vehicles = len(rows)
        total_samples = sum(r[6] for r in rows)
        avg_samples = total_samples / total_vehicles if total_vehicles > 0 else 0

        summary = {
            'total_vehicle_types': total_vehicles,
            'total_training_samples': total_samples,
            'average_samples_per_type': round(avg_samples, 1),
            'makes_covered': len(coverage_by_make),
            'fully_supported': coverage_by_level.get(CoverageLevel.FULL.value, 0),
            'partially_supported': coverage_by_level.get(CoverageLevel.PARTIAL.value, 0),
        }

        report = CoverageReport(
            report_id=f"cov_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            generated_at=datetime.now().isoformat(),
            total_vehicles=total_vehicles,
            coverage_by_level=coverage_by_level,
            coverage_by_make=coverage_by_make,
            warnings=warnings,
            summary=summary
        )

        return report

    def get_supported_vehicles_list(self) -> List[Dict[str, Any]]:
        """Get list of all supported vehicles for documentation."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT make, model, year_start, year_end, coverage_level, sample_count
            FROM vehicle_coverage
            WHERE coverage_level IN ('full', 'partial')
            ORDER BY make, model, year_start
        """)

        rows = cursor.fetchall()
        conn.close()

        vehicles = []
        for row in rows:
            vehicles.append({
                'make': row[0],
                'model': row[1],
                'years': f"{row[2]}-{row[3]}" if row[2] != row[3] else str(row[2]),
                'coverage': row[4],
                'samples': row[5]
            })

        return vehicles

    def export_coverage_documentation(self, output_path: Path) -> Path:
        """Export coverage documentation to markdown file."""
        report = self.generate_coverage_report()
        vehicles = self.get_supported_vehicles_list()

        content = f"""# Vehicle Coverage Documentation

Generated: {report.generated_at}

## Summary

- **Total Vehicle Types**: {report.summary['total_vehicle_types']}
- **Total Training Samples**: {report.summary['total_training_samples']:,}
- **Makes Covered**: {report.summary['makes_covered']}
- **Fully Supported**: {report.summary['fully_supported']}
- **Partially Supported**: {report.summary['partially_supported']}

## Coverage Levels Explained

| Level | Description | Sample Count | Confidence |
|-------|-------------|--------------|------------|
| Full | Extensively tested | 500+ samples | High |
| Partial | Moderate data | 100-499 samples | Moderate |
| Minimal | Limited data | 10-99 samples | Low |
| Unsupported | No data | <10 samples | Very Low |

## Supported Vehicles

| Make | Model | Years | Coverage | Samples |
|------|-------|-------|----------|---------|
"""

        for v in vehicles:
            content += f"| {v['make']} | {v['model']} | {v['years']} | {v['coverage']} | {v['samples']:,} |\n"

        content += """

## Important Notes

1. **Unsupported Vehicles**: If your vehicle is not listed above, predictions may be unreliable.
2. **Year Ranges**: Coverage applies to the listed year range. Newer models may not be covered.
3. **Verification**: Always verify predictions with a qualified automotive technician.
4. **Updates**: This documentation is updated when the model is retrained.

## Disclaimer

This AI system is trained on historical data from the vehicles listed above.
Predictions for unlisted vehicles are extrapolated and should be treated with caution.
Professional inspection is recommended for all safety-critical decisions.
"""

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(content)

        logger.info(f"Coverage documentation exported to {output_path}")

        return output_path


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_tracker_instance: Optional[VehicleCoverageTracker] = None


def get_coverage_tracker() -> VehicleCoverageTracker:
    """Get or create singleton tracker instance."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = VehicleCoverageTracker()
    return _tracker_instance


def check_vehicle_coverage(make: str, model: str, year: int) -> Dict[str, Any]:
    """Convenience function to check vehicle coverage."""
    tracker = get_coverage_tracker()
    return tracker.check_prediction_coverage(make, model, year)


def register_training_vehicle(
    make: str,
    model: str,
    year: int,
    sample_count: int = 1,
    failure_count: int = 0
):
    """Convenience function to register a training vehicle."""
    tracker = get_coverage_tracker()
    tracker.register_training_vehicle(make, model, year, sample_count, failure_count)
