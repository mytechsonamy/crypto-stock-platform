-- Migration 000: Initialize PostgreSQL extensions
-- Description: Enable TimescaleDB and other required extensions

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pg_stat_statements for query performance monitoring
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Comments
COMMENT ON EXTENSION timescaledb IS 'Time-series database extension for PostgreSQL';
COMMENT ON EXTENSION "uuid-ossp" IS 'UUID generation functions';
COMMENT ON EXTENSION pg_stat_statements IS 'Track execution statistics of SQL statements';
