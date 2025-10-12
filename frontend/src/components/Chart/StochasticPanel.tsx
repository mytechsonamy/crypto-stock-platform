/**
 * Stochastic Panel Component
 * Displays %K and %D lines with 20/80 threshold lines
 */

import React, { useEffect, useRef, memo } from 'react';
import { createChart, IChartApi, ISeriesApi, LineData } from 'lightweight-charts';
import { useChartStore } from '@/store/chartStore';

interface StochasticPanelProps {
  height?: number;
}

export const StochasticPanel = memo<StochasticPanelProps>(({ height = 150 }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const kLineRef = useRef<ISeriesApi<'Line'> | null>(null);
  const dLineRef = useRef<ISeriesApi<'Line'> | null>(null);
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

    // Create %K line series
    const kLine = chart.addLineSeries({
      color: '#2962FF',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
    });

    kLineRef.current = kLine;

    // Create %D line series
    const dLine = chart.addLineSeries({
      color: '#FF6D00',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
    });

    dLineRef.current = dLine;

    // Create oversold line (20)
    const oversoldLine = chart.addLineSeries({
      color: '#10b981',
      lineWidth: 1,
      lineStyle: 2, // Dashed
      priceLineVisible: false,
      lastValueVisible: false,
    });

    oversoldLineRef.current = oversoldLine;

    // Create overbought line (80)
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

  // Update Stochastic data
  useEffect(() => {
    if (!kLineRef.current || !dLineRef.current || !oversoldLineRef.current || !overboughtLineRef.current || bars.length === 0) return;

    // %K data
    const kData: LineData[] = bars
      .map((bar) => {
        const k = (bar as any).stoch_k;
        return k !== undefined && k !== null
          ? { time: bar.time as any, value: k }
          : null;
      })
      .filter((d): d is LineData => d !== null);

    // %D data
    const dData: LineData[] = bars
      .map((bar) => {
        const d = (bar as any).stoch_d;
        return d !== undefined && d !== null
          ? { time: bar.time as any, value: d }
          : null;
      })
      .filter((d): d is LineData => d !== null);

    if (kData.length > 0) {
      kLineRef.current.setData(kData);

      // Threshold lines
      const firstTime = kData[0].time;
      const lastTime = kData[kData.length - 1].time;

      oversoldLineRef.current.setData([
        { time: firstTime, value: 20 },
        { time: lastTime, value: 20 },
      ]);

      overboughtLineRef.current.setData([
        { time: firstTime, value: 80 },
        { time: lastTime, value: 80 },
      ]);
    }

    if (dData.length > 0) {
      dLineRef.current.setData(dData);
    }
  }, [bars]);

  return (
    <div className="relative w-full border-t border-dark-700" style={{ height }}>
      <div className="absolute top-2 left-2 z-10 flex items-center space-x-4">
        <span className="text-xs font-semibold text-gray-400">Stochastic (14, 3, 3)</span>
        <div className="flex items-center space-x-2 text-xs">
          <div className="flex items-center space-x-1">
            <div className="w-3 h-0.5 bg-blue-600"></div>
            <span className="text-gray-500">%K</span>
          </div>
          <div className="flex items-center space-x-1">
            <div className="w-3 h-0.5 bg-orange-600"></div>
            <span className="text-gray-500">%D</span>
          </div>
        </div>
      </div>
      <div ref={chartContainerRef} className="w-full h-full" />
    </div>
  );
});

StochasticPanel.displayName = 'StochasticPanel';
