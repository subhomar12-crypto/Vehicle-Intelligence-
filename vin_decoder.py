"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Vin Decoder
"""

import requests
import json
import sqlite3
from datetime import datetime
import re

class VINDecoder:
    """Professional VIN decoding with multiple API fallbacks"""
    
    def __init__(self, db_path='./data/vehicle_profiles.db'):
        self.db_path = db_path
        self.cache = {}
        self.setup_database()
    
    def setup_database(self):
        """Setup VIN cache database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vin_cache (
                vin TEXT PRIMARY KEY,
                decoded_data TEXT,
                timestamp DATETIME,
                source TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def decode_vin(self, vin, use_cache=True):
        """
        Decode VIN with multiple fallback strategies
        
        Args:
            vin: Vehicle Identification Number
            use_cache: Use cached results if available
            
        Returns:
            dict: Decoded vehicle information
        """
        vin = self.clean_vin(vin)
        
        if not self.validate_vin(vin):
            return {'error': 'Invalid VIN format'}
        
        # Check cache first
        if use_cache:
            cached = self.get_cached_vin(vin)
            if cached:
                print(f"✅ Using cached VIN data for {vin}")
                return cached
        
        # Try multiple decoding strategies
        strategies = [
            self._decode_nhtsa,
            self._decode_vindecoder_api,
            self._decode_local_rules
        ]
        
        for strategy in strategies:
            try:
                result = strategy(vin)
                if result and not result.get('error'):
                    # Cache successful result
                    self.cache_vin(vin, result, strategy.__name__)
                    return result
            except Exception as e:
                print(f"❌ VIN decoding strategy failed: {e}")
                continue
        
        return {'error': 'Unable to decode VIN'}
    
    def clean_vin(self, vin):
        """Clean and standardize VIN"""
        if not vin:
            return ""
        return vin.upper().strip().replace(' ', '').replace('-', '')
    
    def validate_vin(self, vin):
        """Validate VIN format"""
        if not vin or len(vin) != 17:
            return False
        
        # Basic VIN validation pattern
        vin_pattern = r'^[A-HJ-NPR-Z0-9]{17}$'
        return bool(re.match(vin_pattern, vin))
    
    def _decode_nhtsa(self, vin):
        """Decode using NHTSA API (free)"""
        try:
            url = f"https://vpic.nhtsa.dot.gov/api/vehicles/decodevin/{vin}?format=json"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_nhtsa_response(data)
        except Exception as e:
            print(f"❌ NHTSA API error: {e}")
        
        return None
    
    def _parse_nhtsa_response(self, data):
        """Parse NHTSA API response"""
        if not data.get('Results'):
            return None
        
        results = {}
        for item in data['Results']:
            variable = item.get('Variable')
            value = item.get('Value')
            
            if variable and value and value != 'Not Applicable':
                # Map NHTSA variables to our schema
                if variable == 'Make':
                    results['make'] = value
                elif variable == 'Model':
                    results['model'] = value
                elif variable == 'Model Year':
                    results['year'] = int(value) if value and value.isdigit() else None
                elif variable == 'Vehicle Type':
                    results['vehicle_type'] = value
                elif variable == 'Body Class':
                    results['body_style'] = value
                elif variable == 'Engine Model':
                    results['engine_type'] = value
                elif variable == 'Fuel Type - Primary':
                    results['fuel_type'] = value
        
        # Only return if we got meaningful data
        if any(key in results for key in ['make', 'model', 'year']):
            results['source'] = 'nhtsa'
            return results
        
        return None
    
    def _decode_vindecoder_api(self, vin):
        """
        Decode using VINDecoder API (requires API key)
        Fallback to demo mode if no key
        """
        try:
            # You would replace this with your actual API key
            api_key = "YOUR_API_KEY_HERE"
            
            if api_key == "YOUR_API_KEY_HERE":
                # Use demo mode with limited data
                return self._demo_decode(vin)
            
            url = f"https://api.vindecoder.eu/2.0/{api_key}/{vin}/decode"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_vindecoder_response(data)
                
        except Exception as e:
            print(f"❌ VINDecoder API error: {e}")
        
        return None
    
    def _demo_decode(self, vin):
        """Demo decoding for common VIN patterns"""
        # This is a simplified demo - in production you'd use real API
        demo_data = {
            '1HGCM82633A123456': {
                'make': 'Honda', 'model': 'Accord', 'year': 2003,
                'vehicle_type': 'Passenger Car', 'engine_type': '2.4L L4',
                'fuel_type': 'Gasoline', 'source': 'demo'
            },
            '2FMDK3GC5DBA12345': {
                'make': 'Ford', 'model': 'Escape', 'year': 2013,
                'vehicle_type': 'SUV', 'engine_type': '2.5L L4',
                'fuel_type': 'Gasoline', 'source': 'demo'
            },
            '5YJSA1CN5DFP12345': {
                'make': 'Tesla', 'model': 'Model S', 'year': 2013,
                'vehicle_type': 'Passenger Car', 'engine_type': 'Electric',
                'fuel_type': 'Electric', 'source': 'demo'
            }
        }
        
        return demo_data.get(vin, None)
    
    def _parse_vindecoder_response(self, data):
        """Parse VINDecoder API response"""
        if not data.get('success'):
            return None
        
        results = {}
        specs = data.get('specification', {})
        
        mapping = {
            'make': 'make',
            'model': 'model',
            'year': 'year',
            'fuel_type': 'fuel_type',
            'engine': 'engine_type',
            'body': 'body_style',
            'trim': 'trim_level'
        }
        
        for api_key, our_key in mapping.items():
            if api_key in specs and specs[api_key]:
                results[our_key] = specs[api_key]
        
        if results:
            results['source'] = 'vindecoder'
        
        return results
    
    def _decode_local_rules(self, vin):
        """Basic VIN decoding using local rules for common manufacturers"""
        if not vin or len(vin) < 3:
            return None
        
        # World Manufacturer Identifier (first 3 characters)
        wmi = vin[:3]
        
        # Common WMI patterns
        wmi_patterns = {
            '1HG': ('Honda', 'Passenger Car'),
            '2HG': ('Honda', 'Passenger Car'),
            '1FV': ('Ford', 'Truck'),
            '2FM': ('Ford', 'SUV'),
            '5YJ': ('Tesla', 'Passenger Car'),
            '3VW': ('Volkswagen', 'Passenger Car'),
            'WBA': ('BMW', 'Passenger Car'),
            'WDB': ('Mercedes-Benz', 'Passenger Car'),
            'JM1': ('Mazda', 'Passenger Car'),
            'JT': ('Toyota', 'Passenger Car'),
        }
        
        results = {}
        
        # Check WMI patterns
        for pattern, (make, vehicle_type) in wmi_patterns.items():
            if vin.startswith(pattern):
                results['make'] = make
                results['vehicle_type'] = vehicle_type
                break
        
        # Extract model year (10th character)
        year_char = vin[9]
        year_map = {
            'A': 2010, 'B': 2011, 'C': 2012, 'D': 2013, 'E': 2014,
            'F': 2015, 'G': 2016, 'H': 2017, 'J': 2018, 'K': 2019,
            'L': 2020, 'M': 2021, 'N': 2022, 'P': 2023, 'R': 2024,
            'S': 2025, 'T': 2026, 'V': 2027, 'W': 2028, 'X': 2029,
            'Y': 2030, '1': 2001, '2': 2002, '3': 2003, '4': 2004,
            '5': 2005, '6': 2006, '7': 2007, '8': 2008, '9': 2009
        }
        
        if year_char in year_map:
            results['year'] = year_map[year_char]
        
        if results:
            results['source'] = 'local_rules'
        
        return results if results else None
    
    def get_cached_vin(self, vin):
        """Get cached VIN data"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT decoded_data FROM vin_cache WHERE vin = ? AND timestamp > datetime('now', '-30 days')",
                (vin,)
            )
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return json.loads(result[0])
                
        except Exception as e:
            print(f"❌ Cache read error: {e}")
        
        return None
    
    def cache_vin(self, vin, data, source):
        """Cache VIN data"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO vin_cache (vin, decoded_data, timestamp, source)
                VALUES (?, ?, datetime('now'), ?)
            ''', (vin, json.dumps(data), source))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"❌ Cache write error: {e}")
    
    def batch_decode(self, vins, progress_callback=None):
        """Decode multiple VINs with progress tracking"""
        results = {}
        total = len(vins)
        
        for i, vin in enumerate(vins):
            if progress_callback:
                progress_callback(i, total, f"Decoding {vin}")
            
            results[vin] = self.decode_vin(vin)
        
        if progress_callback:
            progress_callback(total, total, "Complete")
        
        return results
    
    def get_decoding_statistics(self):
        """Get VIN decoding statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN timestamp > datetime('now', '-7 days') THEN 1 END) as recent,
                    source,
                    COUNT(*) as count
                FROM vin_cache 
                GROUP BY source
            ''')
            
            stats = {
                'total_cache_entries': 0,
                'recent_entries': 0,
                'sources': {}
            }
            
            for row in cursor.fetchall():
                stats['total_cache_entries'] += row[3]
                if row[1]:  # recent count
                    stats['recent_entries'] += row[1]
                stats['sources'][row[2]] = row[3]
            
            conn.close()
            return stats
            
        except Exception as e:
            print(f"❌ Statistics error: {e}")
            return {}

