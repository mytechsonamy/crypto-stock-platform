-- Migration: Create ml_features table
-- Description: Stores engineered features for machine learning models
-- Version: 004
-- Created: 2024-10-11

-- Create ml_features table
CREATE TABLE IF NOT EXISTS ml_features (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    feature_version TEXT NOT NULL,
    
    -- Price features
    return_1 DOUBLE PRECISION,
    return_5 DOUBLE PRECISION,
    return_10 DOUBLE PRECISION,
    log_return DOUBLE PRECISION,
    price_momentum_5 DOUBLE PRECISION,
    price_momentum_10 DOUBLE PRECISION,
    price_acceleration DOUBLE PRECISION,
    
    -- Volatility features
    volatility_5 DOUBLE PRECISION,
    volatility_10 DOUBLE PRECISION,
    volatility_20 DOUBLE PRECISION,
    high_low_ratio DOUBLE PRECISION,
    true_range DOUBLE PRECISION,
    volatility_trend DOUBLE PRECISION,
    
    -- Volume features
    volume_change DOUBLE PRECISION,
    volume_momentum_5 DOUBLE PRECISION,
    volume_momentum_10 DOUBLE PRECISION,
    volume_ratio_5 DOUBLE PRECISION,
    volume_ratio_20 DOUBLE PRECISION,
    volume_price_trend DOUBLE PRECISION,
    volume_price_trend_norm DOUBLE PRECISION,
    
    -- Technical features
    rsi DOUBLE PRECISION,
    rsi_oversold INTEGER,
    rsi_overbought INTEGER,
    rsi_neutral INTEGER,
    macd DOUBLE PRECISION,
    macd_signal DOUBLE PRECISION,
    macd_diff DOUBLE PRECISION,
    macd_crossover INTEGER,
    macd_crossunder INTEGER,
    bb_upper DOUBLE PRECISION,
    bb_middle DOUBLE PRECISION,
    bb_lower DOUBLE PRECISION,
    bb_position DOUBLE PRECISION,
    bb_width DOUBLE PRECISION,
    bb_squeeze INTEGER,
    
    -- Time features
    hour INTEGER,
    day_of_week INTEGER,
    is_weekend INTEGER,
    is_market_open INTEGER,
    
    -- Trend features
    sma_20 DOUBLE PRECISION,
    sma_50 DOUBLE PRECISION,
    sma_100 DOUBLE PRECISION,
    sma_200 DOUBLE PRECISION,
    sma_20_distance DOUBLE PRECISION,
    sma_50_distance DOUBLE PRECISION,
    sma_100_distance DOUBLE PRECISION,
    sma_200_distance DOUBLE PRECISION,
    price_above_sma_20 INTEGER,
    price_above_sma_50 INTEGER,
    price_above_sma_100 INTEGER,
    price_above_sma_200 INTEGER,
    trend_strength DOUBLE PRECISION,
    
    -- Metadata
    engineered_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create hypertable
SELECT create_hypertable('ml_features', 'time', if_not_exists => TRUE);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_ml_features_symbol_time 
    ON ml_features (symbol, time DESC);

CREATE INDEX IF NOT EXISTS idx_ml_features_exchange_time 
    ON ml_features (exchange, time DESC);

CREATE INDEX IF NOT EXISTS idx_ml_features_version 
    ON ml_features (feature_version, time DESC);

CREATE INDEX IF NOT EXISTS idx_ml_features_symbol_version_time 
    ON ml_features (symbol, feature_version, time DESC);

-- Create composite index for training queries
CREATE INDEX IF NOT EXISTS idx_ml_features_training 
    ON ml_features (symbol, feature_version, timeframe, time DESC);

-- Add retention policy (365 days for ML features)
SELECT add_retention_policy('ml_features', INTERVAL '365 days', if_not_exists => TRUE);

-- Create continuous aggregate for daily feature statistics
CREATE MATERIALIZED VIEW IF NOT EXISTS ml_features_daily_stats
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS bucket,
    symbol,
    feature_version,
    COUNT(*) as feature_count,
    AVG(return_1) as avg_return_1,
    AVG(volatility_20) as avg_volatility,
    AVG(volume_ratio_20) as avg_volume_ratio,
    AVG(rsi) as avg_rsi
FROM ml_features
GROUP BY bucket, symbol, feature_version
WITH NO DATA;

-- Refresh policy for daily stats
SELECT add_continuous_aggregate_policy('ml_features_daily_stats',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Grant permissions (adjust as needed)
-- GRANT SELECT, INSERT ON ml_features TO app_user;
-- GRANT SELECT ON ml_features_daily_stats TO app_user;

-- Add comments
COMMENT ON TABLE ml_features IS 'Stores engineered features for machine learning models';
COMMENT ON COLUMN ml_features.time IS 'Timestamp of the feature data';
COMMENT ON COLUMN ml_features.symbol IS 'Trading symbol';
COMMENT ON COLUMN ml_features.exchange IS 'Exchange name (binance, alpaca, yahoo)';
COMMENT ON COLUMN ml_features.timeframe IS 'Timeframe (1m, 5m, 15m, 1h, etc.)';
COMMENT ON COLUMN ml_features.feature_version IS 'Feature schema version for reproducibility';
COMMENT ON COLUMN ml_features.return_1 IS 'Price return over 1 period';
COMMENT ON COLUMN ml_features.volatility_20 IS 'Rolling standard deviation over 20 periods';
COMMENT ON COLUMN ml_features.rsi IS 'Relative Strength Index';
COMMENT ON COLUMN ml_features.macd IS 'MACD indicator value';
COMMENT ON COLUMN ml_features.bb_position IS 'Position within Bollinger Bands (0-1)';
