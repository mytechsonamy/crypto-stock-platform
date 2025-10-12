#!/usr/bin/env python3
"""
Database initialization script.

Runs all SQL migrations in order and verifies the database schema.
"""

import asyncio
import asyncpg
import os
from pathlib import Path
from loguru import logger
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings


async def run_migration(conn: asyncpg.Connection, migration_file: Path) -> None:
    """
    Run a single migration file.
    
    Args:
        conn: Database connection
        migration_file: Path to SQL migration file
    """
    logger.info(f"Running migration: {migration_file.name}")
    
    try:
        sql = migration_file.read_text()
        await conn.execute(sql)
        logger.success(f"✅ Migration {migration_file.name} completed")
    except Exception as e:
        logger.error(f"❌ Migration {migration_file.name} failed: {e}")
        raise


async def init_database():
    """Initialize database with all migrations."""
    logger.info("🚀 Starting database initialization...")
    
    # Connect to database
    try:
        conn = await asyncpg.connect(
            host=settings.database.host,
            port=settings.database.port,
            database=settings.database.database,
            user=settings.database.user,
            password=settings.database.password
        )
        logger.success(f"✅ Connected to database: {settings.database.database}")
    except Exception as e:
        logger.error(f"❌ Failed to connect to database: {e}")
        return False
    
    try:
        # Get all migration files
        migrations_dir = Path(__file__).parent.parent / "storage" / "migrations"
        migration_files = sorted(migrations_dir.glob("*.sql"))
        
        if not migration_files:
            logger.warning("⚠️  No migration files found")
            return True
        
        logger.info(f"📁 Found {len(migration_files)} migration files")
        
        # Run migrations in order
        for migration_file in migration_files:
            await run_migration(conn, migration_file)
        
        # Verify tables
        logger.info("🔍 Verifying database schema...")
        
        tables = await conn.fetch("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
        """)
        
        logger.info(f"📊 Created tables:")
        for table in tables:
            logger.info(f"  - {table['tablename']}")
        
        # Verify hypertables
        hypertables = await conn.fetch("""
            SELECT hypertable_name 
            FROM timescaledb_information.hypertables
            ORDER BY hypertable_name
        """)
        
        logger.info(f"⏰ TimescaleDB hypertables:")
        for ht in hypertables:
            logger.info(f"  - {ht['hypertable_name']}")
        
        # Count symbols
        symbol_count = await conn.fetchval("SELECT COUNT(*) FROM symbols")
        logger.info(f"🎯 Loaded {symbol_count} symbols")
        
        logger.success("✅ Database initialization completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        return False
    finally:
        await conn.close()


if __name__ == "__main__":
    # Configure logger
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # Run initialization
    success = asyncio.run(init_database())
    sys.exit(0 if success else 1)
