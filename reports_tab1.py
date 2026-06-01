"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Reports Tab1
"""

import os
import json
import glob
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import defaultdict
import statistics

# Import centralized configuration
try:
    from config import get_config
    CONFIG = get_config()
except ImportError:
    CONFIG = None

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QHBoxLayout, QPlainTextEdit, QFileDialog, QGroupBox,
    QMessageBox, QProgressBar, QFrame, QGridLayout,
    QComboBox, QCheckBox, QTabWidget, QScrollArea,
    QSpinBox, QDateEdit, QListWidget, QListWidgetItem,
    QTextEdit, QSplitter
)
from PySide6.QtGui import QFont, QColor, QPalette
from PySide6.QtCore import Qt, QThread, Signal, QDate

from ui_common import show_error, ProfessionalTheme

# Define show_info locally if not available in ui_common
def show_info(parent, title, message):
    QMessageBox.information(parent, title, message)

try:
    from pdf_exporter import PDFExporter
except ImportError:
    PDFExporter = None


# ================================
# SESSION DATA READER
# ================================

class SessionDataReader:
    """Reads and parses session data from JSONL log files"""
    
    # FIXED: Default path for session logs - uses CONFIG for portability
    @property
    def DEFAULT_LOGS_PATH(self):
        if CONFIG:
            return str(CONFIG.LOGS_DIR)
        # Fallback for development
        return os.path.join(os.path.dirname(__file__), "data", "logs")
    
    def __init__(self, logs_directory: str = None):
        self.logs_directory = logs_directory or self.DEFAULT_LOGS_PATH
        self.sessions = {}
        self.all_data_points = []
    
    def get_available_sessions(self, profile_name: str = None) -> List[Dict[str, Any]]:
        """Get list of available session files"""
        sessions = []
        
        if not os.path.exists(self.logs_directory):
            return sessions
        
        # Find all session files
        pattern = os.path.join(self.logs_directory, "session_*.jsonl")
        files = glob.glob(pattern)
        
        for filepath in files:
            try:
                filename = os.path.basename(filepath)
                # Parse filename: session_PROFILENAME_YYYYMMDD_HHMMSS.jsonl
                parts = filename.replace("session_", "").replace(".jsonl", "").split("_")
                
                if len(parts) >= 3:
                    name = parts[0]
                    date_str = parts[1]
                    time_str = parts[2] if len(parts) > 2 else "000000"
                    
                    # Filter by profile name if specified
                    if profile_name and name.lower() != profile_name.lower():
                        continue
                    
                    # Get file stats
                    file_stat = os.stat(filepath)
                    file_size = file_stat.st_size
                    
                    # Count data points
                    data_count = self._count_data_points(filepath)
                    
                    sessions.append({
                        'filepath': filepath,
                        'filename': filename,
                        'profile_name': name,
                        'date': date_str,
                        'time': time_str,
                        'size_bytes': file_size,
                        'data_points': data_count,
                        'display_name': f"{name} - {date_str[:4]}-{date_str[4:6]}-{date_str[6:]} {time_str[:2]}:{time_str[2:4]}"
                    })
            except Exception as e:
                print(f"Error parsing session file {filepath}: {e}")
        
        # Sort by date (newest first)
        sessions.sort(key=lambda x: x['date'] + x['time'], reverse=True)
        return sessions
    
    def _count_data_points(self, filepath: str) -> int:
        """Count data points in a session file"""
        count = 0
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    if '"type": "data_point"' in line:
                        count += 1
        except:
            pass
        return count
    
    def load_session(self, filepath: str) -> Dict[str, Any]:
        """Load and parse a session file"""
        session_data = {
            'header': None,
            'profile': None,
            'data_points': [],
            'statistics': {},
            'filepath': filepath
        }
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        record = json.loads(line)
                        record_type = record.get('type', '')
                        
                        if record_type == 'session_header':
                            session_data['header'] = record
                            session_data['profile'] = record.get('vehicle_profile', {})
                        elif record_type == 'data_point':
                            data = record.get('data', {})
                            data['_timestamp'] = record.get('timestamp', '')
                            session_data['data_points'].append(data)
                    except json.JSONDecodeError:
                        continue
            
            # Calculate statistics
            session_data['statistics'] = self._calculate_statistics(session_data['data_points'])
            
        except Exception as e:
            print(f"Error loading session {filepath}: {e}")
        
        return session_data
    
    def load_all_sessions_for_profile(self, profile_name: str) -> List[Dict[str, Any]]:
        """Load all session data for a specific profile"""
        sessions = self.get_available_sessions(profile_name)
        all_sessions = []
        
        for session_info in sessions:
            session_data = self.load_session(session_info['filepath'])
            if session_data['data_points']:
                all_sessions.append(session_data)
        
        return all_sessions
    
    def get_combined_data_for_profile(self, profile_name: str) -> Dict[str, Any]:
        """Get combined statistics from all sessions for a profile"""
        sessions = self.load_all_sessions_for_profile(profile_name)
        
        if not sessions:
            return None
        
        # Combine all data points
        all_data_points = []
        for session in sessions:
            all_data_points.extend(session['data_points'])
        
        # Calculate combined statistics
        combined = {
            'profile': sessions[0]['profile'] if sessions else {},
            'total_sessions': len(sessions),
            'total_data_points': len(all_data_points),
            'data_points': all_data_points,
            'statistics': self._calculate_statistics(all_data_points),
            'sessions': sessions
        }
        
        return combined
    
    def _calculate_statistics(self, data_points: List[Dict]) -> Dict[str, Any]:
        """Calculate statistics from data points"""
        if not data_points:
            return {}
        
        stats = {}
        
        # Fields to analyze
        numeric_fields = [
            'rpm', 'speed', 'coolant_temp', 'engine_load', 'throttle_position',
            'intake_temp', 'maf', 'map', 'timing_advance', 'short_fuel_trim_1',
            'long_fuel_trim_1', 'runtime', 'ambient_temp', 'battery_voltage',
            'fuel_level', 'oil_temp'
        ]
        
        for field in numeric_fields:
            values = []
            for dp in data_points:
                val = dp.get(field)
                if val is not None:
                    try:
                        values.append(float(val))
                    except (ValueError, TypeError):
                        pass
            
            if values:
                stats[field] = {
                    'min': min(values),
                    'max': max(values),
                    'avg': statistics.mean(values),
                    'median': statistics.median(values),
                    'stdev': statistics.stdev(values) if len(values) > 1 else 0,
                    'count': len(values),
                    'latest': values[-1] if values else None
                }
        
        # Calculate derived metrics
        stats['_derived'] = {}
        
        # Idle stability (RPM variation at low throttle)
        idle_rpms = []
        for dp in data_points:
            throttle = dp.get('throttle_position', 100)
            rpm = dp.get('rpm')
            if throttle is not None and throttle < 5 and rpm is not None:
                idle_rpms.append(float(rpm))
        
        if idle_rpms:
            idle_variation = max(idle_rpms) - min(idle_rpms)
            stats['_derived']['idle_stability'] = {
                'variation': idle_variation,
                'stable': idle_variation < 100,
                'avg_idle_rpm': statistics.mean(idle_rpms)
            }
        
        # Fuel trim analysis
        stft = stats.get('short_fuel_trim_1', {})
        ltft = stats.get('long_fuel_trim_1', {})
        
        if stft and ltft:
            total_trim = (stft.get('avg', 0) + ltft.get('avg', 0))
            stats['_derived']['fuel_system'] = {
                'total_trim': total_trim,
                'status': 'Normal' if abs(total_trim) < 15 else ('Lean' if total_trim > 0 else 'Rich'),
                'health': 'Good' if abs(total_trim) < 10 else ('Fair' if abs(total_trim) < 20 else 'Poor')
            }
        
        # Temperature trends
        coolant = stats.get('coolant_temp', {})
        if coolant:
            avg_temp = coolant.get('avg', 85)
            max_temp = coolant.get('max', 100)
            stats['_derived']['cooling_system'] = {
                'avg_operating_temp': avg_temp,
                'max_temp_reached': max_temp,
                'status': 'Normal' if max_temp < 105 else ('Warning' if max_temp < 115 else 'Critical'),
                'health': 'Good' if max_temp < 100 else ('Fair' if max_temp < 110 else 'Poor')
            }
        
        return stats


# ================================
# HEALTH ANALYZER
# ================================

class VehicleHealthAnalyzer:
    """Analyzes vehicle health from session data"""
    
    # Thresholds for health scoring
    THRESHOLDS = {
        'coolant_temp': {'optimal': (82, 100), 'warning': (75, 110), 'critical': (70, 120)},
        'engine_load': {'optimal': (0, 80), 'warning': (0, 90), 'critical': (0, 100)},
        'rpm': {'optimal': (600, 3500), 'warning': (500, 5000), 'critical': (400, 6500)},
        'fuel_trim_total': {'optimal': (-10, 10), 'warning': (-20, 20), 'critical': (-25, 25)},
        'intake_temp': {'optimal': (10, 50), 'warning': (0, 60), 'critical': (-10, 70)},
    }
    
    def analyze_health(self, statistics: Dict, profile: Dict = None) -> Dict[str, Any]:
        """Perform comprehensive health analysis"""
        health = {
            'overall_score': 0,
            'grade': 'N/A',
            'subsystems': {},
            'alerts': [],
            'recommendations': [],
            'predictions': []
        }
        
        if not statistics:
            return health
        
        subsystem_scores = []
        
        # Analyze each subsystem
        health['subsystems']['engine'] = self._analyze_engine(statistics)
        subsystem_scores.append(health['subsystems']['engine']['score'])
        
        health['subsystems']['cooling'] = self._analyze_cooling(statistics)
        subsystem_scores.append(health['subsystems']['cooling']['score'])
        
        health['subsystems']['fuel_system'] = self._analyze_fuel_system(statistics)
        subsystem_scores.append(health['subsystems']['fuel_system']['score'])
        
        health['subsystems']['electrical'] = self._analyze_electrical(statistics)
        subsystem_scores.append(health['subsystems']['electrical']['score'])
        
        # Calculate overall score
        if subsystem_scores:
            health['overall_score'] = sum(subsystem_scores) / len(subsystem_scores)
        
        # Determine grade
        score = health['overall_score']
        if score >= 90:
            health['grade'] = 'A'
        elif score >= 80:
            health['grade'] = 'B'
        elif score >= 70:
            health['grade'] = 'C'
        elif score >= 60:
            health['grade'] = 'D'
        else:
            health['grade'] = 'F'
        
        # Generate alerts and recommendations
        health['alerts'] = self._generate_alerts(health['subsystems'], statistics)
        health['recommendations'] = self._generate_recommendations(health['subsystems'], statistics)
        health['predictions'] = self._generate_predictions(health['subsystems'], statistics)
        
        return health
    
    def _analyze_engine(self, stats: Dict) -> Dict:
        """Analyze engine health"""
        score = 100
        issues = []
        
        # Check RPM stability
        rpm_stats = stats.get('rpm', {})
        if rpm_stats:
            stdev = rpm_stats.get('stdev', 0)
            if stdev > 200:
                score -= 15
                issues.append(f"High RPM variation ({stdev:.0f} RPM)")
            elif stdev > 100:
                score -= 5
        
        # Check engine load patterns
        load_stats = stats.get('engine_load', {})
        if load_stats:
            avg_load = load_stats.get('avg', 50)
            max_load = load_stats.get('max', 100)
            if max_load > 95:
                score -= 10
                issues.append(f"Engine reached high load ({max_load:.1f}%)")
            if avg_load > 60:
                score -= 5
        
        # Check idle stability from derived stats
        idle_stats = stats.get('_derived', {}).get('idle_stability', {})
        if idle_stats:
            if not idle_stats.get('stable', True):
                score -= 10
                issues.append(f"Unstable idle ({idle_stats.get('variation', 0):.0f} RPM variation)")
        
        return {
            'score': max(0, score),
            'status': 'Good' if score >= 80 else ('Fair' if score >= 60 else 'Poor'),
            'issues': issues
        }
    
    def _analyze_cooling(self, stats: Dict) -> Dict:
        """Analyze cooling system health"""
        score = 100
        issues = []
        
        coolant = stats.get('coolant_temp', {})
        if coolant:
            max_temp = coolant.get('max', 85)
            avg_temp = coolant.get('avg', 85)
            
            if max_temp > 110:
                score -= 30
                issues.append(f"Overheating detected ({max_temp:.0f}°C)")
            elif max_temp > 100:
                score -= 15
                issues.append(f"High coolant temperature ({max_temp:.0f}°C)")
            elif max_temp > 95:
                score -= 5
            
            if avg_temp < 75:
                score -= 10
                issues.append("Engine running cold - possible thermostat issue")
        
        intake = stats.get('intake_temp', {})
        if intake:
            avg_intake = intake.get('avg', 35)
            if avg_intake > 55:
                score -= 10
                issues.append(f"High intake air temperature ({avg_intake:.0f}°C)")
        
        return {
            'score': max(0, score),
            'status': 'Good' if score >= 80 else ('Fair' if score >= 60 else 'Poor'),
            'issues': issues
        }
    
    def _analyze_fuel_system(self, stats: Dict) -> Dict:
        """Analyze fuel system health"""
        score = 100
        issues = []
        
        stft = stats.get('short_fuel_trim_1', {})
        ltft = stats.get('long_fuel_trim_1', {})
        
        if stft and ltft:
            stft_avg = stft.get('avg', 0)
            ltft_avg = ltft.get('avg', 0)
            total_trim = stft_avg + ltft_avg
            
            if abs(total_trim) > 25:
                score -= 30
                issues.append(f"Severe fuel trim: {total_trim:+.1f}% ({'Lean' if total_trim > 0 else 'Rich'})")
            elif abs(total_trim) > 15:
                score -= 15
                issues.append(f"High fuel trim: {total_trim:+.1f}%")
            elif abs(total_trim) > 10:
                score -= 5
            
            if abs(ltft_avg) > 15:
                score -= 10
                issues.append(f"Long-term adaptation needed ({ltft_avg:+.1f}%)")
        
        maf = stats.get('maf', {})
        if maf:
            avg_maf = maf.get('avg', 0)
            if avg_maf < 2:
                score -= 5
                issues.append("Low MAF readings - check air filter")
        
        return {
            'score': max(0, score),
            'status': 'Good' if score >= 80 else ('Fair' if score >= 60 else 'Poor'),
            'issues': issues
        }
    
    def _analyze_electrical(self, stats: Dict) -> Dict:
        """Analyze electrical system health"""
        score = 100
        issues = []
        
        voltage = stats.get('battery_voltage', stats.get('CONTROL_MODULE_VOLTAGE', {}))
        if voltage:
            min_v = voltage.get('min', 12.5)
            max_v = voltage.get('max', 14.5)
            avg_v = voltage.get('avg', 13.5)
            
            if min_v < 11.5:
                score -= 25
                issues.append(f"Low voltage detected ({min_v:.1f}V)")
            elif min_v < 12.0:
                score -= 10
                issues.append(f"Voltage dropped to {min_v:.1f}V")
            
            if max_v > 15.0:
                score -= 20
                issues.append(f"High voltage ({max_v:.1f}V) - check alternator")
            elif max_v > 14.7:
                score -= 5
        else:
            score = 80  # No data, assume OK
        
        return {
            'score': max(0, score),
            'status': 'Good' if score >= 80 else ('Fair' if score >= 60 else 'Poor'),
            'issues': issues
        }
    
    def _generate_alerts(self, subsystems: Dict, stats: Dict) -> List[Dict]:
        """Generate alerts from analysis"""
        alerts = []
        
        for name, data in subsystems.items():
            if data['score'] < 60:
                alerts.append({
                    'severity': 'HIGH',
                    'system': name,
                    'message': f"{name.replace('_', ' ').title()} needs attention (Score: {data['score']:.0f}%)",
                    'issues': data.get('issues', [])
                })
            elif data['score'] < 80:
                alerts.append({
                    'severity': 'MEDIUM',
                    'system': name,
                    'message': f"{name.replace('_', ' ').title()} showing minor issues (Score: {data['score']:.0f}%)",
                    'issues': data.get('issues', [])
                })
        
        return alerts
    
    def _generate_recommendations(self, subsystems: Dict, stats: Dict) -> List[str]:
        """Generate maintenance recommendations"""
        recommendations = []
        
        # Cooling system
        cooling = subsystems.get('cooling', {})
        if cooling.get('score', 100) < 80:
            recommendations.append("Check coolant level and condition")
            recommendations.append("Inspect radiator for blockages or leaks")
            recommendations.append("Consider thermostat inspection")
        
        # Fuel system
        fuel = subsystems.get('fuel_system', {})
        if fuel.get('score', 100) < 80:
            recommendations.append("Replace air filter if not done recently")
            recommendations.append("Consider fuel injector cleaning")
            recommendations.append("Check for vacuum leaks")
        
        # Engine
        engine = subsystems.get('engine', {})
        if engine.get('score', 100) < 80:
            recommendations.append("Check spark plugs and ignition system")
            recommendations.append("Inspect throttle body")
            recommendations.append("Check engine mounts")
        
        # Electrical
        electrical = subsystems.get('electrical', {})
        if electrical.get('score', 100) < 80:
            recommendations.append("Test battery condition")
            recommendations.append("Check alternator output")
            recommendations.append("Inspect charging system connections")
        
        if not recommendations:
            recommendations.append("Vehicle systems operating within normal parameters")
            recommendations.append("Continue regular maintenance schedule")
        
        return recommendations
    
    def _generate_predictions(self, subsystems: Dict, stats: Dict) -> List[Dict]:
        """Generate predictive maintenance alerts"""
        predictions = []
        
        cooling = subsystems.get('cooling', {})
        if cooling.get('score', 100) < 70:
            predictions.append({
                'component': 'Cooling System',
                'probability': 65,
                'timeframe': '1-3 months',
                'action': 'Thermostat or water pump inspection recommended'
            })
        
        fuel = subsystems.get('fuel_system', {})
        if fuel.get('score', 100) < 75:
            predictions.append({
                'component': 'Fuel Injectors',
                'probability': 50,
                'timeframe': '3-6 months',
                'action': 'Fuel system cleaning or injector service may be needed'
            })
        
        engine = subsystems.get('engine', {})
        if engine.get('score', 100) < 70:
            predictions.append({
                'component': 'Ignition System',
                'probability': 55,
                'timeframe': '2-4 months',
                'action': 'Spark plug inspection or replacement recommended'
            })
        
        electrical = subsystems.get('electrical', {})
        if electrical.get('score', 100) < 75:
            predictions.append({
                'component': 'Battery',
                'probability': 60,
                'timeframe': '1-2 months',
                'action': 'Battery test and possible replacement'
            })
        
        return predictions


# ================================
# REPORT GENERATOR THREAD
# ================================

class ReportGeneratorThread(QThread):
    """Background thread for report generation"""
    progress = Signal(int, str)
    completed = Signal(dict)
    error = Signal(str)

    def __init__(self, report_type: str, profile: Dict, session_data: Dict,
                 health_analysis: Dict, options: Dict = None):
        super().__init__()
        self.report_type = report_type
        self.profile = profile
        self.session_data = session_data
        self.health_analysis = health_analysis
        self.options = options or {}

    def run(self):
        try:
            self.progress.emit(10, "Initializing report generation...")
            
            if self.report_type == 'comprehensive':
                result = self._generate_comprehensive_report()
            elif self.report_type == 'health':
                result = self._generate_health_report()
            elif self.report_type == 'maintenance':
                result = self._generate_maintenance_report()
            elif self.report_type == 'summary':
                result = self._generate_summary_report()
            else:
                result = {'success': False, 'error': 'Unknown report type'}
            
            self.completed.emit(result)
            
        except Exception as e:
            self.error.emit(str(e))

    def _generate_comprehensive_report(self) -> Dict:
        self.progress.emit(30, "Analyzing session data...")
        self.progress.emit(60, "Generating health assessment...")
        self.progress.emit(90, "Building report...")
        
        report_text = self._build_text_report()
        
        self.progress.emit(100, "Report complete!")
        return {
            'success': True,
            'report_text': report_text,
            'type': 'comprehensive'
        }
    
    def _generate_health_report(self) -> Dict:
        self.progress.emit(50, "Building health report...")
        
        report_text = self._build_health_report()
        
        self.progress.emit(100, "Health report complete!")
        return {
            'success': True,
            'report_text': report_text,
            'type': 'health'
        }
    
    def _generate_maintenance_report(self) -> Dict:
        self.progress.emit(50, "Building maintenance report...")
        
        report_text = self._build_maintenance_report()
        
        self.progress.emit(100, "Maintenance report complete!")
        return {
            'success': True,
            'report_text': report_text,
            'type': 'maintenance'
        }
    
    def _generate_summary_report(self) -> Dict:
        self.progress.emit(50, "Building summary report...")
        
        report_text = self._build_summary_report()
        
        self.progress.emit(100, "Summary report complete!")
        return {
            'success': True,
            'report_text': report_text,
            'type': 'summary'
        }
    
    def _build_text_report(self) -> str:
        """Build comprehensive text report"""
        lines = []
        profile = self.profile or {}
        health = self.health_analysis or {}
        stats = self.session_data.get('statistics', {}) if self.session_data else {}
        
        lines.append("=" * 70)
        lines.append("           PREDICT VEHICLE DIAGNOSTIC REPORT")
        lines.append("=" * 70)
        lines.append("")
        
        # Vehicle Information
        lines.append("▸ VEHICLE INFORMATION")
        lines.append("-" * 40)
        lines.append(f"  Name: {profile.get('name', 'N/A')}")
        lines.append(f"  Make: {profile.get('make', 'N/A')}")
        lines.append(f"  Model: {profile.get('model', 'N/A')}")
        lines.append(f"  Year: {profile.get('year', 'N/A')}")
        lines.append(f"  VIN: {profile.get('vin', 'N/A')}")
        lines.append(f"  License: {profile.get('license_plate', 'N/A')}")
        lines.append("")
        
        # Data Summary
        lines.append("▸ DATA SUMMARY")
        lines.append("-" * 40)
        if self.session_data:
            lines.append(f"  Total Sessions: {self.session_data.get('total_sessions', 1)}")
            lines.append(f"  Total Data Points: {self.session_data.get('total_data_points', len(self.session_data.get('data_points', [])))}")
        lines.append(f"  Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # Health Score
        lines.append("▸ OVERALL HEALTH ASSESSMENT")
        lines.append("-" * 40)
        lines.append(f"  Health Score: {health.get('overall_score', 0):.0f}%")
        lines.append(f"  Grade: {health.get('grade', 'N/A')}")
        lines.append("")
        
        # Subsystem Analysis
        lines.append("▸ SUBSYSTEM ANALYSIS")
        lines.append("-" * 40)
        for name, data in health.get('subsystems', {}).items():
            status_icon = "✓" if data.get('score', 0) >= 80 else ("⚠" if data.get('score', 0) >= 60 else "✗")
            lines.append(f"  {status_icon} {name.replace('_', ' ').title()}: {data.get('score', 0):.0f}% ({data.get('status', 'Unknown')})")
            for issue in data.get('issues', []):
                lines.append(f"      • {issue}")
        lines.append("")
        
        # Sensor Statistics
        lines.append("▸ SENSOR DATA STATISTICS")
        lines.append("-" * 40)
        sensor_names = {
            'rpm': 'Engine RPM',
            'coolant_temp': 'Coolant Temp (°C)',
            'engine_load': 'Engine Load (%)',
            'throttle_position': 'Throttle Position (%)',
            'intake_temp': 'Intake Temp (°C)',
            'maf': 'MAF (g/s)',
            'short_fuel_trim_1': 'Short Fuel Trim (%)',
            'long_fuel_trim_1': 'Long Fuel Trim (%)',
            'timing_advance': 'Timing Advance (°)',
            'speed': 'Speed (km/h)',
            'runtime': 'Runtime (s)',
            'ambient_temp': 'Ambient Temp (°C)'
        }
        
        for key, display_name in sensor_names.items():
            if key in stats:
                s = stats[key]
                lines.append(f"  {display_name}:")
                lines.append(f"      Min: {s.get('min', 0):.1f}  Max: {s.get('max', 0):.1f}  Avg: {s.get('avg', 0):.1f}")
        lines.append("")
        
        # Alerts
        if health.get('alerts'):
            lines.append("▸ ALERTS")
            lines.append("-" * 40)
            for alert in health['alerts']:
                severity = alert.get('severity', 'INFO')
                icon = "🔴" if severity == 'HIGH' else ("🟡" if severity == 'MEDIUM' else "🟢")
                lines.append(f"  {icon} [{severity}] {alert.get('message', '')}")
            lines.append("")
        
        # Recommendations
        if health.get('recommendations'):
            lines.append("▸ MAINTENANCE RECOMMENDATIONS")
            lines.append("-" * 40)
            for i, rec in enumerate(health['recommendations'], 1):
                lines.append(f"  {i}. {rec}")
            lines.append("")
        
        # Predictions
        if health.get('predictions'):
            lines.append("▸ PREDICTIVE MAINTENANCE")
            lines.append("-" * 40)
            for pred in health['predictions']:
                lines.append(f"  • {pred.get('component', 'Unknown')}")
                lines.append(f"      Probability: {pred.get('probability', 0)}%")
                lines.append(f"      Timeframe: {pred.get('timeframe', 'Unknown')}")
                lines.append(f"      Action: {pred.get('action', 'N/A')}")
            lines.append("")
        
        lines.append("=" * 70)
        lines.append("         Report generated by PREDICT Professional Car AI")
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def _build_health_report(self) -> str:
        """Build focused health report"""
        lines = []
        health = self.health_analysis or {}
        profile = self.profile or {}
        
        lines.append("=" * 50)
        lines.append("       VEHICLE HEALTH REPORT")
        lines.append("=" * 50)
        lines.append("")
        lines.append(f"Vehicle: {profile.get('name', 'N/A')} ({profile.get('year', '')} {profile.get('make', '')} {profile.get('model', '')})")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append(f"Overall Health: {health.get('overall_score', 0):.0f}% (Grade {health.get('grade', 'N/A')})")
        lines.append("")
        
        for name, data in health.get('subsystems', {}).items():
            lines.append(f"{name.replace('_', ' ').title()}: {data.get('score', 0):.0f}%")
            for issue in data.get('issues', []):
                lines.append(f"  - {issue}")
        
        return "\n".join(lines)
    
    def _build_maintenance_report(self) -> str:
        """Build maintenance-focused report"""
        lines = []
        health = self.health_analysis or {}
        
        lines.append("=" * 50)
        lines.append("    MAINTENANCE RECOMMENDATIONS")
        lines.append("=" * 50)
        lines.append("")
        
        for i, rec in enumerate(health.get('recommendations', []), 1):
            lines.append(f"{i}. {rec}")
        
        lines.append("")
        lines.append("Predictive Alerts:")
        lines.append("-" * 30)
        
        for pred in health.get('predictions', []):
            lines.append(f"• {pred.get('component', 'Unknown')}: {pred.get('action', 'N/A')}")
        
        return "\n".join(lines)
    
    def _build_summary_report(self) -> str:
        """Build quick summary report"""
        health = self.health_analysis or {}
        profile = self.profile or {}
        
        summary = f"""
