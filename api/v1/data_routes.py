"""
Data API Routes.

Endpoints:
- GET /api/v1/symbols - Get available symbols
- GET /api/v1/charts/{symbol} - Get chart data
- GET /api/v1/features/{symbol} - Get ML features
- GET /api/v1/quality/{symbol} - Get data quality metrics
"""

from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from loguru import logger

from api.auth import get_current_user, User
from api.main import get_db_manager, get_redis_manager, get_symbol_manager
from storage.timescale_manager import TimescaleManager
from storage.redis_cache import RedisCacheManager
from storage.symbol_manager import SymbolManager

router = APIRouter()


# ==================== RESPONSE MODELS ====================

class SymbolInfo(BaseModel):
    """Symbol information model."""
    symbol: str
    display_name: str
    asset_class: str
    exchange: str
    is_active: bool


class SymbolsResponse(BaseModel):
    """Symbols response model."""
    binance: List[str]
    alpaca: List[str]
    yahoo: List[str]


class BarData(BaseModel):
    """Bar/candle data model."""
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class ChartData(BaseModel):
    """Chart data response model."""
    symbol: str
    timeframe: str
    bars: List[BarData]
    indicators: Optional[dict] = None


class QualityMetrics(BaseModel):
    """Data quality metrics model."""
    symbol: str
    quality_score: float
    total_checks: int
    passed_checks: int
    failed_checks: int
    recent_failures: List[dict]


# ==================== ENDPOINTS ====================

@router.get("/symbols", response_model=SymbolsResponse)
async def get_symbols(
    symbol_manager: SymbolManager = Depends(get_symbol_manager),
    redis: RedisCacheManager = Depends(get_redis_manager)
):
    """
    Get available symbols grouped by exchange.
    
    Returns symbols dynamically loaded from database.
    Cached in Redis for 1 hour.
    
    Returns:
        Dictionary with symbols grouped by exchange
    """
    try:
        # Try cache first
        cache_key = "api:symbols:all"
        if redis.client:
            cached = await redis.client.get(cache_key)
            if cached:
                import json
                logger.debug("Symbols served from cache")
                return json.loads(cached)
        
        # Load from database
        binance_symbols = await symbol_manager.get_symbols_by_exchange("binance")
        alpaca_symbols = await symbol_manager.get_symbols_by_exchange("alpaca")
        yahoo_symbols = await symbol_manager.get_symbols_by_exchange("yahoo")
        
        response = SymbolsResponse(
            binance=binance_symbols,
            alpaca=alpaca_symbols,
            yahoo=yahoo_symbols
        )
        
        # Cache for 1 hour
        if redis.client:
            import json
            await redis.client.setex(
                cache_key,
                3600,  # 1 hour
                json.dumps(response.dict())
            )
        
        logger.info(
            f"Symbols loaded: "
            f"binance={len(binance_symbols)}, "
            f"alpaca={len(alpaca_symbols)}, "
            f"yahoo={len(yahoo_symbols)}"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error getting symbols: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch symbols"
        )


@router.get("/charts/{symbol}", response_model=ChartData)
async def get_chart_data(
    symbol: str,
    timeframe: str = Query("1m", regex="^(1m|5m|15m|1h|4h|1d)$"),
    limit: int = Query(1000, ge=1, le=5000),
    current_user: Optional[User] = None,  # Made optional for development
    db: TimescaleManager = Depends(get_db_manager),
    redis: RedisCacheManager = Depends(get_redis_manager)
):
    """
    Get chart data for a symbol.
    
    Requires authentication.
    Tries Redis cache first, falls back to database.
    Returns bars and indicators.
    
    Args:
        symbol: Trading symbol
        timeframe: Timeframe (1m, 5m, 15m, 1h, 4h, 1d)
        limit: Number of bars (1-5000)
        current_user: Authenticated user
        
    Returns:
        Chart data with bars and indicators
    """
    try:
        # Try cache first
        cached_bars = await redis.get_cached_bars(symbol, timeframe, limit)
        
        if cached_bars:
            logger.debug(f"Chart data served from cache: {symbol} {timeframe}")
            bars = [BarData(**bar) for bar in cached_bars]
        else:
            # Fetch from database
            db_bars = await db.get_recent_candles(symbol, timeframe, limit)
            
            if not db_bars:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No data found for {symbol} {timeframe}"
                )
            
            bars = [BarData(**bar) for bar in db_bars]
            
            # Cache for next time
            await redis.cache_bars(symbol, timeframe, db_bars)
            
            logger.debug(f"Chart data served from database: {symbol} {timeframe}")
        
        # Get indicators
        indicators = await redis.get_cached_indicators(symbol, timeframe)
        
        response = ChartData(
            symbol=symbol,
            timeframe=timeframe,
            bars=bars,
            indicators=indicators
        )
        
        logger.info(
            f"Chart data served: {symbol} {timeframe}, "
            f"bars={len(bars)}, "
            f"user={current_user.username if current_user else 'anonymous'}"
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chart data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch chart data"
        )


