-- Migration 006: Create data quality metrics table
-- Description: Track data quality checks and scores

CREATE TABLE data_quality_metrics (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    
    -- Quality metrics
    quality_score NUMERIC(5,4) NOT NULL CHECK (quality_score >= 0 AND quality_score <= 1),
    price_anomaly_count INTEGER DEFAULT 0,
    freshness_violations INTEGER DEFAULT 0,
    invalid_values_count INTEGER DEFAULT 0,
    volume_anomaly_count INTEGER DEFAULT 0,
    
    -- Check statistics
    total_checks INTEGER NOT NULL,
    passed_checks INTEGER NOT NULL,
    
    -- Metadata
    details JSONB DEFAULT '{}',
    
    -- Constraints
    PRIMARY KEY (time, symbol)
);

-- Convert to hypertable
SELECT create_hypertable('data_quality_metrics', 'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Create indexes
CREATE INDEX idx_quality_symbol_time ON data_quality_metrics (symbol, time DESC);
CREATE INDEX idx_quality_score ON data_quality_metrics (quality_score, time DESC);

-- Add retention policy (90 days for quality metrics)
SELECT add_retention_policy('data_quality_metrics', INTERVAL '90 days', if_not_exists => TRUE);

-- Enable compression
ALTER TABLE data_quality_metrics SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol',
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy('data_quality_metrics', INTERVAL '7 days', if_not_exists => TRUE);

-- Create continuous aggregate for daily quality summary
CREATE MATERIALIZED VIEW data_quality_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS day,
    symbol,
    AVG(quality_score) as avg_quality_score,
    MIN(quality_score) as min_quality_score,
    SUM(price_anomaly_count) as total_price_anomalies,
    SUM(freshness_violations) as total_freshness_violations,
    SUM(invalid_values_count) as total_invalid_values,
    SUM(volume_anomaly_count) as total_volume_anomalies,
    SUM(total_checks) as total_checks,
    SUM(passed_checks) as total_passed_checks
FROM data_quality_metrics
GROUP BY time_bucket('1 day', time), symbol
WITH NO DATA;

SELECT add_continuous_aggregate_policy('data_quality_daily',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Comments
COMMENT ON TABLE data_quality_metrics IS 'Data quality metrics and validation results';
COMMENT ON COLUMN data_quality_metrics.quality_score IS 'Overall quality score (0-1)';
COMMENT ON COLUMN data_quality_metrics.price_anomaly_count IS 'Number of price anomalies detected';
COMMENT ON COLUMN data_quality_metrics.freshness_violations IS 'Number of stale data violations';
COMMENT ON COLUMN data_quality_metrics.invalid_values_count IS 'Number of invalid values detected';
COMMENT ON COLUMN data_quality_metrics.volume_anomaly_count IS 'Number of volume anomalies detected';
