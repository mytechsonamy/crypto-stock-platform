/**
 * Header component with symbol selector and status indicators
 */

import React from 'react';
import { useChartStore } from '@/store/chartStore';
import { ConnectionStatus } from '@/components/ConnectionStatus';
import { websocketService } from '@/services/websocket';

export const Header: React.FC = () => {
  const { symbol, error } = useChartStore();
  const connectionState = websocketService.getState();
  const reconnectAttempts = websocketService.getReconnectAttempts();

  return (
    <header className="bg-dark-900 border-b border-dark-700 px-6 py-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <h1 className="text-2xl font-bold text-primary-400">
            Crypto-Stock Platform
          </h1>
          <div className="flex items-center space-x-2">
            <span className="text-gray-400">Symbol:</span>
            <span className="text-xl font-semibold text-white">{symbol}</span>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          {/* Connection Status */}
          <ConnectionStatus
            state={connectionState}
            reconnectAttempts={reconnectAttempts}
          />

          {/* Error Indicator */}
          {error && (
            <div className="flex items-center space-x-2 text-red-400">
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
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <span className="text-sm">{error}</span>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
