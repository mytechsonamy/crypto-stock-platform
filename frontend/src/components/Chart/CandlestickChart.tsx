/**
 * Main Candlestick Chart Component
 * Uses Lightweight Charts library for high-performance rendering
 */

import React, { useEffect, useRef, memo } from 'react';
import { createChart, IChartApi, ISeriesApi, CandlestickData, LineData } from 'lightweight-charts';
import { useChartStore } from '@/store/chartStore';
import type { Candle, Indicators } from '@/types/chart.types';

interface CandlestickChartProps {
  height?: number;
}

export const CandlestickChart = memo<CandlestickChartProps>(({ height = 600 }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  
  // Indicator series refs
  const indicatorSeriesRef = useRef<{
    sma20?: ISeriesApi<'Line'>;
    sma50?: ISeriesApi<'Line'>;
    sma100?: ISeriesApi<'Line'>;
    sma200?: ISeriesApi<'Line'>;
    ema12?: ISeriesApi<'Line'>;
    ema26?: ISeriesApi<'Line'>;
    ema50?: ISeriesApi<'Line'>;
    bbUpper?: ISeriesApi<'Line'>;
    bbMiddle?: ISeriesApi<'Line'>;
    bbLower?: ISeriesApi<'Line'>;
    vwap?: ISeriesApi<'Line'>;
  }>({});

  const { bars, indicators: enabledIndicators } = useChartStore();

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height,
      layout: {
        background: { color: '#0f172a' },
        textColor: '#94a3b8',
      },
      grid: {
        vertLines: { color: '#1e293b' },
        horzLines: { color: '#1e293b' },
      },
      crosshair: {
        mode: 1, // Normal crosshair
        vertLine: {
          width: 1,
          color: '#475569',
          style: 2, // Dashed
        },
        horzLine: {
          width: 1,
          color: '#475569',
          style: 2,
        },
      },
      rightPriceScale: {
        borderColor: '#334155',
      },
      timeScale: {
        borderColor: '#334155',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    chartRef.current = chart;

    // Create candlestick series
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#10b981',
      downColor: '#ef4444',
      borderUpColor: '#10b981',
      borderDownColor: '#ef4444',
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
    });

    candlestickSeriesRef.current = candlestickSeries;

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    // Cleanup
    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [height]);

  // Update candlestick data
  useEffect(() => {
    if (!candlestickSeriesRef.current || bars.length === 0) return;

    const candleData: CandlestickData[] = bars.map((bar) => ({
      time: bar.time as any,
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
    }));

    candlestickSeriesRef.current.setData(candleData);
  }, [bars]);

  // Update indicators
  useEffect(() => {
    if (!chartRef.current || bars.length === 0) return;

    // Helper to create or update line series
    const updateLineSeries = (
      key: keyof typeof indicatorSeriesRef.current,
      enabled: boolean,
      indicatorKey: keyof Indicators,
      color: string,
      lineWidth: number = 2,
      lineStyle: number = 0
    ) => {
      if (enabled) {
        // Create series if it doesn't exist
        if (!indicatorSeriesRef.current[key]) {
          indicatorSeriesRef.current[key] = chartRef.current!.addLineSeries({
            color,
            lineWidth,
            lineStyle,
            priceLineVisible: false,
            lastValueVisible: false,
          });
        }

        // Update data
        const data: LineData[] = bars
          .map((bar, index) => {
            // Get indicator value from bar or use a placeholder
            const value = (bar as any)[indicatorKey];
            return value !== undefined && value !== null
              ? { time: bar.time as any, value }
              : null;
          })
          .filter((d): d is LineData => d !== null);

        if (data.length > 0) {
          indicatorSeriesRef.current[key]!.setData(data);
        }
      } else {
        // Remove series if it exists
        if (indicatorSeriesRef.current[key]) {
          chartRef.current!.removeSeries(indicatorSeriesRef.current[key]!);
          delete indicatorSeriesRef.current[key];
        }
      }
    };

    // SMA indicators
    updateLineSeries('sma20', enabledIndicators.sma20, 'sma_20', '#3b82f6', 2);
    updateLineSeries('sma50', enabledIndicators.sma50, 'sma_50', '#10b981', 2);
    updateLineSeries('sma100', enabledIndicators.sma100, 'sma_100', '#f59e0b', 2);
    updateLineSeries('sma200', enabledIndicators.sma200, 'sma_200', '#ef4444', 2);

    // EMA indicators
    updateLineSeries('ema12', enabledIndicators.ema12, 'ema_12', '#8b5cf6', 2);
    updateLineSeries('ema26', enabledIndicators.ema26, 'ema_26', '#ec4899', 2);
    updateLineSeries('ema50', enabledIndicators.ema50, 'ema_50', '#6366f1', 2);

    // Bollinger Bands
    updateLineSeries('bbUpper', enabledIndicators.bollingerBands, 'bb_upper', '#64748b', 1, 2);
    updateLineSeries('bbMiddle', enabledIndicators.bollingerBands, 'bb_middle', '#94a3b8', 1);
    updateLineSeries('bbLower', enabledIndicators.bollingerBands, 'bb_lower', '#64748b', 1, 2);

    // VWAP
    updateLineSeries('vwap', enabledIndicators.vwap, 'vwap', '#f97316', 2);
  }, [bars, enabledIndicators]);

  return (
    <div className="relative w-full" style={{ height }}>
      <div ref={chartContainerRef} className="w-full h-full" />
      {bars.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="text-gray-500">No data available</div>
        </div>
      )}
    </div>
  );
});

CandlestickChart.displayName = 'CandlestickChart';
