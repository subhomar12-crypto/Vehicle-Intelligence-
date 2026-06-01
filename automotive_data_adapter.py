"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Automotive Data Adapter

Universal Automotive Dataset Adapter
=====================================

This script automatically converts ANY automotive dataset to the format your AI expects.

Expected Format by Your AI:
- timestamp: datetime
- vehicle_id: unique identifier
- rpm: engine RPM
- speed_kmh: vehicle speed
- coolant_temp_c: coolant temperature
- engine_load_pct: engine load percentage
- battery_voltage_v: battery voltage
- overall_failure_7d: failure flag (0/1) within next 7 days

This adapter intelligently maps various column names and creates missing columns.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import glob


class AutomotiveDataAdapter:
    """
    Converts any automotive dataset to standardized format.
    """
    
    def __init__(self):
        # Column mapping dictionary - maps common variations to standard names
        self.column_mappings = {
            'timestamp': [
                'timestamp', 'time', 'datetime', 'date_time', 'date', 
                'record_time', 'measurement_time', 'sample_time'
            ],
            'vehicle_id': [
                'vehicle_id', 'car_id', 'id', 'vehicle', 'car', 
                'vin', 'device_id', 'unit_id', 'truck_id'
            ],
            'rpm': [
                'rpm', 'engine_rpm', 'revolutions', 'engine_speed',
                'rotational_speed', 'motor_rpm'
            ],
            'speed_kmh': [
                'speed', 'speed_kmh', 'vehicle_speed', 'speed_km_h',
                'velocity', 'speed_kph', 'kmh', 'km_h'
            ],
            'coolant_temp_c': [
                'coolant_temp', 'coolant_temperature', 'engine_coolant_temp',
                'coolant_temp_c', 'engine_temperature', 'engine_temp',
                'coolant_temp_celsius'
            ],
            'engine_load_pct': [
                'engine_load', 'load', 'engine_load_pct', 'engine_load_percent',
                'calculated_engine_load', 'load_percentage'
            ],
            'battery_voltage_v': [
                'battery_voltage', 'voltage', 'battery_v', 'battery_voltage_v',
                'battery', 'system_voltage'
            ],
            'overall_failure_7d': [
                'failure', 'failure_flag', 'anomaly', 'needs_maintenance',
                'maintenance_required', 'fault', 'overall_failure_7d',
                'anomaly_indication', 'target', 'label'
            ]
        }
        
        # Sensor value ranges for validation
        self.value_ranges = {
            'rpm': (0, 8000),
            'speed_kmh': (0, 250),
            'coolant_temp_c': (-40, 150),
            'engine_load_pct': (0, 100),
            'battery_voltage_v': (10, 16)
        }
        
    def find_column(self, df, target_column):
        """
        Find the actual column name in dataframe that matches target column.
        Case-insensitive matching.
        """
        df_columns_lower = [col.lower() for col in df.columns]
        
        for possible_name in self.column_mappings[target_column]:
            if possible_name.lower() in df_columns_lower:
                # Return original column name (preserving case)
                idx = df_columns_lower.index(possible_name.lower())
                return df.columns[idx]
        
        return None
    
    def create_synthetic_column(self, df, column_name):
        """
        Create synthetic data for missing columns based on available data.
        """
        n_rows = len(df)
        
        if column_name == 'timestamp':
            # Create timestamps at 1-second intervals
            start_time = datetime(2024, 1, 1, 0, 0, 0)
            return [start_time + timedelta(seconds=i) for i in range(n_rows)]
        
        elif column_name == 'vehicle_id':
            # Create vehicle IDs based on row groups (assume 1000 rows per vehicle)
            return [f"vehicle_{i // 1000 + 1:04d}" for i in range(n_rows)]
        
        elif column_name == 'rpm':
            # Synthetic RPM based on speed if available
            if 'speed_kmh' in df.columns:
                # Rough approximation: RPM ≈ speed * 40 (varies by gear)
                return df['speed_kmh'] * 40 + np.random.normal(0, 100, n_rows)
            else:
                # Random realistic RPM values
                return np.random.uniform(800, 4000, n_rows)
        
        elif column_name == 'speed_kmh':
            # Synthetic speed - random driving pattern
            return np.abs(np.random.normal(50, 25, n_rows))
        
        elif column_name == 'coolant_temp_c':
            # Synthetic coolant temp - normal operating range
            return np.random.normal(90, 5, n_rows)
        
        elif column_name == 'engine_load_pct':
            # Synthetic engine load
            if 'speed_kmh' in df.columns:
                # Higher speed = higher load (simplified)
                return (df['speed_kmh'] / 2.5) + np.random.normal(0, 5, n_rows)
            else:
                return np.random.uniform(20, 70, n_rows)
        
        elif column_name == 'battery_voltage_v':
            # Synthetic battery voltage - normal range
            return np.random.normal(13.8, 0.3, n_rows)
        
        elif column_name == 'overall_failure_7d':
            # Synthetic failure labels based on heuristics
            failure = np.zeros(n_rows)
            
            # Create some failures based on extreme sensor values
            if 'coolant_temp_c' in df.columns:
                failure[df['coolant_temp_c'] > 105] = 1
            if 'battery_voltage_v' in df.columns:
                failure[df['battery_voltage_v'] < 12.0] = 1
            if 'engine_load_pct' in df.columns:
                failure[df['engine_load_pct'] > 95] = 1
            
            return failure
        
        return None
    
    def validate_and_clip(self, df, column, min_val, max_val):
        """
        Validate sensor values and clip to realistic ranges.
        """
        if column in df.columns:
            # Replace infinite values with NaN
            df[column] = df[column].replace([np.inf, -np.inf], np.nan)
            
            # Clip to valid range
            df[column] = df[column].clip(min_val, max_val)
            
            # Fill NaN with median (safe default)
            median_val = df[column].median()
            df[column] = df[column].fillna(median_val)
        
        return df
    
    def adapt_dataset(self, input_file, output_file=None, log_callback=None):
        """
        Main function to adapt any dataset to expected format.
        
        Parameters:
        -----------
        input_file : str
            Path to input CSV file
        output_file : str, optional
            Path to output CSV file. If None, auto-generated.
        log_callback : callable, optional
            Function to call with log messages
        
        Returns:
        --------
        pd.DataFrame : Adapted dataframe
        str : Output file path
        """
        def log(msg):
            if log_callback:
                log_callback(msg)
            else:
                print(msg)
        
        log(f"\n{'='*80}")
        log(f"🔄 Adapting Dataset: {os.path.basename(input_file)}")
        log(f"{'='*80}\n")
        
        # Load the dataset
        try:
            df = pd.read_csv(input_file)
            log(f"✅ Loaded dataset: {len(df)} rows, {len(df.columns)} columns")
            log(f"   Original columns: {list(df.columns)}\n")
        except Exception as e:
            log(f"❌ Error loading file: {e}")
            return None, None
        
        # Create new dataframe with expected columns
        adapted_df = pd.DataFrame()
        
        # Required columns for your AI
        required_columns = [
            'timestamp', 'vehicle_id', 'rpm', 'speed_kmh', 
            'coolant_temp_c', 'engine_load_pct', 'battery_voltage_v',
            'overall_failure_7d'
        ]
        
        log("📋 Column Mapping:")
        log("-" * 80)
        
        for required_col in required_columns:
            # Try to find existing column
            existing_col = self.find_column(df, required_col)
            
            if existing_col:
                # Map existing column
                adapted_df[required_col] = df[existing_col]
                log(f"✅ {required_col:20s} <- {existing_col}")
            else:
                # Create synthetic column
                adapted_df[required_col] = self.create_synthetic_column(df, required_col)
                log(f"🔧 {required_col:20s} <- CREATED (synthetic data)")
        
        log("-" * 80)
        log("")
        
        # Validate and clip sensor values
        log("🔍 Validating Sensor Ranges:")
        log("-" * 80)
        
        for column, (min_val, max_val) in self.value_ranges.items():
            if column in adapted_df.columns:
                before_clip = adapted_df[column].describe()
                adapted_df = self.validate_and_clip(adapted_df, column, min_val, max_val)
                after_clip = adapted_df[column].describe()
                
                clipped = (before_clip['max'] > max_val) or (before_clip['min'] < min_val)
                status = "⚠️  CLIPPED" if clipped else "✅ OK"
                
                log(f"{status} {column:20s} : [{min_val:6.1f}, {max_val:6.1f}] "
                      f"(actual: [{after_clip['min']:6.1f}, {after_clip['max']:6.1f}])")
        
        log("-" * 80)
        log("")
        
        # Convert timestamp to datetime if it's not already
        if adapted_df['timestamp'].dtype == 'object':
            try:
                adapted_df['timestamp'] = pd.to_datetime(adapted_df['timestamp'])
                log("✅ Converted timestamp to datetime format\n")
            except:
                log("⚠️  Timestamp is synthetic (sequential)\n")
        
        # Sort by timestamp and vehicle_id
        adapted_df = adapted_df.sort_values(['vehicle_id', 'timestamp'])
        adapted_df = adapted_df.reset_index(drop=True)
        
        # Generate output filename if not provided
        if output_file is None:
            base_name = os.path.splitext(os.path.basename(input_file))[0]
            output_dir = os.path.join(os.path.dirname(input_file), 'adapted')
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{base_name}_adapted.csv")
        
        # Save adapted dataset
        adapted_df.to_csv(output_file, index=False)
        
        # Print summary statistics
        log("📊 Adapted Dataset Summary:")
        log("-" * 80)
        log(f"Total Rows:       {len(adapted_df):,}")
        log(f"Unique Vehicles:  {adapted_df['vehicle_id'].nunique():,}")
        log(f"Failures:         {adapted_df['overall_failure_7d'].sum():,} "
              f"({adapted_df['overall_failure_7d'].mean()*100:.2f}%)")
        log(f"Time Range:       {adapted_df['timestamp'].min()} to {adapted_df['timestamp'].max()}")
        log(f"\nOutput File:      {output_file}")
        log("-" * 80)
        log("")
        
        return adapted_df, output_file
