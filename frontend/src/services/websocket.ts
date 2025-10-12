/**
 * WebSocket Service
 * Handles WebSocket connection and message handling
 */

import type { WSMessage, WSInitialMessage, WSUpdateMessage, WSErrorMessage } from '@/types/chart.types';

type MessageHandler = (message: WSMessage) => void;
type ErrorHandler = (error: Error) => void;
type ConnectionHandler = () => void;

export class WebSocketService {
  private ws: WebSocket | null = null;
  private url: string;
  private symbol: string | null = null;
  private token: string | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 1000; // Start with 1 second
  private maxReconnectDelay = 30000; // Max 30 seconds
  private reconnectTimer: NodeJS.Timeout | null = null;
  private pingInterval: NodeJS.Timeout | null = null;
  private isIntentionallyClosed = false;

  // Event handlers
  private messageHandlers: Set<MessageHandler> = new Set();
  private errorHandlers: Set<ErrorHandler> = new Set();
  private connectHandlers: Set<ConnectionHandler> = new Set();
  private disconnectHandlers: Set<ConnectionHandler> = new Set();

  constructor(baseUrl?: string) {
    this.url = baseUrl || import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000';
  }

  /**
   * Connect to WebSocket server
   */
  connect(symbol: string, token?: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected');
      return;
    }

    this.symbol = symbol;
    this.token = token || null;
    this.isIntentionallyClosed = false;

    try {
      // Build WebSocket URL
      const wsUrl = `${this.url}/ws/${symbol}${token ? `?token=${token}` : ''}`;
      
      console.log(`Connecting to WebSocket: ${wsUrl}`);
      this.ws = new WebSocket(wsUrl);

      // Set up event listeners
      this.ws.onopen = this.handleOpen.bind(this);
      this.ws.onmessage = this.handleMessage.bind(this);
      this.ws.onerror = this.handleError.bind(this);
      this.ws.onclose = this.handleClose.bind(this);
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      this.notifyError(error as Error);
      this.scheduleReconnect();
    }
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    this.isIntentionallyClosed = true;
    this.clearReconnectTimer();
    this.clearPingInterval();

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
  }

  /**
   * Close connection (alias for disconnect)
   */
  close(): void {
    this.disconnect();
  }

  /**
   * Send a message to the server
   */
  send(data: any): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      console.warn('WebSocket is not connected');
    }
  }

  /**
   * Handle WebSocket open event
   */
  private handleOpen(): void {
    console.log('WebSocket connected');
    this.reconnectAttempts = 0;
    this.reconnectDelay = 1000;
    
    // Start ping interval to keep connection alive
    this.startPingInterval();
    
    // Notify connect handlers
    this.connectHandlers.forEach(handler => handler());
  }

  /**
   * Handle incoming WebSocket messages
   */
  private handleMessage(event: MessageEvent): void {
    try {
      const message: WSMessage = JSON.parse(event.data);
      
      // Handle pong response
      if (message.type === 'pong') {
        return;
      }

      // Notify message handlers
      this.messageHandlers.forEach(handler => handler(message));
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
      this.notifyError(new Error('Failed to parse message'));
    }
  }

  /**
   * Handle WebSocket error event
   */
  private handleError(event: Event): void {
    console.error('WebSocket error:', event);
    this.notifyError(new Error('WebSocket error'));
  }

  /**
   * Handle WebSocket close event
   */
  private handleClose(event: CloseEvent): void {
    console.log(`WebSocket closed: ${event.code} - ${event.reason}`);
    
    this.clearPingInterval();
    
    // Notify disconnect handlers
    this.disconnectHandlers.forEach(handler => handler());

    // Attempt to reconnect if not intentionally closed
    if (!this.isIntentionallyClosed && event.code !== 1000) {
      this.scheduleReconnect();
    }
  }

  /**
   * Schedule reconnection with exponential backoff
   */
  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      this.notifyError(new Error('Max reconnection attempts reached'));
      return;
    }

    this.clearReconnectTimer();

    const delay = Math.min(
      this.reconnectDelay * Math.pow(2, this.reconnectAttempts),
      this.maxReconnectDelay
    );

    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})`);

    this.reconnectTimer = setTimeout(() => {
      this.reconnectAttempts++;
      if (this.symbol) {
        this.connect(this.symbol, this.token || undefined);
      }
    }, delay);
  }

  /**
   * Clear reconnect timer
   */
  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  /**
   * Start ping interval to keep connection alive
   */
  private startPingInterval(): void {
    this.clearPingInterval();
    
    this.pingInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.send({ type: 'ping' });
      }
    }, 30000); // Ping every 30 seconds
  }

  /**
   * Clear ping interval
   */
  private clearPingInterval(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  /**
   * Notify error handlers
   */
  private notifyError(error: Error): void {
    this.errorHandlers.forEach(handler => handler(error));
  }

  /**
   * Register message handler
   */
  onMessage(handler: MessageHandler): () => void {
    this.messageHandlers.add(handler);
    return () => this.messageHandlers.delete(handler);
  }

  /**
   * Register error handler
   */
  onError(handler: ErrorHandler): () => void {
    this.errorHandlers.add(handler);
    return () => this.errorHandlers.delete(handler);
  }

  /**
   * Register connect handler
   */
  onConnect(handler: ConnectionHandler): () => void {
    this.connectHandlers.add(handler);
    return () => this.connectHandlers.delete(handler);
  }

  /**
   * Register disconnect handler
   */
  onDisconnect(handler: ConnectionHandler): () => void {
    this.disconnectHandlers.add(handler);
    return () => this.disconnectHandlers.delete(handler);
  }

  /**
   * Get connection state
   */
  getState(): 'connecting' | 'connected' | 'disconnected' {
    if (!this.ws) return 'disconnected';
    
    switch (this.ws.readyState) {
      case WebSocket.CONNECTING:
        return 'connecting';
      case WebSocket.OPEN:
        return 'connected';
      default:
        return 'disconnected';
    }
  }

  /**
   * Get reconnect attempts
   */
  getReconnectAttempts(): number {
    return this.reconnectAttempts;
  }
}

// Export singleton instance
export const websocketService = new WebSocketService();
