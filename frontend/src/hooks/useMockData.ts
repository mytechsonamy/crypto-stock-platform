/**
 * Mock data hook for testing charts
 * Generates random OHLC data with indicators
 */

import { useEffect } from 'react';
import { useChartStore } from '@/store/chartStore';
import type { Candle } from '@/types/chart.types';

export const useMockData = (enabled: boolean = false) => {
  const { setBars, setLoading } = useChartStore();

  useEffect(() => {
    if (!enabled) return;

    setLoading(true);

    // Generate mock data
    const generateMockData = (): Candle[] => {
      const bars: Candle[] = [];
      const now = Math.floor(Date.now() / 1000);
      const startTime = now - 1000 * 60; // 1000 minutes ago
      let price = 50000;

      for (let i = 0; i < 1000; i++) {
        const time = startTime + i * 60;
        const change = (Math.random() - 0.5) * 100;
        const open = price;
        const close = price + change;
        const high = Math.max(open, close) + Math.random() * 50;
        const low = Math.min(open, close) - Math.random() * 50;
        const volume = Math.random() * 1000000;

        bars.push({
          time,
          open,
          high,
          low,
          close,
          volume,
        } as any);

        price = close;
      }

      // Add mock indicators
      return bars.map((bar, index) => {
        if (index < 20) return bar;

        // Calculate simple moving averages
        const sma20 = bars.slice(index - 19, index + 1).reduce((sum, b) => sum + b.close, 0) / 20;
        const sma50 = index >= 50 ? bars.slice(index - 49, index + 1).reduce((sum, b) => sum + b.close, 0) / 50 : undefined;

        // Mock RSI (oscillates between 30-70)
        const rsi = 50 + Math.sin(index / 10) * 20;

        // Mock MACD
        const macd = Math.sin(index / 20) * 100;
        const macd_signal = Math.sin((index - 5) / 20) * 100;
        const macd_histogram = macd - macd_signal;

        // Mock Bollinger Bands
        const bb_middle = sma20;
        const bb_upper = sma20 + 200;
        const bb_lower = sma20 - 200;

        return {
          ...bar,
          sma_20: sma20,
          sma_50: sma50,
          rsi,
          macd,
          macd_signal,
          macd_histogram,
          bb_upper,
          bb_middle,
          bb_lower,
          vwap: bar.close * 1.001,
          stoch_k: 50 + Math.sin(index / 8) * 30,
          stoch_d: 50 + Math.sin((index - 3) / 8) * 30,
        };
      });
    };

    // Simulate loading delay
    setTimeout(() => {
      const mockData = generateMockData();
      setBars(mockData);
    }, 500);
  }, [enabled, setBars, setLoading]);
};
