/**
 * Chart data types for Crypto-Stock Platform
 */

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  trade_count?: number;
}

export interface Indicators {
  // Moving Averages
  sma_20?: number;
  sma_50?: number;
  sma_100?: number;
  sma_200?: number;
  ema_12?: number;
  ema_26?: number;
  ema_50?: number;
  
  // Bollinger Bands
  bb_upper?: number;
  bb_middle?: number;
  bb_lower?: number;
  
  // RSI
  rsi?: number;
  
  // MACD
  macd?: number;
  macd_signal?: number;
  macd_histogram?: number;
  
  // Stochastic
  stoch_k?: number;
  stoch_d?: number;
  
  // Other
  vwap?: number;
  atr?: number;
  adx?: number;
  volume_sma?: number;
}

export interface ChartData {
  symbol: string;
  timeframe: string;
  bars: Candle[];
  indicators?: Record<string, Indicators>;
}

export type Timeframe = '1m' | '5m' | '15m' | '1h' | '4h' | '1d';

export interface IndicatorConfig {
  name: string;
  enabled: boolean;
  color?: string;
  lineWidth?: number;
}

export interface ChartSettings {
  symbol: string;
  timeframe: Timeframe;
  indicators: {
    sma20: boolean;
    sma50: boolean;
    sma100: boolean;
    sma200: boolean;
    ema12: boolean;
    ema26: boolean;
    ema50: boolean;
    bollingerBands: boolean;
    vwap: boolean;
    rsi: boolean;
    macd: boolean;
    stochastic: boolean;
    volume: boolean;
  };
}

// WebSocket message types
export interface WSMessage {
  type: 'initial' | 'update' | 'error' | 'pong';
  symbol?: string;
  data?: any;
  error?: string;
}

export interface WSInitialMessage extends WSMessage {
  type: 'initial';
  symbol: string;
  bars: Candle[];
  indicators: Record<string, Indicators>;
}

export interface WSUpdateMessage extends WSMessage {
  type: 'update';
  symbol: string;
  bar: Candle;
  indicators: Indicators;
}

export interface WSErrorMessage extends WSMessage {
  type: 'error';
  error: string;
}

// API response types
export interface SymbolInfo {
  symbol: string;
  exchange: string;
  type: 'crypto' | 'stock';
  active: boolean;
}

export interface SymbolsResponse {
  binance: SymbolInfo[];
  alpaca: SymbolInfo[];
  yahoo: SymbolInfo[];
}

export interface ChartDataResponse {
  symbol: string;
  timeframe: string;
  bars: Candle[];
  indicators: Record<string, Indicators>;
}

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  components: {
    database: {
      status: string;
      pool_size?: number;
      pool_free?: number;
    };
    redis: {
      status: string;
      memory_usage?: number;
    };
  };
}
