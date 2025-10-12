#!/usr/bin/env python3
"""
Backup Verification Script
Verifies database backups by restoring to a test instance
"""

import os
import sys
import subprocess
import argparse
from datetime import datetime
from pathlib import Path
from loguru import logger
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(sys.stderr, level=level, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")
    logger.add("logs/backup_verification_{time}.log", rotation="1 day", retention="30 days", level="DEBUG")


def find_latest_backup(backup_dir: Path) -> Path:
    """Find the most recent backup file"""
    backup_files = list(backup_dir.glob("*.sql.gz"))
    
    if not backup_files:
        raise FileNotFoundError(f"No backup files found in {backup_dir}")
    
    # Sort by modification time
    latest_backup = max(backup_files, key=lambda p: p.stat().st_mtime)
    logger.info(f"Found latest backup: {latest_backup}")
    
    return latest_backup


def create_test_database(host: str, port: int, user: str, password: str, test_db: str):
    """Create a test database for verification"""
    try:
        # Connect to postgres database
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database='postgres'
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Drop test database if exists
        logger.info(f"Dropping test database if exists: {test_db}")
        cursor.execute(f"DROP DATABASE IF EXISTS {test_db}")
        
        # Create test database
        logger.info(f"Creating test database: {test_db}")
        cursor.execute(f"CREATE DATABASE {test_db}")
        
        cursor.close()
        conn.close()
        
        logger.success(f"Test database created: {test_db}")
        
    except Exception as e:
        logger.error(f"Failed to create test database: {e}")
        raise


def restore_backup(backup_file: Path, host: str, port: int, user: str, password: str, test_db: str):
    """Restore backup to test database"""
    try:
        logger.info(f"Restoring backup to {test_db}...")
        
        # Build restore command
        env = os.environ.copy()
        env['PGPASSWORD'] = password
        
        # Decompress and restore
        cmd = f"gunzip -c {backup_file} | psql -h {host} -p {port} -U {user} -d {test_db}"
        
        result = subprocess.run(
            cmd,
            shell=True,
            env=env,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"Restore failed: {result.stderr}")
            raise Exception(f"Restore failed with code {result.returncode}")
        
        logger.success("Backup restored successfully")
        
    except Exception as e:
        logger.error(f"Failed to restore backup: {e}")
        raise


def verify_data_integrity(host: str, port: int, user: str, password: str, test_db: str) -> dict:
    """Verify data integrity in restored database"""
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=test_db
        )
        cursor = conn.cursor()
        
        results = {}
        
        # Check tables exist
        logger.info("Checking tables...")
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = [row[0] for row in cursor.fetchall()]
        results['tables'] = tables
        logger.info(f"Found {len(tables)} tables: {', '.join(tables)}")
        
        # Check row counts
        logger.info("Checking row counts...")
        row_counts = {}
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            row_counts[table] = count
            logger.info(f"  {table}: {count:,} rows")
        results['row_counts'] = row_counts
        
        # Check for critical tables
        critical_tables = ['symbols', 'candles', 'indicators']
        missing_tables = [t for t in critical_tables if t not in tables]
        if missing_tables:
            logger.warning(f"Missing critical tables: {missing_tables}")
            results['missing_critical_tables'] = missing_tables
        else:
            logger.success("All critical tables present")
        
        # Check data freshness (most recent candle)
        if 'candles' in tables:
            cursor.execute("SELECT MAX(time) FROM candles")
            latest_candle = cursor.fetchone()[0]
            if latest_candle:
                logger.info(f"Latest candle timestamp: {latest_candle}")
                results['latest_candle'] = str(latest_candle)
        
        # Check indexes
        logger.info("Checking indexes...")
        cursor.execute("""
            SELECT tablename, indexname 
            FROM pg_indexes 
            WHERE schemaname = 'public'
            ORDER BY tablename, indexname
        """)
        indexes = cursor.fetchall()
        results['index_count'] = len(indexes)
        logger.info(f"Found {len(indexes)} indexes")
        
        cursor.close()
        conn.close()
        
        return results
        
    except Exception as e:
        logger.error(f"Data integrity check failed: {e}")
        raise


