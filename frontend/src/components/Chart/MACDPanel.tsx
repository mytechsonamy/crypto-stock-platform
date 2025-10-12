/**
 * MACD Panel Component
 * Displays MACD line, signal line, and histogram
 */

import React, { useEffect, useRef, memo } from 'react';
import { createChart, IChartApi, ISeriesApi, LineData, HistogramData } from 'lightweight-charts';
import { useChartStore } from '@/store/chartStore';

interface MACDPanelProps {
  height?: number;
}

export const MACDPanel = memo<MACDPanelProps>(({ height = 150 }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const macdLineRef = useRef<ISeriesApi<'Line'> | null>(null);
  const signalLineRef = useRef<ISeriesApi<'Line'> | null>(null);
  const histogramRef = useRef<ISeriesApi<'Histogram'> | null>(null);

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

    // Create histogram series (must be added first for proper layering)
    const histogram = chart.addHistogramSeries({
      color: '#26a69a',
      priceFormat: {
        type: 'price',
        precision: 4,
        minMove: 0.0001,
      },
      priceScaleId: '',
    });

    histogramRef.current = histogram;

    // Create MACD line series
    const macdLine = chart.addLineSeries({
      color: '#2962FF',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
    });

    macdLineRef.current = macdLine;

    // Create signal line series
    const signalLine = chart.addLineSeries({
      color: '#FF6D00',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
    });

    signalLineRef.current = signalLine;

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

  // Update MACD data
  useEffect(() => {
    if (!macdLineRef.current || !signalLineRef.current || !histogramRef.current || bars.length === 0) return;

    // MACD line data
    const macdData: LineData[] = bars
      .map((bar) => {
        const macd = (bar as any).macd;
        return macd !== undefined && macd !== null
          ? { time: bar.time as any, value: macd }
          : null;
      })
      .filter((d): d is LineData => d !== null);

    // Signal line data
    const signalData: LineData[] = bars
      .map((bar) => {
        const signal = (bar as any).macd_signal;
        return signal !== undefined && signal !== null
          ? { time: bar.time as any, value: signal }
          : null;
      })
      .filter((d): d is LineData => d !== null);

    // Histogram data
    const histogramData: HistogramData[] = bars
      .map((bar) => {
        const histogram = (bar as any).macd_histogram;
        if (histogram === undefined || histogram === null) return null;

        return {
          time: bar.time as any,
          value: histogram,
          color: histogram >= 0 ? '#10b981' : '#ef4444',
        };
      })
      .filter((d): d is HistogramData => d !== null);

    if (macdData.length > 0) {
      macdLineRef.current.setData(macdData);
    }

    if (signalData.length > 0) {
      signalLineRef.current.setData(signalData);
    }

    if (histogramData.length > 0) {
      histogramRef.current.setData(histogramData);
    }
  }, [bars]);

  return (
    <div className="relative w-full border-t border-dark-700" style={{ height }}>
      <div className="absolute top-2 left-2 z-10 flex items-center space-x-4">
        <span className="text-xs font-semibold text-gray-400">MACD (12, 26, 9)</span>
        <div className="flex items-center space-x-2 text-xs">
          <div className="flex items-center space-x-1">
            <div className="w-3 h-0.5 bg-blue-600"></div>
            <span className="text-gray-500">MACD</span>
          </div>
          <div className="flex items-center space-x-1">
            <div className="w-3 h-0.5 bg-orange-600"></div>
            <span className="text-gray-500">Signal</span>
          </div>
        </div>
      </div>
      <div ref={chartContainerRef} className="w-full h-full" />
    </div>
  );
});

MACDPanel.displayName = 'MACDPanel';
