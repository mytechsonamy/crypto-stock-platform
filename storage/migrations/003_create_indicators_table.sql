-- Migration 003: Create indicators table
-- Description: Technical indicators calculated from candle data

CREATE TABLE indicators (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    
    -- Momentum indicators
    rsi_14 NUMERIC(10,4),
    
    -- Trend indicators
    macd NUMERIC(10,4),
    macd_signal NUMERIC(10,4),
    macd_hist NUMERIC(10,4),
    adx_14 NUMERIC(10,4),
    
    -- Volatility indicators
    bb_upper NUMERIC(20,8),
    bb_middle NUMERIC(20,8),
    bb_lower NUMERIC(20,8),
    atr_14 NUMERIC(20,8),
    
    -- Moving averages
    sma_20 NUMERIC(20,8),
    sma_50 NUMERIC(20,8),
    sma_100 NUMERIC(20,8),
    sma_200 NUMERIC(20,8),
    ema_12 NUMERIC(20,8),
    ema_26 NUMERIC(20,8),
    ema_50 NUMERIC(20,8),
    
    -- Volume indicators
    volume_sma NUMERIC(20,8),
    vwap NUMERIC(20,8),
    
    -- Oscillators
    stoch_k NUMERIC(10,4),
    stoch_d NUMERIC(10,4),
    
    -- Constraints
    PRIMARY KEY (time, symbol)
);

-- Convert to hypertable
SELECT create_hypertable('indicators', 'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Create indexes
CREATE INDEX idx_indicators_symbol_time ON indicators (symbol, time DESC);

-- Add retention policy (365 days)
SELECT add_retention_policy('indicators', INTERVAL '365 days', if_not_exists => TRUE);

-- Enable compression
ALTER TABLE indicators SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol',
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy('indicators', INTERVAL '7 days', if_not_exists => TRUE);

-- Comments
COMMENT ON TABLE indicators IS 'Technical indicators calculated from candle data';
COMMENT ON COLUMN indicators.time IS 'Indicator timestamp';
COMMENT ON COLUMN indicators.symbol IS 'Trading symbol';
COMMENT ON COLUMN indicators.rsi_14 IS 'Relative Strength Index (14 period)';
COMMENT ON COLUMN indicators.macd IS 'MACD line';
COMMENT ON COLUMN indicators.macd_signal IS 'MACD signal line';
COMMENT ON COLUMN indicators.macd_hist IS 'MACD histogram';
COMMENT ON COLUMN indicators.bb_upper IS 'Bollinger Band upper';
COMMENT ON COLUMN indicators.bb_middle IS 'Bollinger Band middle (SMA)';
COMMENT ON COLUMN indicators.bb_lower IS 'Bollinger Band lower';
COMMENT ON COLUMN indicators.vwap IS 'Volume Weighted Average Price';
