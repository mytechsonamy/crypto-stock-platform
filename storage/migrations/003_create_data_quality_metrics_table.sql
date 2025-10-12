-- Migration: Create data_quality_metrics table
-- Description: Stores data quality validation metrics for monitoring and analysis
-- Version: 003
-- Created: 2024-10-11

-- Create data_quality_metrics table
CREATE TABLE IF NOT EXISTS data_quality_metrics (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    check_type TEXT NOT NULL,
    result TEXT NOT NULL,  -- 'passed' or 'failed'
    error_message TEXT,
    trade_price DOUBLE PRECISION,
    trade_quantity DOUBLE PRECISION,
    quality_score DOUBLE PRECISION,
    metadata JSONB
);

-- Create hypertable
SELECT create_hypertable('data_quality_metrics', 'time', if_not_exists => TRUE);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_data_quality_metrics_symbol_time 
    ON data_quality_metrics (symbol, time DESC);

CREATE INDEX IF NOT EXISTS idx_data_quality_metrics_exchange_time 
    ON data_quality_metrics (exchange, time DESC);

CREATE INDEX IF NOT EXISTS idx_data_quality_metrics_result 
    ON data_quality_metrics (result, time DESC);

CREATE INDEX IF NOT EXISTS idx_data_quality_metrics_check_type 
    ON data_quality_metrics (check_type, time DESC);

-- Create composite index for filtering
CREATE INDEX IF NOT EXISTS idx_data_quality_metrics_symbol_check_result 
    ON data_quality_metrics (symbol, check_type, result, time DESC);

-- Add retention policy (90 days for quality metrics)
SELECT add_retention_policy('data_quality_metrics', INTERVAL '90 days', if_not_exists => TRUE);

-- Create continuous aggregate for hourly quality metrics
CREATE MATERIALIZED VIEW IF NOT EXISTS data_quality_metrics_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    symbol,
    exchange,
    check_type,
    result,
    COUNT(*) as check_count,
    AVG(quality_score) as avg_quality_score,
    MIN(quality_score) as min_quality_score,
    MAX(quality_score) as max_quality_score
FROM data_quality_metrics
GROUP BY bucket, symbol, exchange, check_type, result
WITH NO DATA;

-- Refresh policy for continuous aggregate
SELECT add_continuous_aggregate_policy('data_quality_metrics_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- Create daily aggregate view
CREATE MATERIALIZED VIEW IF NOT EXISTS data_quality_metrics_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS bucket,
    symbol,
    exchange,
    COUNT(*) as total_checks,
    SUM(CASE WHEN result = 'passed' THEN 1 ELSE 0 END) as passed_checks,
    SUM(CASE WHEN result = 'failed' THEN 1 ELSE 0 END) as failed_checks,
    AVG(quality_score) as avg_quality_score,
    ROUND((SUM(CASE WHEN result = 'passed' THEN 1 ELSE 0 END)::NUMERIC / COUNT(*)::NUMERIC) * 100, 2) as pass_rate
FROM data_quality_metrics
GROUP BY bucket, symbol, exchange
WITH NO DATA;

-- Refresh policy for daily aggregate
SELECT add_continuous_aggregate_policy('data_quality_metrics_daily',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Grant permissions (adjust as needed)
-- GRANT SELECT, INSERT ON data_quality_metrics TO app_user;
-- GRANT SELECT ON data_quality_metrics_hourly TO app_user;
-- GRANT SELECT ON data_quality_metrics_daily TO app_user;

-- Add comments
COMMENT ON TABLE data_quality_metrics IS 'Stores data quality validation metrics for monitoring';
COMMENT ON COLUMN data_quality_metrics.time IS 'Timestamp of the quality check';
COMMENT ON COLUMN data_quality_metrics.symbol IS 'Trading symbol';
COMMENT ON COLUMN data_quality_metrics.exchange IS 'Exchange name (binance, alpaca, yahoo)';
COMMENT ON COLUMN data_quality_metrics.check_type IS 'Type of quality check (valid_values, data_freshness, price_anomaly, volume_sanity)';
COMMENT ON COLUMN data_quality_metrics.result IS 'Check result (passed or failed)';
COMMENT ON COLUMN data_quality_metrics.error_message IS 'Error message if check failed';
COMMENT ON COLUMN data_quality_metrics.quality_score IS 'Current quality score for the symbol (0.0 to 1.0)';
COMMENT ON COLUMN data_quality_metrics.metadata IS 'Additional metadata in JSON format';