VEHICLE SUMMARY - {profile.get('name', 'Unknown')}
{'=' * 40}
Make/Model: {profile.get('year', '')} {profile.get('make', '')} {profile.get('model', '')}
Health Score: {health.get('overall_score', 0):.0f}% (Grade {health.get('grade', 'N/A')})
Status: {'Good Condition' if health.get('overall_score', 0) >= 80 else 'Needs Attention'}
"""
        return summary


# ================================
# REPORTS TAB
# ================================

class ReportsTab(QWidget):
    """Enhanced Reports Tab with session data reading"""
    
    def _get_button_style(self, style_type: str = 'primary') -> str:
        """Get consistent button stylesheet based on style type."""
        styles = {
            'primary': """
                QPushButton {
                    background-color: #C40000;
                    color: #F0F6FC;
                    border: none;
                    padding: 12px 24px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #E53935;
                }
                QPushButton:pressed {
                    background-color: #B71C1C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """,
            'secondary': """
                QPushButton {
                    background-color: #21262D;
                    color: #F0F6FC;
                    border: 1px solid #30363D;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #30363D;
                    border-color: #8B949E;
                }
                QPushButton:pressed {
                    background-color: #161B22;
                }
                QPushButton:disabled {
                    background-color: #161B22;
                    color: #484F58;
                    border-color: #30363D;
                }
            """,
            'danger': """
                QPushButton {
                    background-color: #C40000;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #E53935;
                }
                QPushButton:pressed {
                    background-color: #B71C1C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """,
            'success': """
                QPushButton {
                    background-color: #4CAF50;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #66BB6A;
                }
                QPushButton:pressed {
                    background-color: #388E3C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """,
            'warning': """
                QPushButton {
                    background-color: #FFC107;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #FFB300;
                }
                QPushButton:pressed {
                    background-color: #FF8F00;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """,
            'info': """
                QPushButton {
                    background-color: #2196F3;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #42A5F5;
                }
                QPushButton:pressed {
                    background-color: #1976D2;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """
        }
        return styles.get(style_type, styles['primary'])

    def __init__(self, ai_module=None, get_active_profile=None,
                 get_latest_snapshot=None, get_dtc_codes=None, parent=None):
        super().__init__(parent)
        print("[ReportsTab] Initializing...")
        
        self.ai_module = ai_module
        self.get_active_profile = get_active_profile
        self.get_latest_snapshot = get_latest_snapshot
        self.get_dtc_codes = get_dtc_codes
        
        # Current data
        self.current_session_data = None
        self.current_health_analysis = None
        self.current_profile = None
        self.gen_thread = None
        
        # Initialize data reader and analyzer with error handling
        try:
            self.session_reader = SessionDataReader()
            self.health_analyzer = VehicleHealthAnalyzer()
            print(f"[ReportsTab] Session reader initialized, logs dir: {self.session_reader.logs_directory}")
        except Exception as e:
            print(f"[ReportsTab] Error initializing readers: {e}")
            import traceback
            traceback.print_exc()
            self.session_reader = None
            self.health_analyzer = None
        
        try:
            print("[ReportsTab] Building UI...")
            self._build_ui()
            print("[ReportsTab] UI built successfully")
        except Exception as e:
            print(f"[ReportsTab] Error building UI: {e}")
            import traceback
            traceback.print_exc()
            self._build_fallback_ui(str(e))
            return
        
        try:
            print("[ReportsTab] Refreshing sessions...")
            self._refresh_sessions()
            print("[ReportsTab] Sessions refreshed")
        except Exception as e:
            print(f"[ReportsTab] Error refreshing sessions: {e}")
        
        print("[ReportsTab] Initialization complete")
    
    def _build_fallback_ui(self, error_msg: str):
        """Build a fallback UI when main UI fails"""
        layout = QVBoxLayout(self)
        error_label = QLabel(f"Reports Tab Error: {error_msg}")
        error_label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
        error_label.setWordWrap(True)
        layout.addWidget(error_label)
    
    def _build_ui(self):
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {ProfessionalTheme.BACKGROUND};
                color: {ProfessionalTheme.TEXT_PRIMARY};
            }}
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {ProfessionalTheme.BORDER};
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 15px;
                color: {ProfessionalTheme.PRIMARY};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px;
            }}
            QPushButton {{
                background-color: {ProfessionalTheme.CARD_BG};
                color: {ProfessionalTheme.TEXT_PRIMARY};
                border: 1px solid {ProfessionalTheme.BORDER};
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {ProfessionalTheme.PRIMARY};
                color: white;
            }}
            QListWidget {{
                background-color: {ProfessionalTheme.CARD_BG};
                border: 1px solid {ProfessionalTheme.BORDER};
                border-radius: 5px;
            }}
            QListWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {ProfessionalTheme.BORDER};
            }}
            QListWidget::item:selected {{
                background-color: {ProfessionalTheme.PRIMARY};
            }}
            QTextEdit, QPlainTextEdit {{
                background-color: {ProfessionalTheme.CARD_BG};
                border: 1px solid {ProfessionalTheme.BORDER};
                border-radius: 5px;
                padding: 10px;
                font-family: 'Consolas', monospace;
            }}
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("📊 Reports & Analysis")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title.setStyleSheet(f"color: {ProfessionalTheme.PRIMARY};")
        header.addWidget(title)
        header.addStretch()
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh Sessions")
        refresh_btn.setStyleSheet(self._get_button_style('secondary'))
        refresh_btn.clicked.connect(self._refresh_sessions)
        header.addWidget(refresh_btn)
        
        main_layout.addLayout(header)
        
        # Main content splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - Session selection
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Session list
        sessions_group = QGroupBox("📁 Saved Sessions")
        sessions_layout = QVBoxLayout(sessions_group)
        
        self.session_list = QListWidget()
        self.session_list.itemClicked.connect(self._on_session_selected)
        sessions_layout.addWidget(self.session_list)
        
        # Load button
        load_btn = QPushButton("📥 Load Selected Session")
        load_btn.setStyleSheet(self._get_button_style('primary'))
        load_btn.clicked.connect(self._load_selected_session)
        sessions_layout.addWidget(load_btn)
        
        # Load all for profile
        load_all_btn = QPushButton("📚 Load All Sessions for Profile")
        load_all_btn.setStyleSheet(self._get_button_style('secondary'))
        load_all_btn.clicked.connect(self._load_all_sessions)
        sessions_layout.addWidget(load_all_btn)
        
        left_layout.addWidget(sessions_group)
        
        # Report options
        options_group = QGroupBox("📋 Report Options")
        options_layout = QVBoxLayout(options_group)
        
        self.report_type_combo = QComboBox()
        self.report_type_combo.addItems([
            "Comprehensive Report",
            "Health Analysis",
            "Maintenance Report",
            "Quick Summary"
        ])
        options_layout.addWidget(QLabel("Report Type:"))
        options_layout.addWidget(self.report_type_combo)
        
        generate_btn = QPushButton("📄 Generate Report")
        generate_btn.setStyleSheet(self._get_button_style('primary'))
        generate_btn.clicked.connect(self._generate_report)
        options_layout.addWidget(generate_btn)
        
        # Save report button
        save_btn = QPushButton("💾 Save Report to File")
        save_btn.setStyleSheet(self._get_button_style('secondary'))
        save_btn.clicked.connect(self._save_report)
        options_layout.addWidget(save_btn)
        
        left_layout.addWidget(options_group)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        left_layout.addWidget(self.progress_bar)
        
        left_layout.addStretch()
        
        splitter.addWidget(left_panel)
        
        # Right panel - Report output
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Data info
        self.info_label = QLabel("No session loaded. Select a session from the left panel.")
        self.info_label.setStyleSheet(f"""
            background-color: {ProfessionalTheme.CARD_BG};
            padding: 15px;
            border-radius: 5px;
            color: {ProfessionalTheme.TEXT_SECONDARY};
        """)
        self.info_label.setWordWrap(True)
        right_layout.addWidget(self.info_label)
        
        # Report output
        report_group = QGroupBox("📝 Report Output")
        report_layout = QVBoxLayout(report_group)
        
        self.report_output = QPlainTextEdit()
        self.report_output.setReadOnly(True)
        self.report_output.setFont(QFont("Consolas", 10))
        self.report_output.setPlaceholderText("Generate a report to see results here...")
        report_layout.addWidget(self.report_output)
        
        right_layout.addWidget(report_group)
        
        splitter.addWidget(right_panel)
        splitter.setSizes([350, 650])
        
        main_layout.addWidget(splitter)
    
    def _refresh_sessions(self):
        """Refresh the list of available sessions"""
        self.session_list.clear()
        
        if not self.session_reader:
            item = QListWidgetItem("Session reader not available")
            item.setFlags(Qt.NoItemFlags)
            self.session_list.addItem(item)
            return
        
        # Get profile name if available
        profile_name = None
        if self.get_active_profile:
            try:
                profile = self.get_active_profile()
                if profile:
                    profile_name = profile.get('name')
            except Exception as e:
                print(f"[ReportsTab] Error getting profile: {e}")
        
        # Get all sessions (or filtered by profile)
        try:
            sessions = self.session_reader.get_available_sessions()
        except Exception as e:
            print(f"[ReportsTab] Error getting sessions: {e}")
            item = QListWidgetItem(f"Error loading sessions: {e}")
            item.setFlags(Qt.NoItemFlags)
            self.session_list.addItem(item)
            return
        
        if not sessions:
            item = QListWidgetItem("No sessions found in logs folder")
            item.setFlags(Qt.NoItemFlags)
            self.session_list.addItem(item)
            return
        
        for session in sessions:
            item = QListWidgetItem(
                f"📁 {session['display_name']}\n"
                f"    {session['data_points']} data points"
            )
            item.setData(Qt.UserRole, session)
            self.session_list.addItem(item)
    
    def _on_session_selected(self, item):
        """Handle session selection"""
        session_info = item.data(Qt.UserRole)
        if session_info:
            self.info_label.setText(
                f"Selected: {session_info['display_name']}\n"
                f"Profile: {session_info['profile_name']}\n"
                f"Data Points: {session_info['data_points']}\n"
                f"File: {session_info['filename']}"
            )
    
    def _load_selected_session(self):
        """Load the selected session data"""
        current_item = self.session_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection", "Please select a session first")
            return
        
        session_info = current_item.data(Qt.UserRole)
        if not session_info:
            return
        
        # Load session data
        self.current_session_data = self.session_reader.load_session(session_info['filepath'])
        self.current_profile = self.current_session_data.get('profile', {})
        
        # Analyze health
        self.current_health_analysis = self.health_analyzer.analyze_health(
            self.current_session_data.get('statistics', {}),
            self.current_profile
        )
        
        # Update info label
        stats = self.current_session_data.get('statistics', {})
        data_count = len(self.current_session_data.get('data_points', []))
        
        self.info_label.setText(
            f"✅ Session Loaded: {session_info['display_name']}\n"
            f"Profile: {self.current_profile.get('name', 'N/A')} "
            f"({self.current_profile.get('year', '')} {self.current_profile.get('make', '')} {self.current_profile.get('model', '')})\n"
            f"Data Points: {data_count}\n"
            f"Health Score: {self.current_health_analysis.get('overall_score', 0):.0f}% "
            f"(Grade {self.current_health_analysis.get('grade', 'N/A')})\n"
            f"\nReady to generate report!"
        )
        self.info_label.setStyleSheet(f"""
            background-color: #1a3d1a;
            padding: 15px;
            border-radius: 5px;
            color: {ProfessionalTheme.SUCCESS};
            border-left: 4px solid {ProfessionalTheme.SUCCESS};
        """)
        
        QMessageBox.information(self, "Session Loaded", 
                               f"Loaded {data_count} data points from session.\n"
                               f"Health Score: {self.current_health_analysis.get('overall_score', 0):.0f}%")
    
    def _load_all_sessions(self):
        """Load all sessions for current profile"""
        if not self.session_reader:
            QMessageBox.warning(self, "Error", "Session reader not available")
            return
        
        profile_name = None
        
        # Try to get from loaded session first
        if self.current_profile:
            profile_name = self.current_profile.get('name')
        
        # Or from active profile
        if not profile_name and self.get_active_profile:
            try:
                profile = self.get_active_profile()
                if profile:
                    profile_name = profile.get('name')
            except Exception as e:
                print(f"[ReportsTab] Error getting active profile: {e}")
        
        if not profile_name:
            QMessageBox.warning(self, "No Profile", 
                               "Please load a session first or select an active profile")
            return
        
        # Load combined data
        try:
            combined = self.session_reader.get_combined_data_for_profile(profile_name)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load sessions: {e}")
            return
        
        if not combined:
            QMessageBox.warning(self, "No Data", 
                               f"No session data found for profile: {profile_name}")
            return
        
        self.current_session_data = combined
        self.current_profile = combined.get('profile', {})
        
        # Analyze health
        if self.health_analyzer:
            self.current_health_analysis = self.health_analyzer.analyze_health(
                combined.get('statistics', {}),
                self.current_profile
            )
        else:
            self.current_health_analysis = {'overall_score': 0, 'grade': 'N/A'}
        
        # Update info
        self.info_label.setText(
            f"✅ All Sessions Loaded for: {profile_name}\n"
            f"Total Sessions: {combined.get('total_sessions', 0)}\n"
            f"Total Data Points: {combined.get('total_data_points', 0)}\n"
            f"Health Score: {self.current_health_analysis.get('overall_score', 0):.0f}% "
            f"(Grade {self.current_health_analysis.get('grade', 'N/A')})\n"
            f"\nCombined analysis ready!"
        )
        self.info_label.setStyleSheet(f"""
            background-color: #1a3d1a;
            padding: 15px;
            border-radius: 5px;
            color: {ProfessionalTheme.SUCCESS};
            border-left: 4px solid {ProfessionalTheme.SUCCESS};
        """)
        
        QMessageBox.information(self, "Sessions Loaded", 
                               f"Loaded {combined.get('total_sessions', 0)} sessions with "
                               f"{combined.get('total_data_points', 0)} total data points")
    
    def _generate_report(self):
        """Generate the selected report type"""
        if not self.current_session_data:
            # Try to use live data
            if self.get_latest_snapshot:
                snapshot = self.get_latest_snapshot()
                if snapshot:
                    self.current_session_data = {
                        'data_points': [snapshot],
                        'statistics': self.session_reader._calculate_statistics([snapshot])
                    }
                    if self.get_active_profile:
                        self.current_profile = self.get_active_profile()
                    self.current_health_analysis = self.health_analyzer.analyze_health(
                        self.current_session_data.get('statistics', {}),
                        self.current_profile
                    )
            
            if not self.current_session_data:
                QMessageBox.warning(self, "No Data", 
                                   "Please load a session first or connect to a vehicle")
                return
        
        # Get report type
        report_type_map = {
            "Comprehensive Report": "comprehensive",
            "Health Analysis": "health",
            "Maintenance Report": "maintenance",
            "Quick Summary": "summary"
        }
        report_type = report_type_map.get(self.report_type_combo.currentText(), "comprehensive")
        
        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Start generation thread
        self.gen_thread = ReportGeneratorThread(
            report_type=report_type,
            profile=self.current_profile,
            session_data=self.current_session_data,
            health_analysis=self.current_health_analysis
        )
        self.gen_thread.progress.connect(self._on_progress)
        self.gen_thread.completed.connect(self._on_report_completed)
        self.gen_thread.error.connect(self._on_report_error)
        self.gen_thread.start()
    
    def _on_progress(self, value: int, message: str):
        """Handle progress updates"""
        self.progress_bar.setValue(value)
    
    def _on_report_completed(self, result: Dict):
        """Handle report completion"""
        self.progress_bar.setVisible(False)
        
        if result.get('success'):
            self.report_output.setPlainText(result.get('report_text', ''))
            QMessageBox.information(self, "Report Generated", 
                                   "Report generated successfully!")
        else:
            QMessageBox.warning(self, "Error", 
                               result.get('error', 'Unknown error'))
    
    def _on_report_error(self, error: str):
        """Handle report generation error"""
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Error", f"Report generation failed: {error}")
    
    def _save_report(self):
        """Save report to file"""
        if not self.report_output.toPlainText():
            QMessageBox.warning(self, "No Report", "Generate a report first")
            return
        
        # Get file path
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Report", 
            f"vehicle_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;All Files (*)"
        )
        
        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(self.report_output.toPlainText())
                QMessageBox.information(self, "Saved", f"Report saved to:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save: {e}")