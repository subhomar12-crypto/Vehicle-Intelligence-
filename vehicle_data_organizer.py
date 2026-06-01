"""
PREDICT - Vehicle Intelligence Platform
Copyright 2026 PREDICT
All rights reserved.

Vehicle Data Organizer - Hierarchical Storage Management
Manages Make/Model/Year folder structure with server-desktop sync.

Folder Structure:
    PredictData/
    └── vehicles/
        ├── _index.json                    # Vehicle lookup index
        └── Toyota/
            ├── _make_info.json            # Make-level research
            └── Camry/
                ├── _model_info.json       # Model-level research
                └── 2012/
                    ├── _year_research.json # Year-specific research
                    ├── _fleet_data.json   # Aggregated fleet learning data
                    └── vehicle_abc123/
                        ├── profile.json
                        ├── obd_readings/
                        ├── trips/
                        ├── predictions/
                        ├── research_data.json
                        └── service_records/
"""

from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict, field
import json
import shutil
import logging
from datetime import datetime
import hashlib
import re

logger = logging.getLogger(__name__)


@dataclass
class VehicleLocation:
    """Represents a vehicle's location in the hierarchy"""
    make: str
    model: str
    year: int
    vehicle_id: str
    base_path: Path

    @property
    def folder_path(self) -> Path:
        return self.base_path / self.make / self.model / str(self.year) / f"vehicle_{self.vehicle_id}"

    @property
    def research_path(self) -> Path:
        return self.folder_path / "research_data.json"

    @property
    def profile_path(self) -> Path:
        return self.folder_path / "profile.json"

    @property
    def obd_readings_path(self) -> Path:
        return self.folder_path / "obd_readings"

    @property
    def predictions_path(self) -> Path:
        return self.folder_path / "predictions"

    @property
    def trips_path(self) -> Path:
        return self.folder_path / "trips"

    @property
    def service_records_path(self) -> Path:
        return self.folder_path / "service_records"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'make': self.make,
            'model': self.model,
            'year': self.year,
            'vehicle_id': self.vehicle_id,
            'path': str(self.folder_path.relative_to(self.base_path))
        }


