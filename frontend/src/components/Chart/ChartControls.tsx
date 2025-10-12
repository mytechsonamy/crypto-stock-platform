/**
 * Chart Controls Component
 * Provides zoom, fit, and other chart control buttons
 */

import React from 'react';
import { useChartStore } from '@/store/chartStore';
import type { Timeframe } from '@/types/chart.types';

const TIMEFRAMES: Timeframe[] = ['1m', '5m', '15m', '1h', '4h', '1d'];

interface ChartControlsProps {
  onZoomIn?: () => void;
  onZoomOut?: () => void;
  onFitContent?: () => void;
}

export const ChartControls: React.FC<ChartControlsProps> = ({
  onZoomIn,
  onZoomOut,
  onFitContent,
}) => {
  const { timeframe, setTimeframe } = useChartStore();

  return (
    <div className="flex items-center justify-between px-4 py-2 bg-dark-900 border-b border-dark-700">
      {/* Timeframe Selector */}
      <div className="flex items-center space-x-2">
        <span className="text-sm text-gray-400">Timeframe:</span>
        <div className="flex space-x-1">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={`px-3 py-1 text-sm font-medium rounded transition-colors ${
                timeframe === tf
                  ? 'bg-primary-600 text-white'
                  : 'bg-dark-800 text-gray-400 hover:bg-dark-700 hover:text-gray-300'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* Chart Controls */}
      <div className="flex items-center space-x-2">
        {/* Zoom In */}
        <button
          onClick={onZoomIn}
          className="p-2 text-gray-400 hover:text-white hover:bg-dark-800 rounded transition-colors"
          title="Zoom In"
        >
          <svg
            className="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v6m3-3H7"
            />
          </svg>
        </button>

        {/* Zoom Out */}
        <button
          onClick={onZoomOut}
          className="p-2 text-gray-400 hover:text-white hover:bg-dark-800 rounded transition-colors"
          title="Zoom Out"
        >
          <svg
            className="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM13 10H7"
            />
          </svg>
        </button>

        {/* Fit Content */}
        <button
          onClick={onFitContent}
          className="p-2 text-gray-400 hover:text-white hover:bg-dark-800 rounded transition-colors"
          title="Fit Content"
        >
          <svg
            className="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"
            />
          </svg>
        </button>

        {/* Separator */}
        <div className="w-px h-6 bg-dark-700"></div>

        {/* Crosshair Toggle */}
        <button
          className="p-2 text-gray-400 hover:text-white hover:bg-dark-800 rounded transition-colors"
          title="Crosshair"
        >
          <svg
            className="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 4v16m8-8H4"
            />
          </svg>
        </button>

        {/* Screenshot */}
        <button
          className="p-2 text-gray-400 hover:text-white hover:bg-dark-800 rounded transition-colors"
          title="Take Screenshot"
        >
          <svg
            className="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"
            />
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"
            />
          </svg>
        </button>
      </div>
    </div>
  );
};
