"""Pi5 edge device registration and status tracking."""

import secrets
import time
from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from predict.core.db.base import Base


class Pi5Device(Base):
    __tablename__ = "pi5_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    vehicle_id: Mapped[int] = mapped_column(Integer, ForeignKey("vehicle_profiles.profile_id"))
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    firmware_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    last_seen: Mapped[float] = mapped_column(Float, default=time.time)
    cpu_temp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ram_used_mb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sd_free_gb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wifi_signal_dbm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    wifi_ssid: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    buffer_remaining: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    odometer_km: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    device_token: Mapped[Optional[str]] = mapped_column(String(128), unique=True, index=True, nullable=True)
    token_expires_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)

    @staticmethod
    def generate_token() -> str:
        return secrets.token_urlsafe(64)
