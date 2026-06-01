"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Data Provenance Tracker

Data Provenance Tracker
========================
Tracks the lineage and provenance of all training data.
Essential for understanding model behavior and debugging predictions.

This module provides:
1. Data source tracking
2. Transformation history
3. Quality annotations
4. Lineage visualization
5. Audit trail for data changes
"""

import sqlite3
import hashlib
import json
import logging
from typing import Dict, Any, Optional, List, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


# =============================================================================
# PROVENANCE TYPES
# =============================================================================

class DataSourceType(Enum):
    """Types of data sources."""
    OBD_DEVICE = "obd_device"              # Direct OBD-II connection
    UPLOADED_FILE = "uploaded_file"         # User uploaded data
    SYNTHETIC = "synthetic"                 # Synthetically generated
    AUGMENTED = "augmented"                 # Augmented from real data
    EXTERNAL_API = "external_api"           # From external service
    MANUAL_ENTRY = "manual_entry"           # Manually entered
    IMPORTED = "imported"                   # Imported from other system


class TransformationType(Enum):
    """Types of data transformations."""
    NORMALIZATION = "normalization"
    FEATURE_ENGINEERING = "feature_engineering"
    MISSING_VALUE_IMPUTATION = "missing_value_imputation"
    OUTLIER_REMOVAL = "outlier_removal"
    RESAMPLING = "resampling"
    AGGREGATION = "aggregation"
    FILTERING = "filtering"
    AUGMENTATION = "augmentation"
    LABELING = "labeling"
    VALIDATION = "validation"


class DataQualityLevel(Enum):
    """Quality levels for data."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"
    SUSPECT = "suspect"


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class DataSource:
    """Information about a data source."""
    source_id: str
    source_type: DataSourceType
    source_name: str
    source_description: str
    created_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    vehicle_info: Optional[Dict[str, str]] = None
    quality_level: DataQualityLevel = DataQualityLevel.UNKNOWN
    sample_count: int = 0


@dataclass
class DataTransformation:
    """Record of a data transformation."""
    transformation_id: str
    transformation_type: TransformationType
    input_data_ids: List[str]
    output_data_id: str
    transformation_params: Dict[str, Any]
    timestamp: str
    description: str
    reversible: bool = False
    validation_status: str = "pending"


@dataclass
class DataLineage:
    """Complete lineage for a data point or dataset."""
    data_id: str
    data_hash: str
    source: DataSource
    transformations: List[DataTransformation]
    created_at: str
    last_modified: str
    quality_annotations: List[Dict[str, Any]]
    usage_history: List[Dict[str, Any]]


@dataclass
class ProvenanceReport:
    """Report on data provenance for a model or prediction."""
    report_id: str
    generated_at: str
    entity_id: str
    entity_type: str
    sources_used: List[DataSource]
    transformation_chain: List[DataTransformation]
    quality_summary: Dict[str, Any]
    lineage_depth: int
    warnings: List[str]


# =============================================================================
# DATA PROVENANCE TRACKER
# =============================================================================

