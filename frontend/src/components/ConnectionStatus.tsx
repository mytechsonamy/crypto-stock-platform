/**
 * Connection Status Component
 * Displays WebSocket connection status with visual indicators
 */

import React from 'react';

interface ConnectionStatusProps {
  state: 'connecting' | 'connected' | 'disconnected';
  reconnectAttempts?: number;
}

export const ConnectionStatus: React.FC<ConnectionStatusProps> = ({
  state,
  reconnectAttempts = 0,
}) => {
  const getStatusConfig = () => {
    switch (state) {
      case 'connected':
        return {
          color: 'bg-green-500',
          text: 'Connected',
          textColor: 'text-green-400',
          icon: (
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                clipRule="evenodd"
              />
            </svg>
          ),
        };
      case 'connecting':
        return {
          color: 'bg-yellow-500',
          text: reconnectAttempts > 0 ? `Reconnecting (${reconnectAttempts})` : 'Connecting',
          textColor: 'text-yellow-400',
          icon: (
            <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
          ),
        };
      case 'disconnected':
        return {
          color: 'bg-red-500',
          text: 'Disconnected',
          textColor: 'text-red-400',
          icon: (
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clipRule="evenodd"
              />
            </svg>
          ),
        };
    }
  };

  const config = getStatusConfig();

  return (
    <div className="flex items-center space-x-2">
      {/* Status Indicator */}
      <div className="relative">
        <div className={`w-2 h-2 rounded-full ${config.color}`} />
        {state === 'connected' && (
          <div className={`absolute inset-0 w-2 h-2 rounded-full ${config.color} animate-ping opacity-75`} />
        )}
      </div>

      {/* Status Text */}
      <div className="flex items-center space-x-1">
        <span className={`${config.textColor}`}>{config.icon}</span>
        <span className="text-sm text-gray-400">{config.text}</span>
      </div>
    </div>
  );
};
