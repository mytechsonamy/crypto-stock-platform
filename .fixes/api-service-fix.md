# API Service Fix Documentation

## Service Status
- **Container Name**: crypto-stock-api
- **Status**: Running but Unhealthy
- **Image**: crypto-stock-platform-api
- **Ports**: 8000:8000, 9091:9091

## Problem Description
API service fails to start due to database authentication error.

### Error Details
```
asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "admin"
```

**Error Location**: `storage/timescale_manager.py:109`

## Root Cause
Database password mismatch between:
- `.env` file configuration (DB_PASSWORD=crypto_stock_password_123)
- TimescaleDB actual password (different or not set correctly)

## Solution Steps

1. **Verify Current DB Password**
   - Check TimescaleDB container environment variables
   - Verify if password was set correctly during initialization

2. **Option A: Fix .env File**
   - Update DB_PASSWORD in .env to match TimescaleDB's actual password
   - Restart API service

3. **Option B: Recreate TimescaleDB with Correct Password**
   - Stop and remove TimescaleDB container and volume
   - Ensure .env has correct DB_PASSWORD
   - Restart services to recreate database with correct password

## Files to Check/Modify
- `crypto-stock-platform/.env` (line 8: DB_PASSWORD)
- `crypto-stock-platform/docker-compose.yml` (TimescaleDB environment section)

## Validation
After fix, verify:
- API health check passes: `docker-compose ps` shows "healthy"
- API accessible at http://localhost:8000
- API docs accessible at http://localhost:8000/docs

## Priority
**HIGH** - API is core service, blocks frontend functionality
