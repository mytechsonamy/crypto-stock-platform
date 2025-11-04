/**
 * useWebSocket Hook
 * Manages WebSocket connection and provides real-time data
 */

import { useEffect, useRef, useCallback } from 'react';
import { useChartStore } from '@/store/chartStore';
import { websocketService } from '@/services/websocket';
import type { WSMessage, WSInitialMessage, WSUpdateMessage } from '@/types/chart.types';

interface UseWebSocketOptions {
  symbol: string;
  token?: string;
  enabled?: boolean;
  throttleMs?: number;
}

export const useWebSocket = ({
  symbol,
  token,
  enabled = true,
  throttleMs = 1000,
}: UseWebSocketOptions) => {
  const {
    setBars,
    updateBar,
    setIndicators,
    setLoading,
    setError,
    setConnected,
  } = useChartStore();

  const lastUpdateRef = useRef<number>(0);
  const pendingUpdateRef = useRef<any>(null);
  const throttleTimerRef = useRef<NodeJS.Timeout | null>(null);

  /**
   * Handle incoming WebSocket messages
   */
  const handleMessage = useCallback((message: WSMessage) => {
    try {
      switch (message.type) {
        case 'initial': {
          const initialMsg = message as WSInitialMessage;
          console.log('Received initial data:', initialMsg.bars?.length, 'bars');

          if (initialMsg.bars && initialMsg.bars.length > 0) {
            // Convert timestamps from ISO string to Unix timestamp
            const convertedBars = initialMsg.bars.map((bar: any) => ({
              ...bar,
              time: typeof bar.time === 'string'
                ? new Date(bar.time).getTime() / 1000
                : bar.time
            }));
            setBars(convertedBars);
            setLoading(false);
            setError(null);
          }
          break;
        }

        case 'update': {
          const updateMsg = message as WSUpdateMessage;
          
          // Throttle updates
          const now = Date.now();
          const timeSinceLastUpdate = now - lastUpdateRef.current;

          if (timeSinceLastUpdate >= throttleMs) {
            // Update immediately
            if (updateMsg.bar) {
              // Convert timestamp if it's a string
              const convertedBar = {
                ...updateMsg.bar,
                time: typeof updateMsg.bar.time === 'string'
                  ? new Date(updateMsg.bar.time).getTime() / 1000
                  : updateMsg.bar.time
              };
              updateBar(convertedBar);
            }
            if (updateMsg.indicators) {
              setIndicators(updateMsg.indicators);
            }
            lastUpdateRef.current = now;
          } else {
            // Store pending update
            pendingUpdateRef.current = updateMsg;

            // Schedule update if not already scheduled
            if (!throttleTimerRef.current) {
              const delay = throttleMs - timeSinceLastUpdate;
              throttleTimerRef.current = setTimeout(() => {
                if (pendingUpdateRef.current) {
                  const pending = pendingUpdateRef.current;
                  if (pending.bar) {
                    // Convert timestamp if it's a string
                    const convertedBar = {
                      ...pending.bar,
                      time: typeof pending.bar.time === 'string'
                        ? new Date(pending.bar.time).getTime() / 1000
                        : pending.bar.time
                    };
                    updateBar(convertedBar);
                  }
                  if (pending.indicators) {
                    setIndicators(pending.indicators);
                  }
                  pendingUpdateRef.current = null;
                  lastUpdateRef.current = Date.now();
                }
                throttleTimerRef.current = null;
              }, delay);
            }
          }
          break;
        }

        case 'error': {
          const errorMsg = message as any;
          console.error('WebSocket error message:', errorMsg.error);
          setError(errorMsg.error || 'Unknown error');
          setLoading(false);
          break;
        }

        default:
          console.warn('Unknown message type:', message.type);
      }
    } catch (error) {
      console.error('Error handling WebSocket message:', error);
      setError('Failed to process message');
    }
  }, [setBars, updateBar, setIndicators, setLoading, setError, throttleMs]);

  /**
   * Handle connection
   */
  const handleConnect = useCallback(() => {
    console.log('WebSocket connected');
    setConnected(true);
    setError(null);
  }, [setConnected, setError]);

  /**
   * Handle disconnection
   */
  const handleDisconnect = useCallback(() => {
    console.log('WebSocket disconnected');
    setConnected(false);
  }, [setConnected]);

  /**
   * Handle errors
   */
  const handleError = useCallback((error: Error) => {
    console.error('WebSocket error:', error);
    setError(error.message);
    setConnected(false);
  }, [setError, setConnected]);

  /**
   * Connect to WebSocket
   */
  useEffect(() => {
    if (!enabled || !symbol) return;

    console.log(`Connecting to WebSocket for symbol: ${symbol}`);
    setLoading(true);
    setError(null);

    // Register event handlers
    const unsubscribeMessage = websocketService.onMessage(handleMessage);
    const unsubscribeConnect = websocketService.onConnect(handleConnect);
    const unsubscribeDisconnect = websocketService.onDisconnect(handleDisconnect);
    const unsubscribeError = websocketService.onError(handleError);

    // Connect
    websocketService.connect(symbol, token);

    // Cleanup
    return () => {
      console.log('Cleaning up WebSocket connection');
      
      // Clear throttle timer
      if (throttleTimerRef.current) {
        clearTimeout(throttleTimerRef.current);
        throttleTimerRef.current = null;
      }

      // Unsubscribe from events
      unsubscribeMessage();
      unsubscribeConnect();
      unsubscribeDisconnect();
      unsubscribeError();

      // Disconnect
      websocketService.disconnect();
    };
  }, [
    enabled,
    symbol,
    token,
    handleMessage,
    handleConnect,
    handleDisconnect,
    handleError,
    setLoading,
    setError,
  ]);

  return {
    connectionState: websocketService.getState(),
    reconnectAttempts: websocketService.getReconnectAttempts(),
  };
};
