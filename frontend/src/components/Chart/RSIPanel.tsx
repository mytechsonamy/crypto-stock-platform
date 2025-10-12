/**
 * RSI Panel Component
 * Displays RSI indicator with 30/70 threshold lines
 */

import React, { useEffect, useRef, memo } from 'react';
import { createChart, IChartApi, ISeriesApi, LineData } from 'lightweight-charts';
import { useChartStore } from '@/store/chartStore';

interface RSIPanelProps {
  height?: number;
}

export const RSIPanel = memo<RSIPanelProps>(({ height = 150 }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const rsiSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const oversoldLineRef = useRef<ISeriesApi<'Line'> | null>(null);
  const overboughtLineRef = useRef<ISeriesApi<'Line'> | null>(null);

  const { bars } = useChartStore();

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
      rightPriceScale: {
        borderColor: '#334155',
        scaleMargins: {
          top: 0.1,
          bottom: 0.1,
        },
      },
      timeScale: {
        borderColor: '#334155',
        visible: false,
      },
      crosshair: {
        mode: 1,
        vertLine: {
          width: 1,
          color: '#475569',
          style: 2,
        },
        horzLine: {
          width: 1,
          color: '#475569',
          style: 2,
        },
      },
    });

    chartRef.current = chart;

    // Create RSI line series
    const rsiSeries = chart.addLineSeries({
      color: '#8b5cf6',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
    });

    rsiSeriesRef.current = rsiSeries;

    // Create oversold line (30)
    const oversoldLine = chart.addLineSeries({
      color: '#10b981',
      lineWidth: 1,
      lineStyle: 2, // Dashed
      priceLineVisible: false,
      lastValueVisible: false,
    });

    oversoldLineRef.current = oversoldLine;

    // Create overbought line (70)
    const overboughtLine = chart.addLineSeries({
      color: '#ef4444',
      lineWidth: 1,
      lineStyle: 2, // Dashed
      priceLineVisible: false,
      lastValueVisible: false,
    });

    overboughtLineRef.current = overboughtLine;

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

  // Update RSI data
  useEffect(() => {
    if (!rsiSeriesRef.current || !oversoldLineRef.current || !overboughtLineRef.current || bars.length === 0) return;

    // RSI data
    const rsiData: LineData[] = bars
      .map((bar) => {
        const rsi = (bar as any).rsi;
        return rsi !== undefined && rsi !== null
          ? { time: bar.time as any, value: rsi }
          : null;
      })
      .filter((d): d is LineData => d !== null);

    if (rsiData.length > 0) {
      rsiSeriesRef.current.setData(rsiData);

      // Threshold lines
      const firstTime = rsiData[0].time;
      const lastTime = rsiData[rsiData.length - 1].time;

      oversoldLineRef.current.setData([
        { time: firstTime, value: 30 },
        { time: lastTime, value: 30 },
      ]);

      overboughtLineRef.current.setData([
        { time: firstTime, value: 70 },
        { time: lastTime, value: 70 },
      ]);
    }
  }, [bars]);

  return (
    <div className="relative w-full border-t border-dark-700" style={{ height }}>
      <div className="absolute top-2 left-2 z-10">
        <span className="text-xs font-semibold text-gray-400">RSI (14)</span>
      </div>
      <div ref={chartContainerRef} className="w-full h-full" />
    </div>
  );
});

RSIPanel.displayName = 'RSIPanel';
