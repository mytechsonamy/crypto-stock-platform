# Services

This directory contains service modules for external communication.

## WebSocket Service

The WebSocket service (`websocket.ts`) handles real-time data communication with the backend.

### Features

- **Automatic Reconnection**: Exponential backoff strategy (1s → 30s max)
- **Connection Management**: Connect, disconnect, and state tracking
- **Event Handling**: Message, error, connect, and disconnect events
- **Ping/Pong**: Keep-alive mechanism (30s interval)
- **Type Safety**: Full TypeScript support

### Usage

#### Basic Connection

```typescript
import { websocketService } from '@/services/websocket';

// Connect to a symbol
websocketService.connect('BTCUSDT', 'optional-jwt-token');

// Listen for messages
const unsubscribe = websocketService.onMessage((message) => {
  console.log('Received:', message);
});

// Disconnect
websocketService.disconnect();

// Cleanup
unsubscribe();
```

#### With React Hook

```typescript
import { useWebSocket } from '@/hooks/useWebSocket';

function MyComponent() {
  const { connectionState, reconnectAttempts } = useWebSocket({
    symbol: 'BTCUSDT',
    token: 'optional-jwt-token',
    enabled: true,
    throttleMs: 1000, // Throttle updates to 1 per second
  });

  return (
    <div>
      Status: {connectionState}
      {reconnectAttempts > 0 && ` (Attempt ${reconnectAttempts})`}
    </div>
  );
}
```

### Message Types

#### Initial Data

Sent when connection is established:

```typescript
{
  type: 'initial',
  symbol: 'BTCUSDT',
  bars: [...], // Array of OHLC bars
  indicators: {...} // Indicator values
}
```

#### Real-time Update

Sent for each new bar or update:

```typescript
{
  type: 'update',
  symbol: 'BTCUSDT',
  bar: {...}, // Updated OHLC bar
  indicators: {...} // Updated indicator values
}
```

#### Error

Sent when an error occurs:

```typescript
{
  type: 'error',
  error: 'Error message'
}
```

#### Ping/Pong

Keep-alive messages:

```typescript
// Client sends
{ type: 'ping' }

// Server responds
{ type: 'pong' }
```

### Configuration

Set WebSocket URL in `.env`:

```env
VITE_WS_BASE_URL=ws://localhost:8000
```

### Reconnection Strategy

The service uses exponential backoff for reconnection:

1. Initial delay: 1 second
2. Max delay: 30 seconds
3. Max attempts: 10
4. Formula: `delay * 2^attempts`

Example progression:
- Attempt 1: 1s
- Attempt 2: 2s
- Attempt 3: 4s
- Attempt 4: 8s
- Attempt 5: 16s
- Attempt 6+: 30s (capped)

### Throttling

The `useWebSocket` hook throttles updates to prevent overwhelming the UI:

- Default: 1 update per second
- Configurable via `throttleMs` option
- Batches updates within the throttle window
- Ensures smooth 60 FPS rendering

### Error Handling

Errors are handled at multiple levels:

1. **Connection Errors**: Trigger reconnection
2. **Message Parse Errors**: Logged and notified
3. **Handler Errors**: Caught and logged
4. **Max Reconnect**: Error notification after max attempts

### State Management

Connection states:

- `connecting`: Initial connection or reconnecting
- `connected`: Successfully connected
- `disconnected`: Not connected

Check state:

```typescript
const state = websocketService.getState();
const attempts = websocketService.getReconnectAttempts();
```

### Best Practices

1. **Always Cleanup**: Unsubscribe from events when component unmounts
2. **Use the Hook**: Prefer `useWebSocket` hook over direct service usage
3. **Handle Errors**: Always provide error handlers
4. **Throttle Updates**: Use appropriate throttle values for your use case
5. **Test Reconnection**: Test with network interruptions

### Testing

Mock WebSocket for testing:

```typescript
// Mock WebSocket
class MockWebSocket {
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  readyState = WebSocket.CONNECTING;

  constructor(url: string) {
    setTimeout(() => {
      this.readyState = WebSocket.OPEN;
      this.onopen?.();
    }, 100);
  }

  send(data: string) {
    // Mock send
  }

  close() {
    this.readyState = WebSocket.CLOSED;
    this.onclose?.(new CloseEvent('close'));
  }
}

global.WebSocket = MockWebSocket as any;
```

### Troubleshooting

#### Connection Fails Immediately

- Check WebSocket URL in `.env`
- Verify backend is running
- Check CORS settings
- Check authentication token

#### Frequent Disconnections

- Check network stability
- Verify ping/pong is working
- Check backend timeout settings
- Review server logs

#### Updates Not Appearing

- Check throttle settings
- Verify message handlers are registered
- Check message format matches types
- Review browser console for errors

#### High Memory Usage

- Ensure proper cleanup on unmount
- Check for memory leaks in handlers
- Limit stored data in state
- Use React.memo for expensive components
