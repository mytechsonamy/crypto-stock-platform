#!/usr/bin/env python3
"""
Automated Restore Test Script
Tests backup restore procedures monthly
"""

import os
import sys
import subprocess
import argparse
from datetime import datetime
from pathlib import Path
from loguru import logger
import json


def setup_logging():
    """Setup logging"""
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"restore_test_{timestamp}.log"
    logger.add(log_file, level="DEBUG")
    
    return log_file


def run_command(cmd: str, env: dict = None) -> tuple:
    """Run shell command and return output"""
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        env=env or os.environ.copy()
    )
    return result.returncode, result.stdout, result.stderr


def test_backup_verification(backup_dir: str, db_config: dict) -> dict:
    """Test backup verification"""
    logger.info("Testing backup verification...")
    
    cmd = f"""python scripts/verify_backup.py \
        --backup-dir {backup_dir} \
        --host {db_config['host']} \
        --port {db_config['port']} \
        --user {db_config['user']} \
        --password {db_config['password']} \
        --test-db restore_test_db \
        --verbose"""
    
    start_time = datetime.now()
    returncode, stdout, stderr = run_command(cmd)
    duration = (datetime.now() - start_time).total_seconds()
    
    success = returncode == 0
    
    return {
        'test': 'backup_verification',
        'success': success,
        'duration_seconds': duration,
        'output': stdout if success else stderr
    }


def test_application_startup(compose_file: str) -> dict:
    """Test application startup after restore"""
    logger.info("Testing application startup...")
    
    # Start services
    cmd = f"docker-compose -f {compose_file} up -d"
    start_time = datetime.now()
    returncode, stdout, stderr = run_command(cmd)
    
    if returncode != 0:
        return {
            'test': 'application_startup',
            'success': False,
            'duration_seconds': 0,
            'error': stderr
        }
    
    # Wait for services to be healthy
    import time
    max_wait = 60
    waited = 0
    
    while waited < max_wait:
        cmd = f"docker-compose -f {compose_file} ps"
        returncode, stdout, stderr = run_command(cmd)
        
        if 'Up (healthy)' in stdout:
            break
        
        time.sleep(5)
        waited += 5
    
    duration = (datetime.now() - start_time).total_seconds()
    success = waited < max_wait
    
    return {
        'test': 'application_startup',
        'success': success,
        'duration_seconds': duration,
        'waited_seconds': waited
    }


def test_api_endpoints(base_url: str) -> dict:
    """Test API endpoints"""
    logger.info("Testing API endpoints...")
    
    import requests
    
    endpoints = [
        '/health',
        '/api/v1/symbols',
    ]
    
    results = []
    for endpoint in endpoints:
        url = f"{base_url}{endpoint}"
        try:
            response = requests.get(url, timeout=10)
            results.append({
                'endpoint': endpoint,
                'status_code': response.status_code,
                'success': response.status_code == 200
            })
        except Exception as e:
            results.append({
                'endpoint': endpoint,
                'success': False,
                'error': str(e)
            })
    
    all_success = all(r['success'] for r in results)
    
    return {
        'test': 'api_endpoints',
        'success': all_success,
        'endpoints': results
    }


def cleanup_test_environment(compose_file: str):
    """Cleanup test environment"""
    logger.info("Cleaning up test environment...")
    
    cmd = f"docker-compose -f {compose_file} down -v"
    returncode, stdout, stderr = run_command(cmd)
    
    if returncode == 0:
        logger.success("Test environment cleaned up")
    else:
        logger.warning(f"Cleanup warning: {stderr}")


def generate_report(results: list, log_file: Path) -> Path:
    """Generate test report"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = Path(f"logs/restore_test_report_{timestamp}.json")
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'log_file': str(log_file),
        'tests': results,
        'summary': {
            'total': len(results),
            'passed': sum(1 for r in results if r['success']),
            'failed': sum(1 for r in results if not r['success']),
            'total_duration': sum(r.get('duration_seconds', 0) for r in results)
        }
    }
    
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"Report saved: {report_file}")
    
    # Print summary
    print("\n" + "=" * 80)
    print("RESTORE TEST SUMMARY")
    print("=" * 80)
    print(f"Total Tests: {report['summary']['total']}")
    print(f"Passed: {report['summary']['passed']}")
    print(f"Failed: {report['summary']['failed']}")
    print(f"Total Duration: {report['summary']['total_duration']:.2f}s")
    print("=" * 80)
    
    for result in results:
        status = "✓ PASS" if result['success'] else "✗ FAIL"
        print(f"{status} - {result['test']}")
    
    print("=" * 80 + "\n")
    
    return report_file


def main():
    parser = argparse.ArgumentParser(description="Automated restore test")
    parser.add_argument('--backup-dir', type=str, default='./backups', help='Backup directory')
    parser.add_argument('--test-env', type=str, default='test', help='Test environment name')
    parser.add_argument('--db-host', type=str, default='localhost', help='Database host')
    parser.add_argument('--db-port', type=int, default=5432, help='Database port')
    parser.add_argument('--db-user', type=str, default='admin', help='Database user')
    parser.add_argument('--db-password', type=str, help='Database password')
    parser.add_argument('--api-url', type=str, default='http://localhost:8000', help='API base URL')
    parser.add_argument('--no-cleanup', action='store_true', help='Skip cleanup')
    
    args = parser.parse_args()
    
    log_file = setup_logging()
    
    logger.info("=" * 80)
    logger.info("AUTOMATED RESTORE TEST")
    logger.info("=" * 80)
    logger.info(f"Test Environment: {args.test_env}")
    logger.info(f"Backup Directory: {args.backup_dir}")
    logger.info(f"Start Time: {datetime.now().isoformat()}")
    logger.info("=" * 80)
    
    # Get password
    db_password = args.db_password or os.getenv('DB_PASSWORD')
    if not db_password:
        logger.error("Database password required")
        sys.exit(1)
    
    db_config = {
        'host': args.db_host,
        'port': args.db_port,
        'user': args.db_user,
        'password': db_password
    }
    
    compose_file = f"docker-compose.{args.test_env}.yml"
    
    results = []
    
    try:
        # Test 1: Backup Verification
        result = test_backup_verification(args.backup_dir, db_config)
        results.append(result)
        
        if not result['success']:
            logger.error("Backup verification failed, stopping tests")
            return results
        
        # Test 2: Application Startup
        result = test_application_startup(compose_file)
        results.append(result)
        
        if not result['success']:
            logger.error("Application startup failed, stopping tests")
            return results
        
        # Test 3: API Endpoints
        result = test_api_endpoints(args.api_url)
        results.append(result)
        
        logger.success("All tests completed")
        
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        results.append({
            'test': 'exception',
            'success': False,
            'error': str(e)
        })
    
    finally:
        # Cleanup
        if not args.no_cleanup:
            cleanup_test_environment(compose_file)
        
        # Generate report
        report_file = generate_report(results, log_file)
        
        # Exit code
        all_passed = all(r['success'] for r in results)
        sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
