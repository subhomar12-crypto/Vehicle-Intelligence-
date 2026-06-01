"""
PID Atlas Seed Data — Verified manufacturer PIDs for major OEMs.

Run: python -m predict.core.db.seeds.pid_atlas_seed
"""

import asyncio
import logging
import time

from sqlalchemy import select, and_

from predict.core.config import get_config
from predict.core.db.engine import init_engine
from predict.core.db.session import get_session_maker
from predict.core.db.models.pid_atlas import PIDAtlas

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Seed entries: (make, model_pattern, service, pid_hex, name, unit, formula, is_dynamic, year_min, year_max)
# model_pattern="*" means all models for that make

SEED_DATA = [
    # ==========================================
    # Nissan / Infiniti (Consult-III / UDS)
    # ==========================================
    ("NISSAN", "*", 0x21, "01", "Engine RPM (MFR)", "RPM", "((A*256)+B)/4", True, 1996, 2030),
    ("NISSAN", "*", 0x21, "02", "Intake Air Temperature", "\u00b0C", "A-50", True, 1996, 2030),
    ("NISSAN", "*", 0x21, "03", "O2 Sensor Voltage", "V", "A*0.02", True, 1996, 2030),
    ("NISSAN", "*", 0x21, "05", "Coolant Temperature (MFR)", "\u00b0C", "A-40", True, 1996, 2030),
    ("NISSAN", "*", 0x21, "07", "Ignition Timing Advance", "\u00b0", "A*0.5", True, 1996, 2030),
    ("NISSAN", "*", 0x21, "08", "Battery Voltage (MFR)", "V", "A*0.2", True, 1996, 2030),
    ("NISSAN", "*", 0x21, "09", "Vehicle Speed (MFR)", "km/h", "A", True, 1996, 2030),
    ("NISSAN", "*", 0x21, "0A", "Mass Air Flow", "g/s", "((A*256)+B)/100", True, 1996, 2030),
    ("NISSAN", "*", 0x21, "0B", "Throttle Position (MFR)", "%", "A*100/255", True, 1996, 2030),
    ("NISSAN", "*", 0x21, "0E", "Fuel Injection Timing", "ms", "((A*256)+B)/100", True, 1996, 2030),
    ("NISSAN", "*", 0x21, "14", "AT Fluid Temperature", "\u00b0C", "A-50", True, 1996, 2030),
    ("NISSAN", "*", 0x21, "17", "Steering Angle", "\u00b0", "((A*256)+B)*0.1", True, 2003, 2030),
    ("NISSAN", "*", 0x21, "1A", "Boost Pressure", "kPa", "A*2", True, 2003, 2030),
    ("NISSAN", "*", 0x22, "F190", "VIN (UDS)", "-", "ASCII", False, 2003, 2030),
    ("NISSAN", "*", 0x22, "F191", "ECU Hardware Number", "-", "ASCII", False, 2003, 2030),
    ("NISSAN", "*", 0x22, "F194", "System Supplier Software Number", "-", "ASCII", False, 2003, 2030),

    # ==========================================
    # Toyota / Lexus
    # ==========================================
    ("TOYOTA", "*", 0x22, "7104", "Hybrid Battery SOC", "%", "A*100/255", True, 2004, 2030),
    ("TOYOTA", "*", 0x22, "7105", "Hybrid Battery Temperature", "\u00b0C", "A-40", True, 2004, 2030),
    ("TOYOTA", "*", 0x22, "2101", "Engine Coolant Temp (Toyota)", "\u00b0C", "A-40", True, 1996, 2030),
    ("TOYOTA", "*", 0x22, "2103", "Engine RPM (Toyota)", "RPM", "((A*256)+B)/4", True, 1996, 2030),
    ("TOYOTA", "*", 0x22, "2121", "CVT Fluid Temperature", "\u00b0C", "A-40", True, 2004, 2030),
    ("TOYOTA", "*", 0x22, "2141", "Fuel Rail Pressure", "kPa", "((A*256)+B)*0.079", True, 2004, 2030),
    # Lexus shares Toyota platform
    ("LEXUS", "*", 0x22, "7104", "Hybrid Battery SOC", "%", "A*100/255", True, 2004, 2030),
    ("LEXUS", "*", 0x22, "7105", "Hybrid Battery Temperature", "\u00b0C", "A-40", True, 2004, 2030),
    ("LEXUS", "*", 0x22, "2101", "Engine Coolant Temp", "\u00b0C", "A-40", True, 1996, 2030),
    ("LEXUS", "*", 0x22, "2103", "Engine RPM", "RPM", "((A*256)+B)/4", True, 1996, 2030),

    # ==========================================
    # GM / Chevrolet
    # ==========================================
    ("CHEVROLET", "*", 0x22, "0240", "Transmission Fluid Temp (GM)", "\u00b0C", "A-40", True, 2006, 2030),
    ("CHEVROLET", "*", 0x22, "024E", "Engine Oil Life Remaining", "%", "A*100/255", False, 2006, 2030),
    ("CHEVROLET", "*", 0x22, "02B3", "AFM (Active Fuel Management) Status", "-", "A", True, 2007, 2030),
    ("CHEVROLET", "*", 0x22, "1867", "Tire Pressure FL", "kPa", "A*0.25", True, 2008, 2030),
    ("CHEVROLET", "*", 0x22, "1868", "Tire Pressure FR", "kPa", "A*0.25", True, 2008, 2030),
    ("CHEVROLET", "*", 0x22, "1869", "Tire Pressure RL", "kPa", "A*0.25", True, 2008, 2030),
    ("CHEVROLET", "*", 0x22, "186A", "Tire Pressure RR", "kPa", "A*0.25", True, 2008, 2030),
    # GMC shares GM platform
    ("GMC", "*", 0x22, "0240", "Transmission Fluid Temp", "\u00b0C", "A-40", True, 2006, 2030),
    ("GMC", "*", 0x22, "024E", "Engine Oil Life Remaining", "%", "A*100/255", False, 2006, 2030),
    ("GMC", "*", 0x22, "1867", "Tire Pressure FL", "kPa", "A*0.25", True, 2008, 2030),
    ("GMC", "*", 0x22, "1868", "Tire Pressure FR", "kPa", "A*0.25", True, 2008, 2030),
    ("GMC", "*", 0x22, "1869", "Tire Pressure RL", "kPa", "A*0.25", True, 2008, 2030),
    ("GMC", "*", 0x22, "186A", "Tire Pressure RR", "kPa", "A*0.25", True, 2008, 2030),

    # ==========================================
    # BMW
    # ==========================================
    ("BMW", "*", 0x22, "0500", "Charge Air Pressure", "kPa", "((A*256)+B)*0.01", True, 2005, 2030),
    ("BMW", "*", 0x22, "0510", "Engine Oil Temperature (BMW)", "\u00b0C", "((A*256)+B)*0.1-273.15", True, 2005, 2030),
    ("BMW", "*", 0x22, "0519", "Electric Water Pump Status", "-", "A", True, 2005, 2030),
    ("BMW", "*", 0x22, "052A", "VANOS Intake Position", "\u00b0", "((A*256)+B)*0.01", True, 2005, 2030),
    ("BMW", "*", 0x22, "052B", "VANOS Exhaust Position", "\u00b0", "((A*256)+B)*0.01", True, 2005, 2030),

    # ==========================================
    # Hyundai / Kia
    # ==========================================
    ("HYUNDAI", "*", 0x22, "0105", "ISG (Idle Stop-Go) Status", "-", "A", True, 2012, 2030),
    ("HYUNDAI", "*", 0x22, "0195", "DPF Soot Level", "%", "A*100/255", True, 2010, 2030),
    ("HYUNDAI", "*", 0x22, "01A4", "SCR Catalyst Temperature", "\u00b0C", "((A*256)+B)*0.1-40", True, 2014, 2030),
    ("HYUNDAI", "*", 0x22, "0112", "Battery Management State", "-", "A", True, 2012, 2030),
    ("KIA", "*", 0x22, "0105", "ISG (Idle Stop-Go) Status", "-", "A", True, 2012, 2030),
    ("KIA", "*", 0x22, "0195", "DPF Soot Level", "%", "A*100/255", True, 2010, 2030),
    ("KIA", "*", 0x22, "01A4", "SCR Catalyst Temperature", "\u00b0C", "((A*256)+B)*0.1-40", True, 2014, 2030),
    ("KIA", "*", 0x22, "0112", "Battery Management State", "-", "A", True, 2012, 2030),

    # ==========================================
    # Mercedes-Benz
    # ==========================================
    ("MERCEDES-BENZ", "*", 0x22, "1002", "AdBlue Level", "%", "A*100/255", False, 2010, 2030),
    ("MERCEDES-BENZ", "*", 0x22, "200D", "Air Suspension Height FL", "mm", "((A*256)+B)*0.1", True, 2005, 2030),
    ("MERCEDES-BENZ", "*", 0x22, "200E", "Air Suspension Height FR", "mm", "((A*256)+B)*0.1", True, 2005, 2030),
    ("MERCEDES-BENZ", "*", 0x22, "200F", "Air Suspension Height RL", "mm", "((A*256)+B)*0.1", True, 2005, 2030),
    ("MERCEDES-BENZ", "*", 0x22, "2010", "Air Suspension Height RR", "mm", "((A*256)+B)*0.1", True, 2005, 2030),

    # ==========================================
    # Ford
    # ==========================================
    ("FORD", "*", 0x22, "040C", "EcoBoost Boost Pressure", "kPa", "((A*256)+B)*0.03625", True, 2010, 2030),
    ("FORD", "*", 0x22, "1E23", "DPF Regen Status", "-", "A", True, 2008, 2030),
    ("FORD", "*", 0x22, "4025", "IWE Hub Lock Status", "-", "A", True, 2009, 2030),
    ("FORD", "*", 0x22, "407E", "EPAS Motor Torque", "Nm", "((A*256)+B)*0.01", True, 2010, 2030),

    # ==========================================
    # Infiniti (shares Nissan platform)
    # ==========================================
    ("INFINITI", "*", 0x21, "01", "Engine RPM (MFR)", "RPM", "((A*256)+B)/4", True, 1996, 2030),
    ("INFINITI", "*", 0x21, "02", "Intake Air Temperature", "\u00b0C", "A-50", True, 1996, 2030),
    ("INFINITI", "*", 0x21, "05", "Coolant Temperature (MFR)", "\u00b0C", "A-40", True, 1996, 2030),
    ("INFINITI", "*", 0x21, "08", "Battery Voltage (MFR)", "V", "A*0.2", True, 1996, 2030),
    ("INFINITI", "*", 0x21, "14", "AT Fluid Temperature", "\u00b0C", "A-50", True, 1996, 2030),
]


