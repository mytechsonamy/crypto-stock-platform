#!/bin/bash
# Entrypoint script for data collectors

set -e

echo "🚀 Starting ${COLLECTOR_TYPE} collector..."

# Wait for dependencies
echo "⏳ Waiting for TimescaleDB..."
while ! nc -z ${DB_HOST:-timescaledb} ${DB_PORT:-5432}; do
    sleep 1
done
echo "✅ TimescaleDB is ready"

echo "⏳ Waiting for Redis..."
while ! nc -z ${REDIS_HOST:-redis} ${REDIS_PORT:-6379}; do
    sleep 1
done
echo "✅ Redis is ready"

# Start the collector based on type
case ${COLLECTOR_TYPE} in
    binance)
        echo "📊 Starting Binance collector..."
        exec python -m collectors.binance_collector
        ;;
    alpaca)
        echo "📊 Starting Alpaca collector..."
        exec python -m collectors.alpaca_collector
        ;;
    yahoo)
        echo "📊 Starting Yahoo Finance collector..."
        exec python -m collectors.yahoo_collector
        ;;
    *)
        echo "❌ Unknown collector type: ${COLLECTOR_TYPE}"
        exit 1
        ;;
esac
