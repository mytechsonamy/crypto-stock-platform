# Binance Collector Service Fix Documentation

## Service Status
- **Container Name**: crypto-stock-binance-collector
- **Status**: Restarting (Exit Code 1)
- **Image**: crypto-stock-platform-binance-collector

## Problem Description
Binance collector service crashes on startup due to missing Python module.

### Error Details
```
ModuleNotFoundError: No module named 'binance'
```

**Error Location**: `collectors/binance_collector.py:17`

## Root Cause
The `python-binance` package is listed in requirements.txt but not being installed in the collector container.

### Dependency Status
- **requirements.txt line 26**: `python-binance==1.0.19` ✅ Present
- **Container pip list**: `binance` module missing ❌

## Solution Steps

1. **Verify Docker Build Process**
   - Check if requirements.txt is being copied correctly
   - Verify pip install command runs successfully
   - Check for build cache issues

2. **Debug Build**
   ```bash
   cd crypto-stock-platform
   docker-compose build --no-cache binance-collector
   docker-compose up binance-collector
   ```

3. **Verify Installation**
   ```bash
   docker exec crypto-stock-binance-collector pip list | grep binance
   ```

4. **Check for Missing Dependencies**
   - python-binance requires: requests, aiohttp, websockets
   - Verify all dependencies are in requirements.txt

## Likely Issues

### Issue 1: Build Cache
Docker cached layer before requirements.txt was properly copied.

**Fix**: Rebuild with `--no-cache`

### Issue 2: Wrong requirements.txt Path
Dockerfile might be copying wrong file or not running pip install.

**Check**: `docker/Dockerfile.collector` lines 20-21

### Issue 3: User Permissions
Package installed under wrong user (root vs collector)

**Fix**: Ensure pip install runs before user switch

## Files to Check
- `docker/Dockerfile.collector`
- `requirements.txt`
- Build logs for any pip errors

## Validation
After fix:
- Container starts without restart
- Logs show: "📊 Starting Binance collector..."
- No ModuleNotFoundError
- Check: `docker exec crypto-stock-binance-collector python -c "import binance; print(binance.__version__)"`

## Priority
**MEDIUM** - Required for crypto data collection, but platform can work without it initially
