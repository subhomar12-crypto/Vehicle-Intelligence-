"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Check Db Schema
"""

import sqlite3
from config import get_config
CONFIG = get_config()

conn = sqlite3.connect(str(CONFIG.PROFILES_DB_PATH))
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(vehicle_profiles)")
columns = cursor.fetchall()
for col in columns:
    print(col)
conn.close()
