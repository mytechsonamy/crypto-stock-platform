"""
Database models and schemas for Crypto-Stock Platform.

This module defines Pydantic models for data validation and
database schema representations.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
import json
from pydantic import BaseModel, Field, field_validator


class AssetClass(str, Enum):
    """Asset class enumeration."""
    CRYPTO = "CRYPTO"
    BIST = "BIST"
    NASDAQ = "NASDAQ"
    NYSE = "NYSE"


class Symbol(BaseModel):
    """Symbol model for database representation."""
    id: Optional[int] = None
    asset_class: AssetClass
    symbol: str = Field(..., max_length=20)
    display_name: Optional[str] = Field(None, max_length=100)
    exchange: str = Field(..., max_length=50)
    is_active: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator('metadata', mode='before')
    @classmethod
    def parse_metadata(cls, v):
        """Parse metadata field if it comes as a JSON string from the database."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        return v if v is not None else {}

    class Config:
        use_enum_values = True


class Candle(BaseModel):
    """OHLC candlestick bar model."""
    time: datetime
    symbol: str
    exchange: str
    timeframe: str = "1m"
    open: float
    high: float
    low: float
    close: float
    volume: float
    completed: bool = False


class Indicators(BaseModel):
    """Technical indicators model."""
    time: datetime
    symbol: str
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_100: Optional[float] = None
    sma_200: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    ema_50: Optional[float] = None
    vwap: Optional[float] = None
    stoch_k: Optional[float] = None
    stoch_d: Optional[float] = None
    volume_sma: Optional[float] = None
    atr_14: Optional[float] = None
    adx_14: Optional[float] = None


class Trade(BaseModel):
    """Raw trade event model."""
    exchange: str
    symbol: str
    price: float
    quantity: float
    timestamp: int
    is_buyer_maker: Optional[bool] = None


class DataQualityMetric(BaseModel):
    """Data quality metrics model."""
    time: datetime
    symbol: str
    quality_score: float = Field(..., ge=0.0, le=1.0)
    price_anomaly_count: int = 0
    freshness_violations: int = 0
    invalid_values_count: int = 0
    volume_anomaly_count: int = 0
    total_checks: int = 0
    passed_checks: int = 0


class Alert(BaseModel):
    """Alert configuration model."""
    id: Optional[int] = None
    user_id: Optional[str] = None
    symbol: str
    condition: str  # PRICE_ABOVE, PRICE_BELOW, RSI_ABOVE, RSI_BELOW, etc.
    threshold: float
    channels: list[str]  # WEBSOCKET, EMAIL, WEBHOOK, SLACK
    cooldown: int = 300  # seconds
    one_time: bool = False
    is_active: bool = True
    last_triggered: Optional[datetime] = None
    created_at: Optional[datetime] = None
