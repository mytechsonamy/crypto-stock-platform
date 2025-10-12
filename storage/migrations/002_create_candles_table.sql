-- Migration 002: Create candles (OHLC) table
-- Description: Time-series table for candlestick data

CREATE TABLE candles (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    exchange VARCHAR(50) NOT NULL,
    timeframe VARCHAR(5) NOT NULL,
    open NUMERIC(20,8) NOT NULL,
    high NUMERIC(20,8) NOT NULL,
    low NUMERIC(20,8) NOT NULL,
    close NUMERIC(20,8) NOT NULL,
    volume NUMERIC(20,8) NOT NULL,
    
    -- Constraints
    PRIMARY KEY (time, symbol, exchange, timeframe),
    CHECK (high >= open AND high >= close),
    CHECK (low <= open AND low <= close),
    CHECK (volume >= 0)
);

-- Convert to hypertable (partitioned by time)
SELECT create_hypertable('candles', 'time', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Create indexes for efficient queries
CREATE INDEX idx_candles_symbol_time ON candles (symbol, time DESC);
CREATE INDEX idx_candles_exchange_time ON candles (exchange, time DESC);
CREATE INDEX idx_candles_timeframe ON candles (timeframe, time DESC);
CREATE INDEX idx_candles_symbol_timeframe ON candles (symbol, timeframe, time DESC);

-- Add retention policy (keep data for 365 days)
SELECT add_retention_policy('candles', INTERVAL '365 days', if_not_exists => TRUE);

-- Enable compression (compress chunks older than 7 days)
ALTER TABLE candles SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol,exchange,timeframe',
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy('candles', INTERVAL '7 days', if_not_exists => TRUE);

-- Create continuous aggregate for 1-hour candles from 1-minute data
CREATE MATERIALIZED VIEW candles_1h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS time,
    symbol,
    exchange,
    '1h' as timeframe,
    FIRST(open, time) as open,
    MAX(high) as high,
    MIN(low) as low,
    LAST(close, time) as close,
    SUM(volume) as volume
FROM candles
WHERE timeframe = '1m'
GROUP BY time_bucket('1 hour', time), symbol, exchange
WITH NO DATA;

-- Refresh policy for continuous aggregate
SELECT add_continuous_aggregate_policy('candles_1h',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- Create continuous aggregate for 4-hour candles
CREATE MATERIALIZED VIEW candles_4h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('4 hours', time) AS time,
    symbol,
    exchange,
    '4h' as timeframe,
    FIRST(open, time) as open,
    MAX(high) as high,
    MIN(low) as low,
    LAST(close, time) as close,
    SUM(volume) as volume
FROM candles
WHERE timeframe = '1m'
GROUP BY time_bucket('4 hours', time), symbol, exchange
WITH NO DATA;

SELECT add_continuous_aggregate_policy('candles_4h',
    start_offset => INTERVAL '12 hours',
    end_offset => INTERVAL '4 hours',
    schedule_interval => INTERVAL '4 hours',
    if_not_exists => TRUE
);

-- Create continuous aggregate for daily candles
CREATE MATERIALIZED VIEW candles_1d
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS time,
    symbol,
    exchange,
    '1d' as timeframe,
    FIRST(open, time) as open,
    MAX(high) as high,
    MIN(low) as low,
    LAST(close, time) as close,
    SUM(volume) as volume
FROM candles
WHERE timeframe = '1m'
GROUP BY time_bucket('1 day', time), symbol, exchange
WITH NO DATA;

SELECT add_continuous_aggregate_policy('candles_1d',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Comments
COMMENT ON TABLE candles IS 'OHLC candlestick data for all symbols and timeframes';
COMMENT ON COLUMN candles.time IS 'Candle timestamp (start of period)';
COMMENT ON COLUMN candles.symbol IS 'Trading symbol';
COMMENT ON COLUMN candles.exchange IS 'Exchange name (binance, alpaca, yahoo)';
COMMENT ON COLUMN candles.timeframe IS 'Timeframe (1m, 5m, 15m, 1h, 4h, 1d)';
COMMENT ON COLUMN candles.open IS 'Opening price';
COMMENT ON COLUMN candles.high IS 'Highest price';
COMMENT ON COLUMN candles.low IS 'Lowest price';
COMMENT ON COLUMN candles.close IS 'Closing price';
COMMENT ON COLUMN candles.volume IS 'Trading volume';
