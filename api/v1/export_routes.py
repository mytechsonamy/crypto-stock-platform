"""
Data Export API Routes
Supports CSV, JSON, and Parquet formats
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from datetime import datetime
from typing import Optional
import pandas as pd
import io
import json

from api.auth import get_current_user
from api.rate_limiter import check_rate_limit
from storage.timescale_manager import TimescaleManager
from monitoring.logger import logger


router = APIRouter(prefix="/export", tags=["export"])


@router.get("/{symbol}")
async def export_data(
    symbol: str,
    format: str = Query("csv", regex="^(csv|json|parquet)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    timeframe: str = Query("1h", regex="^(1m|5m|15m|1h|4h|1d)$"),
    include_indicators: bool = True,
    limit: int = Query(10000, ge=1, le=100000),
    current_user: dict = Depends(get_current_user),
    _rate_limit: None = Depends(check_rate_limit)
):
    """
    Export market data in various formats
    
    - **symbol**: Trading symbol (e.g., BTCUSDT)
    - **format**: Export format (csv, json, parquet)
    - **start_date**: Start date (optional)
    - **end_date**: End date (optional)
    - **timeframe**: Candle timeframe
    - **include_indicators**: Include technical indicators
    - **limit**: Maximum number of records (1-100000)
    """
    try:
        logger.info(f"Export request: {symbol}, format={format}, user={current_user.get('email')}")
        
        # Get database manager
        db = TimescaleManager()
        await db.connect()
        
        # Fetch candles
        if start_date and end_date:
            candles = await db.get_candles_range(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                limit=limit
            )
        else:
            candles = await db.get_recent_candles(
                symbol=symbol,
                timeframe=timeframe,
                limit=limit
            )
        
        if not candles:
            raise HTTPException(status_code=404, detail="No data found")
        
        # Convert to DataFrame
        df = pd.DataFrame(candles)
        
        # Fetch indicators if requested
        if include_indicators:
            if start_date and end_date:
                indicators = await db.get_indicators_range(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date
                )
            else:
                indicators = await db.get_indicators(
                    symbol=symbol,
                    timeframe=timeframe,
                    limit=limit
                )
            
            if indicators:
                indicators_df = pd.DataFrame(indicators)
                df = df.merge(indicators_df, on=['time', 'symbol', 'timeframe'], how='left')
        
        # Export based on format
        if format == "csv":
            return await export_csv(df, symbol)
        elif format == "json":
            return await export_json(df, symbol)
        elif format == "parquet":
            return await export_parquet(df, symbol)
        
    except Exception as e:
        logger.error(f"Export error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await db.close()


async def export_csv(df: pd.DataFrame, symbol: str) -> StreamingResponse:
    """Export data as CSV"""
    
    # Create CSV in memory
    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)
    
    # Stream response
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={symbol}_{datetime.now().strftime('%Y%m%d')}.csv"
        }
    )


async def export_json(df: pd.DataFrame, symbol: str) -> StreamingResponse:
    """Export data as JSON"""
    
    # Convert to JSON
    data = {
        "symbol": symbol,
        "exported_at": datetime.now().isoformat(),
        "count": len(df),
        "data": df.to_dict(orient='records')
    }
    
    # Create JSON in memory
    output = io.StringIO()
    json.dump(data, output, default=str, indent=2)
    output.seek(0)
    
    # Stream response
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename={symbol}_{datetime.now().strftime('%Y%m%d')}.json"
        }
    )


async def export_parquet(df: pd.DataFrame, symbol: str) -> StreamingResponse:
    """Export data as Parquet"""
    
    # Create Parquet in memory
    output = io.BytesIO()
    df.to_parquet(output, index=False, compression='snappy')
    output.seek(0)
    
    # Stream response
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={symbol}_{datetime.now().strftime('%Y%m%d')}.parquet"
        }
    )


@router.get("/{symbol}/stream")
async def export_data_stream(
    symbol: str,
    format: str = Query("csv", regex="^(csv|json)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    timeframe: str = Query("1h", regex="^(1m|5m|15m|1h|4h|1d)$"),
    chunk_size: int = Query(1000, ge=100, le=10000),
    current_user: dict = Depends(get_current_user),
    _rate_limit: None = Depends(check_rate_limit)
):
    """
    Stream large exports in chunks to avoid memory issues
    
    - **symbol**: Trading symbol
    - **format**: Export format (csv, json)
    - **start_date**: Start date (optional)
    - **end_date**: End date (optional)
    - **timeframe**: Candle timeframe
    - **chunk_size**: Records per chunk (100-10000)
    """
    
    async def generate_chunks():
        """Generate data chunks"""
        db = TimescaleManager()
        await db.connect()
        
        try:
            offset = 0
            is_first_chunk = True
            
            while True:
                # Fetch chunk
                if start_date and end_date:
                    chunk = await db.get_candles_range(
                        symbol=symbol,
                        timeframe=timeframe,
                        start_date=start_date,
                        end_date=end_date,
                        limit=chunk_size,
                        offset=offset
                    )
                else:
                    chunk = await db.get_recent_candles(
                        symbol=symbol,
                        timeframe=timeframe,
                        limit=chunk_size,
                        offset=offset
                    )
                
                if not chunk:
                    break
                
                # Convert to DataFrame
                df = pd.DataFrame(chunk)
                
                # Export chunk
                if format == "csv":
                    output = io.StringIO()
                    df.to_csv(output, index=False, header=is_first_chunk)
                    yield output.getvalue()
                elif format == "json":
                    for record in df.to_dict(orient='records'):
                        yield json.dumps(record, default=str) + "\n"
                
                offset += chunk_size
                is_first_chunk = False
                
        finally:
            await db.close()
    
    # Stream response
    media_type = "text/csv" if format == "csv" else "application/x-ndjson"
    
    return StreamingResponse(
        generate_chunks(),
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename={symbol}_{datetime.now().strftime('%Y%m%d')}.{format}"
        }
    )