# Convenience functions
def decode_vin(vin, use_cache=True):
    """Convenience function for quick VIN decoding"""
    decoder = VINDecoder()
    return decoder.decode_vin(vin, use_cache)

def validate_vin(vin):
    """Convenience function for VIN validation"""
    decoder = VINDecoder()
    return decoder.validate_vin(vin)

# Example usage and testing
if __name__ == "__main__":
    decoder = VINDecoder()
    
    # Test VINs
    test_vins = [
        "1HGCM82633A123456",  # Honda Accord
        "2FMDK3GC5DBA12345",  # Ford Escape
        "5YJSA1CN5DFP12345",  # Tesla Model S
        "INVALIDVIN12345678"  # Invalid VIN
    ]
    
    for vin in test_vins:
        print(f"\n🔍 Decoding VIN: {vin}")
        result = decoder.decode_vin(vin)
        
        if result and not result.get('error'):
            print(f"✅ Success: {result.get('make')} {result.get('model')} {result.get('year')}")
            print(f"   Source: {result.get('source')}")
            print(f"   Full data: {result}")
        else:
            print(f"❌ Failed: {result.get('error', 'Unknown error')}")
    
    # Show statistics
    stats = decoder.get_decoding_statistics()
    print(f"\n📊 Decoding Statistics: {stats}")