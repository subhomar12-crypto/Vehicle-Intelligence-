"""
One-time migration: SQLite → PostgreSQL.

Migrates data from ALL 3 SQLite databases:
1. server_database.db (users, subscriptions, API keys)
2. data/vehicle_data.db (OBD data, 40+ tables)
3. PredictData/vehicle_profiles.db (vehicle profiles)

Usage:
    python scripts/migrate_sqlite_to_pg.py --sqlite-dir /path/to/sqlite --pg-url postgresql+asyncpg://...

Or with default paths:
    python scripts/migrate_sqlite_to_pg.py
"""

import argparse
import asyncio
import json
import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class SQLiteToPGMigrator:
    """Migrates data from SQLite to PostgreSQL."""
    
    def __init__(self, sqlite_dir: Path, pg_url: str, dry_run: bool = False):
        self.sqlite_dir = Path(sqlite_dir)
        self.pg_url = pg_url
        self.dry_run = dry_run
        self.stats = {
            "databases": 0,
            "tables": 0,
            "rows": 0,
            "errors": 0,
            "skipped": 0,
        }
        self.pg_engine = None
        self.session_factory = None
    
    async def init_postgres(self):
        """Initialize PostgreSQL connection."""
        self.pg_engine = create_async_engine(self.pg_url, echo=False)
        self.session_factory = async_sessionmaker(
            self.pg_engine, class_=AsyncSession, expire_on_commit=False
        )
        logger.info(f"Connected to PostgreSQL")
    
    async def close(self):
        """Close PostgreSQL connection."""
        if self.pg_engine:
            await self.pg_engine.dispose()
    
    async def migrate_all(self) -> Dict[str, Any]:
        """Migrate all SQLite databases."""
        await self.init_postgres()
        
        try:
            # Define databases and their tables
            databases: Dict[str, List[str]] = {
                "server_database.db": [
                    "users",
                    "api_keys",
                    "verification_codes",
                    "subscriptions",
                    "audit_log",
                ],
                "vehicle_data.db": [
                    "vehicle_data",
                    "telemetry_records",
                    "dtc_history",
                    "trips",
                    "trip_events",
                    "predictions",
                    "service_records",
                ],
                "vehicle_profiles.db": [
                    "vehicle_profiles",
                ],
            }
            
            for db_name, tables in databases.items():
                await self._migrate_database(db_name, tables)
            
            return self.stats
        
        finally:
            await self.close()
    
    async def _migrate_database(self, db_name: str, tables: List[str]):
        """Migrate a single SQLite database."""
        db_path = self.sqlite_dir / db_name
        
        if not db_path.exists():
            logger.warning(f"SQLite DB not found: {db_path}")
            return
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Migrating {db_name}")
        logger.info(f"{'='*60}")
        
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        
        try:
            for table in tables:
                await self._migrate_table(conn, table)
            
            self.stats["databases"] += 1
        
        finally:
            conn.close()
    
    async def _migrate_table(self, sqlite_conn: sqlite3.Connection, table_name: str):
        """Migrate a single table."""
        logger.info(f"  Migrating table: {table_name}")
        
        try:
            # Get column info
            cursor = sqlite_conn.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            # Fetch all rows
            cursor = sqlite_conn.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            
            if not rows:
                logger.info(f"    {table_name}: 0 rows (skipped)")
                return
            
            if self.dry_run:
                logger.info(f"    {table_name}: {len(rows)} rows (DRY RUN - not inserted)")
                self.stats["rows"] += len(rows)
                return
            
            # Insert into PostgreSQL
            async with self.session_factory() as session:
                async with session.begin():
                    migrated = await self._insert_rows(
                        session, table_name, column_names, rows
                    )
            
            self.stats["tables"] += 1
            self.stats["rows"] += migrated
            logger.info(f"    {table_name}: {migrated} rows migrated")
        
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"    {table_name}: FAILED - {e}")
    
    async def _insert_rows(
        self,
        session: AsyncSession,
        table_name: str,
        columns: List[str],
        rows: List[sqlite3.Row],
    ) -> int:
        """Insert rows into PostgreSQL with type conversion."""
        from sqlalchemy import text
        
        migrated = 0
        
        for row in rows:
            try:
                # Convert row to dict with type conversions
                data = {}
                for i, col_name in enumerate(columns):
                    value = row[i]
                    data[col_name] = self._convert_value(value, col_name)
                
                # Build INSERT statement
                col_list = ", ".join(f'"{c}"' for c in columns)
                param_list = ", ".join(f":{c}" for c in columns)
                
                # Check for existing record (simple duplicate check on ID)
                if "id" in data:
                    check_sql = f'SELECT 1 FROM "{table_name}" WHERE id = :id'
                    result = await session.execute(text(check_sql), {"id": data["id"]})
                    if result.scalar():
                        self.stats["skipped"] += 1
                        continue
                
                insert_sql = f'INSERT INTO "{table_name}" ({col_list}) VALUES ({param_list})'
                await session.execute(text(insert_sql), data)
                migrated += 1
            
            except Exception as e:
                logger.warning(f"    Failed to insert row: {e}")
                self.stats["errors"] += 1
        
        return migrated
    
    def _convert_value(self, value: Any, column_name: str) -> Any:
        """Convert SQLite values to PostgreSQL-compatible types."""
        if value is None:
            return None
        
        # Convert datetime strings to Unix timestamps
        if isinstance(value, str):
            # Check for ISO datetime format
            if column_name.endswith(("_at", "_time", "date", "timestamp")):
                try:
                    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    return dt.timestamp()
                except (ValueError, TypeError):
                    pass
            
            # Check for JSON strings
            if column_name in ("metadata", "data", "config", "settings", "params"):
                try:
                    json.loads(value)
                    return value  # Keep as JSON string
                except json.JSONDecodeError:
                    pass
        
        # Convert booleans (SQLite uses 0/1)
        if column_name.startswith("is_") or column_name.startswith("has_"):
            if isinstance(value, int):
                return bool(value)
        
        return value
    
    def print_summary(self):
        """Print migration summary."""
        print("\n" + "="*60)
        print("MIGRATION SUMMARY")
        print("="*60)
        print(f"Databases processed: {self.stats['databases']}")
        print(f"Tables migrated:     {self.stats['tables']}")
        print(f"Rows migrated:       {self.stats['rows']:,}")
        print(f"Rows skipped:        {self.stats['skipped']:,}")
        print(f"Errors:              {self.stats['errors']}")
        print("="*60)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate SQLite databases to PostgreSQL"
    )
    parser.add_argument(
        "--sqlite-dir",
        type=str,
        default=".",
        help="Directory containing SQLite databases",
    )
    parser.add_argument(
        "--pg-url",
        type=str,
        default="postgresql+asyncpg://predict_admin:password@localhost:5432/predict",
        help="PostgreSQL connection URL",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without inserting",
    )
    
    args = parser.parse_args()
    
    sqlite_dir = Path(args.sqlite_dir)
    if not sqlite_dir.exists():
        logger.error(f"SQLite directory not found: {sqlite_dir}")
        return 1
    
    migrator = SQLiteToPGMigrator(sqlite_dir, args.pg_url, args.dry_run)
    
    try:
        await migrator.migrate_all()
        migrator.print_summary()
        return 0
    except Exception as e:
        logger.exception(f"Migration failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
