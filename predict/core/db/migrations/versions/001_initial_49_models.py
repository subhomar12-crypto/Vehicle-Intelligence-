"""
Initial migration - 49 ORM models

Revision ID: 001
Revises: 
Create Date: 2026-02-08 13:00:00.000000

This migration creates all 49 tables across 8 domains:
- User (9 tables)
- Vehicle (5 tables)
- DTC (2 tables)
- Guardian (8 tables)
- Trip (8 tables)
- Prediction (5 tables)
- Subscription (5 tables)
- Audit (7 tables)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all 49 tables for PREDICT v3.0.0."""
    
    # ========================
    # USER DOMAIN (9 tables)
    # ========================
    
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('password_hash', sa.String(255), nullable=True),
        sa.Column('name', sa.String(100), nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_verified', sa.Boolean(), default=False),
        sa.Column('tier', sa.String(20), default='free'),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.Column('updated_at', sa.Float(), nullable=False),
        sa.Column('last_login', sa.Float(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), default={}),
    )
    
    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('key_hash', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('legacy_sha256_hash', sa.String(64), nullable=True, index=True),
        sa.Column('name', sa.String(100), nullable=True),
        sa.Column('tier', sa.String(20), default='free'),
        sa.Column('permissions', postgresql.JSONB(), default=[]),
        sa.Column('apps', postgresql.JSONB(), default=['obd']),
        sa.Column('rate_limit', sa.Integer(), default=100),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('expires_at', sa.Float(), nullable=True),
        sa.Column('last_used_at', sa.Float(), nullable=True),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=True, index=True),
    )
    
    op.create_table(
        'entitlements',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('feature', sa.String(50), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), default=True),
        sa.Column('expires_at', sa.Float(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), default={}),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'rate_limits',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('api_key_id', sa.Integer(), sa.ForeignKey('api_keys.id', ondelete='CASCADE'), nullable=False),
        sa.Column('endpoint', sa.String(100), nullable=False),
        sa.Column('requests_count', sa.Integer(), default=0),
        sa.Column('window_start', sa.Float(), nullable=False),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'usage_counters',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('api_key_id', sa.Integer(), sa.ForeignKey('api_keys.id', ondelete='CASCADE'), nullable=False),
        sa.Column('feature', sa.String(50), nullable=False),
        sa.Column('count', sa.Integer(), default=0),
        sa.Column('period', sa.String(20), nullable=False),  # daily, monthly
        sa.Column('reset_at', sa.Float(), nullable=False),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'tier_presets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(20), unique=True, nullable=False),
        sa.Column('display_name', sa.String(50), nullable=False),
        sa.Column('price_monthly', sa.Numeric(10, 2), nullable=False),
        sa.Column('price_yearly', sa.Numeric(10, 2), nullable=False),
        sa.Column('features', postgresql.JSONB(), default={}),
        sa.Column('limits', postgresql.JSONB(), default={}),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'driver_assignments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('guardian_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('driver_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('vehicle_profile_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'user_feature_overrides',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('feature', sa.String(50), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.Float(), nullable=True),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'pricing_configs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('country_code', sa.String(2), nullable=False),
        sa.Column('currency', sa.String(3), default='USD'),
        sa.Column('tier_name', sa.String(20), nullable=False),
        sa.Column('price_monthly', sa.Numeric(10, 2), nullable=False),
        sa.Column('price_yearly', sa.Numeric(10, 2), nullable=False),
        sa.Column('tax_rate', sa.Numeric(5, 4), default=0),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.UniqueConstraint('country_code', 'tier_name', name='unique_country_tier'),
    )
    
    # ========================
    # VEHICLE DOMAIN (5 tables)
    # ========================
    
    op.create_table(
        'vehicle_profiles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('vin', sa.String(17), unique=True, nullable=True, index=True),
        sa.Column('make', sa.String(50), nullable=True),
        sa.Column('model', sa.String(50), nullable=True),
        sa.Column('year', sa.Integer(), nullable=True),
        sa.Column('engine_type', sa.String(20), nullable=True),
        sa.Column('mileage', sa.Integer(), nullable=True),
        sa.Column('nickname', sa.String(50), nullable=True),
        sa.Column('color', sa.String(20), nullable=True),
        sa.Column('license_plate', sa.String(20), nullable=True),
        sa.Column('fuel_type', sa.String(20), nullable=True),
        sa.Column('transmission', sa.String(20), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), default={}),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.Column('updated_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'vehicle_data',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('profile_id', sa.Integer(), sa.ForeignKey('vehicle_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('timestamp', sa.Float(), nullable=False, index=True),
        sa.Column('rpm', sa.Integer(), nullable=True),
        sa.Column('speed', sa.Integer(), nullable=True),
        sa.Column('coolant_temp', sa.Integer(), nullable=True),
        sa.Column('battery_voltage', sa.Numeric(4, 2), nullable=True),
        sa.Column('fuel_level', sa.Numeric(5, 2), nullable=True),
        sa.Column('engine_load', sa.Numeric(5, 2), nullable=True),
        sa.Column('maf', sa.Numeric(8, 2), nullable=True),
        sa.Column('intake_temp', sa.Integer(), nullable=True),
        sa.Column('throttle_pos', sa.Numeric(5, 2), nullable=True),
        sa.Column('raw_data', postgresql.JSONB(), default={}),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'obd_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('profile_id', sa.Integer(), sa.ForeignKey('vehicle_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_id', sa.String(36), nullable=False, index=True),
        sa.Column('timestamp', sa.Float(), nullable=False),
        sa.Column('pid', sa.String(10), nullable=False),
        sa.Column('value', sa.Numeric(12, 4), nullable=True),
        sa.Column('unit', sa.String(10), nullable=True),
        sa.Column('is_calculated', sa.Boolean(), default=False),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'telemetry_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('profile_id', sa.Integer(), sa.ForeignKey('vehicle_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_id', sa.String(36), nullable=False, index=True),
        sa.Column('timestamp', sa.Float(), nullable=False, index=True),
        sa.Column('latitude', sa.Numeric(10, 8), nullable=True),
        sa.Column('longitude', sa.Numeric(11, 8), nullable=True),
        sa.Column('altitude', sa.Numeric(8, 2), nullable=True),
        sa.Column('gps_speed', sa.Numeric(5, 2), nullable=True),
        sa.Column('heading', sa.Integer(), nullable=True),
        sa.Column('acceleration_x', sa.Numeric(6, 3), nullable=True),
        sa.Column('acceleration_y', sa.Numeric(6, 3), nullable=True),
        sa.Column('acceleration_z', sa.Numeric(6, 3), nullable=True),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'service_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('profile_id', sa.Integer(), sa.ForeignKey('vehicle_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('service_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('mileage_at_service', sa.Integer(), nullable=True),
        sa.Column('cost', sa.Numeric(10, 2), nullable=True),
        sa.Column('service_date', sa.Date(), nullable=False),
        sa.Column('next_service_date', sa.Date(), nullable=True),
        sa.Column('next_service_mileage', sa.Integer(), nullable=True),
        sa.Column('provider', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('receipt_url', sa.String(255), nullable=True),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    # ========================
    # DTC DOMAIN (2 tables)
    # ========================
    
    op.create_table(
        'dtc_codes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(10), unique=True, nullable=False, index=True),
        sa.Column('category', sa.String(5), nullable=False),  # P0, P1, B0, etc.
        sa.Column('severity', sa.String(10), default='moderate'),  # low, moderate, high, critical
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('meaning', sa.Text(), nullable=True),
        sa.Column('symptoms', postgresql.JSONB(), default=[]),
        sa.Column('causes', postgresql.JSONB(), default=[]),
        sa.Column('solutions', postgresql.JSONB(), default=[]),
        sa.Column('related_pids', postgresql.JSONB(), default=[]),
        sa.Column('estimated_repair_cost', postgresql.JSONB(), default={}),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'dtc_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('profile_id', sa.Integer(), sa.ForeignKey('vehicle_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('dtc_code_id', sa.Integer(), sa.ForeignKey('dtc_codes.id'), nullable=False),
        sa.Column('status', sa.String(10), nullable=False),  # active, pending, cleared
        sa.Column('first_seen_at', sa.Float(), nullable=False),
        sa.Column('last_seen_at', sa.Float(), nullable=False),
        sa.Column('cleared_at', sa.Float(), nullable=True),
        sa.Column('freeze_frame', postgresql.JSONB(), default={}),
        sa.Column('mileage_at_detection', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    # ========================
    # GUARDIAN DOMAIN (8 tables)
    # ========================
    
    op.create_table(
        'guardians',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('notification_settings', postgresql.JSONB(), default={}),
        sa.Column('alert_thresholds', postgresql.JSONB(), default={}),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.Column('updated_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'vehicle_guardians',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('guardian_id', sa.Integer(), sa.ForeignKey('guardians.id', ondelete='CASCADE'), nullable=False),
        sa.Column('vehicle_profile_id', sa.Integer(), sa.ForeignKey('vehicle_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('driver_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('monitoring_start', sa.Float(), nullable=True),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.UniqueConstraint('guardian_id', 'vehicle_profile_id', name='unique_guardian_vehicle'),
    )
    
    op.create_table(
        'guardian_alerts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('vehicle_guardian_id', sa.Integer(), sa.ForeignKey('vehicle_guardians.id', ondelete='CASCADE'), nullable=False),
        sa.Column('alert_type', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(10), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('data', postgresql.JSONB(), default={}),
        sa.Column('is_read', sa.Boolean(), default=False),
        sa.Column('read_at', sa.Float(), nullable=True),
        sa.Column('sent_via', postgresql.JSONB(), default=[]),  # push, email, sms
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'guardian_commands',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('vehicle_guardian_id', sa.Integer(), sa.ForeignKey('vehicle_guardians.id', ondelete='CASCADE'), nullable=False),
        sa.Column('command', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), default='pending'),  # pending, sent, acknowledged, completed, failed
        sa.Column('parameters', postgresql.JSONB(), default={}),
        sa.Column('response', postgresql.JSONB(), nullable=True),
        sa.Column('sent_at', sa.Float(), nullable=True),
        sa.Column('completed_at', sa.Float(), nullable=True),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'location_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('vehicle_guardian_id', sa.Integer(), sa.ForeignKey('vehicle_guardians.id', ondelete='CASCADE'), nullable=False),
        sa.Column('requested_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('latitude', sa.Numeric(10, 8), nullable=True),
        sa.Column('longitude', sa.Numeric(11, 8), nullable=True),
        sa.Column('accuracy', sa.Numeric(6, 2), nullable=True),
        sa.Column('responded_at', sa.Float(), nullable=True),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'consent_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('consent_type', sa.String(50), nullable=False),
        sa.Column('version', sa.String(10), nullable=False),
        sa.Column('is_granted', sa.Boolean(), default=False),
        sa.Column('granted_at', sa.Float(), nullable=True),
        sa.Column('revoked_at', sa.Float(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'guardian_telemetry',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('vehicle_guardian_id', sa.Integer(), sa.ForeignKey('vehicle_guardians.id', ondelete='CASCADE'), nullable=False),
        sa.Column('timestamp', sa.Float(), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('data', postgresql.JSONB(), default={}),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'driving_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('vehicle_guardian_id', sa.Integer(), sa.ForeignKey('vehicle_guardians.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),  # harsh_braking, harsh_acceleration, speeding, etc.
        sa.Column('severity', sa.String(10), nullable=False),
        sa.Column('timestamp', sa.Float(), nullable=False),
        sa.Column('latitude', sa.Numeric(10, 8), nullable=True),
        sa.Column('longitude', sa.Numeric(11, 8), nullable=True),
        sa.Column('speed', sa.Integer(), nullable=True),
        sa.Column('data', postgresql.JSONB(), default={}),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    # ========================
    # TRIP DOMAIN (8 tables)
    # ========================
    
    op.create_table(
        'trips',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('profile_id', sa.Integer(), sa.ForeignKey('vehicle_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('driver_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('session_id', sa.String(36), unique=True, nullable=False),
        sa.Column('start_time', sa.Float(), nullable=False),
        sa.Column('end_time', sa.Float(), nullable=True),
        sa.Column('start_latitude', sa.Numeric(10, 8), nullable=True),
        sa.Column('start_longitude', sa.Numeric(11, 8), nullable=True),
        sa.Column('end_latitude', sa.Numeric(10, 8), nullable=True),
        sa.Column('end_longitude', sa.Numeric(11, 8), nullable=True),
        sa.Column('distance_km', sa.Numeric(8, 2), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('fuel_consumed_l', sa.Numeric(6, 3), nullable=True),
        sa.Column('avg_speed', sa.Numeric(5, 2), nullable=True),
        sa.Column('max_speed', sa.Integer(), nullable=True),
        sa.Column('harsh_events_count', sa.Integer(), default=0),
        sa.Column('score', sa.Integer(), nullable=True),
        sa.Column('is_completed', sa.Boolean(), default=False),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'trip_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('trip_id', sa.Integer(), sa.ForeignKey('trips.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('timestamp', sa.Float(), nullable=False),
        sa.Column('latitude', sa.Numeric(10, 8), nullable=True),
        sa.Column('longitude', sa.Numeric(11, 8), nullable=True),
        sa.Column('data', postgresql.JSONB(), default={}),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'drivers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('license_number', sa.String(50), nullable=True),
        sa.Column('license_expiry', sa.Date(), nullable=True),
        sa.Column('driving_since', sa.Date(), nullable=True),
        sa.Column('total_trips', sa.Integer(), default=0),
        sa.Column('total_distance_km', sa.Numeric(10, 2), default=0),
        sa.Column('avg_score', sa.Numeric(4, 2), default=0),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.Column('updated_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'vehicle_drivers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('vehicle_profile_id', sa.Integer(), sa.ForeignKey('vehicle_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('driver_id', sa.Integer(), sa.ForeignKey('drivers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('is_primary', sa.Boolean(), default=False),
        sa.Column('assigned_at', sa.Float(), nullable=False),
        sa.UniqueConstraint('vehicle_profile_id', 'driver_id', name='unique_vehicle_driver'),
    )
    
    op.create_table(
        'driver_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('driver_id', sa.Integer(), sa.ForeignKey('drivers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('vehicle_profile_id', sa.Integer(), sa.ForeignKey('vehicle_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('trip_id', sa.Integer(), sa.ForeignKey('trips.id'), nullable=True),
        sa.Column('started_at', sa.Float(), nullable=False),
        sa.Column('ended_at', sa.Float(), nullable=True),
        sa.Column('start_mileage', sa.Integer(), nullable=True),
        sa.Column('end_mileage', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'driver_invite_codes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('fleet_manager_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code', sa.String(20), unique=True, nullable=False),
        sa.Column('tier', sa.String(20), default='fleet_driver'),
        sa.Column('max_uses', sa.Integer(), default=1),
        sa.Column('uses_count', sa.Integer(), default=0),
        sa.Column('expires_at', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'driver_behavior_summaries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('driver_id', sa.Integer(), sa.ForeignKey('drivers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('period', sa.String(20), nullable=False),  # weekly, monthly
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('total_trips', sa.Integer(), default=0),
        sa.Column('total_distance_km', sa.Numeric(10, 2), default=0),
        sa.Column('avg_score', sa.Numeric(4, 2), default=0),
        sa.Column('harsh_braking_count', sa.Integer(), default=0),
        sa.Column('harsh_acceleration_count', sa.Integer(), default=0),
        sa.Column('speeding_count', sa.Integer(), default=0),
        sa.Column('idle_time_minutes', sa.Integer(), default=0),
        sa.Column('fuel_efficiency', sa.Numeric(5, 2), nullable=True),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'guardian_trips',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('guardian_id', sa.Integer(), sa.ForeignKey('guardians.id', ondelete='CASCADE'), nullable=False),
        sa.Column('trip_id', sa.Integer(), sa.ForeignKey('trips.id', ondelete='CASCADE'), nullable=False),
        sa.Column('notification_sent', sa.Boolean(), default=False),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.UniqueConstraint('guardian_id', 'trip_id', name='unique_guardian_trip'),
    )
    
    # ========================
    # PREDICTION DOMAIN (5 tables)
    # ========================
    
    op.create_table(
        'predictions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('profile_id', sa.Integer(), sa.ForeignKey('vehicle_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('prediction_type', sa.String(50), nullable=False),
        sa.Column('component', sa.String(50), nullable=False),
        sa.Column('failure_probability', sa.Numeric(5, 4), nullable=False),
        sa.Column('estimated_rul_days', sa.Integer(), nullable=True),
        sa.Column('confidence_score', sa.Numeric(5, 4), nullable=False),
        sa.Column('model_version', sa.String(20), nullable=False),
        sa.Column('feature_importance', postgresql.JSONB(), default={}),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('is_feedback_provided', sa.Boolean(), default=False),
        sa.Column('feedback_outcome', sa.String(20), nullable=True),  # confirmed, false_positive
        sa.Column('feedback_at', sa.Float(), nullable=True),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'ml_training_labels',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('profile_id', sa.Integer(), sa.ForeignKey('vehicle_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('prediction_id', sa.Integer(), sa.ForeignKey('predictions.id'), nullable=True),
        sa.Column('label_type', sa.String(50), nullable=False),
        sa.Column('component', sa.String(50), nullable=False),
        sa.Column('outcome', sa.String(20), nullable=False),  # failure, normal, repair_prevented
        sa.Column('labeled_at', sa.Float(), nullable=False),
        sa.Column('mileage_at_label', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'ml_aggregated_features',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('profile_id', sa.Integer(), sa.ForeignKey('vehicle_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('feature_name', sa.String(100), nullable=False),
        sa.Column('feature_value', sa.Numeric(12, 6), nullable=False),
        sa.Column('aggregation_window', sa.String(20), nullable=False),  # hourly, daily, weekly
        sa.Column('window_start', sa.Float(), nullable=False),
        sa.Column('window_end', sa.Float(), nullable=False),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'fleet_baselines',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('make', sa.String(50), nullable=False),
        sa.Column('model', sa.String(50), nullable=False),
        sa.Column('year_start', sa.Integer(), nullable=False),
        sa.Column('year_end', sa.Integer(), nullable=False),
        sa.Column('engine_type', sa.String(20), nullable=True),
        sa.Column('component', sa.String(50), nullable=False),
        sa.Column('baseline_value', sa.Numeric(12, 6), nullable=False),
        sa.Column('std_deviation', sa.Numeric(12, 6), nullable=True),
        sa.Column('sample_size', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.Column('updated_at', sa.Float(), nullable=False),
        sa.UniqueConstraint('make', 'model', 'year_start', 'year_end', 'component', name='unique_fleet_baseline'),
    )
    
    op.create_table(
        'obd_sensor_configs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('pid', sa.String(10), unique=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('unit', sa.String(20), nullable=True),
        sa.Column('min_value', sa.Numeric(12, 4), nullable=True),
        sa.Column('max_value', sa.Numeric(12, 4), nullable=True),
        sa.Column('warning_low', sa.Numeric(12, 4), nullable=True),
        sa.Column('warning_high', sa.Numeric(12, 4), nullable=True),
        sa.Column('critical_low', sa.Numeric(12, 4), nullable=True),
        sa.Column('critical_high', sa.Numeric(12, 4), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), default=True),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    # ========================
    # SUBSCRIPTION DOMAIN (5 tables)
    # ========================
    
    op.create_table(
        'fleet_invites',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('fleet_manager_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('invited_email', sa.String(255), nullable=False),
        sa.Column('token', sa.String(64), unique=True, nullable=False),
        sa.Column('status', sa.String(20), default='pending'),  # pending, accepted, declined, expired
        sa.Column('tier', sa.String(20), default='fleet_driver'),
        sa.Column('expires_at', sa.Float(), nullable=False),
        sa.Column('accepted_at', sa.Float(), nullable=True),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'geofences',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('vehicle_guardian_id', sa.Integer(), sa.ForeignKey('vehicle_guardians.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('geofence_type', sa.String(20), default='circle'),  # circle, polygon
        sa.Column('center_latitude', sa.Numeric(10, 8), nullable=True),
        sa.Column('center_longitude', sa.Numeric(11, 8), nullable=True),
        sa.Column('radius_meters', sa.Integer(), nullable=True),
        sa.Column('polygon_points', postgresql.JSONB(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('notify_on_enter', sa.Boolean(), default=True),
        sa.Column('notify_on_exit', sa.Boolean(), default=True),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'geofence_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('geofence_id', sa.Integer(), sa.ForeignKey('geofences.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(10), nullable=False),  # enter, exit
        sa.Column('latitude', sa.Numeric(10, 8), nullable=False),
        sa.Column('longitude', sa.Numeric(11, 8), nullable=False),
        sa.Column('timestamp', sa.Float(), nullable=False),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'tier_upgrade_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('current_tier', sa.String(20), nullable=False),
        sa.Column('requested_tier', sa.String(20), nullable=False),
        sa.Column('payment_reference', sa.String(100), nullable=True),
        sa.Column('status', sa.String(20), default='pending'),  # pending, processing, completed, failed
        sa.Column('processed_at', sa.Float(), nullable=True),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'subscription_audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('old_value', postgresql.JSONB(), nullable=True),
        sa.Column('new_value', postgresql.JSONB(), nullable=True),
        sa.Column('performed_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    # ========================
    # AUDIT DOMAIN (7 tables)
    # ========================
    
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('api_key_id', sa.Integer(), sa.ForeignKey('api_keys.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('resource_id', sa.String(50), nullable=True),
        sa.Column('old_data', postgresql.JSONB(), nullable=True),
        sa.Column('new_data', postgresql.JSONB(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('request_id', sa.String(36), nullable=True, index=True),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'verification_codes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code_hash', sa.String(255), nullable=False),
        sa.Column('purpose', sa.String(20), nullable=False),  # email, phone, password_reset
        sa.Column('expires_at', sa.Float(), nullable=False),
        sa.Column('used_at', sa.Float(), nullable=True),
        sa.Column('attempts', sa.Integer(), default=0),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'verification_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_token', sa.String(64), unique=True, nullable=False),
        sa.Column('purpose', sa.String(20), nullable=False),
        sa.Column('is_verified', sa.Boolean(), default=False),
        sa.Column('verified_at', sa.Float(), nullable=True),
        sa.Column('expires_at', sa.Float(), nullable=False),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'idempotency_cache',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key', sa.String(64), unique=True, nullable=False, index=True),
        sa.Column('request_method', sa.String(10), nullable=False),
        sa.Column('request_path', sa.String(255), nullable=False),
        sa.Column('request_body_hash', sa.String(64), nullable=True),
        sa.Column('response_status', sa.Integer(), nullable=False),
        sa.Column('response_body', postgresql.JSONB(), nullable=True),
        sa.Column('expires_at', sa.Float(), nullable=False),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'failed_operations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('operation_type', sa.String(50), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('retry_count', sa.Integer(), default=0),
        sa.Column('max_retries', sa.Integer(), default=3),
        sa.Column('next_retry_at', sa.Float(), nullable=True),
        sa.Column('status', sa.String(20), default='pending'),  # pending, retrying, failed, resolved
        sa.Column('resolved_at', sa.Float(), nullable=True),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'data_export_configs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('export_type', sa.String(20), nullable=False),  # json, csv, pdf
        sa.Column('data_types', postgresql.JSONB(), default=[]),
        sa.Column('date_range_start', sa.Date(), nullable=True),
        sa.Column('date_range_end', sa.Date(), nullable=True),
        sa.Column('schedule', sa.String(20), nullable=True),  # once, daily, weekly, monthly
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    op.create_table(
        'export_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('config_id', sa.Integer(), sa.ForeignKey('data_export_configs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(20), default='pending'),  # pending, processing, completed, failed
        sa.Column('file_path', sa.String(255), nullable=True),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('record_count', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.Float(), nullable=True),
        sa.Column('completed_at', sa.Float(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    
    # Create indexes for performance
    op.create_index('idx_vehicle_data_profile_timestamp', 'vehicle_data', ['profile_id', 'timestamp'])
    op.create_index('idx_obd_records_session', 'obd_records', ['session_id', 'timestamp'])
    op.create_index('idx_telemetry_profile_timestamp', 'telemetry_records', ['profile_id', 'timestamp'])
    op.create_index('idx_predictions_profile_type', 'predictions', ['profile_id', 'prediction_type'])
    op.create_index('idx_trips_profile_time', 'trips', ['profile_id', 'start_time'])
    op.create_index('idx_alerts_guardian_unread', 'guardian_alerts', ['vehicle_guardian_id', 'is_read'])
    op.create_index('idx_audit_logs_user_action', 'audit_logs', ['user_id', 'action'])


def downgrade() -> None:
    """Drop all tables - reverse order to handle dependencies."""
    
    # Drop in reverse order to handle foreign keys
    tables = [
        # Audit domain
        'export_history', 'data_export_configs', 'failed_operations',
        'idempotency_cache', 'verification_sessions', 'verification_codes', 'audit_logs',
        # Subscription domain
        'subscription_audit_logs', 'tier_upgrade_requests', 'geofence_events', 'geofences', 'fleet_invites',
        # Prediction domain
        'obd_sensor_configs', 'fleet_baselines', 'ml_aggregated_features', 'ml_training_labels', 'predictions',
        # Trip domain
        'guardian_trips', 'driver_behavior_summaries', 'driver_invite_codes', 'driver_sessions',
        'vehicle_drivers', 'drivers', 'trip_events', 'trips',
        # Guardian domain
        'driving_events', 'guardian_telemetry', 'consent_records', 'location_requests',
        'guardian_commands', 'guardian_alerts', 'vehicle_guardians', 'guardians',
        # DTC domain
        'dtc_history', 'dtc_codes',
        # Vehicle domain
        'service_records', 'telemetry_records', 'obd_records', 'vehicle_data', 'vehicle_profiles',
        # User domain
        'pricing_configs', 'user_feature_overrides', 'driver_assignments', 'tier_presets',
        'usage_counters', 'rate_limits', 'entitlements', 'api_keys', 'users',
    ]
    
    for table in tables:
        op.drop_table(table)
