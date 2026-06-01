"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: NHTSA Recall API
"""

import logging
import sqlite3
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RecallAlert:
    """NHTSA recall alert data structure"""
    campaign: str
    description: str
    severity: str  # HIGH, MEDIUM, LOW
    status: str  # active, completed, investigated
    manufacturer: Optional[str] = None
    recall_date: Optional[str] = None
    remedy: Optional[str] = None
    notes: Optional[str] = None


class RecallChecker:
    """
    NHTSA Recall Checker - Queries NHTSA API for vehicle recalls
    
    Features:
    - Query NHTSA API for vehicle recalls by VIN
    - Cache results locally to reduce API calls
    - Track checked VINs
    - Store recall history
    """
    
    # NHTSA API endpoint
    NHTSA_API_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/decodevin/"
    
    def __init__(self, db_path: str = None, api_timeout: int = 10):
        """
        Initialize recall checker
        
        Args:
            db_path: Path to SQLite database
            api_timeout: API request timeout in seconds
        """
        from config import get_config
        CONFIG = get_config()
        
        self.db_path = db_path if db_path else str(CONFIG.DATA_DIR / "vehicle_profiles.db")
        self.api_timeout = api_timeout
        
        # Initialize database tables
        self._init_database()
        
        logger.info("NHTSA Recall Checker initialized")
    
    def _init_database(self):
        """Initialize recall database tables"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Table for checked VINs
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS checked_vins (
                    vin TEXT PRIMARY KEY,
                    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_recall_check TIMESTAMP,
                    recall_count INTEGER DEFAULT 0
                )
            ''')
            
            # Table for recall history
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS recall_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vin TEXT NOT NULL,
                    campaign TEXT,
                    description TEXT,
                    severity TEXT,
                    status TEXT DEFAULT 'active',
                    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error initializing recall database: {e}")
    
    def check_recalls(self, vin: str, make: Optional[str] = None, 
                   model: Optional[str] = None, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Check NHTSA API for recalls on a vehicle
        
        Args:
            vin: 17-character VIN
            make: Vehicle make (optional, will be decoded from VIN)
            model: Vehicle model (optional, will be decoded from VIN)
            year: Vehicle year (optional, will be decoded from VIN)
        
        Returns:
            List of recall alerts
        """
        try:
            # Normalize VIN
            vin = vin.strip().upper()
            if len(vin) != 17 or not vin.isalnum():
                logger.warning(f"Invalid VIN format: {vin}")
                return []
            
            # If make/model/year not provided, decode from VIN
            if not all([make, model, year]):
                decoded = self._decode_vin(vin)
                make = decoded.get('make', make)
                model = decoded.get('model', model)
                year = decoded.get('year', year)
            
            logger.info(f"Checking recalls for {make} {model} {year} (VIN: {vin})")
            
            # Check if already recently checked (cache for 24 hours)
            if self._is_recently_checked(vin):
                logger.info(f"VIN {vin} was recently checked, using cached results")
                recalls = self._get_cached_recalls(vin)
            else:
                # Query NHTSA API
                recalls = self._query_nhtsa_api(vin, make, model, year)
                
                # Cache results
                if recalls:
                    self._cache_recalls(vin, recalls)
                    self._update_checked_vin(vin, len(recalls))
            
            return recalls
            
        except Exception as e:
            logger.error(f"Error checking recalls: {e}")
            return []
    
    def _decode_vin(self, vin: str) -> Dict[str, Any]:
        """
        Decode VIN to extract make, model, year
        Simple WMI (World Manufacturer Identifier) decoding
        
        Args:
            vin: 17-character VIN
        
        Returns:
            Dictionary with make, model, year
        """
        try:
            # WMI (World Manufacturer Identifier) - first 3 characters
            wmi = vin[0:3]
            
            # VIN make codes (simplified mapping)
            makes = {
                '1A': 'Audi', '1B': 'BMW', '1C': 'Chrysler', '1D': 'Dodge',
                '1F': 'Ford', '1G': 'General Motors', '1H': 'Honda', '1J': 'Jeep',
                '1K': 'Kia', '1L': 'Lincoln', '1M': 'Mercury', '1N': 'Nissan',
                '1P': 'Plymouth', '1S': 'Subaru', '1T': 'Toyota', '1V': 'Volkswagen',
                '1Y': 'Mazda', '2A': 'Acura', '2B': 'Buick', '2C': 'Cadillac',
                '2D': 'Pontiac', '2F': 'Fiat', '2G': 'General Motors',
                '2H': 'Acura', '2J': 'Mercury', '2K': 'Buick', '2L': 'Lincoln',
                '2M': 'Mercury', '2N': 'Nissan', '2P': 'Peugeot', '2R': 'Audi',
                '2S': 'Subaru', '2T': 'Toyota', '2V': 'Porsche', '2W': 'Audi',
                '2Y': 'Mazda', '2Z': 'Mazda', '3A': 'Mazda', '3B': 'BMW',
                '3C': 'Chrysler', '3D': 'Dodge', '3F': 'Ford', '3G': 'General Motors',
                '3H': 'Acura', '3J': 'Jeep', '3K': 'Kia', '3L': 'Lincoln',
                '3M': 'Mercury', '3N': 'Nissan', '3P': 'Peugeot', '3S': 'Subaru',
                '3T': 'Toyota', '3V': 'Volvo', '3W': 'Volvo', '3Y': 'Mazda',
                '3Z': 'Mazda', '4A': 'Audi', '4B': 'BMW', '4C': 'Chrysler',
                '4D': 'Dodge', '4F': 'Ford', '4G': 'General Motors', '4H': 'Acura',
                '4J': 'Jeep', '4K': 'Kia', '4L': 'Lincoln', '4M': 'Mercury',
                '4N': 'Nissan', '4P': 'Peugeot', '4S': 'Subaru', '4T': 'Toyota',
                '4V': 'Volvo', '4W': 'Volvo', '4X': 'Volvo', '4Y': 'Mazda',
                '4Z': 'Mazda', '5A': 'Audi', '5B': 'BMW', '5C': 'Chrysler', '5D': 'Dodge',
                '5F': 'Ford', '5G': 'General Motors', '5H': 'Acura', '5J': 'Jeep',
                '5K': 'Kia', '5L': 'Lincoln', '5M': 'Mercury', '5N': 'Nissan',
                '5P': 'Peugeot', '5S': 'Subaru', '5T': 'Toyota', '5V': 'Volvo',
                '5W': 'Volvo', '5X': 'Volvo', '5Y': 'Mazda', '5Z': 'Mazda'
            }
            
            make = makes.get(wmi, 'Unknown')
            
            # VDS (Vehicle Descriptor Section) - characters 4-9
            vds = vin[3:9]
            
            # VIS (Vehicle Identifier Section) - characters 10-17
            vis = vin[9:17]
            
            # Extract year from position 10 (10th character, model year)
            year_char = vin[9]
            try:
                year = 1980 + int(year_char)
                if year > datetime.now().year:
                    year = year - 100  # Handle pre-1980 vehicles
            except (ValueError, IndexError):
                year = None
            
            return {
                'make': make,
                'model': model,
                'year': year
            }
            
        except Exception as e:
            logger.error(f"Error decoding VIN: {e}")
            return {'make': 'Unknown', 'model': None, 'year': None}
    
    def _query_nhtsa_api(self, vin: str, make: str, model: str, year: int) -> List[Dict[str, Any]]:
        """
        Query NHTSA API for recalls
        
        Args:
            vin: Vehicle VIN
            make: Vehicle manufacturer
            model: Vehicle model
            year: Vehicle year
        
        Returns:
            List of recall alerts
        """
        try:
            # Build API URL
            url = f"{self.NHTSA_API_URL}{vin}?format=json"
            
            logger.info(f"Querying NHTSA API: {url}")
            
            # Make API request
            response = requests.get(url, timeout=self.api_timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                # Parse NHTSA response
                recalls = self._parse_nhtsa_response(data, vin, make, model, year)
                
                logger.info(f"Found {len(recalls)} recalls for VIN {vin}")
                return recalls
            else:
                logger.warning(f"NHTSA API returned status {response.status_code}")
                return []
                
        except requests.exceptions.Timeout:
            logger.error(f"NHTSA API timeout after {self.api_timeout} seconds")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"NHTSA API request failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Error querying NHTSA API: {e}")
            return []
    
    def _parse_nhtsa_response(self, data: Dict, vin: str, make: str, model: str, year: int) -> List[Dict[str, Any]]:
        """
        Parse NHTSA API response and convert to recall alerts
        
        Args:
            data: NHTSA API response JSON
            vin: Vehicle VIN
            make: Vehicle manufacturer
            model: Vehicle model
            year: Vehicle year
        
        Returns:
            List of recall alerts
        """
        recalls = []
        
        try:
            # Get results
            results = data.get('results', [])
            
            if not results:
                logger.warning("No results in NHTSA response")
                return recalls
            
            # Process each result (campaign)
            for result in results:
                recall = RecallAlert(
                    campaign=result.get('NHTSACampaignNumber', ''),
                    description=result.get('Summary', 'No description available'),
                    severity=self._determine_severity(result),
                    status='active',
                    manufacturer=make,
                    recall_date=result.get('RecallDate')
                )
                
                recalls.append({
                    'campaign': recall.campaign,
                    'description': recall.description,
                    'severity': recall.severity,
                    'status': recall.status,
                    'manufacturer': recall.manufacturer,
                    'recall_date': recall.recall_date
                })
            
            # Sort by severity (HIGH first)
            severity_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
            recalls.sort(key=lambda r: severity_order.get(r['severity'], 3))
            
            return recalls
            
        except Exception as e:
            logger.error(f"Error parsing NHTSA response: {e}")
            return []
    
    def _determine_severity(self, result: Dict) -> str:
        """
        Determine recall severity from NHTSA result
        
        Args:
            result: Single NHTSA result
        
        Returns:
            Severity level (HIGH, MEDIUM, LOW)
        """
        try:
            # Check for safety-related keywords
            summary = result.get('Summary', '').lower()
            description = result.get('Component', '').lower()
            
            safety_keywords = ['fire', 'crash', 'injury', 'death', 'brake', 'steering', 'airbag', 'seatbelt']
            
            # Check for safety risk
            if any(keyword in summary or keyword in description for keyword in safety_keywords):
                return 'HIGH'
            
            # Check for moderate risk
            moderate_keywords = ['fail', 'leak', 'overheat', 'stall', 'corrode', 'wear']
            if any(keyword in summary or keyword in description for keyword in moderate_keywords):
                return 'MEDIUM'
            
            # Default to LOW
            return 'LOW'
            
        except Exception as e:
            logger.error(f"Error determining severity: {e}")
            return 'LOW'
    
    def _is_recently_checked(self, vin: str) -> bool:
        """
        Check if VIN was checked in the last 24 hours
        
        Args:
            vin: Vehicle VIN
        
        Returns:
            True if checked recently, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT last_recall_check FROM checked_vins WHERE vin = ?
            ''', (vin,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                last_check = datetime.fromisoformat(result[0])
                time_since_check = datetime.now() - last_check
                return time_since_check < timedelta(hours=24)
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking recent VIN check: {e}")
            return False
    
    def _get_cached_recalls(self, vin: str) -> List[Dict[str, Any]]:
        """
        Get cached recalls from database
        
        Args:
            vin: Vehicle VIN
        
        Returns:
            List of cached recalls
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT campaign, description, severity, status FROM recall_history
                WHERE vin = ? AND status = 'active'
                ORDER BY checked_at DESC
            ''', (vin,))
            
            rows = cursor.fetchall()
            conn.close()
            
            recalls = []
            for row in rows:
                recalls.append({
                    'campaign': row[0],
                    'description': row[1],
                    'severity': row[2],
                    'status': row[3]
                })
            
            return recalls
            
        except Exception as e:
            logger.error(f"Error getting cached recalls: {e}")
            return []
    
    def _cache_recalls(self, vin: str, recalls: List[Dict[str, Any]]):
        """
        Cache recalls in database
        
        Args:
            vin: Vehicle VIN
            recalls: List of recall alerts
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Delete old cached recalls for this VIN
            cursor.execute('DELETE FROM recall_history WHERE vin = ?', (vin,))
            
            # Insert new recalls
            for recall in recalls:
                cursor.execute('''
                    INSERT INTO recall_history (vin, campaign, description, severity, status, checked_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    vin,
                    recall['campaign'],
                    recall['description'],
                    recall['severity'],
                    recall['status'],
                    datetime.now().isoformat()
                ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Cached {len(recalls)} recalls for VIN {vin}")
            
        except Exception as e:
            logger.error(f"Error caching recalls: {e}")
    
    def _update_checked_vin(self, vin: str, recall_count: int):
        """
        Update checked VIN record
        
        Args:
            vin: Vehicle VIN
            recall_count: Number of recalls found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if VIN exists
            cursor.execute('SELECT recall_count FROM checked_vins WHERE vin = ?', (vin,))
            result = cursor.fetchone()
            
            if result:
                # Update existing record
                cursor.execute('''
                    UPDATE checked_vins
                    SET recall_count = recall_count + ?,
                        last_recall_check = ?
                    WHERE vin = ?
                ''', (recall_count, datetime.now().isoformat(), vin))
            else:
                # Insert new record
                cursor.execute('''
                    INSERT INTO checked_vins (vin, checked_at, last_recall_check, recall_count)
                    VALUES (?, ?, ?, ?)
                ''', (vin, datetime.now().isoformat(), datetime.now().isoformat(), recall_count))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error updating checked VIN: {e}")
    
    def get_active_recalls(self, vin: Optional[str] = None, make: Optional[str] = None,
                         model: Optional[str] = None, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get active recalls for a vehicle
        
        Args:
            vin: Vehicle VIN (optional)
            make: Vehicle make (optional)
            model: Vehicle model (optional)
            year: Vehicle year (optional)
        
        Returns:
            List of active recall alerts
        """
        try:
            if not vin:
                logger.warning("No VIN provided for recall check")
                return []
            
            # Check cache first
            cached = self._get_cached_recalls(vin)
            if cached:
                logger.info(f"Returning {len(cached)} cached recalls for VIN {vin}")
                return cached
            
            # Query NHTSA API
            recalls = self.check_recalls(vin, make, model, year)
            
            # Cache results
            if recalls:
                self._cache_recalls(vin, recalls)
            
            return recalls
            
        except Exception as e:
            logger.error(f"Error getting active recalls: {e}")
            return []
    
    def get_checked_vins(self) -> List[str]:
        """
        Get list of all checked VINs
        
        Returns:
            List of VINs that have been checked
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT DISTINCT vin FROM checked_vins
                ORDER BY last_recall_check DESC
            ''')
            
            rows = cursor.fetchall()
            conn.close()
            
            vins = [row[0] for row in rows]
            
            logger.info(f"Found {len(vins)} checked VINs")
            return vins
            
        except Exception as e:
            logger.error(f"Error getting checked VINs: {e}")
            return []
    
    def mark_recall_complete(self, vin: str, campaign: str) -> bool:
        """
        Mark a recall as complete
        
        Args:
            vin: Vehicle VIN
            campaign: Campaign number
        
        Returns:
            True if successful
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE recall_history
                SET status = 'completed', updated_at = ?
                WHERE vin = ? AND campaign = ?
            ''', (datetime.now().isoformat(), vin, campaign))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Marked recall {campaign} as complete for VIN {vin}")
            return True
            
        except Exception as e:
            logger.error(f"Error marking recall complete: {e}")
            return False
    
    def get_recall_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recall history
        
        Args:
            limit: Maximum number of records to return
        
        Returns:
            List of recall history records
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT rh.id, rh.vin, rh.campaign, rh.description, rh.severity,
                       rh.status, rh.checked_at, rh.updated_at
                FROM recall_history rh
                ORDER BY rh.checked_at DESC
                LIMIT ?
            ''', (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            history = []
            for row in rows:
                history.append({
                    'id': row[0],
                    'vin': row[1],
                    'campaign': row[2],
                    'description': row[3],
                    'severity': row[4],
                    'status': row[5],
                    'checked_at': row[6],
                    'updated_at': row[7]
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting recall history: {e}")
            return []


# Singleton instance
_recall_checker = None


def get_recall_checker(db_path: str = None) -> RecallChecker:
    """
    Get singleton instance of RecallChecker
    
    Args:
        db_path: Path to SQLite database
    
    Returns:
        RecallChecker instance
    """
    global _recall_checker
    if _recall_checker is None:
        _recall_checker = RecallChecker(db_path=db_path)
    return _recall_checker
