"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Pid Profiles
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

# Setup logging
logger = logging.getLogger('PIDProfileResolver')


@dataclass
class VehicleProfile:
    """Vehicle profile data structure"""
    brand: str
    model: str
    submodel: str = ""
    year: int = 0
    name: str = ""
    profile_id: int = 0


class PIDProfileResolver:
    """
    Resolves PID profiles based on vehicle specifications.
    
    Loads JSON PID profile files and selects the best match
    based on brand, model, submodel, and year.
    """
    
    def __init__(self, profiles_directory: str = None):
        """
        Initialize the PID Profile Resolver.
        
        Args:
            profiles_directory: Path to directory containing PID profile JSON files.
                              Defaults to ./configs/pid_profiles
        """
        if profiles_directory is None:
            # Default to configs/pid_profiles in the application directory
            base_dir = os.path.dirname(os.path.abspath(__file__))
            profiles_directory = os.path.join(base_dir, "configs", "pid_profiles")
        
        self.profiles_directory = profiles_directory
        self.profiles: Dict[str, Dict] = {}
        self.default_profile: Optional[Dict] = None
        
        self._load_all_profiles()
        logger.info(f"PIDProfileResolver initialized with {len(self.profiles)} profiles")
    
    def _load_all_profiles(self):
        """Load all PID profile JSON files from the profiles directory."""
        if not os.path.exists(self.profiles_directory):
            logger.warning(f"Profiles directory not found: {self.profiles_directory}")
            os.makedirs(self.profiles_directory, exist_ok=True)
            return
        
        for filename in os.listdir(self.profiles_directory):
            if filename.endswith('.json'):
                filepath = os.path.join(self.profiles_directory, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        profile_data = json.load(f)
                        profile_id = profile_data.get('id', filename.replace('.json', ''))
                        self.profiles[profile_id] = profile_data
                        
                        # Store default profile separately
                        if profile_id == 'default':
                            self.default_profile = profile_data
                        
                        logger.debug(f"Loaded PID profile: {profile_id}")
                except Exception as e:
                    logger.error(f"Error loading profile {filename}: {e}")
        
        logger.info(f"Loaded {len(self.profiles)} PID profiles from {self.profiles_directory}")
    
    def reload_profiles(self):
        """Reload all profiles from disk."""
        self.profiles.clear()
        self.default_profile = None
        self._load_all_profiles()
    
    def resolve(self, vehicle_profile: VehicleProfile) -> Optional[Dict]:
        """
        Find the best matching PID profile for a vehicle.
        
        Args:
            vehicle_profile: VehicleProfile containing brand, model, submodel, year
            
        Returns:
            Best matching PID profile dict, or default profile, or None
        """
        if not vehicle_profile:
            logger.warning("No vehicle profile provided")
            return self.default_profile
        
        brand = (vehicle_profile.brand or "").lower().strip()
        model = (vehicle_profile.model or "").lower().strip()
        submodel = (vehicle_profile.submodel or "").lower().strip()
        year = vehicle_profile.year or 0
        
        if not brand:
            logger.warning("Vehicle profile has no brand specified")
            return self.default_profile
        
        best_match = None
        best_score = -1
        
        for profile_id, profile in self.profiles.items():
            if profile_id == 'default':
                continue
            
            match_info = profile.get('match', {})
            profile_brand = (match_info.get('brand', '') or '').lower().strip()
            
            # STRICT brand filtering - only consider profiles for the same brand
            if profile_brand != '*' and profile_brand != brand:
                continue
            
            # Calculate match score
            score = self._calculate_match_score(
                match_info, brand, model, submodel, year
            )
            
            if score > best_score:
                best_score = score
                best_match = profile
                logger.debug(f"New best match: {profile_id} with score {score}")
        
        if best_match:
            logger.info(f"Resolved PID profile: {best_match.get('id')} (score: {best_score})")
            return best_match
        
        logger.info("No specific profile found, returning default")
        return self.default_profile
    
    def _calculate_match_score(
        self,
        match_info: Dict,
        brand: str,
        model: str,
        submodel: str,
        year: int
    ) -> int:
        """
        Calculate match score between vehicle and profile.
        
        Scoring:
        - +2 for model match
        - +2 for submodel match  
        - +1 for year within range
        - +1 for brand match (if not wildcard)
        """
        score = 0
        
        # Brand match (already filtered, but add score for exact match)
        profile_brand = (match_info.get('brand', '') or '').lower().strip()
        if profile_brand == brand:
            score += 1
        
        # Model match (+2)
        profile_model = (match_info.get('model', '') or '').lower().strip()
        if profile_model and profile_model == model:
            score += 2
        
        # Submodel match (+2)
        profile_submodel = (match_info.get('submodel', '') or '').lower().strip()
        if profile_submodel and profile_submodel == submodel:
            score += 2
        
        # Year range match (+1)
        year_from = match_info.get('year_from', 0) or 0
        year_to = match_info.get('year_to', 9999) or 9999
        if year and year_from <= year <= year_to:
            score += 1
        
        return score
    
    def get_profiles_for_brand(self, brand: str) -> List[Dict]:
        """
        Get all PID profiles for a specific brand.
        
        Args:
            brand: Brand name to filter by
            
        Returns:
            List of profile dicts for the specified brand
        """
        brand = brand.lower().strip()
        matching = []
        
        for profile_id, profile in self.profiles.items():
            if profile_id == 'default':
                continue
            
            match_info = profile.get('match', {})
            profile_brand = (match_info.get('brand', '') or '').lower().strip()
            
            if profile_brand == brand or profile_brand == '*':
                matching.append(profile)
        
        return matching
    
    def get_all_pids(self, profile: Dict) -> Dict[str, Dict]:
        """
        Get all PIDs from a profile (Mode 01 + Mode 22).
        
        Args:
            profile: PID profile dict
            
        Returns:
            Combined dict of all PIDs with their info
        """
        all_pids = {}
        
        if not profile:
            return all_pids
        
        # Add Mode 01 PIDs
        mode01 = profile.get('mode01_pids', {})
        for key, info in mode01.items():
            info['service'] = info.get('service', 1)
            all_pids[key] = info
        
        # Add Mode 22 PIDs
        mode22 = profile.get('mode22_pids', {})
        for key, info in mode22.items():
            info['service'] = info.get('service', 34)  # 0x22 = 34
            all_pids[key] = info
        
        return all_pids
    
    def merge_with_defaults(self, profile: Dict) -> Dict[str, Dict]:
        """
        Merge a vehicle-specific profile with the default profile.
        
        Args:
            profile: Vehicle-specific PID profile
            
        Returns:
            Combined dict with all PIDs
        """
        merged = {}
        
        # Start with default profile
        if self.default_profile:
            merged.update(self.get_all_pids(self.default_profile))
        
        # Override/add from specific profile
        if profile and profile.get('id') != 'default':
            merged.update(self.get_all_pids(profile))
        
        return merged


class VehicleCatalog:
    """
    Manages the vehicle catalog for brand/model/year selection.
    """
    
    def __init__(self, catalog_path: str = None):
        """
        Initialize the Vehicle Catalog.
        
        Args:
            catalog_path: Path to vehicle_catalog.json file
        """
        if catalog_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            catalog_path = os.path.join(base_dir, "configs", "vehicle_catalog.json")
        
        self.catalog_path = catalog_path
        self.catalog_data: Dict = {}
        
        self._load_catalog()
    
    def _load_catalog(self):
        """Load the vehicle catalog from JSON file."""
        if not os.path.exists(self.catalog_path):
            logger.warning(f"Vehicle catalog not found: {self.catalog_path}")
            self.catalog_data = {"brands": []}
            return
        
        try:
            with open(self.catalog_path, 'r', encoding='utf-8') as f:
                self.catalog_data = json.load(f)
            logger.info(f"Loaded vehicle catalog with {len(self.get_brands())} brands")
        except Exception as e:
            logger.error(f"Error loading vehicle catalog: {e}")
            self.catalog_data = {"brands": []}
    
    def reload(self):
        """Reload the catalog from disk."""
        self._load_catalog()
    
    def save(self):
        """Save the catalog to disk."""
        try:
            os.makedirs(os.path.dirname(self.catalog_path), exist_ok=True)
            with open(self.catalog_path, 'w', encoding='utf-8') as f:
                json.dump(self.catalog_data, f, indent=2)
            logger.info("Vehicle catalog saved successfully")
            return True
        except Exception as e:
            logger.error(f"Error saving vehicle catalog: {e}")
            return False
    
    def get_brands(self) -> List[Dict]:
        """Get all brands from the catalog."""
        return self.catalog_data.get('brands', [])
    
    def get_brand_names(self) -> List[str]:
        """Get list of brand display names."""
        return [b.get('display_name', b.get('name', '')) for b in self.get_brands()]
    
    def get_brand_by_name(self, name: str) -> Optional[Dict]:
        """Get brand info by name (case-insensitive)."""
        name_lower = name.lower().strip()
        for brand in self.get_brands():
            if brand.get('name', '').lower() == name_lower or \
               brand.get('display_name', '').lower() == name_lower:
                return brand
        return None
    
    def get_models_for_brand(self, brand_name: str) -> List[Dict]:
        """Get all models for a specific brand."""
        brand = self.get_brand_by_name(brand_name)
        if brand:
            return brand.get('models', [])
        return []
    
    def get_model_names_for_brand(self, brand_name: str) -> List[str]:
        """Get list of model display names for a brand."""
        models = self.get_models_for_brand(brand_name)
        return [m.get('display_name', m.get('name', '')) for m in models]
    
    def get_model_by_name(self, brand_name: str, model_name: str) -> Optional[Dict]:
        """Get model info by name within a brand."""
        model_lower = model_name.lower().strip()
        for model in self.get_models_for_brand(brand_name):
            if model.get('name', '').lower() == model_lower or \
               model.get('display_name', '').lower() == model_lower:
                return model
        return None
    
    def get_years_for_model(self, brand_name: str, model_name: str) -> List[int]:
        """Get available years for a specific model."""
        model = self.get_model_by_name(brand_name, model_name)
        if model:
            return sorted(model.get('years', []))
        return []
    
    def get_submodels_for_model(self, brand_name: str, model_name: str) -> List[str]:
        """Get available submodels for a specific model."""
        model = self.get_model_by_name(brand_name, model_name)
        if model:
            return model.get('submodels', [])
        return []
    
    def add_brand(self, name: str, display_name: str = None) -> bool:
        """Add a new brand to the catalog."""
        if self.get_brand_by_name(name):
            return False  # Already exists
        
        self.catalog_data.setdefault('brands', []).append({
            'name': name.lower().strip(),
            'display_name': display_name or name.title(),
            'models': []
        })
        return self.save()
    
    def add_model(self, brand_name: str, model_name: str, 
                  display_name: str = None, years: List[int] = None,
                  submodels: List[str] = None, pid_profile_ids: List[str] = None) -> bool:
        """Add a new model to a brand."""
        brand = self.get_brand_by_name(brand_name)
        if not brand:
            return False
        
        if self.get_model_by_name(brand_name, model_name):
            return False  # Already exists
        
        brand.setdefault('models', []).append({
            'name': model_name.lower().strip().replace(' ', '_'),
            'display_name': display_name or model_name.title(),
            'submodels': submodels or [],
            'years': sorted(years or []),
            'pid_profile_ids': pid_profile_ids or []
        })
        return self.save()
    
    def add_years_to_model(self, brand_name: str, model_name: str, years: List[int]) -> bool:
        """Add years to an existing model."""
        model = self.get_model_by_name(brand_name, model_name)
        if not model:
            return False
        
        existing_years = set(model.get('years', []))
        existing_years.update(years)
        model['years'] = sorted(list(existing_years))
        return self.save()


# ================================
# FULL RANGE PID DISCOVERY
# ================================

class FullRangePIDDiscovery:
    """
    Implements full-range PID discovery using OBD-II bitmap responses.
    
    Queries PID support bitmaps (00, 20, 40, 60, 80, A0, C0) to discover
    all supported PIDs for a vehicle.
    """
    
    # Standard Mode 01 PIDs that return support bitmaps
    SUPPORT_PIDS = ['00', '20', '40', '60', '80', 'A0', 'C0', 'E0']
    
    # Mode 09 support PIDs
    MODE09_SUPPORT_PIDS = ['00', '20']
    
    def __init__(self):
        """Initialize the PID discovery system."""
        self.discovered_pids: Dict[str, Dict] = {}
        self.supported_mode01: List[str] = []
        self.supported_mode09: List[str] = []
        
        # Standard PID definitions
        self.standard_pids = self._load_standard_pid_definitions()
    
    def _load_standard_pid_definitions(self) -> Dict[str, Dict]:
        """Load standard OBD-II PID definitions."""
        return {
            # Mode 01 PIDs
            '04': {'name': 'Engine Load', 'unit': '%', 'bytes': 1},
            '05': {'name': 'Coolant Temperature', 'unit': 'C', 'bytes': 1},
            '06': {'name': 'Short Term Fuel Trim Bank 1', 'unit': '%', 'bytes': 1},
            '07': {'name': 'Long Term Fuel Trim Bank 1', 'unit': '%', 'bytes': 1},
            '08': {'name': 'Short Term Fuel Trim Bank 2', 'unit': '%', 'bytes': 1},
            '09': {'name': 'Long Term Fuel Trim Bank 2', 'unit': '%', 'bytes': 1},
            '0A': {'name': 'Fuel Pressure', 'unit': 'kPa', 'bytes': 1},
            '0B': {'name': 'Intake Manifold Pressure', 'unit': 'kPa', 'bytes': 1},
            '0C': {'name': 'Engine RPM', 'unit': 'RPM', 'bytes': 2},
            '0D': {'name': 'Vehicle Speed', 'unit': 'km/h', 'bytes': 1},
            '0E': {'name': 'Timing Advance', 'unit': 'deg', 'bytes': 1},
            '0F': {'name': 'Intake Air Temperature', 'unit': 'C', 'bytes': 1},
            '10': {'name': 'MAF Flow Rate', 'unit': 'g/s', 'bytes': 2},
            '11': {'name': 'Throttle Position', 'unit': '%', 'bytes': 1},
            '12': {'name': 'Secondary Air Status', 'unit': '', 'bytes': 1},
            '13': {'name': 'O2 Sensors Present', 'unit': '', 'bytes': 1},
            '14': {'name': 'O2 Sensor 1 Voltage', 'unit': 'V', 'bytes': 2},
            '15': {'name': 'O2 Sensor 2 Voltage', 'unit': 'V', 'bytes': 2},
            '16': {'name': 'O2 Sensor 3 Voltage', 'unit': 'V', 'bytes': 2},
            '17': {'name': 'O2 Sensor 4 Voltage', 'unit': 'V', 'bytes': 2},
            '18': {'name': 'O2 Sensor 5 Voltage', 'unit': 'V', 'bytes': 2},
            '19': {'name': 'O2 Sensor 6 Voltage', 'unit': 'V', 'bytes': 2},
            '1A': {'name': 'O2 Sensor 7 Voltage', 'unit': 'V', 'bytes': 2},
            '1B': {'name': 'O2 Sensor 8 Voltage', 'unit': 'V', 'bytes': 2},
            '1C': {'name': 'OBD Standards', 'unit': '', 'bytes': 1},
            '1D': {'name': 'O2 Sensors Present (4 Bank)', 'unit': '', 'bytes': 1},
            '1E': {'name': 'Aux Input Status', 'unit': '', 'bytes': 1},
            '1F': {'name': 'Runtime Since Start', 'unit': 's', 'bytes': 2},
            '21': {'name': 'Distance with MIL On', 'unit': 'km', 'bytes': 2},
            '22': {'name': 'Fuel Rail Pressure', 'unit': 'kPa', 'bytes': 2},
            '23': {'name': 'Fuel Rail Gauge Pressure', 'unit': 'kPa', 'bytes': 2},
            '24': {'name': 'O2 Sensor 1 Equiv Ratio', 'unit': '', 'bytes': 4},
            '2C': {'name': 'Commanded EGR', 'unit': '%', 'bytes': 1},
            '2D': {'name': 'EGR Error', 'unit': '%', 'bytes': 1},
            '2E': {'name': 'Commanded Evap Purge', 'unit': '%', 'bytes': 1},
            '2F': {'name': 'Fuel Tank Level', 'unit': '%', 'bytes': 1},
            '30': {'name': 'Warmups Since Clear', 'unit': '', 'bytes': 1},
            '31': {'name': 'Distance Since Clear', 'unit': 'km', 'bytes': 2},
            '32': {'name': 'Evap System Vapor Pressure', 'unit': 'Pa', 'bytes': 2},
            '33': {'name': 'Barometric Pressure', 'unit': 'kPa', 'bytes': 1},
            '3C': {'name': 'Catalyst Temp B1S1', 'unit': 'C', 'bytes': 2},
            '3D': {'name': 'Catalyst Temp B2S1', 'unit': 'C', 'bytes': 2},
            '3E': {'name': 'Catalyst Temp B1S2', 'unit': 'C', 'bytes': 2},
            '3F': {'name': 'Catalyst Temp B2S2', 'unit': 'C', 'bytes': 2},
            '42': {'name': 'Control Module Voltage', 'unit': 'V', 'bytes': 2},
            '43': {'name': 'Absolute Load Value', 'unit': '%', 'bytes': 2},
            '44': {'name': 'Commanded Equiv Ratio', 'unit': '', 'bytes': 2},
            '45': {'name': 'Relative Throttle Position', 'unit': '%', 'bytes': 1},
            '46': {'name': 'Ambient Air Temperature', 'unit': 'C', 'bytes': 1},
            '47': {'name': 'Absolute Throttle B', 'unit': '%', 'bytes': 1},
            '48': {'name': 'Absolute Throttle C', 'unit': '%', 'bytes': 1},
            '49': {'name': 'Accelerator Pedal D', 'unit': '%', 'bytes': 1},
            '4A': {'name': 'Accelerator Pedal E', 'unit': '%', 'bytes': 1},
            '4B': {'name': 'Accelerator Pedal F', 'unit': '%', 'bytes': 1},
            '4C': {'name': 'Commanded Throttle Actuator', 'unit': '%', 'bytes': 1},
            '4D': {'name': 'Time Run MIL On', 'unit': 'min', 'bytes': 2},
            '4E': {'name': 'Time Since Clear', 'unit': 'min', 'bytes': 2},
            '5A': {'name': 'Relative Accelerator Pedal', 'unit': '%', 'bytes': 1},
            '5B': {'name': 'Hybrid Battery Pack Life', 'unit': '%', 'bytes': 1},
            '5C': {'name': 'Engine Oil Temperature', 'unit': 'C', 'bytes': 1},
            '5D': {'name': 'Fuel Injection Timing', 'unit': 'deg', 'bytes': 2},
            '5E': {'name': 'Engine Fuel Rate', 'unit': 'L/h', 'bytes': 2},
            '61': {'name': 'Driver Demand Torque', 'unit': '%', 'bytes': 1},
            '62': {'name': 'Actual Engine Torque', 'unit': '%', 'bytes': 1},
            '63': {'name': 'Engine Reference Torque', 'unit': 'Nm', 'bytes': 2},
            '64': {'name': 'Engine Percent Torque Data', 'unit': '%', 'bytes': 5},
        }
    
    def parse_support_bitmap(self, response_bytes: bytes, base_pid: int) -> List[str]:
        """
        Parse a 4-byte support bitmap to determine supported PIDs.
        
        Args:
            response_bytes: 4 bytes of bitmap data
            base_pid: Base PID (e.g., 0x00, 0x20, 0x40)
            
        Returns:
            List of supported PID hex strings
        """
        supported = []
        
        if len(response_bytes) < 4:
            return supported
        
        # Convert 4 bytes to 32-bit value
        bitmap = int.from_bytes(response_bytes[:4], byteorder='big')
        
        # Check each of the 32 bits
        for i in range(32):
            if bitmap & (1 << (31 - i)):
                pid_num = base_pid + i + 1
                # Skip support PIDs themselves (20, 40, 60, etc.)
                if pid_num % 32 != 0:
                    supported.append(f"{pid_num:02X}")
        
        return supported
    
    def get_candidate_pids(self, supported_pids: List[str], 
                           profile_pids: Dict[str, Dict]) -> Dict[str, Dict]:
        """
        Build complete list of candidate PIDs for learning.
        
        Args:
            supported_pids: List of discovered supported PIDs
            profile_pids: PIDs from the active profile
            
        Returns:
            Combined dict of all candidate PIDs
        """
        candidates = {}
        
        # Add standard PIDs that are supported
        for pid_hex in supported_pids:
            if pid_hex in self.standard_pids:
                candidates[f"mode01_{pid_hex.lower()}"] = {
                    'service': 1,
                    'pid': f"0x{pid_hex}",
                    **self.standard_pids[pid_hex]
                }
        
        # Add profile Mode 22 PIDs
        for key, info in profile_pids.items():
            if info.get('service') == 34:  # Mode 22
                candidates[key] = info
        
        return candidates


# ================================
# EXPORTS
# ================================

__all__ = [
    'PIDProfileResolver',
    'VehicleProfile', 
    'VehicleCatalog',
    'FullRangePIDDiscovery'
]


if __name__ == "__main__":
    # Test the resolver
    logging.basicConfig(level=logging.DEBUG)
    
    resolver = PIDProfileResolver()
    catalog = VehicleCatalog()
    
    print(f"Available brands: {catalog.get_brand_names()}")
    
    # Test profile resolution
    test_vehicle = VehicleProfile(
        brand="nissan",
        model="altima",
        submodel="",
        year=2017
    )
    
    profile = resolver.resolve(test_vehicle)
    if profile:
        print(f"Matched profile: {profile.get('id')}")
        all_pids = resolver.get_all_pids(profile)
        print(f"Available PIDs: {len(all_pids)}")
