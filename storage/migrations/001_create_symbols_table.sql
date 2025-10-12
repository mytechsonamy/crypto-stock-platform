-- Migration: Create symbols management table
-- Description: Dynamic symbol configuration instead of hardcoded YAML

-- Asset classes enum
CREATE TYPE asset_class_enum AS ENUM ('CRYPTO', 'BIST', 'NASDAQ', 'NYSE');

-- Symbols table
CREATE TABLE symbols (
    id SERIAL PRIMARY KEY,
    asset_class asset_class_enum NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    display_name VARCHAR(100),
    exchange VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Unique constraint
    UNIQUE(asset_class, symbol, exchange)
);

-- Indexes
CREATE INDEX idx_symbols_asset_class ON symbols(asset_class);
CREATE INDEX idx_symbols_is_active ON symbols(is_active);
CREATE INDEX idx_symbols_exchange ON symbols(exchange);
CREATE INDEX idx_symbols_active_class ON symbols(asset_class, is_active);

-- Comments
COMMENT ON TABLE symbols IS 'Dynamic symbol configuration for all asset classes';
COMMENT ON COLUMN symbols.asset_class IS 'Asset class: CRYPTO, BIST, NASDAQ, NYSE';
COMMENT ON COLUMN symbols.symbol IS 'Trading symbol (e.g., BTC, AAPL, THYAO.IS)';
COMMENT ON COLUMN symbols.display_name IS 'Human-readable name';
COMMENT ON COLUMN symbols.exchange IS 'Exchange name (binance, alpaca, yahoo)';
COMMENT ON COLUMN symbols.is_active IS 'Whether to actively collect data for this symbol';
COMMENT ON COLUMN symbols.metadata IS 'Additional metadata (lot size, tick size, etc.)';

-- Insert initial symbols
INSERT INTO symbols (asset_class, symbol, display_name, exchange, metadata) VALUES
-- Crypto (Binance)
('CRYPTO', 'BTCUSDT', 'Bitcoin', 'binance', '{"base": "BTC", "quote": "USDT"}'),
('CRYPTO', 'ETHUSDT', 'Ethereum', 'binance', '{"base": "ETH", "quote": "USDT"}'),
('CRYPTO', 'SOLUSDT', 'Solana', 'binance', '{"base": "SOL", "quote": "USDT"}'),
('CRYPTO', 'AVAXUSDT', 'Avalanche', 'binance', '{"base": "AVAX", "quote": "USDT"}'),
('CRYPTO', 'XRPUSDT', 'Ripple', 'binance', '{"base": "XRP", "quote": "USDT"}'),
('CRYPTO', 'SUIUSDT', 'Sui', 'binance', '{"base": "SUI", "quote": "USDT"}'),
('CRYPTO', 'ENAUSDT', 'Ethena', 'binance', '{"base": "ENA", "quote": "USDT"}'),
('CRYPTO', 'UNIUSDT', 'Uniswap', 'binance', '{"base": "UNI", "quote": "USDT"}'),
('CRYPTO', 'BNBUSDT', 'Binance Coin', 'binance', '{"base": "BNB", "quote": "USDT"}'),

-- BIST (Yahoo Finance)
('BIST', 'THYAO.IS', 'Türk Hava Yolları', 'yahoo', '{"currency": "TRY"}'),
('BIST', 'GARAN.IS', 'Garanti BBVA', 'yahoo', '{"currency": "TRY"}'),
('BIST', 'ISCTR.IS', 'İş Bankası (C)', 'yahoo', '{"currency": "TRY"}'),
('BIST', 'AKBNK.IS', 'Akbank', 'yahoo', '{"currency": "TRY"}'),
('BIST', 'SISE.IS', 'Şişe Cam', 'yahoo', '{"currency": "TRY"}'),

-- NASDAQ (Alpaca)
('NASDAQ', 'AAPL', 'Apple Inc.', 'alpaca', '{"sector": "Technology"}'),
('NASDAQ', 'TSLA', 'Tesla Inc.', 'alpaca', '{"sector": "Automotive"}'),
('NASDAQ', 'NVDA', 'NVIDIA Corporation', 'alpaca', '{"sector": "Technology"}'),
('NASDAQ', 'MSFT', 'Microsoft Corporation', 'alpaca', '{"sector": "Technology"}'),
('NASDAQ', 'GOOGL', 'Alphabet Inc.', 'alpaca', '{"sector": "Technology"}'),
('NASDAQ', 'AMZN', 'Amazon.com Inc.', 'alpaca', '{"sector": "E-commerce"}'),
('NASDAQ', 'META', 'Meta Platforms Inc.', 'alpaca', '{"sector": "Technology"}'),

-- NYSE (Alpaca)
('NYSE', 'BA', 'Boeing Company', 'alpaca', '{"sector": "Aerospace"}'),
('NYSE', 'JPM', 'JPMorgan Chase & Co.', 'alpaca', '{"sector": "Financial"}');

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_symbols_updated_at BEFORE UPDATE ON symbols
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