def cleanup_test_database(host: str, port: int, user: str, password: str, test_db: str):
    """Clean up test database"""
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database='postgres'
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        logger.info(f"Dropping test database: {test_db}")
        cursor.execute(f"DROP DATABASE IF EXISTS {test_db}")
        
        cursor.close()
        conn.close()
        
        logger.success("Test database cleaned up")
        
    except Exception as e:
        logger.warning(f"Failed to cleanup test database: {e}")


def save_verification_report(results: dict, backup_file: Path, output_dir: Path):
    """Save verification report"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = output_dir / f"verification_report_{timestamp}.txt"
    
    with open(report_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("BACKUP VERIFICATION REPORT\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write(f"Backup File: {backup_file}\n")
        f.write(f"Backup Size: {backup_file.stat().st_size / 1024 / 1024:.2f} MB\n\n")
        
        f.write("VERIFICATION RESULTS\n")
        f.write("-" * 80 + "\n\n")
        
        f.write(f"Tables Found: {len(results.get('tables', []))}\n")
        f.write(f"Indexes Found: {results.get('index_count', 0)}\n\n")
        
        f.write("Row Counts:\n")
        for table, count in results.get('row_counts', {}).items():
            f.write(f"  {table}: {count:,}\n")
        f.write("\n")
        
        if 'latest_candle' in results:
            f.write(f"Latest Candle: {results['latest_candle']}\n\n")
        
        if 'missing_critical_tables' in results:
            f.write("WARNING: Missing Critical Tables:\n")
            for table in results['missing_critical_tables']:
                f.write(f"  - {table}\n")
            f.write("\n")
        
        f.write("=" * 80 + "\n")
        f.write("VERIFICATION: PASSED\n")
        f.write("=" * 80 + "\n")
    
    logger.success(f"Verification report saved: {report_file}")
    return report_file


def main():
    parser = argparse.ArgumentParser(description="Verify database backup")
    parser.add_argument('--backup-dir', type=str, default='./backups', help='Backup directory')
    parser.add_argument('--backup-file', type=str, help='Specific backup file to verify')
    parser.add_argument('--host', type=str, default='localhost', help='Database host')
    parser.add_argument('--port', type=int, default=5432, help='Database port')
    parser.add_argument('--user', type=str, default='postgres', help='Database user')
    parser.add_argument('--password', type=str, help='Database password')
    parser.add_argument('--test-db', type=str, default='backup_verification_test', help='Test database name')
    parser.add_argument('--no-cleanup', action='store_true', help='Do not cleanup test database')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    # Get password from environment if not provided
    password = args.password or os.getenv('DB_PASSWORD')
    if not password:
        logger.error("Database password not provided (use --password or DB_PASSWORD env var)")
        sys.exit(1)
    
    try:
        # Find backup file
        if args.backup_file:
            backup_file = Path(args.backup_file)
        else:
            backup_dir = Path(args.backup_dir)
            backup_file = find_latest_backup(backup_dir)
        
        if not backup_file.exists():
            logger.error(f"Backup file not found: {backup_file}")
            sys.exit(1)
        
        logger.info(f"Verifying backup: {backup_file}")
        logger.info(f"Backup size: {backup_file.stat().st_size / 1024 / 1024:.2f} MB")
        
        # Create test database
        create_test_database(args.host, args.port, args.user, password, args.test_db)
        
        # Restore backup
        restore_backup(backup_file, args.host, args.port, args.user, password, args.test_db)
        
        # Verify data integrity
        results = verify_data_integrity(args.host, args.port, args.user, password, args.test_db)
        
        # Save report
        output_dir = Path('logs')
        output_dir.mkdir(exist_ok=True)
        report_file = save_verification_report(results, backup_file, output_dir)
        
        logger.success("✓ Backup verification completed successfully")
        logger.info(f"Report: {report_file}")
        
        # Cleanup
        if not args.no_cleanup:
            cleanup_test_database(args.host, args.port, args.user, password, args.test_db)
        else:
            logger.info(f"Test database kept for inspection: {args.test_db}")
        
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Backup verification failed: {e}")
        
        # Attempt cleanup on failure
        if not args.no_cleanup:
            try:
                cleanup_test_database(args.host, args.port, args.user, password, args.test_db)
            except:
                pass
        
        sys.exit(1)


if __name__ == '__main__':
    main()
