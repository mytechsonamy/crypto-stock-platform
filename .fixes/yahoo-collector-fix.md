# Yahoo Collector Service Fix Documentation

## Service Status
- **Container Name**: crypto-stock-yahoo-collector
- **Status**: Restarting (Exit Code 1)
- **Image**: crypto-stock-platform-yahoo-collector

## Problem Description
Yahoo collector service crashes on startup due to missing Python module.

### Error Details
```
ModuleNotFoundError: No module named 'pytz'
```

**Error Location**: `collectors/yahoo_collector.py:18`

## Root Cause
The `pytz` package is listed in requirements.txt but not being installed in the collector container.

### Dependency Status
- **requirements.txt line 55**: `pytz==2023.3` ✅ Present
- **Container pip list**: `pytz` module missing ❌
- **API container**: Has pytz installed ✅

## Solution Steps

1. **Verify Docker Build Process**
   - Check if requirements.txt is being copied correctly in collector Dockerfile
   - Verify pip install command runs successfully
   - Check for build cache issues

2. **Debug Build**
   ```bash
   cd crypto-stock-platform
   docker-compose build --no-cache yahoo-collector
   docker-compose up yahoo-collector
   ```

3. **Verify Installation**
   ```bash
   docker exec crypto-stock-yahoo-collector pip list | grep pytz
   ```

4. **Compare with Working API Container**
   ```bash
   docker exec crypto-stock-api pip list | grep pytz
   ```

## Likely Issues

### Issue 1: Build Cache
Docker cached layer before requirements.txt was properly copied.

**Fix**: Rebuild with `--no-cache`

### Issue 2: Python Path Issue
Package installed but not in collector user's Python path.

**Check**: ENV PATH in Dockerfile.collector
**Fix**: Ensure PATH includes `/root/.local/bin`

### Issue 3: Requirements Not Copied
Dockerfile might have wrong COPY path or order.

**Check**: `docker/Dockerfile.collector` line 20

## Files to Check
- `docker/Dockerfile.collector`
- `requirements.txt`
- Build logs for any pip errors

## Validation
After fix:
- Container starts without restart
- Logs show: "📊 Starting Yahoo Finance collector..."
- No ModuleNotFoundError
- Check: `docker exec crypto-stock-yahoo-collector python -c "import pytz; print(pytz.__version__)"`

## Priority
**MEDIUM** - Required for stock data collection, but platform can work without it initially

## Notes
- Same Dockerfile used for both binance-collector and yahoo-collector
- If this is fixed, binance-collector likely also fixed
- Both share same root cause
