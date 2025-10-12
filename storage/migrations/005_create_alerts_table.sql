-- Migration: Create alerts table
-- Description: Stores user-defined alerts for price and indicator conditions

CREATE TABLE IF NOT EXISTS alerts (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    condition VARCHAR(50) NOT NULL,  -- price_above, price_below, rsi_above, etc.
    threshold DOUBLE PRECISION NOT NULL,
    channels TEXT[] NOT NULL,  -- Array of notification channels
    cooldown_seconds INTEGER DEFAULT 300,  -- 5 minutes default
    one_time BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_triggered_at TIMESTAMPTZ,
    trigger_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb,  -- Additional configuration (email, webhook_url, etc.)
    
    -- Constraints
    CONSTRAINT valid_condition CHECK (
        condition IN (
            'price_above', 'price_below',
            'rsi_above', 'rsi_below',
            'macd_crossover', 'volume_spike'
        )
    ),
    CONSTRAINT valid_threshold CHECK (threshold >= 0),
    CONSTRAINT valid_cooldown CHECK (cooldown_seconds >= 0)
);

-- Indexes for efficient queries
CREATE INDEX idx_alerts_user_id ON alerts(user_id);
CREATE INDEX idx_alerts_symbol ON alerts(symbol);
CREATE INDEX idx_alerts_active ON alerts(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_alerts_user_symbol ON alerts(user_id, symbol);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_alerts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER alerts_updated_at_trigger
    BEFORE UPDATE ON alerts
    FOR EACH ROW
    EXECUTE FUNCTION update_alerts_updated_at();

-- Comments
COMMENT ON TABLE alerts IS 'User-defined alerts for price and indicator conditions';
COMMENT ON COLUMN alerts.alert_id IS 'Unique alert identifier';
COMMENT ON COLUMN alerts.user_id IS 'User who created the alert';
COMMENT ON COLUMN alerts.symbol IS 'Trading symbol to monitor';
COMMENT ON COLUMN alerts.condition IS 'Alert condition type';
COMMENT ON COLUMN alerts.threshold IS 'Threshold value for condition';
COMMENT ON COLUMN alerts.channels IS 'Notification delivery channels';
COMMENT ON COLUMN alerts.cooldown_seconds IS 'Minimum time between notifications';
COMMENT ON COLUMN alerts.one_time IS 'If true, alert triggers only once';
COMMENT ON COLUMN alerts.is_active IS 'Whether alert is currently active';
COMMENT ON COLUMN alerts.last_triggered_at IS 'Last time alert was triggered';
COMMENT ON COLUMN alerts.trigger_count IS 'Number of times alert has triggered';
COMMENT ON COLUMN alerts.metadata IS 'Additional configuration (email, webhook URLs, etc.)';
