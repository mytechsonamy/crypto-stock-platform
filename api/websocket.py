"""
WebSocket Server Implementation.

Features:
- Connection management
- JWT authentication
- Per-symbol subscriptions
- Real-time chart updates
- Update throttling and batching
- Reconnection support
- Prometheus metrics
"""

import asyncio
import json
import time
from typing import Dict, Set, Optional
from collections import defaultdict, deque
from fastapi import WebSocket, WebSocketDisconnect, Query
from loguru import logger

from prometheus_client import Gauge, Counter
from api.auth import auth_manager


class ConnectionManager:
    """
    WebSocket connection manager.
    
    Features:
    - Connection tracking per symbol
    - Authentication
    - Broadcasting
    - Throttling and batching
    - Metrics
    """
    
    # Prometheus metrics
    websocket_connections = Gauge(
        'websocket_connections',
        'Current WebSocket connections',
        ['symbol']
    )
    
    websocket_messages_sent_total = Counter(
        'websocket_messages_sent_total',
        'Total WebSocket messages sent',
        ['symbol']
    )
    
    websocket_errors_total = Counter(
        'websocket_errors_total',
        'Total WebSocket errors',
        ['error_type']
    )
    
    def __init__(self):
        """Initialize connection manager."""
        # Active connections: {symbol: {websocket: user_info}}
        self.active_connections: Dict[str, Dict[WebSocket, Dict]] = defaultdict(dict)
        
        # Message queues for batching: {websocket: deque}
        self.message_queues: Dict[WebSocket, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Last send time for throttling: {websocket: timestamp}
        self.last_send_time: Dict[WebSocket, float] = {}
        
        # Throttle settings
        self.throttle_interval = 1.0  # 1 second
        self.batch_window = 0.1  # 100ms
        
        logger.info("ConnectionManager initialized")
    
    async def connect(
        self,
        websocket: WebSocket,
        symbol: str,
        user: Dict
    ) -> None:
        """
        Accept and register a new WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            symbol: Trading symbol
            user: Authenticated user info
        """
        await websocket.accept()
        
        # Register connection
        self.active_connections[symbol][websocket] = {
            'user_id': user.get('user_id'),
            'username': user.get('username'),
            'connected_at': time.time(),
            'messages_sent': 0
        }
        
        # Initialize throttling
        self.last_send_time[websocket] = 0
        
        # Update metrics
        self.websocket_connections.labels(symbol=symbol).set(
            len(self.active_connections[symbol])
        )
        
        logger.info(
            f"WebSocket connected: {symbol}, "
            f"user={user.get('username')}, "
            f"total={len(self.active_connections[symbol])}"
        )
    
    async def disconnect(self, websocket: WebSocket, symbol: str) -> None:
        """
        Disconnect and clean up a WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            symbol: Trading symbol
        """
        # Remove connection
        if symbol in self.active_connections:
            user_info = self.active_connections[symbol].pop(websocket, None)
            
            # Clean up empty symbol entries
            if not self.active_connections[symbol]:
                del self.active_connections[symbol]
            
            # Clean up throttling data
            self.last_send_time.pop(websocket, None)
            self.message_queues.pop(websocket, None)
            
            # Update metrics
            count = len(self.active_connections.get(symbol, {}))
            self.websocket_connections.labels(symbol=symbol).set(count)
            
            if user_info:
                logger.info(
                    f"WebSocket disconnected: {symbol}, "
                    f"user={user_info.get('username')}, "
                    f"messages_sent={user_info.get('messages_sent')}, "
                    f"remaining={count}"
                )
    
    async def send_personal_message(
        self,
        message: str,
        websocket: WebSocket
    ) -> bool:
        """
        Send message to specific client.
        
        Args:
            message: JSON message string
            websocket: Target WebSocket
            
        Returns:
            True if sent successfully
        """
        try:
            await websocket.send_text(message)
            return True
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.websocket_errors_total.labels(error_type='send_error').inc()
            return False
    
    async def broadcast(
        self,
        symbol: str,
        message: Dict,
        throttle: bool = True
    ) -> int:
        """
        Broadcast message to all clients subscribed to a symbol.
        
        Args:
            symbol: Trading symbol
            message: Message dictionary
            throttle: Whether to apply throttling
            
        Returns:
            Number of clients message was sent to
        """
        if symbol not in self.active_connections:
            return 0
        
        message_json = json.dumps(message)
        sent_count = 0
        current_time = time.time()
        
        # Send to all connected clients for this symbol
        disconnected = []
        
        for websocket, user_info in self.active_connections[symbol].items():
            try:
                if throttle:
                    # Check throttle
                    last_send = self.last_send_time.get(websocket, 0)
                    if current_time - last_send < self.throttle_interval:
                        # Queue message for batching
                        self.message_queues[websocket].append(message)
                        continue
                
                # Send message
                await websocket.send_text(message_json)
                
                # Update tracking
                self.last_send_time[websocket] = current_time
                user_info['messages_sent'] += 1
                sent_count += 1
                
                # Update metrics
                self.websocket_messages_sent_total.labels(symbol=symbol).inc()
                
            except WebSocketDisconnect:
                disconnected.append(websocket)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                self.websocket_errors_total.labels(error_type='broadcast_error').inc()
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            await self.disconnect(websocket, symbol)
        
        return sent_count
    
    async def flush_queued_messages(self, websocket: WebSocket, symbol: str) -> None:
        """
        Flush queued messages for a client (batching).
        
        Args:
            websocket: WebSocket connection
            symbol: Trading symbol
        """
        queue = self.message_queues.get(websocket)
        if not queue:
            return
        
        try:
            # Batch messages
            if len(queue) == 1:
                # Single message
                message = queue.popleft()
                await websocket.send_text(json.dumps(message))
            elif len(queue) > 1:
                # Multiple messages - send as batch
                messages = []
                while queue:
                    messages.append(queue.popleft())
                
                batch = {
                    'type': 'batch',
                    'count': len(messages),
                    'messages': messages
                }
                await websocket.send_text(json.dumps(batch))
            
            # Update metrics
            if messages:
                self.websocket_messages_sent_total.labels(symbol=symbol).inc()
            
        except Exception as e:
            logger.error(f"Error flushing queued messages: {e}")
            self.websocket_errors_total.labels(error_type='flush_error').inc()
    
    async def start_batch_flusher(self) -> None:
        """
        Background task to flush queued messages periodically.
        
        Runs every 100ms to batch messages.
        """
        while True:
            try:
                await asyncio.sleep(self.batch_window)
                
                # Flush all queues
                for symbol, connections in list(self.active_connections.items()):
                    for websocket in list(connections.keys()):
                        await self.flush_queued_messages(websocket, symbol)
                        
            except Exception as e:
                logger.error(f"Error in batch flusher: {e}")
    
    def get_connection_count(self, symbol: Optional[str] = None) -> int:
        """
        Get number of active connections.
        
        Args:
            symbol: Optional symbol to filter by
            
        Returns:
            Connection count
        """
        if symbol:
            return len(self.active_connections.get(symbol, {}))
        else:
            return sum(len(conns) for conns in self.active_connections.values())
    
    def get_stats(self) -> Dict:
        """
        Get connection manager statistics.
        
        Returns:
            Dictionary with statistics
        """
        total_connections = self.get_connection_count()
        
        symbols_stats = {}
        for symbol, connections in self.active_connections.items():
            symbols_stats[symbol] = {
                'connections': len(connections),
                'users': [info.get('username') for info in connections.values()]
            }
        
        return {
            'total_connections': total_connections,
            'symbols': symbols_stats,
            'throttle_interval': self.throttle_interval,
            'batch_window': self.batch_window
        }


# Global connection manager
connection_manager = ConnectionManager()



# ==================== REDIS PUB/SUB LISTENER ====================

async def start_redis_listener(redis_manager):
    """
    Start Redis pub/sub listener for chart updates.
    
    Listens to 'chart_updates' channel and broadcasts to WebSocket clients.
    
    Args:
        redis_manager: Redis manager instance
    """
    logger.info("Starting Redis pub/sub listener...")
    
    async def message_handler(channel: str, message: str):
        """Handle incoming Redis messages."""
        try:
            data = json.loads(message)
            symbol = data.get('symbol')
            
            if symbol:
                # Broadcast to all clients subscribed to this symbol
                sent_count = await connection_manager.broadcast(
                    symbol=symbol,
                    message=data,
                    throttle=True
                )
                
                logger.debug(
                    f"Broadcasted update: {symbol}, clients={sent_count}"
                )
        except Exception as e:
            logger.error(f"Error handling Redis message: {e}")
    
    # Subscribe to chart_updates channel
    try:
        await redis_manager.subscribe(
            channels=['chart_updates', 'completed_bars'],
            handler=message_handler
        )
    except Exception as e:
        logger.error(f"Error in Redis listener: {e}")
