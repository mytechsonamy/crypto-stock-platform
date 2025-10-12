-- Migration 007: Create audit log table
-- Description: System audit trail for important events

CREATE TYPE audit_event_type AS ENUM (
    'COLLECTOR_START',
    'COLLECTOR_STOP',
    'COLLECTOR_ERROR',
    'CIRCUIT_BREAKER_OPEN',
    'CIRCUIT_BREAKER_CLOSE',
    'SYMBOL_ADDED',
    'SYMBOL_REMOVED',
    'ALERT_TRIGGERED',
    'DATA_QUALITY_ISSUE',
    'BACKUP_COMPLETED',
    'BACKUP_FAILED'
);

CREATE TABLE audit_log (
    id BIGSERIAL,
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type audit_event_type NOT NULL,
    component VARCHAR(50) NOT NULL,
    symbol VARCHAR(20),
    user_id VARCHAR(100),
    message TEXT,
    details JSONB DEFAULT '{}',
    severity VARCHAR(20) DEFAULT 'INFO',
    
    -- Constraints
    PRIMARY KEY (time, id)
);

-- Convert to hypertable
SELECT create_hypertable('audit_log', 'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Create indexes
CREATE INDEX idx_audit_event_type ON audit_log (event_type, time DESC);
CREATE INDEX idx_audit_component ON audit_log (component, time DESC);
CREATE INDEX idx_audit_symbol ON audit_log (symbol, time DESC) WHERE symbol IS NOT NULL;
CREATE INDEX idx_audit_severity ON audit_log (severity, time DESC);

-- Add retention policy (90 days for audit logs)
SELECT add_retention_policy('audit_log', INTERVAL '90 days', if_not_exists => TRUE);

-- Enable compression
ALTER TABLE audit_log SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'event_type,component',
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy('audit_log', INTERVAL '7 days', if_not_exists => TRUE);

-- Comments
COMMENT ON TABLE audit_log IS 'System audit trail for important events';
COMMENT ON COLUMN audit_log.event_type IS 'Type of audit event';
COMMENT ON COLUMN audit_log.component IS 'System component that generated the event';
COMMENT ON COLUMN audit_log.severity IS 'Event severity: DEBUG, INFO, WARNING, ERROR, CRITICAL';
