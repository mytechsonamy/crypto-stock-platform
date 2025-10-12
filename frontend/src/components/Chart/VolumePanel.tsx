/**
 * Volume Panel Component
 * Displays volume as histogram with green/red coloring
 */

import React, { useEffect, useRef, memo } from 'react';
import { createChart, IChartApi, ISeriesApi, HistogramData } from 'lightweight-charts';
import { useChartStore } from '@/store/chartStore';

interface VolumePanelProps {
  height?: number;
}

export const VolumePanel = memo<VolumePanelProps>(({ height = 150 }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);

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
          bottom: 0,
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

    // Create volume series
    const volumeSeries = chart.addHistogramSeries({
      color: '#26a69a',
      priceFormat: {
        type: 'volume',
      },
      priceScaleId: '',
    });

    volumeSeriesRef.current = volumeSeries;

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

  // Update volume data
  useEffect(() => {
    if (!volumeSeriesRef.current || bars.length === 0) return;

    const volumeData: HistogramData[] = bars.map((bar, index) => {
      // Determine color based on price movement
      const isUp = index === 0 || bar.close >= bar.open;
      
      return {
        time: bar.time as any,
        value: bar.volume,
        color: isUp ? '#10b981' : '#ef4444',
      };
    });

    volumeSeriesRef.current.setData(volumeData);
  }, [bars]);

  return (
    <div className="relative w-full border-t border-dark-700" style={{ height }}>
      <div className="absolute top-2 left-2 z-10">
        <span className="text-xs font-semibold text-gray-400">Volume</span>
      </div>
      <div ref={chartContainerRef} className="w-full h-full" />
    </div>
  );
});

VolumePanel.displayName = 'VolumePanel';
