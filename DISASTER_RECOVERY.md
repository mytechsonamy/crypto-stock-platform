# Disaster Recovery Guide

This document provides step-by-step instructions for recovering the Crypto-Stock Platform from various failure scenarios.

## Table of Contents

1. [Backup Strategy](#backup-strategy)
2. [Full Database Restore](#full-database-restore)
3. [Point-in-Time Recovery](#point-in-time-recovery)
4. [Partial Restore](#partial-restore)
5. [Verification Procedures](#verification-procedures)
6. [Recovery Time Objectives](#recovery-time-objectives)
7. [Monthly Restore Drills](#monthly-restore-drills)
8. [Troubleshooting](#troubleshooting)

## Backup Strategy

### Automated Backups

The platform uses automated daily backups with the following retention policy:

- **Daily backups**: 7 days
- **Weekly backups**: 4 weeks
- **Monthly backups**: 6 months

Backups are stored in:
- **Local**: `./backups/` directory
- **Offsite**: AWS S3 or Google Cloud Storage

### Backup Schedule

- **Time**: 2:00 AM UTC daily
- **Method**: PostgreSQL pg_dump with gzip compression
- **Encryption**: AES-256 server-side encryption (S3)

### What's Backed Up

- All database tables (symbols, candles, indicators, ml_features, alerts, etc.)
- Database schema and indexes
- User data and configurations
- Audit logs

### What's NOT Backed Up

- Redis cache (ephemeral data)
- Application logs (retained separately)
- Docker images (rebuilt from source)
- Configuration files (version controlled)

## Full Database Restore

### Prerequisites

- Access to backup files
- PostgreSQL client tools installed
- Database credentials
- Sufficient disk space

### Step 1: Stop Services

```bash
# Stop all services to prevent data corruption
docker-compose down
```

### Step 2: Locate Backup File

```bash
# List available backups
ls -lh backups/

# Or download from S3
aws s3 ls s3://your-bucket/backups/
aws s3 cp s3://your-bucket/backups/2024/01/15/backup.sql.gz ./
```

### Step 3: Drop Existing Database (if needed)

```bash
# Connect to PostgreSQL
docker-compose up -d timescaledb
docker exec -it crypto-stock-timescaledb psql -U admin -d postgres

# Drop database
DROP DATABASE IF EXISTS crypto_stock;
CREATE DATABASE crypto_stock;
\q
```

### Step 4: Restore Backup

```bash
# Decompress and restore
gunzip -c backups/backup.sql.gz | docker exec -i crypto-stock-timescaledb \
  psql -U admin -d crypto_stock

# Or restore directly from compressed file
docker exec -i crypto-stock-timescaledb \
  sh -c 'gunzip -c | psql -U admin -d crypto_stock' < backups/backup.sql.gz
```

### Step 5: Verify Restore

```bash
# Run verification script
python scripts/verify_backup.py \
  --backup-file backups/backup.sql.gz \
  --host localhost \
  --port 5432 \
  --user admin \
  --password your_password
```

### Step 6: Restart Services

```bash
# Start all services
docker-compose up -d

# Check health
curl http://localhost:8000/health
```

### Expected Recovery Time

- **Small database** (<1GB): 5-10 minutes
- **Medium database** (1-10GB): 15-30 minutes
- **Large database** (>10GB): 30-60 minutes

## Point-in-Time Recovery

Point-in-Time Recovery (PITR) allows restoring the database to a specific moment in time using Write-Ahead Logging (WAL).

### Prerequisites

- WAL archiving enabled
- Continuous archiving configured
- Base backup + WAL files

### Enable WAL Archiving

Add to `postgresql.conf`:

```conf
wal_level = replica
archive_mode = on
archive_command = 'cp %p /var/lib/postgresql/wal_archive/%f'
max_wal_senders = 3
```

### Perform PITR

```bash
# 1. Restore base backup
gunzip -c backups/base_backup.sql.gz | psql -U admin -d crypto_stock

# 2. Create recovery.conf
cat > recovery.conf <<EOF
restore_command = 'cp /var/lib/postgresql/wal_archive/%f %p'
recovery_target_time = '2024-01-15 14:30:00'
recovery_target_action = 'promote'
EOF

# 3. Place recovery.conf in data directory
docker cp recovery.conf crypto-stock-timescaledb:/var/lib/postgresql/data/

# 4. Restart PostgreSQL
docker-compose restart timescaledb

# 5. Verify recovery
docker exec crypto-stock-timescaledb psql -U admin -d crypto_stock -c \
  "SELECT MAX(time) FROM candles;"
```

## Partial Restore

Restore specific tables without affecting others.

### Restore Single Table

```bash
# Extract specific table from backup
gunzip -c backups/backup.sql.gz | \
  grep -A 10000 "CREATE TABLE candles" > candles_backup.sql

# Restore table
docker exec -i crypto-stock-timescaledb \
  psql -U admin -d crypto_stock < candles_backup.sql
```

### Restore Specific Data Range

```bash
# Restore candles for specific date range
docker exec -i crypto-stock-timescaledb psql -U admin -d crypto_stock <<EOF
-- Backup existing data
CREATE TABLE candles_backup AS SELECT * FROM candles 
WHERE time >= '2024-01-01' AND time < '2024-02-01';

-- Delete data in range
DELETE FROM candles 
WHERE time >= '2024-01-01' AND time < '2024-02-01';

-- Restore from backup file (manual import)
\copy candles FROM 'candles_jan2024.csv' CSV HEADER;
EOF
```

## Verification Procedures

### Automated Verification

```bash
# Run verification script
python scripts/verify_backup.py \
  --backup-dir ./backups \
  --host localhost \
  --port 5432 \
  --user admin \
  --password $DB_PASSWORD
```

### Manual Verification Checklist

1. **Table Count**: Verify all tables exist
   ```sql
   SELECT COUNT(*) FROM information_schema.tables 
   WHERE table_schema = 'public';
   ```

2. **Row Counts**: Check row counts match expectations
   ```sql
   SELECT 
     schemaname,
     tablename,
     n_live_tup as row_count
   FROM pg_stat_user_tables
   ORDER BY n_live_tup DESC;
   ```

3. **Data Freshness**: Check latest data timestamp
   ```sql
   SELECT MAX(time) as latest_candle FROM candles;
   SELECT MAX(created_at) as latest_alert FROM alerts;
   ```

4. **Indexes**: Verify indexes exist
   ```sql
   SELECT tablename, indexname 
   FROM pg_indexes 
   WHERE schemaname = 'public'
   ORDER BY tablename;
   ```

5. **Constraints**: Check foreign keys and constraints
   ```sql
   SELECT conname, contype 
   FROM pg_constraint 
   WHERE connamespace = 'public'::regnamespace;
   ```

6. **Application Test**: Run application health check
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/api/v1/symbols
   ```

## Recovery Time Objectives

### RTO (Recovery Time Objective)

Maximum acceptable downtime:

- **Critical**: 1 hour
- **High**: 4 hours
- **Medium**: 24 hours

### RPO (Recovery Point Objective)

Maximum acceptable data loss:

- **With WAL archiving**: 0 minutes (zero data loss)
- **Without WAL archiving**: 24 hours (last daily backup)

### Service Priority

1. **Critical** (restore first):
   - Database
   - Redis
   - API server

2. **High** (restore second):
   - Data collectors
   - WebSocket server

3. **Medium** (restore last):
   - Monitoring
   - Frontend

## Monthly Restore Drills

### Purpose

- Verify backup integrity
- Practice recovery procedures
- Identify potential issues
- Update documentation

### Drill Schedule

- **Frequency**: Monthly (first Sunday)
- **Duration**: 2-3 hours
- **Participants**: DevOps team

### Drill Procedure

```bash
# 1. Run automated restore test
python scripts/restore_test.py \
  --backup-dir ./backups \
  --test-env staging

# 2. Verify data integrity
python scripts/verify_backup.py \
  --host staging-db \
  --port 5432

# 3. Test application functionality
./scripts/integration_test.sh staging

# 4. Document results
# - Restore time
# - Data integrity status
# - Issues encountered
# - Lessons learned

# 5. Cleanup test environment
docker-compose -f docker-compose.staging.yml down -v
```

### Drill Checklist

- [ ] Backup file accessible
- [ ] Restore completed successfully
- [ ] All tables present
- [ ] Row counts match
- [ ] Indexes created
- [ ] Application starts
- [ ] API endpoints respond
- [ ] WebSocket connects
- [ ] Data queries work
- [ ] No errors in logs

## Troubleshooting

### Backup File Corrupted

**Symptoms**: Restore fails with decompression errors

**Solution**:
```bash
# Test backup integrity
gunzip -t backups/backup.sql.gz

# If corrupted, use previous backup
ls -lt backups/ | head -5

# Or download from offsite storage
aws s3 cp s3://bucket/backups/previous_backup.sql.gz ./
```

### Insufficient Disk Space

**Symptoms**: Restore fails with "No space left on device"

**Solution**:
```bash
# Check disk space
df -h

# Clean up old logs
docker system prune -a

# Or restore to external volume
docker run -v /mnt/external:/restore postgres:16 \
  sh -c 'gunzip -c /restore/backup.sql.gz | psql ...'
```

### Restore Takes Too Long

**Symptoms**: Restore exceeds RTO

**Solution**:
```bash
# Use parallel restore (if backup was created with -Fd format)
pg_restore -j 4 -d crypto_stock backup.dump

# Or restore without indexes first, then create them
gunzip -c backup.sql.gz | \
  grep -v "CREATE INDEX" | \
  psql -U admin -d crypto_stock

# Create indexes after data load
psql -U admin -d crypto_stock -f indexes.sql
```

### Connection Refused

**Symptoms**: Cannot connect to database after restore

**Solution**:
```bash
# Check PostgreSQL is running
docker ps | grep timescaledb

# Check logs
docker logs crypto-stock-timescaledb

# Restart if needed
docker-compose restart timescaledb

# Verify port binding
netstat -tlnp | grep 5432
```

### Data Mismatch

**Symptoms**: Row counts don't match expectations

**Solution**:
```bash
# Compare with production
psql -h prod-db -U admin -d crypto_stock -c \
  "SELECT COUNT(*) FROM candles;"

psql -h restored-db -U admin -d crypto_stock -c \
  "SELECT COUNT(*) FROM candles;"

# Check backup date
ls -lh backups/backup.sql.gz

# Verify correct backup was used
gunzip -c backups/backup.sql.gz | head -20
```

## Emergency Contacts

- **DevOps Lead**: [contact info]
- **Database Admin**: [contact info]
- **On-Call Engineer**: [contact info]
- **AWS Support**: [account info]

## Related Documents

- [Backup Configuration](docker-compose.yml)
- [Verification Script](scripts/verify_backup.py)
- [Upload Script](scripts/upload_backup.py)
- [Monitoring Guide](monitoring/README.md)

## Revision History

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2024-01-15 | 1.0 | Initial version | DevOps Team |