@router.get("/features/{symbol}")
async def get_features(
    symbol: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    mode: str = Query("realtime", regex="^(realtime|batch)$"),
    current_user: User = Depends(get_current_user),
    db: TimescaleManager = Depends(get_db_manager),
    redis: RedisCacheManager = Depends(get_redis_manager)
):
    """
    Get ML features for a symbol.
    
    Requires authentication.
    Supports real-time (latest) and batch (date range) modes.
    
    Args:
        symbol: Trading symbol
        start_time: Start datetime (batch mode)
        end_time: End datetime (batch mode)
        mode: 'realtime' or 'batch'
        current_user: Authenticated user
        
    Returns:
        ML features
    """
    try:
        if mode == "realtime":
            # Get latest features from Redis
            features = await redis.get_cached_features(symbol)
            
            if not features:
                # Fallback to database
                features = await db.get_latest_features(symbol, "v1.0")
            
            if not features:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No features found for {symbol}"
                )
            
            logger.info(f"Real-time features served: {symbol}, user={current_user.username}")
            
            return {
                "symbol": symbol,
                "mode": "realtime",
                "features": features
            }
            
        else:  # batch mode
            if not start_time or not end_time:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_time and end_time required for batch mode"
                )
            
            # Get features from database
            features = await db.get_features_range(
                symbol=symbol,
                feature_version="v1.0",
                start_time=start_time,
                end_time=end_time
            )
            
            if not features:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No features found for {symbol} in date range"
                )
            
            logger.info(
                f"Batch features served: {symbol}, "
                f"count={len(features)}, "
                f"user={current_user.username}"
            )
            
            return {
                "symbol": symbol,
                "mode": "batch",
                "start_time": start_time,
                "end_time": end_time,
                "count": len(features),
                "features": features
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting features: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch features"
        )


@router.get("/quality/{symbol}", response_model=QualityMetrics)
async def get_quality_metrics(
    symbol: str,
    hours: int = Query(24, ge=1, le=168),  # Last N hours (max 1 week)
    current_user: User = Depends(get_current_user),
    db: TimescaleManager = Depends(get_db_manager)
):
    """
    Get data quality metrics for a symbol.
    
    Requires authentication.
    Returns quality score and recent check results.
    
    Args:
        symbol: Trading symbol
        hours: Number of hours to look back (1-168)
        current_user: Authenticated user
        
    Returns:
        Data quality metrics
    """
    try:
        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        # Get quality metrics from database
        metrics = await db.get_quality_metrics(symbol, start_time, end_time)
        
        if not metrics:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No quality metrics found for {symbol}"
            )
        
        # Calculate statistics
        total_checks = len(metrics)
        passed_checks = sum(1 for m in metrics if m.get('result') == 'passed')
        failed_checks = total_checks - passed_checks
        
        # Calculate quality score (percentage of passed checks)
        quality_score = passed_checks / total_checks if total_checks > 0 else 1.0
        
        # Get recent failures
        recent_failures = [
            {
                'time': m.get('time'),
                'check_type': m.get('check_type'),
                'error_message': m.get('error_message')
            }
            for m in metrics
            if m.get('result') == 'failed'
        ][:10]  # Last 10 failures
        
        response = QualityMetrics(
            symbol=symbol,
            quality_score=quality_score,
            total_checks=total_checks,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            recent_failures=recent_failures
        )
        
        logger.info(
            f"Quality metrics served: {symbol}, "
            f"score={quality_score:.2f}, "
            f"user={current_user.username}"
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting quality metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch quality metrics"
        )
