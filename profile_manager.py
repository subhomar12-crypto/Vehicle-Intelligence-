"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Profile Manager
"""

import json
import pandas as pd
import sqlite3
from datetime import datetime
import os
from PySide6.QtWidgets import QProgressDialog, QMessageBox
from PySide6.QtCore import Qt

class ProfileManager:
    """Advanced profile management with export/import and AI insights"""
    
    def __init__(self, db_path='./data/vehicle_profiles.db'):
        self.db_path = db_path
        self.ensure_directories()
    
    def ensure_directories(self):
        """Ensure necessary directories exist"""
        os.makedirs('./data/exports', exist_ok=True)
        os.makedirs('./data/backups', exist_ok=True)
        os.makedirs('./data/imports', exist_ok=True)
    
    def export_profiles(self, profile_ids=None, format='json', include_ai_insights=True, parent_widget=None):
        """
        Export vehicle profiles to various formats
        
        Args:
            profile_ids: List of profile IDs to export (None for all)
            format: 'json', 'excel', 'csv'
            include_ai_insights: Include AI-generated insights
            parent_widget: Parent widget for progress dialogs
        """
        try:
            # Get profiles data
            profiles = self._get_profiles_for_export(profile_ids)
            
            if not profiles:
                return False, "No profiles found to export"
            
            # Generate AI insights if requested
            if include_ai_insights:
                profiles = self._add_ai_insights(profiles, parent_widget)
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if format == 'json':
                return self._export_json(profiles, timestamp)
            elif format == 'excel':
                return self._export_excel(profiles, timestamp)
            elif format == 'csv':
                return self._export_csv(profiles, timestamp)
            else:
                return False, f"Unsupported format: {format}"
                
        except Exception as e:
            return False, f"Export failed: {str(e)}"
    
    def _get_profiles_for_export(self, profile_ids):
        """Get profiles data for export"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if profile_ids:
            placeholders = ','.join('?' * len(profile_ids))
            query = f"""
                SELECT * FROM vehicle_profiles 
                WHERE profile_id IN ({placeholders})
            """
            cursor.execute(query, profile_ids)
        else:
            cursor.execute("SELECT * FROM vehicle_profiles")
        
        profiles = [dict(row) for row in cursor.fetchall()]
        
        # Get related data
        for profile in profiles:
            profile_id = profile['profile_id']
            
            # Get maintenance records
            cursor.execute(
                "SELECT * FROM maintenance_records WHERE vehicle_id = ?",
                (profile_id,)
            )
            profile['maintenance_records'] = [dict(row) for row in cursor.fetchall()]
            
            # Get trip records
            cursor.execute(
                "SELECT * FROM trip_records WHERE vehicle_id = ?",
                (profile_id,)
            )
            profile['trip_records'] = [dict(row) for row in cursor.fetchall()]
            
            # Get cost records
            cursor.execute(
                "SELECT * FROM cost_records WHERE vehicle_id = ?",
                (profile_id,)
            )
            profile['cost_records'] = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return profiles
    
    def _add_ai_insights(self, profiles, parent_widget):
        """Add AI-generated insights to profiles"""
        try:
            from ai_module import generate_comprehensive_insights
            
            if parent_widget:
                progress = QProgressDialog("Generating AI Insights...", "Cancel", 0, len(profiles), parent_widget)
                progress.setWindowModality(Qt.WindowModal)
                progress.show()
            
            for i, profile in enumerate(profiles):
                if parent_widget:
                    progress.setValue(i)
                    progress.setLabelText(f"Analyzing {profile.get('name', 'Unknown')}...")
                    if progress.wasCanceled():
                        break
                
                try:
                    # Generate insights based on profile data
                    insights = generate_comprehensive_insights(profile)
                    profile['ai_insights'] = insights
                    
                    # Add summary metrics
                    profile['export_metrics'] = self._calculate_export_metrics(profile)
                    
                except Exception as e:
                    print(f"❌ AI insights error for {profile.get('name')}: {e}")
                    profile['ai_insights'] = {'error': str(e)}
            
            if parent_widget:
                progress.setValue(len(profiles))
                
        except ImportError:
            print("⚠️ AI module not available for insights")
        
        return profiles
    
    def _calculate_export_metrics(self, profile):
        """Calculate export metrics for profile"""
        maintenance_records = profile.get('maintenance_records', [])
        trip_records = profile.get('trip_records', [])
        cost_records = profile.get('cost_records', [])
        
        total_maintenance_cost = sum(record.get('cost', 0) for record in maintenance_records)
        total_fuel_cost = sum(record.get('fuel_cost', 0) for record in trip_records)
        total_other_costs = sum(record.get('amount', 0) for record in cost_records)
        
        total_distance = sum(record.get('distance', 0) for record in trip_records)
        total_driving_hours = sum(record.get('duration_hours', 0) for record in trip_records)
        
        return {
            'total_maintenance_cost': total_maintenance_cost,
            'total_fuel_cost': total_fuel_cost,
            'total_other_costs': total_other_costs,
            'total_costs': total_maintenance_cost + total_fuel_cost + total_other_costs,
            'total_distance_km': total_distance,
            'total_driving_hours': total_driving_hours,
            'maintenance_count': len(maintenance_records),
            'trip_count': len(trip_records),
            'average_fuel_consumption': self._calculate_avg_fuel_consumption(trip_records),
            'cost_per_km': self._calculate_cost_per_km(total_distance, total_maintenance_cost + total_fuel_cost + total_other_costs)
        }
    
    def _calculate_avg_fuel_consumption(self, trip_records):
        """Calculate average fuel consumption"""
        fuel_records = [r for r in trip_records if r.get('fuel_used') and r.get('distance')]
        if not fuel_records:
            return None
        
        total_fuel = sum(r['fuel_used'] for r in fuel_records)
        total_distance = sum(r['distance'] for r in fuel_records)
        
        if total_distance > 0:
            return (total_fuel / total_distance) * 100  # L/100km
        return None
    
    def _calculate_cost_per_km(self, total_distance, total_cost):
        """Calculate cost per kilometer"""
        if total_distance > 0:
            return total_cost / total_distance
        return None
    
    def _export_json(self, profiles, timestamp):
        """Export profiles to JSON format"""
        filename = f"vehicle_profiles_export_{timestamp}.json"
        filepath = os.path.join('./data/exports', filename)
        
        export_data = {
            'export_info': {
                'timestamp': timestamp,
                'version': '1.0',
                'profile_count': len(profiles),
                'format': 'json'
            },
            'profiles': profiles
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        return True, filepath
    
    def _export_excel(self, profiles, timestamp):
        """Export profiles to Excel format"""
        filename = f"vehicle_profiles_export_{timestamp}.xlsx"
        filepath = os.path.join('./data/exports', filename)
        
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # Main profiles sheet
            profiles_data = []
            for profile in profiles:
                profiles_data.append({
                    'ID': profile.get('profile_id'),
                    'Name': profile.get('name'),
                    'Make': profile.get('make'),
                    'Model': profile.get('model'),
                    'Year': profile.get('year'),
                    'VIN': profile.get('vin'),
                    'Category': profile.get('category'),
                    'Total Distance (km)': profile.get('export_metrics', {}).get('total_distance_km', 0),
                    'Total Costs': profile.get('export_metrics', {}).get('total_costs', 0),
                    'Maintenance Count': profile.get('export_metrics', {}).get('maintenance_count', 0)
                })
            
            if profiles_data:
                df_profiles = pd.DataFrame(profiles_data)
                df_profiles.to_excel(writer, sheet_name='Profiles Summary', index=False)
            
            # Maintenance records sheet
            maintenance_data = []
            for profile in profiles:
                for record in profile.get('maintenance_records', []):
                    maintenance_data.append({
                        'Vehicle': profile.get('name'),
                        'Service Type': record.get('service_type'),
                        'Date': record.get('service_date'),
                        'Cost': record.get('cost'),
                        'Mileage': record.get('mileage'),
                        'Notes': record.get('notes')
                    })
            
            if maintenance_data:
                df_maintenance = pd.DataFrame(maintenance_data)
                df_maintenance.to_excel(writer, sheet_name='Maintenance Records', index=False)
            
            # AI Insights sheet
            insights_data = []
            for profile in profiles:
                ai_insights = profile.get('ai_insights', {})
                if ai_insights and not ai_insights.get('error'):
                    insights_data.append({
                        'Vehicle': profile.get('name'),
                        'Health Score': ai_insights.get('health_score'),
                        'Risk Level': ai_insights.get('risk_assessment', {}).get('overall_risk'),
                        'Key Insights': ' | '.join(ai_insights.get('expert_insights', [])[:3])
                    })
            
            if insights_data:
                df_insights = pd.DataFrame(insights_data)
                df_insights.to_excel(writer, sheet_name='AI Insights', index=False)
        
        return True, filepath
    
    def _export_csv(self, profiles, timestamp):
        """Export profiles to CSV format"""
        filename = f"vehicle_profiles_export_{timestamp}.csv"
        filepath = os.path.join('./data/exports', filename)
        
        # Flatten profile data for CSV
        csv_data = []
        for profile in profiles:
            csv_data.append({
                'id': profile.get('profile_id'),
                'name': profile.get('name'),
                'make': profile.get('make'),
                'model': profile.get('model'),
                'year': profile.get('year'),
                'vin': profile.get('vin'),
                'category': profile.get('category'),
                'total_distance': profile.get('export_metrics', {}).get('total_distance_km', 0),
                'total_costs': profile.get('export_metrics', {}).get('total_costs', 0),
                'maintenance_count': profile.get('export_metrics', {}).get('maintenance_count', 0)
            })
        
        if csv_data:
            df = pd.DataFrame(csv_data)
            df.to_csv(filepath, index=False)
            return True, filepath
        
        return False, "No data to export"
    
    def import_profiles(self, filepath, merge_strategy='skip', parent_widget=None):
        """
        Import vehicle profiles from file
        
        Args:
            filepath: Path to import file
            merge_strategy: 'skip', 'overwrite', 'merge'
            parent_widget: Parent widget for progress dialogs
        """
        try:
            file_ext = os.path.splitext(filepath)[1].lower()
            
            if file_ext == '.json':
                return self._import_json(filepath, merge_strategy, parent_widget)
            elif file_ext in ['.xlsx', '.xls']:
                return self._import_excel(filepath, merge_strategy, parent_widget)
            elif file_ext == '.csv':
                return self._import_csv(filepath, merge_strategy, parent_widget)
            else:
                return False, f"Unsupported file format: {file_ext}"
                
        except Exception as e:
            return False, f"Import failed: {str(e)}"
    
    def _import_json(self, filepath, merge_strategy, parent_widget):
        """Import profiles from JSON file"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        profiles = data.get('profiles', [])
        
        if parent_widget:
            progress = QProgressDialog("Importing Profiles...", "Cancel", 0, len(profiles), parent_widget)
            progress.setWindowModality(Qt.WindowModal)
            progress.show()
        
        imported_count = 0
        skipped_count = 0
        
        for i, profile_data in enumerate(profiles):
            if parent_widget:
                progress.setValue(i)
                progress.setLabelText(f"Importing {profile_data.get('name', 'Unknown')}...")
                if progress.wasCanceled():
                    break
            
            success = self._import_single_profile(profile_data, merge_strategy)
            if success:
                imported_count += 1
            else:
                skipped_count += 1
        
        if parent_widget:
            progress.setValue(len(profiles))
        
        return True, f"Imported {imported_count} profiles, skipped {skipped_count}"
    
    def _import_excel(self, filepath, merge_strategy, parent_widget):
        """Import profiles from Excel file"""
        # This would parse Excel and convert to profile format
        # Implementation depends on your Excel structure
        return False, "Excel import not yet implemented"
    
    def _import_csv(self, filepath, merge_strategy, parent_widget):
        """Import profiles from CSV file"""
        # This would parse CSV and convert to profile format
        # Implementation depends on your CSV structure
        return False, "CSV import not yet implemented"
    
    def _import_single_profile(self, profile_data, merge_strategy):
        """Import a single profile into database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if profile already exists
            cursor.execute(
                "SELECT profile_id FROM vehicle_profiles WHERE vin = ? OR name = ?",
                (profile_data.get('vin'), profile_data.get('name'))
            )
            
            existing = cursor.fetchone()
            
            if existing and merge_strategy == 'skip':
                return False
            
            profile_id = existing[0] if existing else None
            
            if profile_id and merge_strategy == 'overwrite':
                # Update existing profile
                self._update_profile(cursor, profile_id, profile_data)
            elif profile_id and merge_strategy == 'merge':
                # Merge data (complex implementation)
                self._merge_profile(cursor, profile_id, profile_data)
            else:
                # Insert new profile
                profile_id = self._insert_profile(cursor, profile_data)
            
            # Import related records
            if profile_id:
                self._import_related_records(cursor, profile_id, profile_data)
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"❌ Import error: {e}")
            return False
    
    def _insert_profile(self, cursor, profile_data):
        """Insert new profile"""
        cursor.execute('''
            INSERT INTO vehicle_profiles (
                name, make, model, year, vin, license_plate, category,
                engine_type, transmission, fuel_type, drivetrain, color,
                purchase_date, last_service_date, dealer_info, warranty_info,
                insurance_details, is_favorite, is_connected
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            profile_data.get('name'),
            profile_data.get('make'),
            profile_data.get('model'),
            profile_data.get('year'),
            profile_data.get('vin'),
            profile_data.get('license_plate'),
            profile_data.get('category', 'Personal'),
            profile_data.get('engine_type'),
            profile_data.get('transmission'),
            profile_data.get('fuel_type'),
            profile_data.get('drivetrain'),
            profile_data.get('color'),
            profile_data.get('purchase_date'),
            profile_data.get('last_service_date'),
            profile_data.get('dealer_info'),
            profile_data.get('warranty_info'),
            profile_data.get('insurance_details'),
            profile_data.get('is_favorite', False),
            profile_data.get('is_connected', False)
        ))
        
        return cursor.lastrowid
    
    def _update_profile(self, cursor, profile_id, profile_data):
        """Update existing profile"""
        cursor.execute('''
            UPDATE vehicle_profiles SET
                name=?, make=?, model=?, year=?, vin=?, license_plate=?, category=?,
                engine_type=?, transmission=?, fuel_type=?, drivetrain=?, color=?,
                purchase_date=?, last_service_date=?, dealer_info=?, warranty_info=?,
                insurance_details=?, is_favorite=?, is_connected=?
            WHERE profile_id=?
        ''', (
            profile_data.get('name'),
            profile_data.get('make'),
            profile_data.get('model'),
            profile_data.get('year'),
            profile_data.get('vin'),
            profile_data.get('license_plate'),
            profile_data.get('category', 'Personal'),
            profile_data.get('engine_type'),
            profile_data.get('transmission'),
            profile_data.get('fuel_type'),
            profile_data.get('drivetrain'),
            profile_data.get('color'),
            profile_data.get('purchase_date'),
            profile_data.get('last_service_date'),
            profile_data.get('dealer_info'),
            profile_data.get('warranty_info'),
            profile_data.get('insurance_details'),
            profile_data.get('is_favorite', False),
            profile_data.get('is_connected', False),
            profile_id
        ))
    
    def _merge_profile(self, cursor, profile_id, profile_data):
        """Merge profile data (simplified - in practice would be more sophisticated)"""
        # For now, just update non-empty fields
        # This would need more sophisticated merging logic
        self._update_profile(cursor, profile_id, profile_data)
    
    def _import_related_records(self, cursor, profile_id, profile_data):
        """Import related records (maintenance, trips, costs)"""
        # Import maintenance records
        for record in profile_data.get('maintenance_records', []):
            cursor.execute('''
                INSERT OR REPLACE INTO maintenance_records 
                (vehicle_id, service_type, service_date, cost, mileage, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                profile_id,
                record.get('service_type'),
                record.get('service_date'),
                record.get('cost'),
                record.get('mileage'),
                record.get('notes')
            ))
        
        # Similar implementations for trip_records and cost_records
        # ... (implementation would go here)
    
    def create_backup(self, backup_name=None):
        """Create a database backup"""
        if not backup_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"vehicle_profiles_backup_{timestamp}.db"
        
        backup_path = os.path.join('./data/backups', backup_name)
        
        try:
            # Simple file copy for SQLite
            import shutil
            shutil.copy2(self.db_path, backup_path)
            return True, backup_path
        except Exception as e:
            return False, f"Backup failed: {str(e)}"
    
    def restore_backup(self, backup_path):
        """Restore database from backup"""
        try:
            import shutil
            shutil.copy2(backup_path, self.db_path)
            return True, "Backup restored successfully"
        except Exception as e:
            return False, f"Restore failed: {str(e)}"
    
    def list_backups(self):
        """List available backups"""
        backup_dir = './data/backups'
        if not os.path.exists(backup_dir):
            return []
        
        backups = []
        for filename in os.listdir(backup_dir):
            if filename.endswith('.db'):
                filepath = os.path.join(backup_dir, filename)
                stat = os.stat(filepath)
                backups.append({
                    'name': filename,
                    'path': filepath,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime)
                })
        
        return sorted(backups, key=lambda x: x['modified'], reverse=True)

# Convenience functions
def export_profiles(profile_ids=None, format='json'):
    """Convenience function for quick export"""
    manager = ProfileManager()
    return manager.export_profiles(profile_ids, format)

def import_profiles(filepath):
    """Convenience function for quick import"""
    manager = ProfileManager()
    return manager.import_profiles(filepath)

if __name__ == "__main__":
    # Test the profile manager
    manager = ProfileManager()
    
    # Test export
    success, result = manager.export_profiles()
    if success:
        print(f"✅ Export successful: {result}")
    else:
        print(f"❌ Export failed: {result}")
    
    # Test backup
    success, result = manager.create_backup()
    if success:
        print(f"✅ Backup created: {result}")
    
    # List backups
    backups = manager.list_backups()
    print(f"📂 Available backups: {len(backups)}")
    for backup in backups[:3]:
        print(f"  - {backup['name']} ({backup['size']} bytes)")