class VehicleDataOrganizer:
    """
    Manages hierarchical vehicle data storage.

    Features:
    - Create folder structure on vehicle registration
    - Migrate existing flat data to hierarchical structure
    - Maintain vehicle lookup index
    - Support server-desktop synchronization
    - Aggregate fleet data by make/model/year
    """

    VERSION = "1.0"

    def __init__(self, base_path: Path = None):
        """
        Initialize the vehicle data organizer.

        Args:
            base_path: Base path for vehicle data. Defaults to PredictData/vehicles
        """
        if base_path is None:
            # Try to import config to get default path
            try:
                from config import get_config
                config = get_config()
                base_path = Path(config.DATA_DIR) / "vehicles"
            except ImportError:
                base_path = Path("./PredictData/vehicles")

        self.base_path = Path(base_path)
        self.index_path = self.base_path / "_index.json"
        self._index_cache: Dict[str, VehicleLocation] = {}
        self._ensure_base_structure()
        self._load_index()

    def _ensure_base_structure(self):
        """Ensure base directory structure exists"""
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _load_index(self):
        """Load vehicle index from disk"""
        if self.index_path.exists():
            try:
                with open(self.index_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for vehicle_id, loc_data in data.get('vehicles', {}).items():
                        self._index_cache[vehicle_id] = VehicleLocation(
                            make=loc_data['make'],
                            model=loc_data['model'],
                            year=loc_data['year'],
                            vehicle_id=vehicle_id,
                            base_path=self.base_path
                        )
                logger.info(f"Loaded vehicle index with {len(self._index_cache)} vehicles")
            except Exception as e:
                logger.error(f"Failed to load vehicle index: {e}")
                self._index_cache = {}
        else:
            logger.info("No existing vehicle index found, starting fresh")

    def _save_index(self):
        """Save vehicle index to disk"""
        self.base_path.mkdir(parents=True, exist_ok=True)
        data = {
            'version': self.VERSION,
            'updated_at': datetime.now().isoformat(),
            'vehicle_count': len(self._index_cache),
            'vehicles': {
                vid: loc.to_dict()
                for vid, loc in self._index_cache.items()
            }
        }

        # Write atomically
        temp_path = self.index_path.with_suffix('.tmp')
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_path.replace(self.index_path)

        logger.debug(f"Saved vehicle index with {len(self._index_cache)} vehicles")

    @staticmethod
    def _normalize_name(name: str) -> str:
        """
        Normalize make/model name for filesystem.

        - Capitalize first letter of each word
        - Replace spaces with underscores
        - Remove invalid filesystem characters
        """
        if not name:
            return "Unknown"

        # Clean and capitalize
        normalized = name.strip().title()

        # Replace spaces and hyphens with underscores
        normalized = normalized.replace(' ', '_').replace('-', '_')

        # Remove invalid filesystem characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            normalized = normalized.replace(char, '')

        # Collapse multiple underscores
        while '__' in normalized:
            normalized = normalized.replace('__', '_')

        return normalized or "Unknown"

    @staticmethod
    def _generate_vehicle_id(make: str, model: str, year: int, unique_id: str = None) -> str:
        """Generate a unique vehicle ID"""
        if unique_id:
            # Sanitize provided ID
            return re.sub(r'[^a-zA-Z0-9_-]', '', str(unique_id))

        # Generate based on make/model/year + random
        import secrets
        base = f"{make}_{model}_{year}"
        hash_input = f"{base}_{datetime.now().isoformat()}_{secrets.token_hex(4)}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:12]

    def register_vehicle(
        self,
        make: str,
        model: str,
        year: int,
        vehicle_id: str = None,
        additional_data: Dict[str, Any] = None
    ) -> VehicleLocation:
        """
        Register a new vehicle and create folder structure.

        Args:
            make: Vehicle make (e.g., "Toyota")
            model: Vehicle model (e.g., "Camry")
            year: Model year (e.g., 2012)
            vehicle_id: Optional specific vehicle ID
            additional_data: Additional profile data

        Returns:
            VehicleLocation with paths for all data storage
        """
        # Normalize make/model names
        make_normalized = self._normalize_name(make)
        model_normalized = self._normalize_name(model)

        # Generate or use provided vehicle ID
        if not vehicle_id:
            vehicle_id = self._generate_vehicle_id(make_normalized, model_normalized, year)

        # Check if already registered
        if vehicle_id in self._index_cache:
            logger.info(f"Vehicle {vehicle_id} already registered, returning existing location")
            return self._index_cache[vehicle_id]

        location = VehicleLocation(
            make=make_normalized,
            model=model_normalized,
            year=year,
            vehicle_id=vehicle_id,
            base_path=self.base_path
        )

        # Create directory structure
        self._create_vehicle_folders(location)

        # Create make-level info if not exists
        self._ensure_make_info(make_normalized)

        # Create model-level info if not exists
        self._ensure_model_info(make_normalized, model_normalized)

        # Create year-level research placeholder if not exists
        self._ensure_year_research(make_normalized, model_normalized, year)

        # Save profile
        profile_data = {
            'vehicle_id': vehicle_id,
            'make': make,  # Original name
            'make_normalized': make_normalized,
            'model': model,  # Original name
            'model_normalized': model_normalized,
            'year': year,
            'registered_at': datetime.now().isoformat(),
            'folder_path': str(location.folder_path),
            **(additional_data or {})
        }

        with open(location.profile_path, 'w', encoding='utf-8') as f:
            json.dump(profile_data, f, indent=2, ensure_ascii=False)

        # Update index
        self._index_cache[vehicle_id] = location
        self._save_index()

        logger.info(f"Registered vehicle {vehicle_id} ({make} {model} {year}) at {location.folder_path}")
        return location

    def _create_vehicle_folders(self, location: VehicleLocation):
        """Create all subdirectories for a vehicle"""
        folders = [
            location.folder_path,
            location.obd_readings_path,
            location.obd_readings_path / "aggregates",
            location.predictions_path,
            location.trips_path,
            location.service_records_path,
        ]

        for folder in folders:
            folder.mkdir(parents=True, exist_ok=True)

        logger.debug(f"Created folder structure for vehicle at {location.folder_path}")

    def _ensure_make_info(self, make: str):
        """Ensure make-level info file exists"""
        make_path = self.base_path / make
        make_info_path = make_path / "_make_info.json"

        if not make_info_path.exists():
            make_path.mkdir(parents=True, exist_ok=True)
            info = {
                'make': make,
                'created_at': datetime.now().isoformat(),
                'vehicle_count': 0,
                'common_issues': [],
                'research_date': None
            }
            with open(make_info_path, 'w', encoding='utf-8') as f:
                json.dump(info, f, indent=2)
            logger.debug(f"Created make info for {make}")

    def _ensure_model_info(self, make: str, model: str):
        """Ensure model-level info file exists"""
        model_path = self.base_path / make / model
        model_info_path = model_path / "_model_info.json"

        if not model_info_path.exists():
            model_path.mkdir(parents=True, exist_ok=True)
            info = {
                'make': make,
                'model': model,
                'created_at': datetime.now().isoformat(),
                'vehicle_count': 0,
                'common_issues': [],
                'research_date': None
            }
            with open(model_info_path, 'w', encoding='utf-8') as f:
                json.dump(info, f, indent=2)
            logger.debug(f"Created model info for {make} {model}")

    def _ensure_year_research(self, make: str, model: str, year: int):
        """Ensure year-level research file exists"""
        year_path = self.base_path / make / model / str(year)
        year_research_path = year_path / "_year_research.json"

        if not year_research_path.exists():
            year_path.mkdir(parents=True, exist_ok=True)
            info = {
                'make': make,
                'model': model,
                'year': year,
                'created_at': datetime.now().isoformat(),
                'research_status': 'pending',
                'common_problems': [],
                'recalls': [],
                'tsbs': [],
                'reliability_score': None,
                'last_research_date': None
            }
            with open(year_research_path, 'w', encoding='utf-8') as f:
                json.dump(info, f, indent=2)
            logger.debug(f"Created year research for {make} {model} {year}")

    def get_vehicle_location(self, vehicle_id: str) -> Optional[VehicleLocation]:
        """Get location for an existing vehicle"""
        return self._index_cache.get(vehicle_id)

    def get_all_vehicles(self) -> List[VehicleLocation]:
        """Get all registered vehicles"""
        return list(self._index_cache.values())

    def get_vehicles_by_make_model_year(
        self,
        make: str = None,
        model: str = None,
        year: int = None
    ) -> List[VehicleLocation]:
        """Filter vehicles by make, model, and/or year"""
        results = []

        for location in self._index_cache.values():
            if make and location.make.lower() != self._normalize_name(make).lower():
                continue
            if model and location.model.lower() != self._normalize_name(model).lower():
                continue
            if year and location.year != year:
                continue
            results.append(location)

        return results

    def save_obd_reading(self, vehicle_id: str, reading: Dict[str, Any]) -> bool:
        """
        Save OBD reading to organized structure.

        Readings are organized by month and day for efficient access.
        """
        location = self.get_vehicle_location(vehicle_id)
        if not location:
            logger.error(f"Vehicle {vehicle_id} not registered")
            return False

        try:
            # Organize by date
            now = datetime.now()
            month_folder = location.obd_readings_path / now.strftime("%Y-%m")
            month_folder.mkdir(parents=True, exist_ok=True)

            # Append to daily file
            daily_file = month_folder / f"readings_{now.strftime('%Y%m%d')}.json"

            readings = []
            if daily_file.exists():
                with open(daily_file, 'r', encoding='utf-8') as f:
                    readings = json.load(f)

            reading['timestamp'] = reading.get('timestamp', now.isoformat())
            readings.append(reading)

            with open(daily_file, 'w', encoding='utf-8') as f:
                json.dump(readings, f)

            return True

        except Exception as e:
            logger.error(f"Failed to save OBD reading for {vehicle_id}: {e}")
            return False

    def save_prediction(self, vehicle_id: str, prediction: Dict[str, Any]) -> bool:
        """Save AI prediction to vehicle folder"""
        location = self.get_vehicle_location(vehicle_id)
        if not location:
            logger.error(f"Vehicle {vehicle_id} not registered")
            return False

        try:
            now = datetime.now()
            prediction_file = location.predictions_path / f"prediction_{now.strftime('%Y%m%d_%H%M%S')}.json"

            prediction['generated_at'] = now.isoformat()

            with open(prediction_file, 'w', encoding='utf-8') as f:
                json.dump(prediction, f, indent=2)

            # Also update history file
            history_file = location.predictions_path / "history.json"
            history = []
            if history_file.exists():
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)

            # Keep last 100 predictions in history
            history.append({
                'file': prediction_file.name,
                'generated_at': now.isoformat(),
                'summary': prediction.get('summary', {})
            })
            history = history[-100:]

            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2)

            return True

        except Exception as e:
            logger.error(f"Failed to save prediction for {vehicle_id}: {e}")
            return False

    def save_research_data(self, vehicle_id: str, research: Dict[str, Any]) -> bool:
        """Save LLM research data for vehicle"""
        location = self.get_vehicle_location(vehicle_id)
        if not location:
            logger.error(f"Vehicle {vehicle_id} not registered")
            return False

        try:
            research['updated_at'] = datetime.now().isoformat()

            with open(location.research_path, 'w', encoding='utf-8') as f:
                json.dump(research, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved research data for vehicle {vehicle_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save research data for {vehicle_id}: {e}")
            return False

    def get_research_data(self, vehicle_id: str) -> Optional[Dict[str, Any]]:
        """Get LLM research data for vehicle"""
        location = self.get_vehicle_location(vehicle_id)
        if not location or not location.research_path.exists():
            return None

        try:
            with open(location.research_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read research data for {vehicle_id}: {e}")
            return None

    def get_year_research(self, make: str, model: str, year: int) -> Optional[Dict[str, Any]]:
        """Get year-level research data for make/model/year"""
        make_norm = self._normalize_name(make)
        model_norm = self._normalize_name(model)
        year_research_path = self.base_path / make_norm / model_norm / str(year) / "_year_research.json"

        if not year_research_path.exists():
            return None

        try:
            with open(year_research_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read year research for {make} {model} {year}: {e}")
            return None

    def save_year_research(self, make: str, model: str, year: int, research: Dict[str, Any]) -> bool:
        """Save year-level research data"""
        make_norm = self._normalize_name(make)
        model_norm = self._normalize_name(model)
        year_path = self.base_path / make_norm / model_norm / str(year)
        year_research_path = year_path / "_year_research.json"

        try:
            year_path.mkdir(parents=True, exist_ok=True)
            research['updated_at'] = datetime.now().isoformat()

            with open(year_research_path, 'w', encoding='utf-8') as f:
                json.dump(research, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved year research for {make} {model} {year}")
            return True

        except Exception as e:
            logger.error(f"Failed to save year research: {e}")
            return False

    def get_fleet_data(self, make: str, model: str, year: int) -> Optional[Dict[str, Any]]:
        """Get aggregated fleet learning data for make/model/year"""
        make_norm = self._normalize_name(make)
        model_norm = self._normalize_name(model)
        fleet_data_path = self.base_path / make_norm / model_norm / str(year) / "_fleet_data.json"

        if not fleet_data_path.exists():
            return None

        try:
            with open(fleet_data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read fleet data: {e}")
            return None

    def save_fleet_data(self, make: str, model: str, year: int, fleet_data: Dict[str, Any]) -> bool:
        """Save aggregated fleet learning data"""
        make_norm = self._normalize_name(make)
        model_norm = self._normalize_name(model)
        year_path = self.base_path / make_norm / model_norm / str(year)
        fleet_data_path = year_path / "_fleet_data.json"

        try:
            year_path.mkdir(parents=True, exist_ok=True)
            fleet_data['updated_at'] = datetime.now().isoformat()

            with open(fleet_data_path, 'w', encoding='utf-8') as f:
                json.dump(fleet_data, f, indent=2)

            logger.info(f"Saved fleet data for {make} {model} {year}")
            return True

        except Exception as e:
            logger.error(f"Failed to save fleet data: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the vehicle data store"""
        makes = set()
        models = set()
        years = set()

        for loc in self._index_cache.values():
            makes.add(loc.make)
            models.add(f"{loc.make}/{loc.model}")
            years.add(loc.year)

        return {
            'total_vehicles': len(self._index_cache),
            'unique_makes': len(makes),
            'unique_models': len(models),
            'year_range': {
                'min': min(years) if years else None,
                'max': max(years) if years else None
            },
            'makes': sorted(makes),
            'index_path': str(self.index_path),
            'base_path': str(self.base_path)
        }


# Singleton instance
_organizer: Optional[VehicleDataOrganizer] = None


def get_vehicle_organizer(base_path: Path = None) -> VehicleDataOrganizer:
    """Get global vehicle data organizer instance"""
    global _organizer
    if _organizer is None:
        _organizer = VehicleDataOrganizer(base_path)
    return _organizer


def reset_organizer():
    """Reset the singleton instance (for testing)"""
    global _organizer
    _organizer = None
