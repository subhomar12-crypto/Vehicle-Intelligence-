"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Ai Auto Retraining

AI Auto-Retraining Scheduler
Automatically retrains AI models daily for maximum efficiency
"""

import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import schedule
from config import get_config
from advanced_model_factory import ModelArchitecture, get_model_factory

CONFIG = get_config()
logger = logging.getLogger(__name__)

# Import LSTM predictor for training
try:
    from lstm_predictor import LSTMPredictor
    LSTM_AVAILABLE = True
except ImportError as e:
    LSTM_AVAILABLE = False
    logger.warning(f"LSTM predictor not available: {e}")

try:
    from training_data_pipeline import TrainingDataPipeline, get_training_pipeline
    TRAINING_PIPELINE_AVAILABLE = True
except ImportError as e:
    TRAINING_PIPELINE_AVAILABLE = False
    logger.warning(f"Training data pipeline not available: {e}")

# Import new architectures
try:
    from cnn_lstm_model import get_cnn_lstm_model
    CNN_LSTM_AVAILABLE = True
except ImportError as e:
    CNN_LSTM_AVAILABLE = False
    logger.warning(f"CNN-LSTM model not available: {e}")

try:
    from attention_lstm_model import get_attention_lstm_model
    ATTENTION_LSTM_AVAILABLE = True
except ImportError as e:
    ATTENTION_LSTM_AVAILABLE = False
    logger.warning(f"Attention-LSTM model not available: {e}")

try:
    from lstm_autoencoder import get_lstm_autoencoder
    AUTOENCODER_AVAILABLE = True
except ImportError as e:
    AUTOENCODER_AVAILABLE = False
    logger.warning(f"LSTM Autoencoder not available: {e}")


class AIAutoRetrainingScheduler:
    """
    Manages automatic daily retraining of AI models
    - Trains global model (all vehicles)
    - Trains brand-specific models (per brand)
    - Trains vehicle-specific models (per vehicle with enough data)
    """

    def __init__(self, enhanced_ai_learning, historical_data_manager, vehicle_manager):
        """
        Initialize auto-retraining scheduler

        Args:
            enhanced_ai_learning: EnhancedAILearning instance
            historical_data_manager: HistoricalDataManager instance
            vehicle_manager: VehicleProfileManager instance
        """
        self.ai_learning = enhanced_ai_learning
        self.historical_data = historical_data_manager
        self.vehicle_manager = vehicle_manager

        self.is_running = False
        self.scheduler_thread = None
        self.last_training_time = None
        self.training_in_progress = False
        self.incremental_threshold = 100  # Number of new samples to trigger incremental learning
        self.last_sample_count = 0  # Track sample count for incremental learning

        logger.info("AI Auto-Retraining Scheduler initialized")

    def start(self, training_time='03:00', sync_on_startup=True):
        """
        Start automatic retraining scheduler

        Args:
            training_time: Time to run daily training (HH:MM format, 24-hour)
            sync_on_startup: If True, sync and learn immediately on startup
        """
        if self.is_running:
            logger.warning("Scheduler already running")
            return

        self.is_running = True

        # Schedule daily training
        schedule.every().day.at(training_time).do(self._run_daily_training)

        # Start scheduler thread
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()

        logger.info(f"✅ Auto-retraining started - Daily training at {training_time}")

        # IMMEDIATE SYNC: Learn from all server data that accumulated while Desktop was closed
        if sync_on_startup:
            logger.info("=" * 60)
            logger.info("🚀 STARTUP: Syncing server data and training AI models...")
            logger.info("=" * 60)
            # Run in background thread to not block startup
            startup_thread = threading.Thread(target=self._run_startup_sync, daemon=True)
            startup_thread.start()

    def _run_startup_sync(self):
        """Run sync and training on application startup"""
        try:
            # Step 1: Sync data from server
            logger.info("[Startup Sync] Syncing data from server database...")
            self._sync_obd_server_to_historical()

            # Step 2: Check if we have enough data for training
            sample_count = self._get_total_sample_count()
            logger.info(f"[Startup Sync] Total samples available: {sample_count}")

            # Step 3: If we have new data, train models
            if sample_count >= 100:  # Minimum for meaningful training
                logger.info("[Startup Sync] Sufficient data - training models...")
                results = self._run_training_with_sync()

                if results.get('success'):
                    logger.info(f"✅ [Startup Sync] Training completed: {results}")
                else:
                    logger.warning(f"⚠️ [Startup Sync] Training skipped: {results.get('reason', 'Unknown reason')}")
            else:
                logger.info(f"[Startup Sync] Not enough data for training (need 100+, have {sample_count})")

            logger.info("=" * 60)
            logger.info("✅ STARTUP: Server sync complete")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"[Startup Sync] Error during startup sync: {e}")

    def _run_training_with_sync(self) -> dict:
        """Run training with server sync (used by startup sync)"""
        try:
            results = {'success': True, 'models_trained': []}

            # Train global model
            global_result = self.ai_learning.train_global_model(self.historical_data, min_samples=100)
            if global_result.get('success'):
                results['models_trained'].append('global')
                logger.info(f"  ✅ Global model trained")

            # Train brand models
            brands = self._get_unique_brands()
            for brand in brands:
                brand_result = self.ai_learning.train_brand_model(brand, self.historical_data, min_samples=50)
                if brand_result.get('success'):
                    results['models_trained'].append(f'brand_{brand}')
                    logger.info(f"  ✅ Brand model trained: {brand}")

            # Train vehicle models
            profiles = self.vehicle_manager.get_all_profiles()
            for profile in profiles:
                profile_id = profile.get('profile_id')
                profile_name = profile.get('name', f'Profile_{profile_id}')
                if profile_id:
                    vehicle_result = self.ai_learning.train_vehicle_model(
                        profile_id, self.historical_data, min_samples=30
                    )
                    if vehicle_result.get('success'):
                        results['models_trained'].append(f'vehicle_{profile_name}')
                        logger.info(f"  ✅ Vehicle model trained: {profile_name}")

            return results

        except Exception as e:
            logger.error(f"Error in training with sync: {e}")
            return {'success': False, 'reason': str(e)}

    def stop(self):
        """Stop the scheduler"""
        self.is_running = False
        schedule.clear()
        logger.info("Auto-retraining scheduler stopped")

    def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.is_running:
            try:
                schedule.run_pending()
                
                # Check for incremental learning (every 5 minutes)
                # This triggers quick retraining when enough new data accumulates
                from datetime import datetime, timedelta
                now = datetime.now()
                if not hasattr(self, '_last_incremental_check'):
                    self._last_incremental_check = now
                    self.last_sample_count = self._get_total_sample_count()
                
                # Check every 5 minutes
                if (now - self._last_incremental_check) >= timedelta(minutes=5):
                    self._last_incremental_check = now
                    
                    # Check if we should trigger incremental learning
                    check_result = self.check_incremental_learning()
                    if check_result.get('triggered'):
                        logger.info("🚀 Incremental learning triggered automatically")
                
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(60)

    def _sync_obd_server_to_historical(self):
        """
        Sync data from Previlium OBD Server database to historical data archive.
        This ensures AI training uses ALL available data from both desktop and mobile sources.
        """
        import sqlite3
        from datetime import datetime, timedelta
        from pathlib import Path
        
        server_db = CONFIG.SERVER_DB_PATH
        
        if not Path(server_db).exists():
            logger.info("No server OBD database found - skipping sync")
            return
        
        try:
            conn = sqlite3.connect(str(server_db))
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            # Get records from last 24 hours not yet synced
            # We track sync by timestamp to avoid reprocessing
            cutoff = (datetime.now() - timedelta(hours=24)).timestamp()
            
            # Sync from vehicle_data table (Android app data)
            # This table has the actual mobile OBD data from PredictOBD app
            # Get ALL relevant OBD parameters and expand them as individual records
            all_rows = []

            # RPM data
            c.execute('''
                SELECT vehicle_id as device_id, profile_id, timestamp as ts, '0C' as pid, 'RPM' as name, rpm as value, 'rpm' as unit
                FROM vehicle_data WHERE timestamp > ? AND rpm IS NOT NULL AND profile_id IS NOT NULL
            ''', (cutoff,))
            all_rows.extend(c.fetchall())

            # Speed data
            c.execute('''
                SELECT vehicle_id as device_id, profile_id, timestamp as ts, '0D' as pid, 'Speed' as name, speed as value, 'km/h' as unit
                FROM vehicle_data WHERE timestamp > ? AND speed IS NOT NULL AND profile_id IS NOT NULL
            ''', (cutoff,))
            all_rows.extend(c.fetchall())

            # Coolant temp
            c.execute('''
                SELECT vehicle_id as device_id, profile_id, timestamp as ts, '05' as pid, 'Coolant Temp' as name, coolant_temp as value, '°C' as unit
                FROM vehicle_data WHERE timestamp > ? AND coolant_temp IS NOT NULL AND profile_id IS NOT NULL
            ''', (cutoff,))
            all_rows.extend(c.fetchall())

            # Battery voltage
            c.execute('''
                SELECT vehicle_id as device_id, profile_id, timestamp as ts, '42' as pid, 'Battery Voltage' as name, battery_voltage as value, 'V' as unit
                FROM vehicle_data WHERE timestamp > ? AND battery_voltage IS NOT NULL AND profile_id IS NOT NULL
            ''', (cutoff,))
            all_rows.extend(c.fetchall())

            # Engine load
            c.execute('''
                SELECT vehicle_id as device_id, profile_id, timestamp as ts, '04' as pid, 'Engine Load' as name, engine_load as value, '%' as unit
                FROM vehicle_data WHERE timestamp > ? AND engine_load IS NOT NULL AND profile_id IS NOT NULL
            ''', (cutoff,))
            all_rows.extend(c.fetchall())

            # Throttle position
            c.execute('''
                SELECT vehicle_id as device_id, profile_id, timestamp as ts, '11' as pid, 'Throttle Position' as name, throttle_pos as value, '%' as unit
                FROM vehicle_data WHERE timestamp > ? AND throttle_pos IS NOT NULL AND profile_id IS NOT NULL
            ''', (cutoff,))
            all_rows.extend(c.fetchall())

            # Intake temp
            c.execute('''
                SELECT vehicle_id as device_id, profile_id, timestamp as ts, '0F' as pid, 'Intake Temp' as name, intake_temp as value, '°C' as unit
                FROM vehicle_data WHERE timestamp > ? AND intake_temp IS NOT NULL AND profile_id IS NOT NULL
            ''', (cutoff,))
            all_rows.extend(c.fetchall())

            # MAF rate
            c.execute('''
                SELECT vehicle_id as device_id, profile_id, timestamp as ts, '10' as pid, 'MAF' as name, maf_rate as value, 'g/s' as unit
                FROM vehicle_data WHERE timestamp > ? AND maf_rate IS NOT NULL AND profile_id IS NOT NULL
            ''', (cutoff,))
            all_rows.extend(c.fetchall())

            rows = all_rows
            conn.close()
            
            if not rows:
                logger.info("No new server records to sync")
                return
            
            # Group by profile_id and append to historical data
            from collections import defaultdict
            by_profile = defaultdict(list)
            
            for row in rows:
                profile_id = row['profile_id']
                if profile_id:
                    by_profile[profile_id].append({
                        'device_id': row['device_id'],
                        'timestamp': row['ts'],
                        'pid': row['pid'],
                        'name': row['name'],
                        'value': row['value'],
                        'unit': row['unit']
                    })
            
            # Append to historical data manager
            for profile_id, records in by_profile.items():
                try:
                    # Get profile info
                    profile = self.vehicle_manager.get_profile(profile_id)
                    profile_name = profile.get('name', f'Profile_{profile_id}') if profile else f'Profile_{profile_id}'

                    # Append each record individually
                    for record in records:
                        self.historical_data.append_obd_data(profile_name, profile_id, record)

                    logger.info(f"Synced {len(records)} records for profile {profile_name}")
                except Exception as e:
                    logger.error(f"Failed to sync profile {profile_id}: {e}")
            
            logger.info(f"Server sync complete: {len(rows)} total records processed")
            
        except Exception as e:
            logger.error(f"Error syncing server OBD data: {e}")
    
    def _run_daily_training(self):
        """
        Execute daily training routine
        This is the main training orchestrator
        """
        if self.training_in_progress:
            logger.warning("Training already in progress, skipping...")
            return

        try:
            self.training_in_progress = True
            logger.info("=" * 60)
            logger.info("🚀 Starting Daily AI Training Session")
            logger.info("=" * 60)
            
            # CRITICAL: Sync server data BEFORE training
            self._sync_obd_server_to_historical()

            start_time = datetime.now()
            results = {
                'start_time': start_time.isoformat(),
                'global': None,
                'brands': {},
                'vehicles': {},
                'errors': []
            }

            # Step 1: Train Global Model (learns from ALL vehicles)
            logger.info("\n[Step 1/3] Training Global Model...")
            try:
                global_result = self.ai_learning.train_global_model(
                    self.historical_data,
                    min_samples=1000
                )
                results['global'] = global_result

                if global_result.get('success'):
                    logger.info(f"✅ Global model trained successfully!")
                    logger.info(f"   Samples: {global_result.get('samples_trained')}")
                    logger.info(f"   Test Score: {global_result.get('test_score', 0):.3f}")
                else:
                    logger.warning(f"⚠️ Global model training failed: {global_result.get('error')}")

            except Exception as e:
                error_msg = f"Global model training error: {e}"
                logger.error(error_msg)
                results['errors'].append(error_msg)

            # Step 2: Train Brand-Specific Models
            logger.info("\n[Step 2/3] Training Brand-Specific Models...")
            brands = self._get_unique_brands()

            for brand in brands:
                try:
                    logger.info(f"   Training {brand} model...")
                    brand_result = self.ai_learning.train_brand_model(
                        brand,
                        self.historical_data,
                        min_samples=500
                    )
                    results['brands'][brand] = brand_result

                    if brand_result.get('success'):
                        logger.info(f"   ✅ {brand} model trained (Score: {brand_result.get('test_score', 0):.3f})")
                    else:
                        logger.warning(f"   ⚠️ {brand} model skipped: {brand_result.get('error')}")

                except Exception as e:
                    error_msg = f"{brand} model error: {e}"
                    logger.error(f"   ❌ {error_msg}")
                    results['errors'].append(error_msg)

            # Step 3: Train Vehicle-Specific Models
            logger.info("\n[Step 3/3] Training Vehicle-Specific Models...")
            profiles = self.vehicle_manager.get_all_profiles()

            for profile in profiles:
                profile_name = profile.get('name')
                profile_id = profile.get('profile_id')

                try:
                    logger.info(f"   Training model for {profile_name}...")
                    vehicle_result = self.ai_learning.train_vehicle_model(
                        profile_name,
                        profile_id,
                        self.historical_data,
                        min_samples=200
                    )

                    vehicle_key = f"{profile_name}_{profile_id}"
                    results['vehicles'][vehicle_key] = vehicle_result

                    if vehicle_result.get('success'):
                        logger.info(f"   ✅ {profile_name} model trained (Score: {vehicle_result.get('test_score', 0):.3f})")
                    else:
                        if vehicle_result.get('fallback'):
                            logger.info(f"   ℹ️ {profile_name} will use brand/global model")
                        else:
                            logger.warning(f"   ⚠️ {profile_name} skipped: {vehicle_result.get('error')}")

                except Exception as e:
                    error_msg = f"{profile_name} model error: {e}"
                    logger.error(f"   ❌ {error_msg}")
                    results['errors'].append(error_msg)

            # Step 4: Train Advanced AI Models
            logger.info("\n[Step 4/5] Training Advanced AI Models...")
            results['advanced_models'] = {}
            try:
                advanced_results = self._train_advanced_models()
                results['advanced_models'] = advanced_results

                successful_models = [k for k, v in advanced_results.items() if v.get('success')]
                if successful_models:
                    logger.info(f"   ✅ Advanced models trained: {', '.join(successful_models)}")
                else:
                    logger.warning("   ⚠️ No advanced models trained successfully")

            except Exception as e:
                error_msg = f"Advanced model training error: {e}"
                logger.error(f"   ❌ {error_msg}")
                results['errors'].append(error_msg)

            # Step 5: Train LSTM Models (Legacy)
            logger.info("\n[Step 5/5] Training LSTM Deep Learning Models...")
            results['lstm'] = None
            try:
                lstm_result = self._train_lstm_models()
                results['lstm'] = lstm_result

                if lstm_result.get('success'):
                    logger.info(f"   ✅ LSTM model trained successfully!")
                    logger.info(f"      Samples: {lstm_result.get('samples_trained', 0)}")
                    logger.info(f"      Version: {lstm_result.get('version', 'N/A')}")
                    logger.info(f"      Accuracy: {lstm_result.get('accuracy', 0):.2%}")
                else:
                    error_reason = lstm_result.get('error', 'Unknown error')
                    logger.warning(f"   ⚠️ LSTM training skipped: {error_reason}")

            except Exception as e:
                error_msg = f"LSTM training error: {e}"
                logger.error(f"   ❌ {error_msg}")
                results['errors'].append(error_msg)

            # Training Complete
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            results['end_time'] = end_time.isoformat()
            results['duration_seconds'] = duration

            # Determine LSTM status for logging
            lstm_success = results.get('lstm') and results['lstm'].get('success')

            logger.info("\n" + "=" * 60)
            logger.info("✅ Daily AI Training Session Complete!")
            logger.info(f"⏱️ Duration: {duration:.1f} seconds")
            logger.info(f"📊 Global Model: {'✅' if results['global'] and results['global'].get('success') else '❌'}")
            logger.info(f"📊 Brand Models: {len([b for b in results['brands'].values() if b.get('success')])}/{len(brands)}")
            logger.info(f"📊 Vehicle Models: {len([v for v in results['vehicles'].values() if v.get('success')])}/{len(profiles)}")
            logger.info(f"📊 LSTM Model: {'✅' if lstm_success else '⏭️ Skipped'}")

            if results['errors']:
                logger.warning(f"⚠️ Errors encountered: {len(results['errors'])}")

            logger.info("=" * 60 + "\n")

            # Save training results
            self._save_training_log(results)

            self.last_training_time = end_time

        except Exception as e:
            logger.error(f"Critical error in daily training: {e}")

        finally:
            self.training_in_progress = False

    def _train_lstm_models(self) -> dict:
        """
        Train LSTM models using collected feedback data.
        
        Returns:
            Training result dictionary
        """
        if not LSTM_AVAILABLE or not TRAINING_PIPELINE_AVAILABLE:
            return {
                'success': False,
                'error': 'LSTM or training pipeline not available',
                'samples_trained': 0
            }
        
        try:
            logger.info("   Generating training data from feedback...")
            
            # Generate training data from feedback
            pipeline = get_training_pipeline()
            sequences, labels = pipeline.generate_training_data()
            
            if len(sequences) < 10:
                logger.warning(f"   Insufficient training data for LSTM: {len(sequences)} sequences (need 10+)")
                return {
                    'success': False,
                    'error': f'Insufficient training data: {len(sequences)} sequences (need 10+)',
                    'samples_trained': 0
                }
            
            # Train LSTM model
            logger.info(f"   Training LSTM with {len(sequences)} sequences...")
            lstm = LSTMPredictor()
            
            # Prepare training data in format expected by LSTM
            training_data = []
            for i, (seq, label) in enumerate(zip(sequences, labels)):
                training_data.append({
                    'sequence': seq,
                    'label': label
                })
            
            result = lstm.train(training_data, verbose=0)
            
            if result.get('success'):
                logger.info(f"   ✅ LSTM training completed!")
                logger.info(f"      Version: {result.get('version', 'unknown')}")
                logger.info(f"      Epochs: {result.get('epochs', 0)}")
                logger.info(f"      Final Loss: {result.get('final_loss', 0):.4f}")
                logger.info(f"      Accuracy: {result.get('accuracy', 0):.2%}")
                
                # Save training record
                self._save_training_record('lstm', {
                    'version': result.get('version'),
                    'samples_used': len(sequences),
                    'epochs': result.get('epochs', 0),
                    'final_loss': result.get('final_loss', 0),
                    'accuracy': result.get('accuracy', 0),
                    'timestamp': datetime.now().isoformat()
                })
                
                return {
                    'success': True,
                    'samples_trained': len(sequences),
                    'version': result.get('version'),
                    'accuracy': result.get('accuracy', 0)
                }
            else:
                error_msg = result.get('error', 'Unknown error')
                logger.warning(f"   ⚠️ LSTM training failed: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'samples_trained': 0
                }
                
        except Exception as e:
            logger.error(f"   ❌ LSTM training error: {e}")
            return {
                'success': False,
                'error': str(e),
                'samples_trained': 0
            }

    def _save_training_record(self, model_type: str, record: dict):
        """Save training record to log file"""
        try:
            import json
            import os
            
            log_dir = str(CONFIG.LOGS_DIR / "training")
            os.makedirs(log_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = os.path.join(log_dir, f"{model_type}_training_{timestamp}.json")
            
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(record, f, indent=2)
                
            logger.debug(f"Training record saved: {log_file}")
            
        except Exception as e:
            logger.error(f"Error saving training record: {e}")

    def _get_unique_brands(self) -> list:
        """Get list of unique vehicle brands from profiles"""
        try:
            profiles = self.vehicle_manager.get_all_profiles()
            brands = set()

            for profile in profiles:
                make = profile.get('make')
                if make:
                    brands.add(make)

            return sorted(list(brands))

        except Exception as e:
            logger.error(f"Error getting brands: {e}")
            return []

    def _save_training_log(self, results: dict):
        """Save training results to log file"""
        try:
            import json
            import os

            log_dir = str(CONFIG.LOGS_DIR / "training")
            os.makedirs(log_dir, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = os.path.join(log_dir, f'training_log_{timestamp}.json')

            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            logger.debug(f"Training log saved: {log_file}")

        except Exception as e:
            logger.error(f"Error saving training log: {e}")

    def trigger_manual_training(self):
        """
        Trigger training manually (outside of schedule)
        Useful for testing or when user wants immediate retraining
        """
        logger.info("Manual training triggered by user")

        # Run in separate thread to avoid blocking
        training_thread = threading.Thread(target=self._run_daily_training)
        training_thread.start()

        return {"status": "started", "message": "Manual training initiated"}
    
    def check_incremental_learning(self) -> dict:
        """
        Check if enough new data has accumulated for incremental learning.
        Triggers quick retraining if threshold is reached.
        
        Returns:
            dict with status and details
        """
        try:
            # Get current sample count from historical data manager
            current_count = self._get_total_sample_count()
            
            # Calculate new samples since last check
            new_samples = current_count - self.last_sample_count
            
            # Check if we've reached the incremental threshold
            if new_samples >= self.incremental_threshold:
                logger.info(f"📊 Incremental learning triggered: {new_samples} new samples (threshold: {self.incremental_threshold})")
                
                # Trigger incremental training (only LSTM for speed)
                result = self._train_incremental_lstm()
                
                # Update last sample count
                self.last_sample_count = current_count
                
                return {
                    'triggered': True,
                    'new_samples': new_samples,
                    'total_samples': current_count,
                    'result': result
                }
            else:
                logger.debug(f"Incremental check: {new_samples}/{self.incremental_threshold} new samples")
                return {
                    'triggered': False,
                    'new_samples': new_samples,
                    'total_samples': current_count,
                    'threshold': self.incremental_threshold
                }
                
        except Exception as e:
            logger.error(f"Error checking incremental learning: {e}")
            return {
                'triggered': False,
                'error': str(e)
            }
    
    def _get_total_sample_count(self) -> int:
        """Get total OBD data sample count from historical data manager"""
        try:
            import sqlite3
            from pathlib import Path

            # Check both historical database and server database
            total_count = 0

            # Count from historical data (vehicle_data table in profiles DB)
            hist_db_path = CONFIG.PROFILES_DB_PATH
            if Path(hist_db_path).exists():
                conn = sqlite3.connect(str(hist_db_path))
                c = conn.cursor()
                # Check if vehicle_data table exists
                c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vehicle_data'")
                if c.fetchone():
                    c.execute("SELECT COUNT(*) FROM vehicle_data")
                    total_count += c.fetchone()[0]
                conn.close()

            # Count from server database (vehicle_data table - Android app data)
            server_db_path = CONFIG.SERVER_DB_PATH
            if Path(server_db_path).exists():
                conn = sqlite3.connect(str(server_db_path))
                c = conn.cursor()
                # Check if vehicle_data table exists
                c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vehicle_data'")
                if c.fetchone():
                    c.execute("SELECT COUNT(*) FROM vehicle_data")
                    total_count += c.fetchone()[0]
                conn.close()

            return total_count

        except Exception as e:
            logger.error(f"Error getting sample count: {e}")
            return 0
    
    def _train_incremental_lstm(self) -> dict:
        """
        Perform incremental LSTM training with new data.
        Faster than full training - focuses only on LSTM models.
        
        Returns:
            Training result dictionary
        """
        if not LSTM_AVAILABLE or not TRAINING_PIPELINE_AVAILABLE:
            return {
                'success': False,
                'error': 'LSTM or training pipeline not available'
            }
        
        try:
            logger.info("   Starting incremental LSTM training...")
            
            # Generate training data from feedback
            pipeline = get_training_pipeline()
            sequences, labels = pipeline.generate_training_data()
            
            if len(sequences) < 10:
                logger.warning(f"   Insufficient training data: {len(sequences)} sequences (need 10+)")
                return {
                    'success': False,
                    'error': f'Insufficient training data: {len(sequences)} sequences (need 10+)'
                }
            
            # Train LSTM model with fewer epochs for speed
            logger.info(f"   Training incremental LSTM with {len(sequences)} sequences...")
            lstm = LSTMPredictor()
            
            # Prepare training data
            training_data = []
            for seq, label in zip(sequences, labels):
                training_data.append({
                    'sequence': seq,
                    'label': label
                })
            
            # Train with reduced epochs for faster incremental learning
            result = lstm.train(training_data, epochs=5, verbose=0)
            
            if result.get('success'):
                logger.info(f"   ✅ Incremental LSTM training completed!")
                logger.info(f"      Version: {result.get('version', 'unknown')}")
                logger.info(f"      Epochs: {result.get('epochs', 0)}")
                logger.info(f"      Accuracy: {result.get('accuracy', 0):.2%}")
                
                # Save training record
                self._save_training_record('incremental_lstm', {
                    'version': result.get('version'),
                    'samples_used': len(sequences),
                    'epochs': result.get('epochs', 0),
                    'final_loss': result.get('final_loss', 0),
                    'accuracy': result.get('accuracy', 0),
                    'timestamp': datetime.now().isoformat(),
                    'type': 'incremental'
                })
                
                return {
                    'success': True,
                    'samples_trained': len(sequences),
                    'version': result.get('version'),
                    'accuracy': result.get('accuracy', 0)
                }
            else:
                error_msg = result.get('error', 'Unknown error')
                logger.warning(f"   ⚠️ Incremental LSTM training failed: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
                
        except Exception as e:
            logger.error(f"   ❌ Incremental LSTM training error: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _train_advanced_models(self) -> Dict[str, Dict[str, Any]]:
        """
        Train advanced AI models using the factory pattern.

        Returns:
            Dictionary of training results by architecture
        """
        results = {}
        factory = get_model_factory()

        # Define training configurations for each architecture
        training_configs = {
            ModelArchitecture.CNN_LSTM_HYBRID: {
                'available': CNN_LSTM_AVAILABLE,
                'min_samples': 1500,
                'description': 'CNN-LSTM Hybrid'
            },
            ModelArchitecture.ATTENTION_LSTM: {
                'available': ATTENTION_LSTM_AVAILABLE,
                'min_samples': 2000,
                'description': 'Attention-LSTM'
            },
            ModelArchitecture.LSTM_AUTOENCODER: {
                'available': AUTOENCODER_AVAILABLE,
                'min_samples': 5000,
                'description': 'LSTM Autoencoder'
            },
            ModelArchitecture.ENSEMBLE: {
                'available': True,  # Ensemble is always available through factory
                'min_samples': 1000,
                'description': 'Ensemble Model'
            }
        }

        # Get training data from historical data manager
        training_data = self._get_training_data_for_advanced_models()

        for architecture, config in training_configs.items():
            if not config['available']:
                results[architecture.value] = {
                    'success': False,
                    'error': f'{config["description"]} not available'
                }
                continue

            try:
                logger.info(f"   Training {config['description']}...")

                # Check if we have enough data
                if len(training_data) < config['min_samples']:
                    results[architecture.value] = {
                        'success': False,
                        'error': f'Insufficient data: {len(training_data)} < {config["min_samples"]}'
                    }
                    continue

                # Get model from factory
                model = factory.get_model(architecture)
                if not model:
                    results[architecture.value] = {
                        'success': False,
                        'error': 'Model not available from factory'
                    }
                    continue

                # Prepare training data based on architecture
                if architecture == ModelArchitecture.LSTM_AUTOENCODER:
                    # Autoencoder needs sequences of normal data
                    prepared_data = self._prepare_autoencoder_training_data(training_data)
                else:
                    # Other models need labeled failure prediction data
                    prepared_data = self._prepare_failure_prediction_training_data(training_data)

                if not prepared_data:
                    results[architecture.value] = {
                        'success': False,
                        'error': 'No valid training data prepared'
                    }
                    continue

                # Train the model
                train_result = model.train(prepared_data)

                if train_result.get('success'):
                    logger.info(f"   ✅ {config['description']} trained (Samples: {len(prepared_data)})")
                    results[architecture.value] = {
                        'success': True,
                        'samples_trained': len(prepared_data),
                        'version': train_result.get('version'),
                        'accuracy': train_result.get('accuracy', 0),
                        'architecture': architecture.value
                    }
                else:
                    error_msg = train_result.get('error', 'Unknown training error')
                    logger.warning(f"   ⚠️ {config['description']} failed: {error_msg}")
                    results[architecture.value] = {
                        'success': False,
                        'error': error_msg
                    }

            except Exception as e:
                logger.error(f"   ❌ {config['description']} training error: {e}")
                results[architecture.value] = {
                    'success': False,
                    'error': str(e)
                }

        return results

    def _get_training_data_for_advanced_models(self) -> List[Dict]:
        """Get training data suitable for advanced models."""
        try:
            # Get data from historical data manager
            training_samples = []
            
            # Get all profiles to gather their data
            profiles = self.vehicle_manager.get_all_profiles()
            
            for profile in profiles:
                profile_id = profile.get('profile_id')
                profile_name = profile.get('name', f'Profile_{profile_id}')
                
                if not profile_id:
                    continue
                
                try:
                    # Get OBD data from historical data manager
                    obd_data = self.historical_data.get_obd_data(profile_name, limit=100)
                    
                    if not obd_data:
                        continue
                    
                    # Convert OBD data to training samples
                    for record in obd_data:
                        sample = {
                            'vehicle_id': profile_id,
                            'vehicle_name': profile_name,
                            'make': profile.get('make'),
                            'model': profile.get('model'),
                            'year': profile.get('year'),
                            'timestamp': record.get('timestamp'),
                            'rpm': record.get('rpm'),
                            'speed': record.get('speed'),
                            'coolant_temp': record.get('coolant_temp'),
                            'engine_load': record.get('engine_load'),
                            'battery_voltage': record.get('battery_voltage'),
                            'throttle_pos': record.get('throttle_position'),
                            'intake_temp': record.get('intake_temp'),
                            'maf': record.get('maf'),
                        }
                        training_samples.append(sample)
                        
                except Exception as e:
                    logger.warning(f"Failed to get data for profile {profile_name}: {e}")
                    continue
            
            logger.info(f"Retrieved {len(training_samples)} training samples for advanced models")
            return training_samples[:5000]  # Limit to 5000 samples for training efficiency
            
        except Exception as e:
            logger.error(f"Error getting training data: {e}")
            return []

    def _prepare_autoencoder_training_data(self, raw_data: List[Dict]) -> List[List[Dict]]:
        """Prepare training data for LSTM autoencoder (unsupervised)."""
        # Autoencoder needs sequences of normal vehicle operation
        # Filter for normal operation sequences
        normal_sequences = []

        # Group data by vehicle and create sequences
        from collections import defaultdict
        by_vehicle = defaultdict(list)

        for record in raw_data:
            vehicle_id = record.get('vehicle_id', 'unknown')
            by_vehicle[vehicle_id].append(record)

        # Create sequences for each vehicle
        for vehicle_id, records in by_vehicle.items():
            if len(records) >= 60:  # Minimum sequence length
                # Sort by timestamp
                sorted_records = sorted(records, key=lambda x: x.get('timestamp', ''))

                # Create overlapping sequences
                for i in range(0, len(sorted_records) - 60, 30):  # 30-step overlap
                    sequence = sorted_records[i:i+60]
                    normal_sequences.append(sequence)

        return normal_sequences[:1000]  # Limit for training

    def _prepare_failure_prediction_training_data(self, raw_data: List[Dict]) -> List[Dict]:
        """Prepare training data for supervised failure prediction models."""
        training_samples = []
        
        if not raw_data:
            logger.warning("No raw data provided for failure prediction training")
            return []
        
        try:
            # Get historical failure data
            from historical_data_manager import get_historical_data_manager
            hist_manager = get_historical_data_manager()
            
            # Get all profiles
            profiles = self.vehicle_manager.get_all_profiles()
            
            for profile in profiles:
                profile_id = profile.get('profile_id')
                profile_name = profile.get('name', f'Profile_{profile_id}')
                
                if not profile_id:
                    continue
                
                try:
                    # Get OBD data for this profile
                    obd_data = hist_manager.get_obd_data(profile_name, limit=200)
                    
                    if not obd_data:
                        continue
                    
                    # Sort by timestamp
                    sorted_data = sorted(obd_data, key=lambda x: x.get('timestamp', ''))
                    
                    # Create sequences for training
                    for i in range(0, len(sorted_data) - 60, 30):
                        sequence = sorted_data[i:i+60]
                        
                        # Determine if this sequence leads to a failure
                        # Look ahead for failure indicators
                        is_failure = False
                        failure_type = None
                        
                        # Check if any record in sequence has failure indicators
                        for record in sequence:
                            # Check for high coolant temp (potential overheating)
                            if record.get('coolant_temp', 0) > 110:
                                is_failure = True
                                failure_type = 'overheating'
                                break
                            
                            # Check for low battery voltage
                            if record.get('battery_voltage', 14) < 11:
                                is_failure = True
                                failure_type = 'battery_failure'
                                break
                            
                            # Check for high engine load
                            if record.get('engine_load', 0) > 95:
                                is_failure = True
                                failure_type = 'engine_stress'
                                break
                        
                        # Create training sample
                        sample = {
                            'vehicle_id': profile_id,
                            'vehicle_name': profile_name,
                            'make': profile.get('make'),
                            'model': profile.get('model'),
                            'year': profile.get('year'),
                            'sequence': sequence,
                            'is_failure': is_failure,
                            'failure_type': failure_type,
                            'sequence_length': len(sequence)
                        }
                        training_samples.append(sample)
                        
                except Exception as e:
                    logger.warning(f"Failed to prepare data for profile {profile_name}: {e}")
                    continue
            
            # Balance dataset: ensure we have both positive and negative samples
            failure_samples = [s for s in training_samples if s.get('is_failure', False)]
            normal_samples = [s for s in training_samples if not s.get('is_failure', True)]
            
            # Limit to avoid imbalance
            if len(failure_samples) > len(normal_samples):
                failure_samples = failure_samples[:len(normal_samples)]
            elif len(normal_samples) > len(failure_samples):
                normal_samples = normal_samples[:len(failure_samples)]
            
            balanced_samples = failure_samples + normal_samples
            
            logger.info(f"Prepared {len(balanced_samples)} training samples ({len(failure_samples)} failures, {len(normal_samples)} normal)")
            return balanced_samples[:2000]  # Limit for training efficiency
            
        except Exception as e:
            logger.error(f"Error preparing failure prediction training data: {e}")
            return []

    def get_training_status(self) -> dict:
        """Get current training status"""
        return {
            'scheduler_running': self.is_running,
            'training_in_progress': self.training_in_progress,
            'last_training_time': self.last_training_time.isoformat() if self.last_training_time else None,
            'next_training_time': self._get_next_scheduled_time()
        }

    def _get_next_scheduled_time(self) -> Optional[str]:
        """Get next scheduled training time"""
        try:
            next_run = schedule.next_run()
            if next_run:
                return next_run.isoformat()
        except:
            pass
        return None


# Singleton instance with thread-safe initialization
_scheduler_instance: Optional[AIAutoRetrainingScheduler] = None
_scheduler_lock = threading.Lock()


def get_retraining_scheduler(
    enhanced_ai_learning=None,
    historical_data_manager=None,
    vehicle_manager=None
) -> Optional[AIAutoRetrainingScheduler]:
    """
    Get the singleton AIAutoRetrainingScheduler instance.

    Thread-safe singleton pattern ensures only one scheduler exists.

    Args:
        enhanced_ai_learning: Required for first initialization
        historical_data_manager: Required for first initialization
        vehicle_manager: Required for first initialization

    Returns:
        The singleton scheduler instance, or None if not initialized
    """
    global _scheduler_instance

    with _scheduler_lock:
        if _scheduler_instance is None:
            # First initialization requires all dependencies
            if enhanced_ai_learning is None or historical_data_manager is None or vehicle_manager is None:
                logger.warning("Cannot create scheduler: missing required dependencies")
                return None

            _scheduler_instance = AIAutoRetrainingScheduler(
                enhanced_ai_learning,
                historical_data_manager,
                vehicle_manager
            )
            logger.info("AIAutoRetrainingScheduler singleton created")
        elif enhanced_ai_learning is not None:
            # Warn if trying to reinitialize with different dependencies
            logger.warning("AIAutoRetrainingScheduler already initialized - ignoring new dependencies")

        return _scheduler_instance


def reset_retraining_scheduler():
    """
    Reset the singleton scheduler instance.

    Used for testing or when the scheduler needs to be recreated.
    """
    global _scheduler_instance

    with _scheduler_lock:
        if _scheduler_instance is not None:
            if _scheduler_instance.is_running:
                _scheduler_instance.stop()
            _scheduler_instance = None
            logger.info("AIAutoRetrainingScheduler singleton reset")


def trigger_incremental_learning():
    """
    Trigger incremental learning immediately.
    This is a convenience function that can be called from anywhere in the application.
    
    Returns:
        dict with trigger result
    """
    global _scheduler_instance
    
    if _scheduler_instance is None:
        return {
            'success': False,
            'error': 'Scheduler not initialized'
        }
    
    try:
        result = _scheduler_instance.check_incremental_learning()
        return {
            'success': True,
            'result': result
        }
    except Exception as e:
        logger.error(f"Error triggering incremental learning: {e}")
        return {
            'success': False,
            'error': str(e)
        }
