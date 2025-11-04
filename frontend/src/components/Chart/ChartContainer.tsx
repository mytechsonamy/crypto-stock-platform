/**
 * Chart Container Component
 * Combines main chart with indicator panels
 */

import React, { memo, useEffect } from 'react';
import { useChartStore } from '@/store/chartStore';
import { useWebSocket } from '@/hooks/useWebSocket';
import { apiService } from '@/services/api';
import { CandlestickChart } from './CandlestickChart';
import { VolumePanel } from './VolumePanel';
import { RSIPanel } from './RSIPanel';
import { MACDPanel } from './MACDPanel';
import { StochasticPanel } from './StochasticPanel';
import { ChartControls } from './ChartControls';

export const ChartContainer = memo(() => {
  const { symbol, timeframe, indicators, isLoading, error, setBars, setLoading, setError } = useChartStore();

  // Fetch chart data from API
  useEffect(() => {
    const fetchChartData = async () => {
      try {
        setLoading(true);
        const data = await apiService.getChartData(symbol, timeframe, 1000);

        // Convert API response to Candle format
        const bars = data.bars.map((bar: any) => ({
          time: new Date(bar.time).getTime() / 1000, // Convert to Unix timestamp
          open: bar.open,
          high: bar.high,
          low: bar.low,
          close: bar.close,
          volume: bar.volume,
        }));

        setBars(bars);
      } catch (err: any) {
        console.error('Failed to fetch chart data:', err);
        setError(err.message || 'Failed to load chart data');
      }
    };

    // Initial fetch
    fetchChartData();

    // Poll for updates every 30 seconds for 1m timeframe, 60s for others
    const pollInterval = timeframe === '1m' ? 30000 : 60000;
    const intervalId = setInterval(fetchChartData, pollInterval);

    return () => clearInterval(intervalId);
  }, [symbol, timeframe, setBars, setLoading, setError]);

  // Connect to WebSocket for real-time updates
  const token = localStorage.getItem('auth_token') || undefined;
  useWebSocket({
    symbol,
    token,
    enabled: true,
    throttleMs: 1000,
  });

  return (
    <div className="flex flex-col h-full">
      {/* Chart Controls */}
      <ChartControls />

      {/* Loading State */}
      {isLoading && (
        <div className="flex items-center justify-center h-full">
          <div className="text-center">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500 mb-4"></div>
            <p className="text-gray-400">Loading chart data...</p>
          </div>
        </div>
      )}

      {/* Error State */}
      {error && !isLoading && (
        <div className="flex items-center justify-center h-full">
          <div className="text-center">
            <svg
              className="w-16 h-16 text-red-500 mx-auto mb-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <p className="text-red-400 mb-2">Error loading chart</p>
            <p className="text-gray-500 text-sm">{error}</p>
          </div>
        </div>
      )}

      {/* Chart Content */}
      {!isLoading && !error && (
        <div className="flex-1 overflow-auto">
          {/* Main Candlestick Chart */}
          <CandlestickChart height={400} />

          {/* Volume Panel */}
          {indicators.volume && <VolumePanel height={120} />}

          {/* RSI Panel */}
          {indicators.rsi && <RSIPanel height={120} />}

          {/* MACD Panel */}
          {indicators.macd && <MACDPanel height={120} />}

          {/* Stochastic Panel */}
          {indicators.stochastic && <StochasticPanel height={120} />}
        </div>
      )}
    </div>
  );
});

ChartContainer.displayName = 'ChartContainer';
