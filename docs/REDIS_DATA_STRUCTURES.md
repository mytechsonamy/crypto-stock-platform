# Redis Data Structures Documentation

This document describes all Redis data structures used in the Crypto-Stock Platform.

## Overview

Redis is used for:
1. **Caching** - Hot data (last 1000 bars per symbol)
2. **Pub/Sub** - Real-time event messaging
3. **Health Tracking** - Collector and system health status
4. **Rate Limiting** - Token bucket implementation
5. **Session Management** - WebSocket connections

---

## Data Structures

### 1. Chart Data Cache

**Purpose:** Cache last 1000 bars per symbol for fast access

**Key Pattern:** `chart:{symbol}`

**Type:** Sorted Set (ZSET)

**Score:** Timestamp (milliseconds)

**Value:** JSON-encoded bar data

**Example:**
```redis
ZADD chart:BTCUSDT 1704067200000 '{"time":1704067200000,"open":42000,"high":42100,"low":41900,"close":42050,"volume":1234.56}'
```

**Operations:**
```python
# Add bar
await redis.zadd(f"chart:{symbol}", {json.dumps(bar): bar['time']})

# Get last N bars
bars = await redis.zrange(f"chart:{symbol}", -1000, -1)

# Remove old bars (keep last 1000)
await redis.zremrangebyrank(f"chart:{symbol}", 0, -1001)
```

**TTL:** 1 hour

---

### 2. Indicators Cache

**Purpose:** Cache calculated indicators for fast API responses

**Key Pattern:** `indicators:{symbol}`

**Type:** Hash

**Fields:** Indicator names (rsi_14, macd, bb_upper, etc.)

**Example:**
```redis
HSET indicators:BTCUSDT rsi_14 65.5 macd 120.5 macd_signal 115.2
```

**Operations:**
```python
# Store indicators
await redis.hset(f"indicators:{symbol}", mapping=indicators)

# Get all indicators
indicators = await redis.hgetall(f"indicators:{symbol}")

# Get specific indicator
rsi = await redis.hget(f"indicators:{symbol}", "rsi_14")
```

**TTL:** 5 minutes

---

### 3. ML Features Cache

**Purpose:** Cache latest ML features for real-time inference

**Key Pattern:** `features:{symbol}:latest`

**Type:** Hash

**Fields:** Feature names

**Example:**
```redis
HSET features:BTCUSDT:latest returns_1 0.0025 rolling_std_5 0.015 rsi_zone "neutral"
```

**TTL:** 5 minutes

---

### 4. Pub/Sub Channels

#### 4.1 Trade Events

**Channel:** `trades:{exchange}`

**Purpose:** Raw trade events from collectors

**Message Format:**
```json
{
  "exchange": "binance",
  "symbol": "BTCUSDT",
  "price": 42000.50,
  "quantity": 1.5,
  "timestamp": 1704067200000,
  "is_buyer_maker": false
}
```

**Publishers:** Collectors (binance, yahoo)

**Subscribers:** Bar Builder

---

#### 4.2 Completed Bars

**Channel:** `completed_bars`

**Purpose:** Notify when a bar is completed

**Message Format:**
```json
{
  "symbol": "BTCUSDT",
  "time": 1704067200000,
  "timeframe": "1m",
  "open": 42000,
  "high": 42100,
  "low": 41900,
  "close": 42050,
  "volume": 1234.56,
  "completed": true
}
```

**Publishers:** Bar Builder

**Subscribers:** Indicator Calculator

---

#### 4.3 Chart Updates

**Channel:** `chart_updates`

**Purpose:** Push updates to WebSocket clients

**Message Format:**
```json
{
  "symbol": "BTCUSDT",
  "time": 1704067200000,
  "bar": { ... },
  "indicators": { ... }
}
```

**Publishers:** Indicator Calculator

**Subscribers:** WebSocket Handler

---

#### 4.4 Alerts

**Channel:** `alerts:{user_id}`

**Purpose:** User-specific alert notifications

**Message Format:**
```json
{
  "alert_id": 123,
  "symbol": "BTCUSDT",
  "condition": "PRICE_ABOVE",
  "threshold": 45000,
  "current_value": 45100,
  "timestamp": 1704067200000
}
```

---

### 5. System Health

**Purpose:** Track collector and component health

**Key Pattern:** `system:health`

**Type:** Hash

**Fields:** Component names

**Value:** JSON-encoded health status

**Example:**
```redis
HSET system:health binance_collector '{"status":"running","last_update":1704067200,"trades_received":1234}'
```

