# Data Processors

This directory contains data processing components for the Crypto-Stock Platform.

## Components

### 1. DataQualityChecker

Validates incoming trade data for quality issues before processing.

**Features:**
- Real-time anomaly detection
- Data freshness validation
- Value sanity checks
- Quality scoring per symbol
- Quarantine for suspect data
- Database storage for metrics
- Prometheus metrics

**Usage:**

```python
from processors.data_quality import DataQualityChecker
import yaml

# Load configuration
with open('config/exchanges.yaml') as f:
    config = yaml.safe_load(f)

# Initialize checker
quality_checker = DataQualityChecker(
    config=config['data_quality'],
    db_manager=db_manager,  # Optional
    enable_quarantine=True
)

# Validate trade data
trade_data = {
    'exchange': 'binance',
    'symbol': 'BTC/USDT',
    'price': 45000.0,
    'quantity': 0.5,
    'timestamp': 1697000000000
}

is_valid, error_msg = quality_checker.validate_trade(trade_data)

if is_valid:
    # Process trade
    await process_trade(trade_data)
else:
    # Handle invalid data
    logger.warning(f"Invalid trade: {error_msg}")
```

## Integration with Pipeline

### Bar Builder Integration

```python
from processors.data_quality import DataQualityChecker
from processors.bar_builder import BarBuilder

# Initialize components
quality_checker = DataQualityChecker(config['data_quality'])
bar_builder = BarBuilder(config['bars'])

# Process incoming trade
async def process_trade(trade_data: Dict):
    # Step 1: Validate quality
    is_valid, error_msg = quality_checker.validate_trade(trade_data)
    
    if not is_valid:
        logger.warning(f"Quality check failed: {error_msg}")
        return
    
    # Step 2: Build bars
    await bar_builder.process_trade(trade_data)
```

### Collector Integration

```python
from collectors.binance_collector import BinanceCollector
from processors.data_quality import DataQualityChecker

class BinanceCollectorWithQuality(BinanceCollector):
    def __init__(self, config, redis_client, symbol_manager, quality_checker):
        super().__init__(config, redis_client, symbol_manager)
        self.quality_checker = quality_checker
    
    async def handle_message(self, message: Dict):
        # Parse trade data
        trade_data = self._parse_trade(message)
        
        # Validate quality
        is_valid, error_msg = self.quality_checker.validate_trade(trade_data)
        
        if is_valid:
            # Publish valid trade
            await self.publish_trade(trade_data)
        else:
            # Log and skip invalid trade
            logger.warning(f"Invalid trade rejected: {error_msg}")
```

## Quality Checks

### 1. Valid Values Check
- Price > 0
- Volume >= 0
- All values are finite numbers

### 2. Data Freshness Check
- Data not older than 60 seconds
- No future timestamps (with 5s clock skew tolerance)

### 3. Price Anomaly Check
- Z-score threshold: 3σ
- Percentage change threshold: 10%
- Requires 10+ historical data points

### 4. Volume Sanity Check
- Volume not more than 100x average
- Requires 10+ historical data points

## Quality Scoring

Quality score is calculated using exponential moving average:
- Range: 0.0 (poor) to 1.0 (excellent)
- Passed check: score moves toward 1.0
- Failed check: score moves toward 0.0
- Smoothing factor (alpha): 0.1

**Example:**
```python
# Get quality score for a symbol
score = quality_checker.get_quality_score('BTC/USDT')
print(f"Quality score: {score:.2f}")

# Get detailed statistics
stats = quality_checker.get_stats('BTC/USDT')
print(f"Passed: {stats['checks']['passed']}")
print(f"Failed: {stats['checks']['failed']}")
```

## Quarantine System

Suspect data is quarantined for later analysis:

```python
# Get quarantined data
quarantine = quality_checker.get_quarantine(symbol='BTC/USDT', limit=10)

for entry in quarantine:
    print(f"Time: {entry['timestamp']}")
    print(f"Check: {entry['check_type']}")
    print(f"Error: {entry['error_message']}")
    print(f"Data: {entry['trade_data']}")

# Clear quarantine
cleared = quality_checker.clear_quarantine(symbol='BTC/USDT')
print(f"Cleared {cleared} entries")
```

## Database Storage

Quality metrics are stored in `data_quality_metrics` table:

```sql
-- Query failed checks in last hour
SELECT 
    symbol,
    check_type,
    COUNT(*) as failures,
    AVG(quality_score) as avg_score
FROM data_quality_metrics
WHERE 
    time > NOW() - INTERVAL '1 hour'
    AND result = 'failed'
GROUP BY symbol, check_type
ORDER BY failures DESC;

-- Query quality trends
SELECT 
    bucket,
    symbol,
    avg_quality_score,
    check_count
FROM data_quality_metrics_hourly
WHERE symbol = 'BTC/USDT'
ORDER BY bucket DESC
LIMIT 24;
```

## Prometheus Metrics

### Counters
- `data_quality_checks_total{symbol, check_type, result}` - Total checks performed

### Gauges
- `data_quality_score{symbol}` - Current quality score per symbol

### Histograms
- `data_quality_validation_duration_seconds{check_type}` - Validation duration

**Example Queries:**

```promql
# Failed checks rate
rate(data_quality_checks_total{result="failed"}[5m])

# Average quality score
avg(data_quality_score)

# Validation latency p99
histogram_quantile(0.99, data_quality_validation_duration_seconds)
```

## Configuration

Located in `config/exchanges.yaml`:

```yaml
data_quality:
  price_anomaly:
    z_score_threshold: 3.0
    percentage_change_threshold: 0.10  # 10%
  data_freshness:
    max_age_seconds: 60
  volume_sanity:
    multiplier_threshold: 100  # 100x average
  history_window_size: 100
```

## Monitoring

### Grafana Dashboard

Create alerts for:
- Quality score drops below 0.8
- Failed check rate exceeds threshold
- Quarantine size grows too large
- Validation latency increases

### Health Check

```python
# Get overall statistics
stats = quality_checker.get_stats()

print(f"Total symbols: {stats['total_symbols']}")
print(f"Average quality: {stats['average_quality_score']:.2f}")
print(f"Quarantine size: {stats['total_quarantine_size']}")

# Check if quality is degrading
for symbol, data in stats['symbols'].items():
    if data['score'] < 0.8:
        print(f"WARNING: {symbol} quality score low: {data['score']:.2f}")
```

## Troubleshooting

### High False Positive Rate

If too many valid trades are rejected:
1. Increase `z_score_threshold` (e.g., 4.0 or 5.0)
2. Increase `percentage_change_threshold` (e.g., 0.15 or 0.20)
3. Check if market is highly volatile

### Missing Anomalies

If anomalies are not detected:
1. Decrease `z_score_threshold` (e.g., 2.5 or 2.0)
2. Decrease `percentage_change_threshold` (e.g., 0.05)
3. Increase `history_window_size` for better statistics

### Performance Issues

If validation is slow:
1. Reduce `history_window_size`
2. Disable quarantine for high-volume symbols
3. Reduce database sampling rate
4. Use async database inserts

## Future Enhancements

- [ ] Machine learning-based anomaly detection
- [ ] Adaptive thresholds based on market conditions
- [ ] Cross-symbol correlation checks
- [ ] Real-time alerting for quality issues
- [ ] Automated quarantine analysis
- [ ] Quality score prediction

## Related Documentation

- [Data Quality Migration](../storage/migrations/003_create_data_quality_metrics_table.sql)
- [Bar Builder](bar_builder.py) - Next processing step
- [Design Document](../.kiro/specs/crypto-stock-platform/design.md)