async def seed():
    """Upsert all seed PID entries into the atlas."""
    session_maker = get_session_maker()
    inserted = 0
    skipped = 0

    async with session_maker() as session:
        for make, model, service, pid_hex, name, unit, formula, is_dynamic, year_min, year_max in SEED_DATA:
            pid_hex_norm = pid_hex.upper()
            # Check if already exists
            result = await session.execute(
                select(PIDAtlas).where(and_(
                    PIDAtlas.make == make,
                    PIDAtlas.model == model,
                    PIDAtlas.service == service,
                    PIDAtlas.pid_hex == pid_hex_norm,
                    PIDAtlas.ecu_address == "",
                ))
            )
            existing = result.scalar_one_or_none()
            if existing:
                skipped += 1
                continue

            entry = PIDAtlas(
                make=make,
                model=model,
                year_min=year_min,
                year_max=year_max,
                service=service,
                pid_hex=pid_hex_norm,
                ecu_address="",
                data_byte_count=2 if "256" in formula else 1,
                is_dynamic=is_dynamic,
                semantic_type="sensor" if is_dynamic else "config",
                name=name,
                unit=unit,
                formula=formula,
                is_verified=True,
                discovery_count=100,  # Seed data starts with high confidence
                first_discovered_at=time.time(),
                last_seen_at=time.time(),
            )
            session.add(entry)
            inserted += 1

        await session.commit()

    logger.info(f"PID Atlas seed complete: {inserted} inserted, {skipped} already existed")
    return inserted


if __name__ == "__main__":
    config = get_config()
    init_engine(config.DATABASE_URL)
    asyncio.run(seed())