**Operations:**
```python
# Update health
await redis.hset("system:health", collector_name, json.dumps(health_data))

# Get all health statuses
health = await redis.hgetall("system:health")

# Check if collector is healthy
status = await redis.hget("system:health", "binance_collector")
```

**TTL:** None (persistent)

---

### 6. Rate Limiting

**Purpose:** Token bucket rate limiting per client

**Key Pattern:** `ratelimit:{client_id}`

**Type:** Hash

**Fields:**
- `tokens` - Available tokens
- `last_refill` - Last refill timestamp

**Example:**
```redis
HSET ratelimit:192.168.1.100 tokens 95 last_refill 1704067200
```

**Operations:**
```python
# Check and consume token
tokens = await redis.hget(f"ratelimit:{client_id}", "tokens")
if int(tokens) > 0:
    await redis.hincrby(f"ratelimit:{client_id}", "tokens", -1)
```

**TTL:** 60 seconds (auto-refill)

---

### 7. WebSocket Sessions

**Purpose:** Track active WebSocket connections

**Key Pattern:** `ws:connections:{symbol}`

**Type:** Set

**Members:** Connection IDs

**Example:**
```redis
SADD ws:connections:BTCUSDT conn_abc123 conn_def456
```

**Operations:**
```python
# Add connection
await redis.sadd(f"ws:connections:{symbol}", connection_id)

# Remove connection
await redis.srem(f"ws:connections:{symbol}", connection_id)

# Get all connections for symbol
connections = await redis.smembers(f"ws:connections:{symbol}")

# Count connections
count = await redis.scard(f"ws:connections:{symbol}")
```

**TTL:** None (managed by application)

---

### 8. Current Bars (In-Progress)

**Purpose:** Store current incomplete bars

**Key Pattern:** `current_bar:{symbol}:{timeframe}`

**Type:** Hash

**Fields:** OHLC fields

**Example:**
```redis
HSET current_bar:BTCUSDT:1m open 42000 high 42100 low 41900 close 42050 volume 1234.56
```

**TTL:** 2 minutes

---

### 9. Historical Data Temp Storage

**Purpose:** Temporary storage during backfill

**Key Pattern:** `historical:{symbol}:{timeframe}`

**Type:** List

**Example:**
```redis
RPUSH historical:BTCUSDT:1m '{"time":1704067200000,"open":42000,...}'
```

**TTL:** 1 hour

---

## Memory Management

### Eviction Policy

**Policy:** `allkeys-lru`

**Max Memory:** 2GB

**Behavior:** Evict least recently used keys when memory limit is reached

### Key Priorities

1. **High Priority** (should not be evicted):
   - `system:health`
   - `ws:connections:*`

2. **Medium Priority**:
   - `chart:*` (last 1000 bars)
   - `indicators:*`
   - `features:*`

3. **Low Priority** (can be evicted):
   - `historical:*`
   - `current_bar:*`

---

## Monitoring

### Key Metrics

```redis
# Memory usage
INFO memory

# Key count
DBSIZE

# Hit rate
INFO stats | grep keyspace

# Slow queries
SLOWLOG GET 10

# Connected clients
CLIENT LIST
```

### Health Checks

```python
# Ping
await redis.ping()

# Check memory
info = await redis.info("memory")
used_memory = info["used_memory_human"]

# Check connections
clients = await redis.client_list()
```

---

## Best Practices

1. **Use Pipelines** for bulk operations
2. **Set TTLs** on all cache keys
3. **Use SCAN** instead of KEYS for production
4. **Monitor Memory** usage regularly
5. **Use Lua Scripts** for atomic operations
6. **Compress Large Values** before storing
7. **Use Connection Pooling**
8. **Handle Reconnections** gracefully

---

## Example Usage

### Python (redis-py)

```python
import redis.asyncio as redis
import json

# Connect
r = await redis.from_url("redis://localhost:6379")

# Cache bars
await r.zadd(f"chart:{symbol}", {json.dumps(bar): bar['time']})

# Publish event
await r.publish("completed_bars", json.dumps(bar))

# Subscribe to channel
pubsub = r.pubsub()
await pubsub.subscribe("chart_updates")

async for message in pubsub.listen():
    if message['type'] == 'message':
        data = json.loads(message['data'])
        # Process update
```

---

## Troubleshooting

### High Memory Usage

```redis
# Find large keys
redis-cli --bigkeys

# Check memory by key pattern
MEMORY USAGE chart:BTCUSDT
```

### Slow Performance

```redis
# Check slow log
SLOWLOG GET 10

# Monitor commands
MONITOR
```

### Connection Issues

```redis
# Check max clients
CONFIG GET maxclients

# Check connected clients
CLIENT LIST
```
