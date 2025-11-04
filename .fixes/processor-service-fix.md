# Processor Service Fix Documentation

## Service Status
- **Container Name**: crypto-stock-processor
- **Status**: Restarting (Exit Code 1)
- **Image**: crypto-stock-platform-processor

## Problem Description
Processor service crashes on startup due to missing Python module.

### Error Details
```
ModuleNotFoundError: No module named 'talib'
```

**Error Location**: `processors/indicators.py:21`

## Root Cause Analysis

1. **Code imports talib** (line 21 of processors/indicators.py)
2. **requirements.txt has talib commented out** (line 30)
   - Comment reason: "ARM compatibility"
3. **Missing dependency** in Docker build process

## Solution Options

### Option 1: Install TA-Lib (Recommended for x86/x64)
Add to `docker/Dockerfile.processor`:
```dockerfile
# Install TA-Lib C library
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    && wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar -xzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib/ \
    && ./configure --prefix=/usr \
    && make \
    && make install \
    && cd .. \
    && rm -rf ta-lib ta-lib-0.4.0-src.tar.gz
```

Uncomment in `requirements.txt`:
```
TA-Lib==0.4.28
```

### Option 2: Replace TA-Lib with Pandas-TA
- Modify `processors/indicators.py` to use pandas_ta instead
- Update requirements.txt to include pandas_ta
- Rewrite indicator calculations using pandas_ta

### Option 3: Use Pure NumPy/Pandas Implementation
- Remove talib import
- Implement indicators using numpy/pandas (as commented in requirements.txt)
- Keep existing pandas/numpy dependencies

## Files to Modify
- `docker/Dockerfile.processor`
- `requirements.txt`
- `processors/indicators.py`

## Validation
After fix, verify:
- Container starts successfully
- No restart loop
- Logs show: "⚙️ Starting bar builder, indicator calculator..."
- No ModuleNotFoundError

## Priority
**MEDIUM** - Required for technical analysis features, not blocking core trading
