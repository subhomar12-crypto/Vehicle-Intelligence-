"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Dtc Lookup

DTC Code Lookup
Provides detailed information about diagnostic trouble codes
"""

import json
from typing import Dict, List, Optional
import os


class DTCDatabase:
    """Database of diagnostic trouble codes"""

    def __init__(self, db_file: str = "data/dtc_codes.json"):
        self.db_file = db_file
        self.codes = self._load_database()

    def _load_database(self) -> Dict:
        """Load DTC database from file"""
        try:
            if os.path.exists(self.db_file):
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # Return built-in database if file doesn't exist
                return self._get_builtin_database()
        except Exception:
            # Fallback to built-in database on any error
            return self._get_builtin_database()

    def _get_builtin_database(self) -> Dict:
        """Built-in DTC database (comprehensive)"""
        return {
            # Generic OBD-II Codes
            "P0000": {
                "description": "No Error Detected",
                "category": "Powertrain",
                "severity": "info",
                "causes": []
            },

            # Air/Fuel Metering Codes (P0100-P0199)
            "P0100": {
                "description": "Mass Air Flow (MAF) Circuit Malfunction",
                "category": "Powertrain - Air/Fuel",
                "severity": "warning",
                "causes": [
                    "MAF sensor failure",
                    "Dirty MAF sensor",
                    "Vacuum leak",
                    "Damaged wiring"
                ]
            },
            "P0101": {
                "description": "Mass Air Flow (MAF) Circuit Range/Performance",
                "category": "Powertrain - Air/Fuel",
                "severity": "warning",
                "causes": [
                    "Dirty or contaminated MAF sensor",
                    "Air filter restriction",
                    "Vacuum leak",
                    "Faulty MAF sensor"
                ]
            },
            "P0102": {
                "description": "Mass Air Flow (MAF) Circuit Low Input",
                "category": "Powertrain - Air/Fuel",
                "severity": "warning",
                "causes": [
                    "MAF sensor failure",
                    "Open circuit in MAF wiring",
                    "Poor electrical connection"
                ]
            },
            "P0103": {
                "description": "Mass Air Flow (MAF) Circuit High Input",
                "category": "Powertrain - Air/Fuel",
                "severity": "warning",
                "causes": [
                    "MAF sensor failure",
                    "Short circuit in MAF wiring",
                    "Vacuum leak"
                ]
            },
            "P0171": {
                "description": "System Too Lean (Bank 1)",
                "category": "Powertrain - Fuel/Air",
                "severity": "warning",
                "causes": [
                    "Vacuum leak",
                    "Faulty MAF sensor",
                    "Weak fuel pump",
                    "Clogged fuel filter",
                    "Faulty oxygen sensor",
                    "Exhaust leak"
                ]
            },
            "P0172": {
                "description": "System Too Rich (Bank 1)",
                "category": "Powertrain - Fuel/Air",
                "severity": "warning",
                "causes": [
                    "Faulty MAF sensor",
                    "Leaking fuel injectors",
                    "Faulty oxygen sensor",
                    "High fuel pressure",
                    "Faulty coolant temperature sensor"
                ]
            },
            "P0174": {
                "description": "System Too Lean (Bank 2)",
                "category": "Powertrain - Fuel/Air",
                "severity": "warning",
                "causes": [
                    "Vacuum leak on Bank 2",
                    "Faulty MAF sensor",
                    "Weak fuel pump",
                    "Faulty oxygen sensor Bank 2"
                ]
            },
            "P0175": {
                "description": "System Too Rich (Bank 2)",
                "category": "Powertrain - Fuel/Air",
                "severity": "warning",
                "causes": [
                    "Faulty MAF sensor",
                    "Leaking fuel injectors Bank 2",
                    "Faulty oxygen sensor Bank 2",
                    "High fuel pressure"
                ]
            },

            # Ignition System Codes (P0300-P0399)
            "P0300": {
                "description": "Random/Multiple Cylinder Misfire Detected",
                "category": "Powertrain - Ignition",
                "severity": "critical",
                "causes": [
                    "Bad spark plugs",
                    "Faulty ignition coils",
                    "Low compression",
                    "Vacuum leak",
                    "Bad fuel injectors",
                    "Weak fuel pump"
                ]
            },
            "P0301": {
                "description": "Cylinder 1 Misfire Detected",
                "category": "Powertrain - Ignition",
                "severity": "critical",
                "causes": [
                    "Faulty spark plug cylinder 1",
                    "Bad ignition coil cylinder 1",
                    "Fuel injector problem cylinder 1",
                    "Low compression cylinder 1"
                ]
            },
            "P0302": {
                "description": "Cylinder 2 Misfire Detected",
                "category": "Powertrain - Ignition",
                "severity": "critical",
                "causes": [
                    "Faulty spark plug cylinder 2",
                    "Bad ignition coil cylinder 2",
                    "Fuel injector problem cylinder 2"
                ]
            },
            "P0303": {
                "description": "Cylinder 3 Misfire Detected",
                "category": "Powertrain - Ignition",
                "severity": "critical",
                "causes": [
                    "Faulty spark plug cylinder 3",
                    "Bad ignition coil cylinder 3",
                    "Fuel injector problem cylinder 3"
                ]
            },
            "P0304": {
                "description": "Cylinder 4 Misfire Detected",
                "category": "Powertrain - Ignition",
                "severity": "critical",
                "causes": [
                    "Faulty spark plug cylinder 4",
                    "Bad ignition coil cylinder 4",
                    "Fuel injector problem cylinder 4"
                ]
            },
            "P0305": {
                "description": "Cylinder 5 Misfire Detected",
                "category": "Powertrain - Ignition",
                "severity": "critical",
                "causes": [
                    "Faulty spark plug cylinder 5",
                    "Bad ignition coil cylinder 5",
                    "Fuel injector problem cylinder 5"
                ]
            },
            "P0306": {
                "description": "Cylinder 6 Misfire Detected",
                "category": "Powertrain - Ignition",
                "severity": "critical",
                "causes": [
                    "Faulty spark plug cylinder 6",
                    "Bad ignition coil cylinder 6",
                    "Fuel injector problem cylinder 6"
                ]
            },

            # Emissions System Codes (P0400-P0499)
            "P0420": {
                "description": "Catalyst System Efficiency Below Threshold (Bank 1)",
                "category": "Powertrain - Emissions",
                "severity": "warning",
                "causes": [
                    "Faulty catalytic converter",
                    "Damaged oxygen sensor",
                    "Exhaust leak",
                    "Engine running rich/lean",
                    "Misfiring engine"
                ]
            },
            "P0430": {
                "description": "Catalyst System Efficiency Below Threshold (Bank 2)",
                "category": "Powertrain - Emissions",
                "severity": "warning",
                "causes": [
                    "Faulty catalytic converter Bank 2",
                    "Damaged oxygen sensor Bank 2",
                    "Exhaust leak Bank 2",
                    "Engine running rich/lean"
                ]
            },
            "P0440": {
                "description": "Evaporative Emission System Malfunction",
                "category": "Powertrain - Emissions",
                "severity": "warning",
                "causes": [
                    "Loose or missing gas cap",
                    "EVAP system leak",
                    "Faulty purge valve",
                    "Cracked EVAP hoses"
                ]
            },
            "P0441": {
                "description": "Evaporative Emission System Incorrect Purge Flow",
                "category": "Powertrain - Emissions",
                "severity": "warning",
                "causes": [
                    "Faulty purge valve",
                    "EVAP system blockage",
                    "Vacuum leak in EVAP system"
                ]
            },
            "P0442": {
                "description": "Evaporative Emission System Leak Detected (Small Leak)",
                "category": "Powertrain - Emissions",
                "severity": "warning",
                "causes": [
                    "Loose gas cap",
                    "Small leak in EVAP system",
                    "Faulty purge valve"
                ]
            },
            "P0455": {
                "description": "Evaporative Emission System Leak Detected (Large Leak)",
                "category": "Powertrain - Emissions",
                "severity": "warning",
                "causes": [
                    "Missing or very loose gas cap",
                    "Large EVAP leak",
                    "Damaged fuel tank",
                    "Failed purge valve"
                ]
            },

            # Oxygen Sensor Codes (P0130-P0167)
            "P0130": {
                "description": "O2 Sensor Circuit Malfunction (Bank 1, Sensor 1)",
                "category": "Powertrain - Oxygen Sensor",
                "severity": "warning",
                "causes": [
                    "Faulty oxygen sensor",
                    "Damaged O2 sensor wiring",
                    "Exhaust leak near sensor"
                ]
            },
            "P0131": {
                "description": "O2 Sensor Circuit Low Voltage (Bank 1, Sensor 1)",
                "category": "Powertrain - Oxygen Sensor",
                "severity": "warning",
                "causes": [
                    "Faulty oxygen sensor",
                    "Short circuit in O2 wiring",
                    "Exhaust leak"
                ]
            },
            "P0132": {
                "description": "O2 Sensor Circuit High Voltage (Bank 1, Sensor 1)",
                "category": "Powertrain - Oxygen Sensor",
                "severity": "warning",
                "causes": [
                    "Faulty oxygen sensor",
                    "Short to voltage in wiring",
                    "Engine running rich"
                ]
            },
            "P0133": {
                "description": "O2 Sensor Circuit Slow Response (Bank 1, Sensor 1)",
                "category": "Powertrain - Oxygen Sensor",
                "severity": "warning",
                "causes": [
                    "Contaminated oxygen sensor",
                    "Aged oxygen sensor",
                    "Exhaust leak"
                ]
            },
            "P0134": {
                "description": "O2 Sensor Circuit No Activity Detected (Bank 1, Sensor 1)",
                "category": "Powertrain - Oxygen Sensor",
                "severity": "warning",
                "causes": [
                    "Failed oxygen sensor",
                    "Open circuit in wiring",
                    "Poor connection"
                ]
            },
            "P0135": {
                "description": "O2 Sensor Heater Circuit Malfunction (Bank 1, Sensor 1)",
                "category": "Powertrain - Oxygen Sensor",
                "severity": "warning",
                "causes": [
                    "Faulty O2 sensor heater",
                    "Blown fuse",
                    "Open circuit in heater wiring"
                ]
            },

            # Additional Common Codes
            "P0200": {
                "description": "Injector Circuit Malfunction",
                "category": "Powertrain - Fuel System",
                "severity": "critical",
                "causes": [
                    "Faulty fuel injector",
                    "Injector wiring problem",
                    "ECM problem"
                ]
            },
            "P0201": {
                "description": "Injector Circuit Malfunction - Cylinder 1",
                "category": "Powertrain - Fuel System",
                "severity": "critical",
                "causes": [
                    "Faulty injector cylinder 1",
                    "Open/short in injector circuit",
                    "ECM problem"
                ]
            },
            "P0335": {
                "description": "Crankshaft Position Sensor 'A' Circuit Malfunction",
                "category": "Powertrain - Ignition",
                "severity": "critical",
                "causes": [
                    "Faulty crankshaft position sensor",
                    "Damaged sensor wiring",
                    "Reluctor ring damage",
                    "ECM problem"
                ]
            },
            "P0340": {
                "description": "Camshaft Position Sensor Circuit Malfunction",
                "category": "Powertrain - Ignition",
                "severity": "critical",
                "causes": [
                    "Faulty camshaft position sensor",
                    "Damaged sensor wiring",
                    "Timing chain/belt problem",
                    "ECM problem"
                ]
            },
            "P0401": {
                "description": "Exhaust Gas Recirculation Flow Insufficient",
                "category": "Powertrain - Emissions",
                "severity": "warning",
                "causes": [
                    "Clogged EGR passages",
                    "Faulty EGR valve",
                    "Vacuum leak",
                    "Carbon buildup"
                ]
            },
            "P0500": {
                "description": "Vehicle Speed Sensor Malfunction",
                "category": "Powertrain - Transmission",
                "severity": "warning",
                "causes": [
                    "Faulty speed sensor",
                    "Damaged sensor wiring",
                    "Faulty speedometer",
                    "Transmission problem"
                ]
            },
            "P0562": {
                "description": "System Voltage Low",
                "category": "Powertrain - Electrical",
                "severity": "warning",
                "causes": [
                    "Weak battery",
                    "Faulty alternator",
                    "Corroded battery terminals",
                    "Parasitic drain"
                ]
            },
            "P0563": {
                "description": "System Voltage High",
                "category": "Powertrain - Electrical",
                "severity": "warning",
                "causes": [
                    "Faulty alternator/voltage regulator",
                    "Damaged wiring",
                    "ECM problem"
                ]
            },
            "P0700": {
                "description": "Transmission Control System Malfunction",
                "category": "Powertrain - Transmission",
                "severity": "critical",
                "causes": [
                    "Transmission control module failure",
                    "Transmission mechanical problem",
                    "Wiring issue",
                    "Low transmission fluid"
                ]
            },
            "P0705": {
                "description": "Transmission Range Sensor Circuit Malfunction (PRNDL Input)",
                "category": "Powertrain - Transmission",
                "severity": "warning",
                "causes": [
                    "Faulty range sensor",
                    "Misadjusted linkage",
                    "Damaged wiring",
                    "Internal transmission problem"
                ]
            },

            # Chassis Codes (C-codes)
            "C0035": {
                "description": "Left Front Wheel Speed Sensor Circuit",
                "category": "Chassis - ABS",
                "severity": "warning",
                "causes": [
                    "Faulty wheel speed sensor",
                    "Damaged sensor wiring",
                    "ABS ring damage"
                ]
            },
            "C0040": {
                "description": "Right Front Wheel Speed Sensor Circuit",
                "category": "Chassis - ABS",
                "severity": "warning",
                "causes": [
                    "Faulty wheel speed sensor",
                    "Damaged sensor wiring",
                    "ABS ring damage"
                ]
            },
            "C1201": {
                "description": "ABS/Traction Control System Communication Fault",
                "category": "Chassis - ABS",
                "severity": "warning",
                "causes": [
                    "ABS module communication error",
                    "CAN bus problem",
                    "Wiring issue"
                ]
            },

            # Body Codes (B-codes)
            "B1000": {
                "description": "Restraint Control Module (RCM) Malfunction",
                "category": "Body - Airbag",
                "severity": "critical",
                "causes": [
                    "Faulty airbag control module",
                    "Crash sensor problem",
                    "Wiring issue"
                ]
            },
            "B1342": {
                "description": "ECU Is Defective",
                "category": "Body - Control Module",
                "severity": "critical",
                "causes": [
                    "Failed control module",
                    "Software corruption",
                    "Electrical damage"
                ]
            },

            # Network Codes (U-codes)
            "U0001": {
                "description": "High Speed CAN Communication Bus",
                "category": "Network - Communication",
                "severity": "warning",
                "causes": [
                    "CAN bus wiring problem",
                    "Module communication error",
                    "Termination resistor issue"
                ]
            },
            "U0100": {
                "description": "Lost Communication With ECM/PCM",
                "category": "Network - Communication",
                "severity": "critical",
                "causes": [
                    "ECM/PCM power issue",
                    "CAN bus problem",
                    "Damaged wiring",
                    "Module failure"
                ]
            },
            "U0101": {
                "description": "Lost Communication With TCM",
                "category": "Network - Communication",
                "severity": "critical",
                "causes": [
                    "TCM power issue",
                    "CAN bus problem",
                    "Module failure"
                ]
            },
        }

    def lookup(self, code: str) -> Dict:
        """
        Look up DTC code details

        Args:
            code: DTC code (e.g., "P0420")

        Returns:
            Dictionary with description, category, severity, causes
        """
        code = code.upper()

        if code in self.codes:
            return self.codes[code]
        else:
            # Return generic info based on code format
            return {
                "description": f"Unknown DTC: {code}",
                "category": self._categorize_code(code),
                "severity": "warning",
                "causes": ["Consult service manual for details"]
            }

    def _categorize_code(self, code: str) -> str:
        """Categorize DTC by prefix"""
        if code.startswith('P'):
            return "Powertrain"
        elif code.startswith('C'):
            return "Chassis"
        elif code.startswith('B'):
            return "Body"
        elif code.startswith('U'):
            return "Network"
        else:
            return "Unknown"


# Global database instance
_dtc_db: Optional[DTCDatabase] = None


def lookup_dtc_details(code: str) -> Dict:
    """Look up DTC code details"""
    global _dtc_db

    if _dtc_db is None:
        _dtc_db = DTCDatabase()

    return _dtc_db.lookup(code)
