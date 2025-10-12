#!/bin/bash
# Entrypoint script for data processor

set -e

echo "🚀 Starting data processor..."

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

# Start the processor
echo "⚙️  Starting bar builder, indicator calculator, and feature engineering..."
exec python -m processors.main