class DataProvenanceTracker:
    """
    Tracks the complete provenance of all training data.

    This system ensures:
    1. All data can be traced to its source
    2. All transformations are documented
    3. Quality issues are annotated
    4. Lineage can be reconstructed for any prediction
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize provenance tracker."""
        self.db_path = db_path or Path("ai_data/provenance.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_database()

        logger.info("Data Provenance Tracker initialized")

    def _init_database(self):
        """Initialize SQLite database."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Data sources table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS data_sources (
                source_id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_description TEXT,
                created_at TEXT NOT NULL,
                metadata TEXT,
                vehicle_info TEXT,
                quality_level TEXT NOT NULL DEFAULT 'unknown',
                sample_count INTEGER DEFAULT 0
            )
        """)

        # Data records table (tracks individual data points/batches)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS data_records (
                data_id TEXT PRIMARY KEY,
                data_hash TEXT NOT NULL,
                source_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_modified TEXT NOT NULL,
                record_type TEXT NOT NULL,
                sample_count INTEGER DEFAULT 1,
                metadata TEXT,
                FOREIGN KEY (source_id) REFERENCES data_sources(source_id)
            )
        """)

        # Transformations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transformations (
                transformation_id TEXT PRIMARY KEY,
                transformation_type TEXT NOT NULL,
                input_data_ids TEXT NOT NULL,
                output_data_id TEXT NOT NULL,
                transformation_params TEXT,
                timestamp TEXT NOT NULL,
                description TEXT,
                reversible INTEGER DEFAULT 0,
                validation_status TEXT DEFAULT 'pending'
            )
        """)

        # Quality annotations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quality_annotations (
                annotation_id TEXT PRIMARY KEY,
                data_id TEXT NOT NULL,
                annotation_type TEXT NOT NULL,
                annotation_value TEXT NOT NULL,
                annotated_by TEXT,
                timestamp TEXT NOT NULL,
                metadata TEXT,
                FOREIGN KEY (data_id) REFERENCES data_records(data_id)
            )
        """)

        # Usage history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usage_history (
                usage_id TEXT PRIMARY KEY,
                data_id TEXT NOT NULL,
                usage_type TEXT NOT NULL,
                model_id TEXT,
                prediction_id TEXT,
                timestamp TEXT NOT NULL,
                details TEXT,
                FOREIGN KEY (data_id) REFERENCES data_records(data_id)
            )
        """)

        # Lineage cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lineage_cache (
                cache_id TEXT PRIMARY KEY,
                data_id TEXT NOT NULL,
                lineage_json TEXT NOT NULL,
                computed_at TEXT NOT NULL,
                valid_until TEXT
            )
        """)

        conn.commit()
        conn.close()

    def register_source(
        self,
        source_type: DataSourceType,
        source_name: str,
        source_description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        vehicle_info: Optional[Dict[str, str]] = None,
        quality_level: DataQualityLevel = DataQualityLevel.UNKNOWN
    ) -> DataSource:
        """
        Register a new data source.

        Args:
            source_type: Type of data source
            source_name: Name/identifier for the source
            source_description: Description of the source
            metadata: Additional metadata
            vehicle_info: Vehicle information if applicable
            quality_level: Initial quality assessment

        Returns:
            DataSource record
        """
        source_id = str(uuid.uuid4())

        source = DataSource(
            source_id=source_id,
            source_type=source_type,
            source_name=source_name,
            source_description=source_description,
            created_at=datetime.now().isoformat(),
            metadata=metadata or {},
            vehicle_info=vehicle_info,
            quality_level=quality_level,
            sample_count=0
        )

        self._save_source(source)

        logger.info(f"Registered data source {source_id}: {source_name}")

        return source

    def record_data(
        self,
        source_id: str,
        data_hash: str,
        record_type: str,
        sample_count: int = 1,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Record a new data entry.

        Args:
            source_id: ID of the data source
            data_hash: Hash of the data for integrity
            record_type: Type of record (e.g., 'training_batch', 'single_reading')
            sample_count: Number of samples in this record
            metadata: Additional metadata

        Returns:
            data_id of the new record
        """
        data_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO data_records
            (data_id, data_hash, source_id, created_at, last_modified,
             record_type, sample_count, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data_id,
            data_hash,
            source_id,
            now,
            now,
            record_type,
            sample_count,
            json.dumps(metadata or {})
        ))

        # Update source sample count
        cursor.execute("""
            UPDATE data_sources
            SET sample_count = sample_count + ?
            WHERE source_id = ?
        """, (sample_count, source_id))

        conn.commit()
        conn.close()

        logger.debug(f"Recorded data {data_id} from source {source_id}")

        return data_id

    def record_transformation(
        self,
        transformation_type: TransformationType,
        input_data_ids: List[str],
        output_data_hash: str,
        output_record_type: str,
        params: Optional[Dict[str, Any]] = None,
        description: str = "",
        reversible: bool = False
    ) -> Tuple[str, str]:
        """
        Record a data transformation.

        Args:
            transformation_type: Type of transformation
            input_data_ids: IDs of input data records
            output_data_hash: Hash of output data
            output_record_type: Type of output record
            params: Transformation parameters
            description: Description of transformation
            reversible: Whether transformation is reversible

        Returns:
            Tuple of (transformation_id, output_data_id)
        """
        transformation_id = str(uuid.uuid4())
        output_data_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Get source from first input
        if input_data_ids:
            cursor.execute("""
                SELECT source_id FROM data_records WHERE data_id = ?
            """, (input_data_ids[0],))
            row = cursor.fetchone()
            source_id = row[0] if row else "transformation_output"
        else:
            source_id = "transformation_output"

        # Create output data record
        cursor.execute("""
            INSERT INTO data_records
            (data_id, data_hash, source_id, created_at, last_modified,
             record_type, sample_count, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            output_data_id,
            output_data_hash,
            source_id,
            now,
            now,
            output_record_type,
            0,  # Will be updated
            json.dumps({'transformation_id': transformation_id})
        ))

        # Create transformation record
        cursor.execute("""
            INSERT INTO transformations
            (transformation_id, transformation_type, input_data_ids, output_data_id,
             transformation_params, timestamp, description, reversible, validation_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            transformation_id,
            transformation_type.value,
            json.dumps(input_data_ids),
            output_data_id,
            json.dumps(params or {}),
            now,
            description,
            1 if reversible else 0,
            'pending'
        ))

        conn.commit()
        conn.close()

        logger.info(f"Recorded transformation {transformation_id}: {transformation_type.value}")

        return transformation_id, output_data_id

    def add_quality_annotation(
        self,
        data_id: str,
        annotation_type: str,
        annotation_value: str,
        annotated_by: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add a quality annotation to a data record.

        Args:
            data_id: ID of data record
            annotation_type: Type of annotation (e.g., 'quality_issue', 'verified')
            annotation_value: Annotation content
            annotated_by: Who added the annotation
            metadata: Additional metadata

        Returns:
            annotation_id
        """
        annotation_id = str(uuid.uuid4())

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO quality_annotations
            (annotation_id, data_id, annotation_type, annotation_value,
             annotated_by, timestamp, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            annotation_id,
            data_id,
            annotation_type,
            annotation_value,
            annotated_by,
            datetime.now().isoformat(),
            json.dumps(metadata or {})
        ))

        conn.commit()
        conn.close()

        logger.debug(f"Added quality annotation {annotation_id} to data {data_id}")

        return annotation_id

    def record_usage(
        self,
        data_id: str,
        usage_type: str,
        model_id: Optional[str] = None,
        prediction_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Record data usage.

        Args:
            data_id: ID of data used
            usage_type: Type of usage (e.g., 'training', 'validation', 'prediction')
            model_id: ID of model if applicable
            prediction_id: ID of prediction if applicable
            details: Additional details

        Returns:
            usage_id
        """
        usage_id = str(uuid.uuid4())

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO usage_history
            (usage_id, data_id, usage_type, model_id, prediction_id, timestamp, details)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            usage_id,
            data_id,
            usage_type,
            model_id,
            prediction_id,
            datetime.now().isoformat(),
            json.dumps(details or {})
        ))

        conn.commit()
        conn.close()

        return usage_id

    def get_lineage(self, data_id: str, max_depth: int = 10) -> DataLineage:
        """
        Get complete lineage for a data record.

        Args:
            data_id: ID of data record
            max_depth: Maximum depth to traverse

        Returns:
            DataLineage object
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Get data record
        cursor.execute("""
            SELECT * FROM data_records WHERE data_id = ?
        """, (data_id,))
        data_row = cursor.fetchone()

        if not data_row:
            raise ValueError(f"Data record {data_id} not found")

        # Get source
        cursor.execute("""
            SELECT * FROM data_sources WHERE source_id = ?
        """, (data_row[2],))  # source_id
        source_row = cursor.fetchone()

        source = DataSource(
            source_id=source_row[0],
            source_type=DataSourceType(source_row[1]),
            source_name=source_row[2],
            source_description=source_row[3] or "",
            created_at=source_row[4],
            metadata=json.loads(source_row[5]) if source_row[5] else {},
            vehicle_info=json.loads(source_row[6]) if source_row[6] else None,
            quality_level=DataQualityLevel(source_row[7]),
            sample_count=source_row[8]
        )

        # Get transformation chain
        transformations = self._get_transformation_chain(cursor, data_id, max_depth)

        # Get quality annotations
        cursor.execute("""
            SELECT * FROM quality_annotations WHERE data_id = ?
        """, (data_id,))
        annotations = [
            {
                'annotation_id': row[0],
                'type': row[2],
                'value': row[3],
                'annotated_by': row[4],
                'timestamp': row[5]
            }
            for row in cursor.fetchall()
        ]

        # Get usage history
        cursor.execute("""
            SELECT * FROM usage_history WHERE data_id = ? ORDER BY timestamp DESC
        """, (data_id,))
        usage = [
            {
                'usage_id': row[0],
                'type': row[2],
                'model_id': row[3],
                'prediction_id': row[4],
                'timestamp': row[5]
            }
            for row in cursor.fetchall()
        ]

        conn.close()

        return DataLineage(
            data_id=data_id,
            data_hash=data_row[1],
            source=source,
            transformations=transformations,
            created_at=data_row[3],
            last_modified=data_row[4],
            quality_annotations=annotations,
            usage_history=usage
        )

    def _get_transformation_chain(
        self,
        cursor,
        data_id: str,
        max_depth: int
    ) -> List[DataTransformation]:
        """Get chain of transformations leading to this data."""
        transformations = []
        current_id = data_id
        depth = 0

        while depth < max_depth:
            cursor.execute("""
                SELECT * FROM transformations WHERE output_data_id = ?
            """, (current_id,))
            row = cursor.fetchone()

            if not row:
                break

            transformations.append(DataTransformation(
                transformation_id=row[0],
                transformation_type=TransformationType(row[1]),
                input_data_ids=json.loads(row[2]),
                output_data_id=row[3],
                transformation_params=json.loads(row[4]) if row[4] else {},
                timestamp=row[5],
                description=row[6] or "",
                reversible=bool(row[7]),
                validation_status=row[8]
            ))

            # Move to first input
            input_ids = json.loads(row[2])
            if input_ids:
                current_id = input_ids[0]
            else:
                break

            depth += 1

        return list(reversed(transformations))

    def generate_provenance_report(
        self,
        entity_id: str,
        entity_type: str
    ) -> ProvenanceReport:
        """
        Generate a provenance report for an entity (model or prediction).

        Args:
            entity_id: ID of the entity
            entity_type: Type of entity ('model' or 'prediction')

        Returns:
            ProvenanceReport
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Get all data used by this entity
        if entity_type == 'model':
            cursor.execute("""
                SELECT DISTINCT data_id FROM usage_history WHERE model_id = ?
            """, (entity_id,))
        else:
            cursor.execute("""
                SELECT DISTINCT data_id FROM usage_history WHERE prediction_id = ?
            """, (entity_id,))

        data_ids = [row[0] for row in cursor.fetchall()]
        conn.close()

        # Collect all sources
        sources_map: Dict[str, DataSource] = {}
        all_transformations: List[DataTransformation] = []
        warnings: List[str] = []
        max_depth = 0

        for data_id in data_ids:
            try:
                lineage = self.get_lineage(data_id)
                sources_map[lineage.source.source_id] = lineage.source
                all_transformations.extend(lineage.transformations)
                max_depth = max(max_depth, len(lineage.transformations))

                # Check for quality issues
                for annotation in lineage.quality_annotations:
                    if annotation['type'] == 'quality_issue':
                        warnings.append(f"Quality issue in source {lineage.source.source_name}: {annotation['value']}")

                if lineage.source.quality_level == DataQualityLevel.LOW:
                    warnings.append(f"Low quality data from source: {lineage.source.source_name}")
                elif lineage.source.quality_level == DataQualityLevel.SUSPECT:
                    warnings.append(f"Suspect data from source: {lineage.source.source_name}")

            except ValueError:
                warnings.append(f"Could not trace lineage for data {data_id}")

        # Quality summary
        quality_summary = {
            'total_sources': len(sources_map),
            'by_quality': {},
            'by_type': {}
        }

        for source in sources_map.values():
            ql = source.quality_level.value
            quality_summary['by_quality'][ql] = quality_summary['by_quality'].get(ql, 0) + 1

            st = source.source_type.value
            quality_summary['by_type'][st] = quality_summary['by_type'].get(st, 0) + 1

        report = ProvenanceReport(
            report_id=f"prov_{entity_type}_{entity_id[:8]}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            generated_at=datetime.now().isoformat(),
            entity_id=entity_id,
            entity_type=entity_type,
            sources_used=list(sources_map.values()),
            transformation_chain=all_transformations,
            quality_summary=quality_summary,
            lineage_depth=max_depth,
            warnings=warnings
        )

        logger.info(f"Generated provenance report for {entity_type} {entity_id}")

        return report

    def get_source_statistics(self) -> Dict[str, Any]:
        """Get statistics about data sources."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Count by type
        cursor.execute("""
            SELECT source_type, COUNT(*), SUM(sample_count)
            FROM data_sources GROUP BY source_type
        """)
        by_type = {row[0]: {'count': row[1], 'samples': row[2]} for row in cursor.fetchall()}

        # Count by quality
        cursor.execute("""
            SELECT quality_level, COUNT(*), SUM(sample_count)
            FROM data_sources GROUP BY quality_level
        """)
        by_quality = {row[0]: {'count': row[1], 'samples': row[2]} for row in cursor.fetchall()}

        # Total counts
        cursor.execute("SELECT COUNT(*), SUM(sample_count) FROM data_sources")
        totals = cursor.fetchone()

        conn.close()

        return {
            'total_sources': totals[0] or 0,
            'total_samples': totals[1] or 0,
            'by_type': by_type,
            'by_quality': by_quality
        }

    def _save_source(self, source: DataSource):
        """Save data source to database."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO data_sources
            (source_id, source_type, source_name, source_description, created_at,
             metadata, vehicle_info, quality_level, sample_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            source.source_id,
            source.source_type.value,
            source.source_name,
            source.source_description,
            source.created_at,
            json.dumps(source.metadata),
            json.dumps(source.vehicle_info) if source.vehicle_info else None,
            source.quality_level.value,
            source.sample_count
        ))

        conn.commit()
        conn.close()


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_tracker_instance: Optional[DataProvenanceTracker] = None


def get_provenance_tracker() -> DataProvenanceTracker:
    """Get or create singleton tracker instance."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = DataProvenanceTracker()
    return _tracker_instance


def register_data_source(
    source_type: DataSourceType,
    source_name: str,
    **kwargs
) -> DataSource:
    """Convenience function to register a data source."""
    tracker = get_provenance_tracker()
    return tracker.register_source(source_type, source_name, **kwargs)


def record_data_transformation(
    transformation_type: TransformationType,
    input_ids: List[str],
    output_hash: str,
    **kwargs
) -> Tuple[str, str]:
    """Convenience function to record a transformation."""
    tracker = get_provenance_tracker()
    return tracker.record_transformation(
        transformation_type, input_ids, output_hash,
        output_record_type=kwargs.get('record_type', 'transformed'),
        **{k: v for k, v in kwargs.items() if k != 'record_type'}
    )
