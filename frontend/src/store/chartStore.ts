/**
 * Chart state management with Zustand
 * Persists settings to localStorage
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ChartSettings, Timeframe, Candle, Indicators } from '@/types/chart.types';

interface ChartState extends ChartSettings {
  // Data
  bars: Candle[];
  currentIndicators: Indicators | null;
  
  // UI State
  isLoading: boolean;
  error: string | null;
  isConnected: boolean;
  
  // Actions
  setSymbol: (symbol: string) => void;
  setTimeframe: (timeframe: Timeframe) => void;
  toggleIndicator: (indicator: keyof ChartSettings['indicators']) => void;
  setBars: (bars: Candle[]) => void;
  updateBar: (bar: Candle) => void;
  setIndicators: (indicators: Indicators) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setConnected: (connected: boolean) => void;
  reset: () => void;
}

const defaultSettings: ChartSettings = {
  symbol: 'BTCUSDT',
  timeframe: '1m',
  indicators: {
    sma20: true,
    sma50: true,
    sma100: false,
    sma200: false,
    ema12: false,
    ema26: false,
    ema50: false,
    bollingerBands: true,
    vwap: false,
    rsi: true,
    macd: true,
    stochastic: false,
    volume: true,
  },
};

export const useChartStore = create<ChartState>()(
  persist(
    (set, get) => ({
      // Initial state
      ...defaultSettings,
      bars: [],
      currentIndicators: null,
      isLoading: false,
      error: null,
      isConnected: false,

      // Actions
      setSymbol: (symbol: string) => {
        set({ symbol, bars: [], currentIndicators: null, error: null });
      },

      setTimeframe: (timeframe: Timeframe) => {
        set({ timeframe, bars: [], currentIndicators: null, error: null });
      },

      toggleIndicator: (indicator: keyof ChartSettings['indicators']) => {
        set((state) => ({
          indicators: {
            ...state.indicators,
            [indicator]: !state.indicators[indicator],
          },
        }));
      },

      setBars: (bars: Candle[]) => {
        set({ bars, isLoading: false, error: null });
      },

      updateBar: (bar: Candle) => {
        set((state) => {
          const bars = [...state.bars];
          const lastBar = bars[bars.length - 1];

          // Update last bar if same timestamp, otherwise append
          if (lastBar && lastBar.time === bar.time) {
            bars[bars.length - 1] = bar;
          } else {
            bars.push(bar);
            // Keep only last 1000 bars in memory
            if (bars.length > 1000) {
              bars.shift();
            }
          }

          return { bars };
        });
      },

      setIndicators: (indicators: Indicators) => {
        set({ currentIndicators: indicators });
      },

      setLoading: (loading: boolean) => {
        set({ isLoading: loading });
      },

      setError: (error: string | null) => {
        set({ error, isLoading: false });
      },

      setConnected: (connected: boolean) => {
        set({ isConnected: connected });
      },

      reset: () => {
        set({
          ...defaultSettings,
          bars: [],
          currentIndicators: null,
          isLoading: false,
          error: null,
          isConnected: false,
        });
      },
    }),
    {
      name: 'chart-settings',
      // Only persist settings, not data or UI state
      partialize: (state) => ({
        symbol: state.symbol,
        timeframe: state.timeframe,
        indicators: state.indicators,
      }),
    }
  )
);
