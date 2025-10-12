/**
 * Indicator Panel Component
 * Provides checkboxes to toggle chart indicators
 */

import React from 'react';
import { useChartStore } from '@/store/chartStore';

export const IndicatorPanel: React.FC = () => {
  const { indicators, toggleIndicator } = useChartStore();

  const overlayIndicators = [
    { key: 'sma20', label: 'SMA 20', color: 'text-blue-400' },
    { key: 'sma50', label: 'SMA 50', color: 'text-green-400' },
    { key: 'sma100', label: 'SMA 100', color: 'text-yellow-400' },
    { key: 'sma200', label: 'SMA 200', color: 'text-red-400' },
    { key: 'ema12', label: 'EMA 12', color: 'text-purple-400' },
    { key: 'ema26', label: 'EMA 26', color: 'text-pink-400' },
    { key: 'ema50', label: 'EMA 50', color: 'text-indigo-400' },
    { key: 'bollingerBands', label: 'Bollinger Bands', color: 'text-gray-400' },
    { key: 'vwap', label: 'VWAP', color: 'text-orange-400' },
  ];

  const panelIndicators = [
    { key: 'volume', label: 'Volume', icon: '📊' },
    { key: 'rsi', label: 'RSI', icon: '📈' },
    { key: 'macd', label: 'MACD', icon: '📉' },
    { key: 'stochastic', label: 'Stochastic', icon: '🔄' },
  ];

  return (
    <div className="space-y-6">
      {/* Overlay Indicators */}
      <div>
        <h3 className="text-sm font-semibold text-gray-400 mb-3 flex items-center">
          <svg
            className="w-4 h-4 mr-2"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"
            />
          </svg>
          Overlay Indicators
        </h3>
        <div className="space-y-2">
          {overlayIndicators.map((indicator) => (
            <label
              key={indicator.key}
              className="flex items-center space-x-2 cursor-pointer group"
            >
              <input
                type="checkbox"
                checked={indicators[indicator.key as keyof typeof indicators]}
                onChange={() => toggleIndicator(indicator.key as any)}
                className="w-4 h-4 rounded border-gray-600 bg-dark-800 text-primary-600 focus:ring-primary-500 focus:ring-offset-0 cursor-pointer"
              />
              <span className={`text-sm ${indicator.color} group-hover:brightness-125 transition-all`}>
                {indicator.label}
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* Panel Indicators */}
      <div>
        <h3 className="text-sm font-semibold text-gray-400 mb-3 flex items-center">
          <svg
            className="w-4 h-4 mr-2"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z"
            />
          </svg>
          Sub-Panel Indicators
        </h3>
        <div className="space-y-2">
          {panelIndicators.map((indicator) => (
            <label
              key={indicator.key}
              className="flex items-center space-x-2 cursor-pointer group"
            >
              <input
                type="checkbox"
                checked={indicators[indicator.key as keyof typeof indicators]}
                onChange={() => toggleIndicator(indicator.key as any)}
                className="w-4 h-4 rounded border-gray-600 bg-dark-800 text-primary-600 focus:ring-primary-500 focus:ring-offset-0 cursor-pointer"
              />
              <span className="text-sm text-gray-300 group-hover:text-white transition-colors flex items-center">
                <span className="mr-2">{indicator.icon}</span>
                {indicator.label}
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="pt-4 border-t border-dark-700">
        <div className="flex space-x-2">
          <button
            onClick={() => {
              // Enable all indicators
              Object.keys(indicators).forEach((key) => {
                if (!indicators[key as keyof typeof indicators]) {
                  toggleIndicator(key as any);
                }
              });
            }}
            className="flex-1 px-3 py-2 text-xs bg-dark-800 hover:bg-dark-700 text-gray-300 rounded transition-colors"
          >
            Enable All
          </button>
          <button
            onClick={() => {
              // Disable all indicators
              Object.keys(indicators).forEach((key) => {
                if (indicators[key as keyof typeof indicators]) {
                  toggleIndicator(key as any);
                }
              });
            }}
            className="flex-1 px-3 py-2 text-xs bg-dark-800 hover:bg-dark-700 text-gray-300 rounded transition-colors"
          >
            Disable All
          </button>
        </div>
      </div>
    </div>
  );
};
