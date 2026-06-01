"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Vehicle Module
"""

import sqlite3
import os
from datetime import datetime
from database_migration import run_migrations

# New AI imports added as requested
from unified_ai_module import UnifiedAIModule
from predictive_failure_engine import PredictiveFailureEngine

# Database utilities with retry logic for SQLite locks
from db_utils import with_db_retry, get_db_connection, create_connection, SQLITE_LOCK_TIMEOUT

# Performance Optimization Imports
from functools import lru_cache
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import json
import hashlib
import weakref
import logging

# Configure logging for database operations
db_logger = logging.getLogger(__name__)

# Performance Configuration Constants
PERFORMANCE_CONFIG = {
    'cache_size': 128,
    'cache_timeout': 300,  # 5 minutes
    'max_connections': 5,
    'connection_timeout': 30,  # seconds
    'batch_size': 50,  # Batch processing size
    'prefetch_related': True,  # Prefetch related data
    'query_timeout': 10,  # seconds
    'memory_limit_mb': 100,  # Memory limit for caching
    'cleanup_interval': 600,  # 10 minutes
    'stats_collection': True
}

class VehicleProfileManager:
    """Enhanced Vehicle Profile Management with Fleet Features, AI Integration, and Performance Optimization"""
    
    def __init__(self, db_path='./PredictData/vehicle_profiles.db'):
        self.db_path = db_path
        self.ensure_data_directory()
        
        # RUN DATABASE MIGRATIONS FIRST
        if not run_migrations():
            print("âŒ Database migration failed!")
        
        # Add new AI properties as requested
        self.ai_integration_enabled = True
        self.fleet_analytics_enabled = True
        self.cost_optimization_enabled = True
        self.predictive_maintenance_enabled = True
        self.ai_system = None  # Will be set by main application
        self.predictive_engine = None  # Will be set by main application
        
        # Performance optimization attributes
        self._profile_cache = {}
        self._cache_lock = threading.Lock()
        self._connection_pool = []
        self._pool_lock = threading.Lock()
        self._cache_stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'last_cleanup': time.time()
        }
        self._query_stats = {
            'total_queries': 0,
            'total_time': 0.0,
            'slow_queries': []
        }
        self._batch_operations = []
        self._batch_lock = threading.Lock()
        self._prefetch_data = {}
        self._prefetch_lock = threading.Lock()
        self._memory_usage = 0
        self._performance_monitor = {
            'enabled': PERFORMANCE_CONFIG['stats_collection'],
            'start_time': time.time(),
            'operations': []
        }
        
        # Track profiles being loaded to prevent recursion
        self._loading_profiles = set()
        self._loading_lock = threading.Lock()
        
        self.setup_database()
        
        # Initialize performance monitoring
        self._init_performance_monitoring()
        self._init_connection_pool()
    
    def ensure_data_directory(self):
        """Ensure data directory exists"""
        os.makedirs('./data', exist_ok=True)
    
    @with_db_retry()
    def setup_database(self):
        """Setup database with proper error handling and ensure all required tables exist"""
        try:
            conn = create_connection(self.db_path)
            cursor = conn.cursor()
            
            # These tables should now exist after migrations
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vehicle_profiles (
                    profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    make TEXT,
                    model TEXT,
                    year INTEGER,
                    vin TEXT,
                    license_plate TEXT,
                    category TEXT DEFAULT 'Commercial',
                    engine_type TEXT,
                    transmission TEXT,
                    fuel_type TEXT,
                    drivetrain TEXT,
                    color TEXT,
                    purchase_date TEXT,
                    last_service_date TEXT,
                    dealer_info TEXT,
                    warranty_info TEXT,
                    insurance_details TEXT,
                    is_connected BOOLEAN DEFAULT 0,
                    is_favorite BOOLEAN DEFAULT 0,
                    total_distance REAL DEFAULT 0,
                    total_driving_hours REAL DEFAULT 0,
                    maintenance_count INTEGER DEFAULT 0,
                    trip_count INTEGER DEFAULT 0,
                    total_costs REAL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Migrate: add displacement + cylinders columns if missing
            try:
                cursor.execute("ALTER TABLE vehicle_profiles ADD COLUMN displacement TEXT")
            except Exception:
                pass  # Column already exists
            try:
                cursor.execute("ALTER TABLE vehicle_profiles ADD COLUMN cylinders INTEGER")
            except Exception:
                pass  # Column already exists

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vehicle_categories (
                    category_name TEXT PRIMARY KEY,
                    color TEXT DEFAULT '#3498db',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create maintenance_records table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS maintenance_records (
                    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vehicle_id INTEGER,
                    service_type TEXT,
                    service_date TEXT,
                    cost REAL,
                    mileage REAL,
                    notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (vehicle_id) REFERENCES vehicle_profiles(profile_id)
                )
            ''')
            
            # Create trip_records table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trip_records (
                    trip_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vehicle_id INTEGER,
                    distance REAL,
                    duration REAL,
                    fuel_consumed REAL,
                    start_time TEXT,
                    end_time TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (vehicle_id) REFERENCES vehicle_profiles(profile_id)
                )
            ''')
            
            # Create cost_records table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cost_records (
                    cost_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vehicle_id INTEGER,
                    amount REAL,
                    category TEXT,
                    date TEXT,
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (vehicle_id) REFERENCES vehicle_profiles(profile_id)
                )
            ''')
            
            # Insert default categories for fleet management
            default_categories = [
                ('Commercial', '#3498db'),
                ('Personal', '#2ecc71'),
                ('Service', '#e74c3c'),
                ('Rental', '#f39c12'),
                ('Executive', '#9b59b6')
            ]
            
            for category_name, color in default_categories:
                cursor.execute('''
                    INSERT OR IGNORE INTO vehicle_categories (category_name, color) 
                    VALUES (?, ?)
                ''', (category_name, color))
            
            conn.commit()
            conn.close()
            print("âœ… Vehicle Profile Database initialized successfully")
            
        except Exception as e:
            print(f"âŒ Database setup error: {e}")
    
    # ==================== PERFORMANCE OPTIMIZATION METHODS ====================
    
    def get_connection(self):
        """Get database connection from pool"""
        try:
            with self._pool_lock:
                # Try to get connection from pool
                if self._connection_pool:
                    conn = self._connection_pool.pop()
                    # Test if connection is still valid
                    try:
                        conn.execute("SELECT 1")
                        return conn
                    except:
                        conn.close()
                
                # Create new connection if pool is empty
                # Use SQLITE_LOCK_TIMEOUT for better concurrent access handling
                conn = sqlite3.connect(self.db_path, timeout=SQLITE_LOCK_TIMEOUT)
                
                # Optimize connection settings
                conn.execute("PRAGMA journal_mode = WAL")
                conn.execute("PRAGMA synchronous = NORMAL")
                conn.execute("PRAGMA cache_size = 10000")
                conn.execute("PRAGMA temp_store = MEMORY")
                conn.execute("PRAGMA mmap_size = 268435456")  # 256MB
                conn.execute(f"PRAGMA busy_timeout = {int(SQLITE_LOCK_TIMEOUT * 1000)}")

                return conn

        except sqlite3.OperationalError as e:
            error_msg = str(e).lower()
            if "locked" in error_msg or "busy" in error_msg:
                db_logger.warning(f"Database lock encountered: {e}")
            raise
        except Exception as e:
            db_logger.error(f"Error getting connection: {e}")
            return sqlite3.connect(self.db_path, timeout=SQLITE_LOCK_TIMEOUT)

    def return_connection(self, conn):
        """Return connection to pool"""
        try:
            with self._pool_lock:
                if len(self._connection_pool) < PERFORMANCE_CONFIG['max_connections']:
                    # Check if connection is still valid
                    try:
                        conn.execute("SELECT 1")
                        self._connection_pool.append(conn)
                    except:
                        conn.close()
                else:
                    conn.close()
        except Exception as e:
            print(f"âŒ Error returning connection: {e}")

    def close_all_connections(self):
        """Close all connections in pool"""
        try:
            with self._pool_lock:
                for conn in self._connection_pool:
                    try:
                        conn.close()
                    except:
                        pass
                self._connection_pool.clear()
        except Exception as e:
            print(f"âŒ Error closing connections: {e}")

    def _init_connection_pool(self):
        """Initialize connection pool with optimal settings"""
        try:
            # Pre-warm connection pool
            for _ in range(min(2, PERFORMANCE_CONFIG['max_connections'])):
                conn = self.get_connection()
                self._connection_pool.append(conn)
            
            print(f"âœ… Connection pool initialized with {len(self._connection_pool)} connections")
        except Exception as e:
            print(f"âŒ Error initializing connection pool: {e}")

    @lru_cache(maxsize=PERFORMANCE_CONFIG['cache_size'])
    def get_cached_profile(self, profile_id):
        """Get profile with LRU caching"""
        try:
            # Check cache first
            cache_key = f"profile_{profile_id}"
            
            with self._cache_lock:
                if cache_key in self._profile_cache:
                    cached_data, timestamp = self._profile_cache[cache_key]
                    
                    # Check if cache is still valid
                    if time.time() - timestamp < PERFORMANCE_CONFIG['cache_timeout']:
                        self._cache_stats['hits'] += 1
                        return cached_data
                    else:
                        # Remove expired cache entry
                        del self._profile_cache[cache_key]
                        self._cache_stats['evictions'] += 1
            
            # Cache miss - load from database
            self._cache_stats['misses'] += 1
            profile = self.load_profile(profile_id)
            
            if profile:
                # Cache the result
                with self._cache_lock:
                    self._profile_cache[cache_key] = (profile, time.time())
                    
                    # Check memory usage
                    self._update_memory_usage()
                    
                    # Periodic cleanup
                    if time.time() - self._cache_stats['last_cleanup'] > PERFORMANCE_CONFIG['cleanup_interval']:
                        self._cleanup_cache()
            
            return profile
            
        except Exception as e:
            print(f"âŒ Error getting cached profile: {e}")
            return self.load_profile(profile_id)

    def _cleanup_cache(self):
        """Clean up expired cache entries"""
        try:
            with self._cache_lock:
                current_time = time.time()
                expired_keys = []
                
                for key, (data, timestamp) in self._profile_cache.items():
                    if current_time - timestamp > PERFORMANCE_CONFIG['cache_timeout']:
                        expired_keys.append(key)
                
                for key in expired_keys:
                    del self._profile_cache[key]
                    self._cache_stats['evictions'] += len(expired_keys)
                
                self._cache_stats['last_cleanup'] = current_time
                
            if expired_keys:
                print(f"ðŸ§¹ Cleaned up {len(expired_keys)} expired cache entries")
                
        except Exception as e:
            print(f"âŒ Error cleaning up cache: {e}")

    def _update_memory_usage(self):
        """Update memory usage tracking"""
        try:
            # Estimate memory usage of cache
            total_size = 0
            for key, (data, timestamp) in self._profile_cache.items():
                # Rough estimation of memory usage
                total_size += len(str(data)) + len(key) + 16  # 16 bytes for timestamp
            
            self._memory_usage = total_size / (1024 * 1024)  # Convert to MB
            
            # Check if we're over memory limit
            if self._memory_usage > PERFORMANCE_CONFIG['memory_limit_mb']:
                # Remove least recently used items
                self._evict_lru_items(int(self._memory_usage * 0.2))
                
        except Exception as e:
            print(f"âŒ Error updating memory usage: {e}")

    def _evict_lru_items(self, count):
        """Evict least recently used items from cache"""
        try:
            with self._cache_lock:
                # Sort by timestamp (oldest first)
                sorted_items = sorted(
                    self._profile_cache.items(),
                    key=lambda x: x[1][1]  # Sort by timestamp
                )
                
                # Remove oldest items
                for i in range(min(count, len(sorted_items))):
                    key = sorted_items[i][0]
                    del self._profile_cache[key]
                    self._cache_stats['evictions'] += 1
                
            print(f"ðŸ§¹ Evicted {count} LRU items from cache")
                
        except Exception as e:
            print(f"âŒ Error evicting LRU items: {e}")

    def clear_cache(self):
        """Clear all cached data"""
        try:
            with self._cache_lock:
                self._profile_cache.clear()
                self._cache_stats = {
                    'hits': 0,
                    'misses': 0,
                    'evictions': 0,
                    'last_cleanup': time.time()
                }
                self._memory_usage = 0
            
            print("ðŸ§¹ Cache cleared")
            
        except Exception as e:
            print(f"âŒ Error clearing cache: {e}")

    def get_cache_stats(self):
        """Get cache performance statistics"""
        with self._cache_lock:
            total_requests = self._cache_stats['hits'] + self._cache_stats['misses']
            hit_rate = self._cache_stats['hits'] / total_requests if total_requests > 0 else 0
            
            return {
                'hits': self._cache_stats['hits'],
                'misses': self._cache_stats['misses'],
                'evictions': self._cache_stats['evictions'],
                'hit_rate': hit_rate,
                'memory_usage_mb': self._memory_usage,
                'cache_size': len(self._profile_cache)
            }

    def batch_update_profiles(self, profile_updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Batch update multiple profiles for better performance"""
        try:
            if not profile_updates:
                return {'success': False, 'message': 'No profiles to update'}
            
            start_time = time.time()
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Begin transaction
            cursor.execute("BEGIN TRANSACTION")
            
            updated_count = 0
            errors = []
            
            try:
                for profile_data in profile_updates:
                    profile_id = profile_data.get('profile_id')
                    if not profile_id:
                        errors.append(f"Missing profile_id in update data")
                        continue
                    
                    # Update profile
                    cursor.execute('''
                        UPDATE vehicle_profiles SET
                            name=?, make=?, model=?, year=?, vin=?, license_plate=?,
                            category=?, engine_type=?, transmission=?, fuel_type=?,
                            drivetrain=?, color=?, purchase_date=?, last_service_date=?,
                            dealer_info=?, warranty_info=?, insurance_details=?,
                            is_favorite=?, is_connected=?, updated_at=CURRENT_TIMESTAMP
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
                    
                    updated_count += 1
                    
                    # Clear cache for updated profile
                    cache_key = f"profile_{profile_id}"
                    with self._cache_lock:
                        if cache_key in self._profile_cache:
                            del self._profile_cache[cache_key]
                
                # Commit transaction
                cursor.execute("COMMIT")
                
                processing_time = time.time() - start_time
                
                # Update performance stats
                self._update_query_stats("batch_update_profiles", processing_time)
                
                self.return_connection(conn)
                
                return {
                    'success': True,
                    'updated_count': updated_count,
                    'processing_time': processing_time,
                    'errors': errors
                }
                
            except Exception as e:
                # Rollback on error
                cursor.execute("ROLLBACK")
                self.return_connection(conn)
                
                return {
                    'success': False,
                    'message': f"Batch update failed: {str(e)}",
                    'updated_count': updated_count,
                    'errors': errors + [str(e)]
                }
                
        except Exception as e:
            print(f"âŒ Error in batch update: {e}")
            return {
                'success': False,
                'message': f"Batch update error: {str(e)}",
                'updated_count': 0,
                'errors': [str(e)]
            }

    def batch_prefetch_related_data(self, profile_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Prefetch related data for multiple profiles"""
        try:
            if not profile_ids:
                return {}
            
            start_time = time.time()
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Build placeholders for IN clause
            placeholders = ','.join(['?'] * len(profile_ids))
            
            # Prefetch maintenance records
            cursor.execute(f'''
                SELECT vehicle_id, service_type, service_date, cost, mileage, notes
                FROM maintenance_records
                WHERE vehicle_id IN ({placeholders})
                ORDER BY service_date DESC
            ''', profile_ids)
            
            maintenance_records = {}
            for row in cursor.fetchall():
                vehicle_id = row[0]
                if vehicle_id not in maintenance_records:
                    maintenance_records[vehicle_id] = []
                
                maintenance_records[vehicle_id].append({
                    'service_type': row[1],
                    'service_date': row[2],
                    'cost': row[3],
                    'mileage': row[4],
                    'notes': row[5]
                })
            
            # Prefetch trip records
            cursor.execute(f'''
                SELECT vehicle_id, distance, duration, fuel_consumed, start_time, end_time
                FROM trip_records
                WHERE vehicle_id IN ({placeholders})
                ORDER BY start_time DESC
                LIMIT 10
            ''', profile_ids)
            
            trip_records = {}
            for row in cursor.fetchall():
                vehicle_id = row[0]
                if vehicle_id not in trip_records:
                    trip_records[vehicle_id] = []
                
                trip_records[vehicle_id].append({
                    'distance': row[1],
                    'duration': row[2],
                    'fuel_consumed': row[3],
                    'start_time': row[4],
                    'end_time': row[5]
                })
            
            # Prefetch cost records
            cursor.execute(f'''
                SELECT vehicle_id, amount, category, date, description
                FROM cost_records
                WHERE vehicle_id IN ({placeholders})
                ORDER BY date DESC
                LIMIT 10
            ''', profile_ids)
            
            cost_records = {}
            for row in cursor.fetchall():
                vehicle_id = row[0]
                if vehicle_id not in cost_records:
                    cost_records[vehicle_id] = []
                
                cost_records[vehicle_id].append({
                    'amount': row[1],
                    'category': row[2],
                    'date': row[3],
                    'description': row[4]
                })
            
            self.return_connection(conn)
            
            # Cache prefetched data
            with self._prefetch_lock:
                for profile_id in profile_ids:
                    self._prefetch_data[profile_id] = {
                        'maintenance_records': maintenance_records.get(profile_id, []),
                        'trip_records': trip_records.get(profile_id, []),
                        'cost_records': cost_records.get(profile_id, []),
                        'prefetch_time': time.time()
                    }
            
            processing_time = time.time() - start_time
            self._update_query_stats("batch_prefetch_related_data", processing_time)
            
            print(f"âœ… Prefetched related data for {len(profile_ids)} profiles in {processing_time:.3f}s")
            
            return self._prefetch_data
            
        except Exception as e:
            print(f"âŒ Error prefetching related data: {e}")
            return {}

    def get_prefetched_data(self, profile_id: int, data_type: str = None) -> Any:
        """Get prefetched data for a profile"""
        try:
            with self._prefetch_lock:
                if profile_id in self._prefetch_data:
                    prefetch_data = self._prefetch_data[profile_id]
                    
                    # Check if data is still fresh (within 5 minutes)
                    if time.time() - prefetch_data.get('prefetch_time', 0) < 300:
                        if data_type:
                            return prefetch_data.get(data_type, [])
                        return prefetch_data
            
            # Return empty if no fresh data
            return [] if data_type else {}
            
        except Exception as e:
            print(f"âŒ Error getting prefetched data: {e}")
            return [] if data_type else {}

    def get_all_profiles_optimized(self) -> List[Dict[str, Any]]:
        """Get all profiles with performance optimizations"""
        try:
            start_time = time.time()
            conn = self.get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Use optimized query with specific columns
            cursor.execute('''
                SELECT profile_id, name, make, model, year, vin, license_plate, category,
                       is_favorite, is_connected, total_distance, total_driving_hours,
                       maintenance_count, trip_count, total_costs, updated_at,
                       last_seen, ever_connected
                FROM vehicle_profiles
                ORDER BY is_favorite DESC, name ASC
            ''')
            
            profiles = [dict(row) for row in cursor.fetchall()]
            
            # Batch process AI enhancements
            if self.ai_integration_enabled:
                profiles = self._batch_ai_enhancements(profiles)
            
            # Batch prefetch related data if enabled
            if PERFORMANCE_CONFIG['prefetch_related']:
                profile_ids = [p['profile_id'] for p in profiles]
                self.batch_prefetch_related_data(profile_ids)
            
            self.return_connection(conn)
            
            processing_time = time.time() - start_time
            self._update_query_stats("get_all_profiles_optimized", processing_time)
            
            return profiles
            
        except Exception as e:
            print(f"âŒ Error getting profiles (optimized): {e}")
            return []

    def _batch_ai_enhancements(self, profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Batch process AI enhancements for multiple profiles"""
        try:
            for profile in profiles:
                # Add AI enhancements in batch
                profile['ai_health_score'] = self._calculate_profile_health_score(profile)
                profile['ai_recommendations'] = self._get_ai_driven_recommendations(profile['profile_id'])
                profile['trends'] = self._analyze_profile_trends(profile['profile_id'])
            
            return profiles
            
        except Exception as e:
            print(f"âŒ Error in batch AI enhancements: {e}")
            return profiles

    def search_profiles_optimized(self, query: str, category: str = None, 
                              favorite_only: bool = False) -> List[Dict[str, Any]]:
        """Search profiles with optimized queries"""
        try:
            start_time = time.time()
            conn = self.get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Build optimized query
            sql = '''
                SELECT profile_id, name, make, model, year, vin, license_plate, category,
                       is_favorite, is_connected, total_distance, total_driving_hours,
                       maintenance_count, trip_count, total_costs
                FROM vehicle_profiles
                WHERE (name LIKE ? OR make LIKE ? OR model LIKE ? OR vin LIKE ?)
            '''
            params = [f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%']
            
            if category:
                sql += ' AND category = ?'
                params.append(category)
            
            if favorite_only:
                sql += ' AND is_favorite = 1'
            
            sql += ' ORDER BY is_favorite DESC, name ASC'
            
            cursor.execute(sql, params)
            profiles = [dict(row) for row in cursor.fetchall()]
            
            # Batch process AI enhancements
            if self.ai_integration_enabled:
                profiles = self._batch_ai_enhancements(profiles)
            
            self.return_connection(conn)
            
            processing_time = time.time() - start_time
            self._update_query_stats("search_profiles_optimized", processing_time)
            
            return profiles
            
        except Exception as e:
            print(f"âŒ Error searching profiles (optimized): {e}")
            return []

    def _init_performance_monitoring(self):
        """Initialize performance monitoring system"""
        try:
            if not self._performance_monitor['enabled']:
                return
            
            # Create performance log file
            log_dir = './logs'
            os.makedirs(log_dir, exist_ok=True)
            
            self._performance_log_path = os.path.join(log_dir, 'vehicle_performance.log')
            
            # Start performance monitoring thread
            self._monitor_thread = threading.Thread(target=self._performance_monitor_loop, daemon=True)
            self._monitor_thread.start()
            
            print("âœ… Performance monitoring initialized")
            
        except Exception as e:
            print(f"âŒ Error initializing performance monitoring: {e}")

    def _performance_monitor_loop(self):
        """Performance monitoring loop"""
        while self._performance_monitor['enabled']:
            try:
                # Collect performance metrics every minute
                time.sleep(60)
                
                # Calculate performance metrics
                cache_stats = self.get_cache_stats()
                query_stats = self._get_query_stats()
                
                # Log performance metrics
                with open(self._performance_log_path, 'a') as f:
                    f.write(f"{datetime.now().isoformat()}, "
                             f"cache_hit_rate={cache_stats['hit_rate']:.3f}, "
                             f"cache_size={cache_stats['cache_size']}, "
                             f"cache_memory_mb={cache_stats['memory_usage_mb']:.2f}, "
                             f"total_queries={query_stats['total_queries']}, "
                             f"avg_query_time={query_stats['avg_time']:.3f}\n")
                
            except Exception as e:
                print(f"âŒ Error in performance monitoring loop: {e}")

    def _update_query_stats(self, query_name: str, execution_time: float):
        """Update query performance statistics"""
        try:
            self._query_stats['total_queries'] += 1
            self._query_stats['total_time'] += execution_time
            
            # Track slow queries (over 100ms)
            if execution_time > 0.1:
                self._query_stats['slow_queries'].append({
                    'query': query_name,
                    'time': execution_time,
                    'timestamp': datetime.now().isoformat()
                })
                
                # Keep only last 50 slow queries
                if len(self._query_stats['slow_queries']) > 50:
                    self._query_stats['slow_queries'] = self._query_stats['slow_queries'][-50:]
            
        except Exception as e:
            print(f"âŒ Error updating query stats: {e}")

    def _get_query_stats(self) -> Dict[str, Any]:
        """Get query performance statistics"""
        try:
            total_queries = self._query_stats['total_queries']
            avg_time = self._query_stats['total_time'] / total_queries if total_queries > 0 else 0
            
            return {
                'total_queries': total_queries,
                'total_time': self._query_stats['total_time'],
                'avg_time': avg_time,
                'slow_queries': self._query_stats['slow_queries']
            }
        except Exception as e:
            print(f"âŒ Error getting query stats: {e}")
            return {
                'total_queries': 0,
                'total_time': 0.0,
                'avg_time': 0.0,
                'slow_queries': []
            }

    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report"""
        try:
            cache_stats = self.get_cache_stats()
            query_stats = self._get_query_stats()
            
            # Calculate uptime
            uptime = time.time() - self._performance_monitor['start_time']
            uptime_hours = uptime / 3600
            uptime_days = uptime / 86400
            
            return {
                'uptime_hours': uptime_hours,
                'uptime_days': uptime_days,
                'cache_stats': cache_stats,
                'query_stats': query_stats,
                'memory_usage_mb': self._memory_usage,
                'connection_pool_size': len(self._connection_pool),
                'prefetch_data_size': len(self._prefetch_data),
                'performance_log_path': getattr(self, '_performance_log_path', None)
            }
            
        except Exception as e:
            print(f"âŒ Error generating performance report: {e}")
            return {}

    def enable_performance_monitoring(self, enabled: bool = True):
        """Enable or disable performance monitoring"""
        self._performance_monitor['enabled'] = enabled
        
        if enabled and not hasattr(self, '_monitor_thread'):
            self._init_performance_monitoring()
        elif not enabled and hasattr(self, '_monitor_thread'):
            # Note: We can't actually stop the thread easily in Python
            print("âš ï¸ Performance monitoring disabled (thread will continue running)")
        
        print(f"ðŸ“Š Performance monitoring {'enabled' if enabled else 'disabled'}")

    # ==================== EXISTING METHODS ENHANCED WITH PERFORMANCE OPTIMIZATIONS ====================

    def load_profile(self, profile_id):
        """Load a specific profile with caching optimizations and recursion protection"""
        try:
            # Check if we're already loading this profile to prevent recursion
            with self._loading_lock:
                if profile_id in self._loading_profiles:
                    # Return minimal profile to break recursion
                    return self._load_minimal_profile(profile_id)
                
                # Mark this profile as being loaded
                self._loading_profiles.add(profile_id)
            
            # Try cache first
            cached_profile = self.get_cached_profile(profile_id)
            if cached_profile:
                with self._loading_lock:
                    self._loading_profiles.discard(profile_id)
                return cached_profile
            
            # If not in cache, load from database
            conn = self.get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM vehicle_profiles WHERE profile_id = ?', (profile_id,))
            result = cursor.fetchone()
            
            self.return_connection(conn)
            
            if result:
                profile = dict(result)
                self._ensure_profile_fields(profile)
                
                # Add AI enhancements if enabled - but avoid recursive calls
                if self.ai_integration_enabled:
                    profile['ai_health_score'] = self._calculate_profile_health_score(profile)
                    # Don't call _get_ai_driven_recommendations here to avoid recursion
                    # profile['ai_recommendations'] = self._get_ai_driven_recommendations(profile_id)
                    profile['trends'] = self._analyze_profile_trends(profile_id)
                
                # Clean up loading tracking
                with self._loading_lock:
                    self._loading_profiles.discard(profile_id)
                
                return profile
            
            # Clean up loading tracking
            with self._loading_lock:
                self._loading_profiles.discard(profile_id)
            return None
            
        except Exception as e:
            # Clean up loading tracking in case of error
            with self._loading_lock:
                self._loading_profiles.discard(profile_id)
            print(f"âŒ Error loading profile {profile_id}: {e}")
            return None

    def _load_minimal_profile(self, profile_id):
        """Load minimal profile data without triggering recursion"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT profile_id, name, make, model, year, category, is_connected, is_favorite
                FROM vehicle_profiles WHERE profile_id = ?
            ''', (profile_id,))
            
            result = cursor.fetchone()
            self.return_connection(conn)
            
            if result:
                profile = {
                    'profile_id': result[0],
                    'name': result[1],
                    'make': result[2],
                    'model': result[3],
                    'year': result[4],
                    'category': result[5],
                    'is_connected': result[6],
                    'is_favorite': result[7]
                }
                self._ensure_profile_fields(profile)
                return profile
            
            return None
            
        except Exception as e:
            print(f"âŒ Error loading minimal profile {profile_id}: {e}")
            return None

    def update_profile(self, profile_id, profile_data):
        """Update a vehicle profile with performance optimizations"""
        try:
            start_time = time.time()
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE vehicle_profiles SET
                    name=?, make=?, model=?, year=?, vin=?, license_plate=?, category=?,
                    engine_type=?, cylinders=?, displacement=?, transmission=?, fuel_type=?,
                    drivetrain=?, color=?,
                    purchase_date=?, last_service_date=?, dealer_info=?, warranty_info=?,
                    insurance_details=?, is_favorite=?, is_connected=?, updated_at=CURRENT_TIMESTAMP
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
                profile_data.get('cylinders'),
                profile_data.get('displacement'),
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
            
            conn.commit()
            self.return_connection(conn)
            
            # Clear cache for updated profile
            cache_key = f"profile_{profile_id}"
            with self._cache_lock:
                if cache_key in self._profile_cache:
                    del self._profile_cache[cache_key]
            
            processing_time = time.time() - start_time
            self._update_query_stats("update_profile", processing_time)
            
            print(f"âœ… Updated profile {profile_id} in {processing_time:.3f}s")
            return True
            
        except Exception as e:
            print(f"âŒ Error updating profile {profile_id}: {e}")
            return False

    def get_fleet_summary(self):
        """Get fleet summary with performance optimizations"""
        try:
            start_time = time.time()
            
            # Check if we have recent fleet summary in cache
            cache_key = "fleet_summary"
            with self._cache_lock:
                if cache_key in self._profile_cache:
                    cached_data, timestamp = self._profile_cache[cache_key]
                    
                    # Use cached data if less than 5 minutes old
                    if time.time() - timestamp < 300:
                        return cached_data
            
            # Generate fresh summary
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Use optimized query with COUNT and SUM
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_vehicles,
                    SUM(CASE WHEN is_connected = 1 THEN 1 ELSE 0 END) as connected_vehicles,
                    SUM(CASE WHEN maintenance_count > 2 THEN 1 ELSE 0 END) as maintenance_due,
                    SUM(total_costs) as total_costs,
                    SUM(total_distance) as total_distance
                FROM vehicle_profiles
            ''')
            
            result = cursor.fetchone()
            self.return_connection(conn)
            
            if result:
                total_vehicles, connected_vehicles, maintenance_due, total_costs, total_distance = result
                
                # Calculate derived metrics
                connected_percentage = (connected_vehicles / total_vehicles * 100) if total_vehicles > 0 else 0
                
                # Get AI-enhanced health metrics
                ai_metrics = self._get_fleet_ai_metrics()
                
                summary = {
                    'total_vehicles': total_vehicles,
                    'connected_vehicles': connected_vehicles,
                    'maintenance_due': maintenance_due,
                    'total_costs': total_costs if total_costs else 0,
                    'total_distance': total_distance if total_distance else 0,
                    'connected_percentage': connected_percentage,
                    'average_health_score': ai_metrics.get('average_health_score', 0),
                    'healthy_vehicles': ai_metrics.get('healthy_vehicles', 0),
                    'fleet_health_percentage': ai_metrics.get('fleet_health_percentage', 0),
                    'generated_at': datetime.now().isoformat()
                }
                
                # Cache the summary
                with self._cache_lock:
                    self._profile_cache[cache_key] = (summary, time.time())
                
                processing_time = time.time() - start_time
                self._update_query_stats("get_fleet_summary", processing_time)
                
                return summary
            
            return {
                'total_vehicles': 0,
                'connected_vehicles': 0,
                'maintenance_due': 0,
                'total_costs': 0,
                'total_distance': 0,
                'connected_percentage': 0,
                'average_health_score': 0,
                'healthy_vehicles': 0,
                'fleet_health_percentage': 0,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"âŒ Error getting fleet summary: {e}")
            return {
                'total_vehicles': 0,
                'connected_vehicles': 0,
                'maintenance_due': 0,
                'total_costs': 0,
                'total_distance': 0,
                'connected_percentage': 0,
                'average_health_score': 0,
                'healthy_vehicles': 0,
                'fleet_health_percentage': 0,
                'generated_at': datetime.now().isoformat()
            }

    def _get_fleet_ai_metrics(self) -> Dict[str, Any]:
        """Get AI metrics for fleet using cached data"""
        try:
            # Get all profiles from cache or database
            profiles = []
            
            # Try to get from cache first
            with self._cache_lock:
                for key, (data, timestamp) in self._profile_cache.items():
                    if key.startswith("profile_") and time.time() - timestamp < PERFORMANCE_CONFIG['cache_timeout']:
                        profiles.append(data)
            
            # If not enough profiles in cache, load from database
            if len(profiles) < 10:
                profiles = self.get_all_profiles_optimized()
            
            # Calculate AI metrics
            total_health_score = 0
            healthy_vehicles = 0
            
            for profile in profiles:
                health_score = profile.get('ai_health_score', 75)
                total_health_score += health_score
                
                if health_score >= 70:
                    healthy_vehicles += 1
            
            average_health_score = total_health_score / len(profiles) if profiles else 0
            fleet_health_percentage = (healthy_vehicles / len(profiles) * 100) if profiles else 0
            
            return {
                'average_health_score': average_health_score,
                'healthy_vehicles': healthy_vehicles,
                'fleet_health_percentage': fleet_health_percentage
            }
            
        except Exception as e:
            print(f"âŒ Error getting fleet AI metrics: {e}")
            return {
                'average_health_score': 0,
                'healthy_vehicles': 0,
                'fleet_health_percentage': 0
            }

    # ==================== ORIGINAL AI METHODS ====================

    def _calculate_profile_health_score(self, profile_data: dict) -> float:
        """Calculate health score using AI insights"""
        # Get AI insights if available
        if hasattr(self, 'ai_system') and self.ai_system:
            ai_insights = self.ai_system.get_profile_health_score(profile_data.get('profile_id', 0))
            if ai_insights:
                return ai_insights
        
        # Fallback to basic scoring
        score = 85.0  # Default good score
        
        # Deduct points for missing data
        if not profile_data.get('vin'):
            score -= 10
        if not profile_data.get('last_service_date'):
            score -= 5
        
        # Deduct points for age
        if profile_data.get('year'):
            current_year = datetime.now().year
            vehicle_age = current_year - profile_data['year']
            if vehicle_age > 10:
                score -= 10
            elif vehicle_age > 5:
                score -= 5
        
        return max(0, score)
    
    def _get_ai_driven_recommendations(self, profile_id: int) -> list:
        """Get AI-driven recommendations for vehicle profile without causing recursion"""
        recommendations = []
        
        # Get AI insights if available
        if hasattr(self, 'ai_system') and self.ai_system:
            ai_insights = self.ai_system.get_profile_insights(profile_id)
            if ai_insights:
                # Add AI recommendations
                recommendations.extend(ai_insights.get('recommendations', []))
        
        # Add basic recommendations using minimal profile data to avoid recursion
        profile = self._load_minimal_profile(profile_id)
        if profile:
            # Use minimal profile data for basic recommendations
            if profile.get('maintenance_count', 0) < 2:
                recommendations.append("No maintenance records found - consider service history")
            
            # Additional basic recommendations based on available data
            if not profile.get('last_service_date'):
                recommendations.append("Schedule initial service - no service history recorded")
        
        return recommendations
    
    def _analyze_profile_trends(self, profile_id: int) -> dict:
        """Analyze trends in profile data over time"""
        trends = {}
        
        try:
            # Get maintenance history
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT service_date, cost, mileage 
                FROM maintenance_records 
                WHERE vehicle_id = ? 
                ORDER BY service_date DESC 
                LIMIT 10
            """, (profile_id,))
            
            maintenance_history = cursor.fetchall()
            conn.close()
            
            if maintenance_history:
                # Calculate cost trend
                costs = [record[1] for record in maintenance_history if record[1]]
                if len(costs) > 1:
                    recent_costs = costs[:5]
                    older_costs = costs[5:]
                    recent_avg = sum(recent_costs) / len(recent_costs)
                    older_avg = sum(older_costs) / len(older_costs)
                    
                    if recent_avg > older_avg * 1.2:
                        trends['maintenance_cost'] = "increasing"
                    elif recent_avg < older_avg * 0.8:
                        trends['maintenance_cost'] = "decreasing"
                    else:
                        trends['maintenance_cost'] = "stable"
        except Exception as e:
            print(f"âŒ Error analyzing trends for profile {profile_id}: {e}")
        
        return trends
    
    def _validate_profile_data(self, profile_data):
        """Validate profile data before creation"""
        errors = []
        
        # Check required fields
        if not profile_data.get('name'):
            errors.append("Name is required")
        
        # Validate VIN format
        vin = profile_data.get('vin', '')
        if vin and len(vin) != 17:
            errors.append("VIN must be 17 characters")
        
        # Validate year
        year = profile_data.get('year')
        if year and (year < 1900 or year > datetime.now().year + 1):
            errors.append("Invalid year")
        
        return len(errors) == 0, errors
    
    # EXISTING METHODS ENHANCED WITH AI CAPABILITIES
    def get_all_profiles(self):
        """Get all vehicle profiles with proper error handling and AI enhancements"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM vehicle_profiles 
                ORDER BY is_favorite DESC, name ASC
            ''')
            
            profiles = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            # Ensure all expected fields exist
            for profile in profiles:
                self._ensure_profile_fields(profile)
                # Set default AI values - lazy load actual calculations when profile is selected
                profile['ai_health_score'] = None  # Lazy load on profile selection
                profile['ai_recommendations'] = []  # Lazy load on profile selection
                profile['trends'] = {}  # Lazy load on profile selection

            return profiles
            
        except Exception as e:
            print(f"âŒ Error getting profiles: {e}")
            return []

    def load_profile_ai_data(self, profile):
        """
        Load AI health score, recommendations, and trends for a single profile.
        Call this when a profile is selected to lazy-load AI data.

        Args:
            profile: dict with at least 'profile_id' key

        Returns:
            profile dict with AI data populated
        """
        try:
            if profile and 'profile_id' in profile:
                profile['ai_health_score'] = self._calculate_profile_health_score(profile)
                profile['ai_recommendations'] = self._get_ai_driven_recommendations(profile['profile_id'])
                profile['trends'] = self._analyze_profile_trends(profile['profile_id'])
        except Exception as e:
            print(f"Warning: Error loading AI data for profile: {e}")
            profile['ai_health_score'] = profile.get('ai_health_score')
            profile['ai_recommendations'] = profile.get('ai_recommendations', [])
            profile['trends'] = profile.get('trends', {})
        return profile

    def _ensure_profile_fields(self, profile):
        """Ensure all expected fields exist in profile"""
        expected_fields = {
            'is_connected': False,
            'is_favorite': False,
            'total_distance': 0,
            'total_driving_hours': 0,
            'maintenance_count': 0,
            'trip_count': 0,
            'total_costs': 0,
            'category': 'Commercial'
        }
        
        for field, default_value in expected_fields.items():
            if field not in profile:
                profile[field] = default_value
    
    def create_profile(self, profile_data):
        """Create a new vehicle profile with AI validation"""
        # AI ENHANCEMENT: Validate profile data before creation
        is_valid, errors = self._validate_profile_data(profile_data)
        
        if not is_valid:
            print(f"âŒ Profile validation failed: {', '.join(errors)}")
            return None
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Prepare data with defaults
            data = {
                'name': profile_data.get('name', 'Unnamed Vehicle'),
                'make': profile_data.get('make', ''),
                'model': profile_data.get('model', ''),
                'year': profile_data.get('year'),
                'vin': profile_data.get('vin', ''),
                'license_plate': profile_data.get('license_plate', ''),
                'category': profile_data.get('category', 'Commercial'),
                'engine_type': profile_data.get('engine_type', ''),
                'transmission': profile_data.get('transmission', ''),
                'fuel_type': profile_data.get('fuel_type', ''),
                'drivetrain': profile_data.get('drivetrain', ''),
                'color': profile_data.get('color', ''),
                'purchase_date': profile_data.get('purchase_date', ''),
                'last_service_date': profile_data.get('last_service_date', ''),
                'dealer_info': profile_data.get('dealer_info', ''),
                'warranty_info': profile_data.get('warranty_info', ''),
                'insurance_details': profile_data.get('insurance_details', ''),
                'is_connected': profile_data.get('is_connected', False),
                'is_favorite': profile_data.get('is_favorite', False),
                'owner_id': profile_data.get('owner_id')
            }

            cursor.execute('''
                INSERT INTO vehicle_profiles (
                    name, make, model, year, vin, license_plate, category,
                    engine_type, transmission, fuel_type, drivetrain, color,
                    purchase_date, last_service_date, dealer_info, warranty_info,
                    insurance_details, is_connected, is_favorite, owner_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', tuple(data.values()))
            
            profile_id = cursor.lastrowid

            # Generate API key for this profile
            api_key = self._generate_profile_api_key(cursor)
            import hashlib
            api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

            # Update profile with API key
            cursor.execute('''
                UPDATE vehicle_profiles
                SET api_key = ?, api_key_hash = ?
                WHERE profile_id = ?
            ''', (api_key, api_key_hash, profile_id))

            conn.commit()
            conn.close()

            # Return the created profile
            new_profile = data.copy()
            new_profile['profile_id'] = profile_id
            new_profile['api_key'] = api_key  # Include API key in response
            self._ensure_profile_fields(new_profile)

            # AI ENHANCEMENT: Calculate initial AI health score
            new_profile['ai_health_score'] = self._calculate_profile_health_score(profile_data)

            # Sync API key to server
            self._sync_profile_api_key_to_server(profile_id, api_key, new_profile)

            print(f"âœ… Created profile: {new_profile['name']} (ID: {profile_id}) with AI health score: {new_profile['ai_health_score']}")
            print(f"🔑 Generated API key: {api_key[:20]}...")
            return new_profile
            
        except Exception as e:
            print(f"âŒ Error creating profile: {e}")
            return None
    
    def add_profile(self, profile_data):
        """
        Add a new vehicle profile. Wrapper for create_profile for compatibility.
        
        Args:
            profile_data: Dict containing profile fields:
                - name: Profile name
                - customer_name: Customer name (optional)
                - make/brand: Vehicle manufacturer
                - model: Vehicle model
                - submodel: Vehicle submodel/variant (optional)
                - year: Model year
                - vin: Vehicle Identification Number
                - license_plate/plate: License plate number
                - And other optional fields...
        
        Returns:
            Created profile dict with profile_id, or None on failure
        """
        # Normalize field names for compatibility
        if 'brand' in profile_data and 'make' not in profile_data:
            profile_data['make'] = profile_data['brand']
        if 'plate' in profile_data and 'license_plate' not in profile_data:
            profile_data['license_plate'] = profile_data['plate']
        if 'customer_name' in profile_data:
            # Store customer name in dealer_info or notes for now
            profile_data['dealer_info'] = f"Customer: {profile_data['customer_name']}"
        
        return self.create_profile(profile_data)

    def _generate_profile_api_key(self, cursor):
        """
        Generate a unique API key for a profile.

        Returns:
            str: API key in format 'profile_XXXXX...'
        """
        import secrets

        max_attempts = 5
        for _ in range(max_attempts):
            # Generate cryptographically secure random token
            token = secrets.token_urlsafe(24)
            api_key = f"profile_{token}"

            # Check uniqueness in database
            cursor.execute('SELECT 1 FROM vehicle_profiles WHERE api_key = ?', (api_key,))
            if not cursor.fetchone():
                return api_key

        # Fallback (should never happen)
        raise Exception("Failed to generate unique API key after multiple attempts")

    def _sync_profile_api_key_to_server(self, profile_id: int, api_key: str, profile: dict):
        """
        Sync profile API key to server using ApiKeySync.

        Args:
            profile_id: The profile ID
            api_key: The generated API key
            profile: The profile data dict
        """
        try:
            from api_key_sync import ApiKeySync

            # Prepare key metadata
            key_data = {
                'name': f"Profile: {profile.get('name', 'Unknown')}",
                'role': 'driver',  # Profile-level keys have driver role
                'apps': ['obd'],  # Profiles have OBD access
                'profile_id': profile_id,
                'owner_id': profile.get('owner_id'),  # Link to owner if exists
                'tier': 'free',
                'permissions': ['vehicle_data', 'predict'],
                'status': 'active'
            }

            # Sync to server
            sync = ApiKeySync()
            success = sync.sync_api_key(api_key, key_data)

            if success:
                print(f"✅ API key synced to server for profile {profile_id}")
            else:
                print(f"⚠️ Failed to sync API key to server for profile {profile_id}")

            return success

        except Exception as e:
            print(f"⚠️ Error syncing API key to server: {e}")
            # Don't fail profile creation if sync fails
            return False

    def delete_profile(self, profile_id):
        """Delete a vehicle profile and ALL associated data (API keys, AI learning, history)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # First, unlink any child profiles (set parent_profile_id to NULL)
            try:
                cursor.execute(
                    'UPDATE vehicle_profiles SET parent_profile_id = NULL WHERE parent_profile_id = ?',
                    (profile_id,)
                )
            except Exception:
                pass  # Column might not exist in older databases

            # Delete the profile
            cursor.execute('DELETE FROM vehicle_profiles WHERE profile_id = ?', (profile_id,))
            conn.commit()
            conn.close()

            # Clean up all associated data
            self._cleanup_api_keys_for_profile(profile_id)
            self._cleanup_ai_learning_data(profile_id)
            self._cleanup_historical_data(profile_id)
            
            print(f"âœ… Deleted profile ID: {profile_id}")
            return True
            
        except Exception as e:
            print(f"âŒ Error deleting profile {profile_id}: {e}")
            return False

    def _cleanup_api_keys_for_profile(self, profile_id: int):
        """Remove API keys associated with a deleted profile"""
        try:
            from pathlib import Path

            # Try to get API keys path from config
            try:
                from config import get_config
                config = get_config()
                api_keys_path = config.API_KEYS_FILE
            except:
                # Fallback paths
                api_keys_path = Path("PredictData/system/config/api_keys.json")
                if not api_keys_path.exists():
                    api_keys_path = Path("config/api_keys.json")

            if not api_keys_path.exists():
                db_logger.debug(f"API keys file not found, skipping cleanup")
                return

            with open(api_keys_path, 'r') as f:
                api_keys = json.load(f)

            # Find and remove keys for this profile
            keys_to_remove = [
                key_id for key_id, data in api_keys.items()
                if data.get('profile_id') == profile_id
            ]

            if not keys_to_remove:
                db_logger.debug(f"No API keys found for profile {profile_id}")
                return

            for key_id in keys_to_remove:
                del api_keys[key_id]
                db_logger.info(f"Removed API key {key_id} for deleted profile {profile_id}")

            # Save updated keys
            with open(api_keys_path, 'w') as f:
                json.dump(api_keys, f, indent=2)

            # Sync to server
            try:
                from api_key_sync import sync_api_keys_to_server
                sync_api_keys_to_server()
                db_logger.info(f"Synced API keys after profile deletion")
            except Exception as sync_error:
                db_logger.warning(f"Failed to sync API keys to server: {sync_error}")

            print(f"Cleaned up {len(keys_to_remove)} API key(s) for profile {profile_id}")

        except Exception as e:
            db_logger.error(f"Failed to cleanup API keys for profile {profile_id}: {e}")

    def _cleanup_ai_learning_data(self, profile_id: int):
        """Remove AI learning data associated with a deleted profile"""
        try:
            from pathlib import Path

            # Try to get data paths from config
            try:
                from config import get_config
                config = get_config()
                data_dir = config.DATA_DIR
            except:
                data_dir = Path("PredictData")

            # Clean up AI model files for this profile
            ai_models_dir = data_dir / "ai_models"
            if ai_models_dir.exists():
                import shutil
                profile_model_dir = ai_models_dir / f"profile_{profile_id}"
                if profile_model_dir.exists():
                    shutil.rmtree(profile_model_dir)
                    db_logger.info(f"Removed AI model directory for profile {profile_id}")

                # Also remove any profile-specific model files
                for model_file in ai_models_dir.glob(f"*_profile_{profile_id}*"):
                    model_file.unlink()
                    db_logger.info(f"Removed AI model file: {model_file.name}")

            # Clean up learning database entries if they exist
            learning_db = data_dir / "learning" / "vehicle_learning.db"
            if learning_db.exists():
                import sqlite3
                conn = sqlite3.connect(learning_db)
                cursor = conn.cursor()

                # Delete learning data for this profile
                tables_to_clean = [
                    'learned_thresholds',
                    'driving_patterns',
                    'anomaly_baselines',
                    'prediction_history'
                ]

                for table in tables_to_clean:
                    try:
                        cursor.execute(f'DELETE FROM {table} WHERE profile_id = ?', (profile_id,))
                    except:
                        pass  # Table might not exist

                conn.commit()
                conn.close()
                db_logger.info(f"Cleaned up AI learning database entries for profile {profile_id}")

            print(f"Cleaned up AI learning data for profile {profile_id}")

        except Exception as e:
            db_logger.error(f"Failed to cleanup AI learning data for profile {profile_id}: {e}")

    def _cleanup_historical_data(self, profile_id: int):
        """Remove historical OBD data associated with a deleted profile"""
        try:
            from pathlib import Path

            # Try to get data paths from config
            try:
                from config import get_config
                config = get_config()
                data_dir = config.DATA_DIR
            except:
                data_dir = Path("PredictData")

            # Clean up historical data files
            history_dir = data_dir / "history"
            if history_dir.exists():
                import shutil
                profile_history_dir = history_dir / f"profile_{profile_id}"
                if profile_history_dir.exists():
                    shutil.rmtree(profile_history_dir)
                    db_logger.info(f"Removed history directory for profile {profile_id}")

                # Also remove any profile-specific history files
                for history_file in history_dir.glob(f"*_profile_{profile_id}*"):
                    history_file.unlink()
                    db_logger.info(f"Removed history file: {history_file.name}")

            # Clean up OBD data database entries
            obd_db = data_dir / "obd_data.db"
            if obd_db.exists():
                import sqlite3
                conn = sqlite3.connect(obd_db)
                cursor = conn.cursor()

                # Delete OBD readings for this profile
                tables_to_clean = [
                    'obd_readings',
                    'sensor_data',
                    'dtc_history',
                    'trip_data'
                ]

                for table in tables_to_clean:
                    try:
                        cursor.execute(f'DELETE FROM {table} WHERE profile_id = ?', (profile_id,))
                    except:
                        pass  # Table might not exist

                conn.commit()
                conn.close()
                db_logger.info(f"Cleaned up OBD database entries for profile {profile_id}")

            # Clean up server database entries
            try:
                server_db = Path("Previlium_OBD_Server/obd_data.db")
                if server_db.exists():
                    import sqlite3
                    conn = sqlite3.connect(server_db)
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM obd_readings WHERE profile_id = ?', (profile_id,))
                    cursor.execute('DELETE FROM live_data WHERE profile_id = ?', (profile_id,))
                    conn.commit()
                    conn.close()
                    db_logger.info(f"Cleaned up server database entries for profile {profile_id}")
            except Exception as server_err:
                db_logger.debug(f"Server database cleanup skipped: {server_err}")

            print(f"Cleaned up historical data for profile {profile_id}")

        except Exception as e:
            db_logger.error(f"Failed to cleanup historical data for profile {profile_id}: {e}")

    # ==================== DRIVER MANAGEMENT METHODS ====================

    def get_drivers_for_profile(self, profile_id: int) -> List[Dict[str, Any]]:
        """Get all active drivers for a vehicle profile"""
        try:
            conn = self.get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT driver_id, profile_id, name, age, license_number, phone, email,
                       photo_url, is_primary, relationship, guardian_role,
                       is_active, created_at, updated_at
                FROM drivers
                WHERE profile_id = ? AND is_active = 1
                ORDER BY is_primary DESC, name ASC
            ''', (profile_id,))

            drivers = [dict(row) for row in cursor.fetchall()]
            self.return_connection(conn)

            return drivers

        except Exception as e:
            db_logger.error(f"Error getting drivers for profile {profile_id}: {e}")
            return []

    def get_driver_by_id(self, driver_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific driver by ID"""
        try:
            conn = self.get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT driver_id, profile_id, name, age, license_number, phone, email,
                       photo_url, is_primary, relationship, guardian_role,
                       is_active, created_at, updated_at
                FROM drivers
                WHERE driver_id = ?
            ''', (driver_id,))

            result = cursor.fetchone()
            self.return_connection(conn)

            return dict(result) if result else None

        except Exception as e:
            db_logger.error(f"Error getting driver {driver_id}: {e}")
            return None

    def add_driver(self, profile_id: int, driver_data: Dict[str, Any]) -> Optional[str]:
        """Add a new driver to a vehicle profile"""
        try:
            import uuid

            # Generate unique driver ID
            driver_id = driver_data.get('driver_id') or str(uuid.uuid4())

            conn = self.get_connection()
            cursor = conn.cursor()

            # Ensure drivers table exists (fallback if migration didn't run)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS drivers (
                    driver_id TEXT PRIMARY KEY,
                    profile_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    age INTEGER,
                    license_number TEXT,
                    phone TEXT,
                    email TEXT,
                    photo_url TEXT,
                    is_primary INTEGER DEFAULT 0,
                    relationship TEXT DEFAULT 'driver',
                    guardian_role TEXT DEFAULT 'driver',
                    is_active INTEGER DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    synced_at DATETIME,
                    server_updated_at DATETIME,
                    FOREIGN KEY (profile_id) REFERENCES vehicle_profiles(profile_id) ON DELETE CASCADE
                )
            ''')

            # Migration: Add guardian_role column if it doesn't exist (for existing databases)
            try:
                cursor.execute("PRAGMA table_info(drivers)")
                columns = [col[1] for col in cursor.fetchall()]
                if 'guardian_role' not in columns:
                    cursor.execute("ALTER TABLE drivers ADD COLUMN guardian_role TEXT DEFAULT 'driver'")
                    db_logger.info("Migrated drivers table: added guardian_role column")
            except Exception as migration_err:
                db_logger.warning(f"Guardian role migration check: {migration_err}")

            # Check if this is the first driver (make primary)
            cursor.execute('SELECT COUNT(*) FROM drivers WHERE profile_id = ? AND is_active = 1', (profile_id,))
            existing_count = cursor.fetchone()[0]
            is_primary = 1 if existing_count == 0 else (1 if driver_data.get('is_primary') else 0)

            # If marking as primary, unset other primaries
            if is_primary:
                cursor.execute('''
                    UPDATE drivers SET is_primary = 0
                    WHERE profile_id = ? AND is_active = 1
                ''', (profile_id,))

            cursor.execute('''
                INSERT INTO drivers (
                    driver_id, profile_id, name, age, license_number, phone, email,
                    photo_url, is_primary, relationship, guardian_role, is_active,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (
                driver_id,
                profile_id,
                driver_data.get('name', 'Unknown Driver'),
                driver_data.get('age'),
                driver_data.get('license_number'),
                driver_data.get('phone'),
                driver_data.get('email'),
                driver_data.get('photo_url'),
                is_primary,
                driver_data.get('relationship', 'driver'),
                driver_data.get('guardian_role', 'driver')
            ))

            conn.commit()
            self.return_connection(conn)

            db_logger.info(f"Added driver {driver_id} ({driver_data.get('name')}) to profile {profile_id}")
            return driver_id

        except Exception as e:
            db_logger.error(f"Error adding driver to profile {profile_id}: {e}")
            return None

    def update_driver(self, driver_id: str, driver_data: Dict[str, Any]) -> bool:
        """Update an existing driver"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Build dynamic update query
            update_fields = []
            params = []

            field_mapping = {
                'name': 'name',
                'age': 'age',
                'license_number': 'license_number',
                'phone': 'phone',
                'email': 'email',
                'photo_url': 'photo_url',
                'relationship': 'relationship',
                'guardian_role': 'guardian_role'
            }

            for key, column in field_mapping.items():
                if key in driver_data:
                    update_fields.append(f"{column} = ?")
                    params.append(driver_data[key])

            if not update_fields:
                return True  # Nothing to update

            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            params.append(driver_id)

            cursor.execute(f'''
                UPDATE drivers SET {', '.join(update_fields)}
                WHERE driver_id = ?
            ''', params)

            conn.commit()
            self.return_connection(conn)

            db_logger.info(f"Updated driver {driver_id}")
            return True

        except Exception as e:
            db_logger.error(f"Error updating driver {driver_id}: {e}")
            return False

    def remove_driver(self, driver_id: str) -> bool:
        """Soft delete a driver (set is_active = 0)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Get profile_id before deactivating
            cursor.execute('SELECT profile_id, is_primary FROM drivers WHERE driver_id = ?', (driver_id,))
            result = cursor.fetchone()

            if not result:
                self.return_connection(conn)
                return False

            profile_id, was_primary = result

            # Deactivate the driver
            cursor.execute('''
                UPDATE drivers SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE driver_id = ?
            ''', (driver_id,))

            # If this was the primary driver, promote another
            if was_primary:
                cursor.execute('''
                    UPDATE drivers SET is_primary = 1
                    WHERE profile_id = ? AND is_active = 1
                    ORDER BY created_at ASC
                    LIMIT 1
                ''', (profile_id,))

            conn.commit()
            self.return_connection(conn)

            db_logger.info(f"Removed driver {driver_id} from profile {profile_id}")
            return True

        except Exception as e:
            db_logger.error(f"Error removing driver {driver_id}: {e}")
            return False

    def set_primary_driver(self, profile_id: int, driver_id: str) -> bool:
        """Set a driver as the primary driver for a profile"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Unset all primaries for this profile
            cursor.execute('''
                UPDATE drivers SET is_primary = 0, updated_at = CURRENT_TIMESTAMP
                WHERE profile_id = ? AND is_active = 1
            ''', (profile_id,))

            # Set the new primary
            cursor.execute('''
                UPDATE drivers SET is_primary = 1, updated_at = CURRENT_TIMESTAMP
                WHERE driver_id = ? AND profile_id = ?
            ''', (driver_id, profile_id))

            conn.commit()
            self.return_connection(conn)

            db_logger.info(f"Set driver {driver_id} as primary for profile {profile_id}")
            return True

        except Exception as e:
            db_logger.error(f"Error setting primary driver {driver_id}: {e}")
            return False

    def get_primary_driver(self, profile_id: int) -> Optional[Dict[str, Any]]:
        """Get the primary driver for a profile"""
        try:
            conn = self.get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT driver_id, profile_id, name, age, license_number, phone, email,
                       photo_url, is_primary, relationship, is_active, created_at
                FROM drivers
                WHERE profile_id = ? AND is_primary = 1 AND is_active = 1
                LIMIT 1
            ''', (profile_id,))

            result = cursor.fetchone()
            self.return_connection(conn)

            return dict(result) if result else None

        except Exception as e:
            db_logger.error(f"Error getting primary driver for profile {profile_id}: {e}")
            return None

    # ==================== DRIVER SESSION METHODS ====================

    def start_driver_session(self, profile_id: int, driver_id: str) -> Optional[str]:
        """Start a new driving session for a driver"""
        try:
            import uuid

            # End any existing active sessions for this profile
            self.end_active_sessions_for_profile(profile_id)

            session_id = str(uuid.uuid4())

            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO driver_sessions (
                    session_id, profile_id, driver_id, started_at, status
                ) VALUES (?, ?, ?, CURRENT_TIMESTAMP, 'active')
            ''', (session_id, profile_id, driver_id))

            conn.commit()
            self.return_connection(conn)

            db_logger.info(f"Started session {session_id} for driver {driver_id} on profile {profile_id}")
            return session_id

        except Exception as e:
            db_logger.error(f"Error starting session for driver {driver_id}: {e}")
            return None

    def end_driver_session(self, session_id: str, distance_km: float = 0,
                          safety_score: int = None, violations_count: int = 0) -> bool:
        """End a driving session with final stats"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Get session start time to calculate duration
            cursor.execute('SELECT started_at FROM driver_sessions WHERE session_id = ?', (session_id,))
            result = cursor.fetchone()

            if not result:
                self.return_connection(conn)
                return False

            cursor.execute('''
                UPDATE driver_sessions SET
                    ended_at = CURRENT_TIMESTAMP,
                    distance_km = ?,
                    duration_minutes = (julianday(CURRENT_TIMESTAMP) - julianday(started_at)) * 24 * 60,
                    safety_score = ?,
                    violations_count = ?,
                    status = 'completed'
                WHERE session_id = ?
            ''', (distance_km, safety_score, violations_count, session_id))

            conn.commit()
            self.return_connection(conn)

            db_logger.info(f"Ended session {session_id}")
            return True

        except Exception as e:
            db_logger.error(f"Error ending session {session_id}: {e}")
            return False

    def end_active_sessions_for_profile(self, profile_id: int) -> bool:
        """End all active sessions for a profile"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE driver_sessions SET
                    ended_at = CURRENT_TIMESTAMP,
                    status = 'ended'
                WHERE profile_id = ? AND status = 'active'
            ''', (profile_id,))

            conn.commit()
            self.return_connection(conn)

            return True

        except Exception as e:
            db_logger.error(f"Error ending sessions for profile {profile_id}: {e}")
            return False

    def get_active_session(self, profile_id: int) -> Optional[Dict[str, Any]]:
        """Get the active driving session for a profile"""
        try:
            conn = self.get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT ds.session_id, ds.profile_id, ds.driver_id, ds.started_at,
                       ds.distance_km, ds.duration_minutes, ds.status,
                       d.name as driver_name, d.relationship
                FROM driver_sessions ds
                JOIN drivers d ON ds.driver_id = d.driver_id
                WHERE ds.profile_id = ? AND ds.status = 'active'
                LIMIT 1
            ''', (profile_id,))

            result = cursor.fetchone()
            self.return_connection(conn)

            return dict(result) if result else None

        except Exception as e:
            db_logger.error(f"Error getting active session for profile {profile_id}: {e}")
            return None

    def get_driver_sessions(self, driver_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent sessions for a driver"""
        try:
            conn = self.get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT session_id, profile_id, driver_id, started_at, ended_at,
                       distance_km, duration_minutes, safety_score, violations_count, status
                FROM driver_sessions
                WHERE driver_id = ?
                ORDER BY started_at DESC
                LIMIT ?
            ''', (driver_id, limit))

            sessions = [dict(row) for row in cursor.fetchall()]
            self.return_connection(conn)

            return sessions

        except Exception as e:
            db_logger.error(f"Error getting sessions for driver {driver_id}: {e}")
            return []

    def get_driver_count_for_profile(self, profile_id: int) -> int:
        """Get the count of active drivers for a profile"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT COUNT(*) FROM drivers
                WHERE profile_id = ? AND is_active = 1
            ''', (profile_id,))

            count = cursor.fetchone()[0]
            self.return_connection(conn)

            return count

        except Exception as e:
            db_logger.error(f"Error getting driver count for profile {profile_id}: {e}")
            return 0

    # ==================== OWNER MANAGEMENT METHODS ====================

    def get_all_owners(self) -> List[Dict[str, Any]]:
        """Get all active owners"""
        try:
            conn = self.get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT o.owner_id, o.name, o.email, o.phone, o.api_key, o.role, o.apps,
                       o.is_active, o.created_at, o.updated_at,
                       COUNT(DISTINCT vp.profile_id) as vehicle_count,
                       COUNT(DISTINCT d.driver_id) as driver_count
                FROM owners o
                LEFT JOIN vehicle_profiles vp ON o.owner_id = vp.owner_id
                LEFT JOIN drivers d ON vp.profile_id = d.profile_id AND d.is_active = 1
                WHERE o.is_active = 1
                GROUP BY o.owner_id
                ORDER BY o.name ASC
            ''')

            owners = [dict(row) for row in cursor.fetchall()]
            self.return_connection(conn)

            return owners

        except Exception as e:
            db_logger.error(f"Error getting all owners: {e}")
            return []

    def get_owner_by_id(self, owner_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific owner by ID"""
        try:
            conn = self.get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT owner_id, name, email, phone, api_key, api_key_hash,
                       role, apps, is_active, created_at, updated_at
                FROM owners
                WHERE owner_id = ?
            ''', (owner_id,))

            result = cursor.fetchone()
            self.return_connection(conn)

            return dict(result) if result else None

        except Exception as e:
            db_logger.error(f"Error getting owner {owner_id}: {e}")
            return None

    def add_owner(self, owner_data: Dict[str, Any]) -> Optional[int]:
        """Add a new owner"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO owners (name, email, phone, api_key, api_key_hash, role, apps)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                owner_data.get('name', 'Unknown Owner'),
                owner_data.get('email'),
                owner_data.get('phone'),
                owner_data.get('api_key'),
                owner_data.get('api_key_hash'),
                owner_data.get('role', 'owner'),
                owner_data.get('apps', 'obd,guardian')
            ))

            owner_id = cursor.lastrowid
            conn.commit()
            self.return_connection(conn)

            db_logger.info(f"Added owner {owner_id} ({owner_data.get('name')})")
            return owner_id

        except Exception as e:
            db_logger.error(f"Error adding owner: {e}")
            return None

    def update_owner(self, owner_id: int, owner_data: Dict[str, Any]) -> bool:
        """Update an existing owner"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Build dynamic update query
            update_fields = []
            params = []

            field_mapping = {
                'name': 'name',
                'email': 'email',
                'phone': 'phone',
                'api_key': 'api_key',
                'api_key_hash': 'api_key_hash',
                'role': 'role',
                'apps': 'apps'
            }

            for key, column in field_mapping.items():
                if key in owner_data:
                    update_fields.append(f"{column} = ?")
                    params.append(owner_data[key])

            if not update_fields:
                return True  # Nothing to update

            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            params.append(owner_id)

            cursor.execute(f'''
                UPDATE owners SET {', '.join(update_fields)}
                WHERE owner_id = ?
            ''', params)

            conn.commit()
            self.return_connection(conn)

            db_logger.info(f"Updated owner {owner_id}")
            return True

        except Exception as e:
            db_logger.error(f"Error updating owner {owner_id}: {e}")
            return False

    def delete_owner(self, owner_id: int) -> bool:
        """Soft delete an owner (set is_active = 0)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Unlink all vehicles from this owner first
            cursor.execute('''
                UPDATE vehicle_profiles SET owner_id = NULL
                WHERE owner_id = ?
            ''', (owner_id,))

            # Deactivate the owner
            cursor.execute('''
                UPDATE owners SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE owner_id = ?
            ''', (owner_id,))

            conn.commit()
            self.return_connection(conn)

            db_logger.info(f"Deleted owner {owner_id}")
            return True

        except Exception as e:
            db_logger.error(f"Error deleting owner {owner_id}: {e}")
            return False

    def get_vehicles_for_owner(self, owner_id: int) -> List[Dict[str, Any]]:
        """Get all vehicles owned by an owner"""
        try:
            conn = self.get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT vp.profile_id, vp.name, vp.make, vp.model, vp.year, vp.vin,
                       vp.license_plate, vp.is_connected, vp.is_favorite, vp.api_key,
                       COUNT(d.driver_id) as driver_count
                FROM vehicle_profiles vp
                LEFT JOIN drivers d ON vp.profile_id = d.profile_id AND d.is_active = 1
                WHERE vp.owner_id = ?
                GROUP BY vp.profile_id
                ORDER BY vp.name ASC
            ''', (owner_id,))

            vehicles = [dict(row) for row in cursor.fetchall()]
            self.return_connection(conn)

            return vehicles

        except Exception as e:
            db_logger.error(f"Error getting vehicles for owner {owner_id}: {e}")
            return []

    def get_unassigned_vehicles(self) -> List[Dict[str, Any]]:
        """Get vehicles that have no owner assigned"""
        try:
            conn = self.get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT vp.profile_id, vp.name, vp.make, vp.model, vp.year, vp.vin,
                       vp.license_plate, vp.is_connected, vp.is_favorite,
                       COUNT(d.driver_id) as driver_count
                FROM vehicle_profiles vp
                LEFT JOIN drivers d ON vp.profile_id = d.profile_id AND d.is_active = 1
                WHERE vp.owner_id IS NULL
                GROUP BY vp.profile_id
                ORDER BY vp.name ASC
            ''')

            vehicles = [dict(row) for row in cursor.fetchall()]
            self.return_connection(conn)

            return vehicles

        except Exception as e:
            db_logger.error(f"Error getting unassigned vehicles: {e}")
            return []

    def assign_vehicle_to_owner(self, profile_id: int, owner_id: int) -> bool:
        """Assign a vehicle to an owner"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE vehicle_profiles
                SET owner_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE profile_id = ?
            ''', (owner_id, profile_id))

            conn.commit()
            self.return_connection(conn)

            db_logger.info(f"Assigned vehicle {profile_id} to owner {owner_id}")
            return True

        except Exception as e:
            db_logger.error(f"Error assigning vehicle {profile_id} to owner {owner_id}: {e}")
            return False

    def unassign_vehicle_from_owner(self, profile_id: int) -> bool:
        """Remove owner assignment from a vehicle"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE vehicle_profiles
                SET owner_id = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE profile_id = ?
            ''', (profile_id,))

            conn.commit()
            self.return_connection(conn)

            db_logger.info(f"Unassigned vehicle {profile_id} from owner")
            return True

        except Exception as e:
            db_logger.error(f"Error unassigning vehicle {profile_id}: {e}")
            return False

    def get_owner_for_vehicle(self, profile_id: int) -> Optional[Dict[str, Any]]:
        """Get the owner of a specific vehicle"""
        try:
            conn = self.get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT o.owner_id, o.name, o.email, o.phone, o.role, o.apps
                FROM owners o
                JOIN vehicle_profiles vp ON o.owner_id = vp.owner_id
                WHERE vp.profile_id = ? AND o.is_active = 1
            ''', (profile_id,))

            result = cursor.fetchone()
            self.return_connection(conn)

            return dict(result) if result else None

        except Exception as e:
            db_logger.error(f"Error getting owner for vehicle {profile_id}: {e}")
            return None

    def set_favorite(self, profile_id, favorite):
        """Set favorite status"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                'UPDATE vehicle_profiles SET is_favorite = ? WHERE profile_id = ?',
                (favorite, profile_id)
            )
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"âŒ Error setting favorite for {profile_id}: {e}")
            return False
    
    def set_connected(self, profile_id, connected):
        """Set connected status"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                'UPDATE vehicle_profiles SET is_connected = ? WHERE profile_id = ?',
                (connected, profile_id)
            )
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"âŒ Error setting connected for {profile_id}: {e}")
            return False

    def update_last_seen(self, profile_id):
        """Update last_seen timestamp when data is received from profile"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                'UPDATE vehicle_profiles SET last_seen = ?, ever_connected = 1 WHERE profile_id = ?',
                (datetime.now().isoformat(), profile_id)
            )

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"Error updating last_seen for {profile_id}: {e}")
            return False

    def update_last_seen_by_name(self, profile_name):
        """Update last_seen timestamp by profile name"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                'UPDATE vehicle_profiles SET last_seen = ?, ever_connected = 1 WHERE name = ?',
                (datetime.now().isoformat(), profile_name)
            )

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"Error updating last_seen for {profile_name}: {e}")
            return False

    def get_categories(self):
        """Get all categories"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM vehicle_categories')
            categories = [{'category_name': row[0], 'color': row[1]} for row in cursor.fetchall()]
            conn.close()
            
            return categories
            
        except Exception as e:
            print(f"âŒ Error getting categories: {e}")
            return [{'category_name': 'Commercial', 'color': '#3498db'}]
    
    def create_category(self, name, color='#3498db'):
        """Create a new category"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                'INSERT OR IGNORE INTO vehicle_categories (category_name, color) VALUES (?, ?)',
                (name, color)
            )
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"âŒ Error creating category {name}: {e}")
            return False
    
    def delete_category(self, name):
        """Delete a category"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Move vehicles to default category
            cursor.execute(
                'UPDATE vehicle_profiles SET category = ? WHERE category = ?',
                ('Commercial', name)
            )
            
            # Delete category
            cursor.execute('DELETE FROM vehicle_categories WHERE category_name = ?', (name,))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"âŒ Error deleting category {name}: {e}")
            return False
    
    def search_profiles(self, query, category=None, favorite_only=False):
        """Search profiles with filters"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            sql = '''
                SELECT * FROM vehicle_profiles 
                WHERE (name LIKE ? OR make LIKE ? OR model LIKE ? OR vin LIKE ?)
            '''
            params = [f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%']
            
            if category:
                sql += ' AND category = ?'
                params.append(category)
            
            if favorite_only:
                sql += ' AND is_favorite = 1'
            
            sql += ' ORDER BY is_favorite DESC, name ASC'
            
            cursor.execute(sql, params)
            profiles = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            # Ensure all fields exist
            for profile in profiles:
                self._ensure_profile_fields(profile)
            
            # AI ENHANCEMENT: Add AI insights to search results
            for profile in profiles:
                profile['ai_health_score'] = self._calculate_profile_health_score(profile)
                profile['ai_recommendations'] = self._get_ai_driven_recommendations(profile['profile_id'])
            
            return profiles
            
        except Exception as e:
            print(f"âŒ Error searching profiles: {e}")
            return []
    
    def get_vehicles_by_status(self):
        """Get vehicles grouped by status for fleet overview with AI enhancements"""
        profiles = self.get_all_profiles()
        
        status_groups = {
            'operational': [],
            'monitoring': [],
            'attention': [],
            'offline': []
        }
        
        for profile in profiles:
            if profile.get('is_connected'):
                # AI ENHANCEMENT: Use health score for status determination
                health_score = profile.get('ai_health_score', 0)
                
                if health_score >= 80 and profile.get('maintenance_count', 0) <= 1 and profile.get('total_costs', 0) < 500:
                    status_groups['operational'].append(profile)
                elif health_score >= 60 and profile.get('maintenance_count', 0) <= 2:
                    status_groups['monitoring'].append(profile)
                else:
                    status_groups['attention'].append(profile)
            else:
                status_groups['offline'].append(profile)
        
        return status_groups

# Convenience functions
def get_vehicle_manager():
    """Get vehicle manager instance"""
    return VehicleProfileManager()

if __name__ == "__main__":
    # Test the vehicle manager
    manager = VehicleProfileManager()
    
    print("ðŸ“Š Vehicle Profiles:")
    profiles = manager.get_all_profiles()
    for profile in profiles:
        health_score = profile.get('ai_health_score', 'N/A')
        print(f"  - {profile['name']} (ID: {profile['profile_id']}) - Health Score: {health_score}")
    
    print("ðŸ“‚ Categories:")
    categories = manager.get_categories()
    for category in categories:
        print(f"  - {category['category_name']}")
    
    print("ðŸ¢ Fleet Summary:")
    fleet_summary = manager.get_fleet_summary()
    for key, value in fleet_summary.items():
        print(f"  - {key}: {value}")
    
    print("ðŸ“ˆ Performance Report:")
    performance_report = manager.get_performance_report()
    for key, value in performance_report.items():
        print(f"  - {key}: {value}")