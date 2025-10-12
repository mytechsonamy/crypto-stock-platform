# Configuration Management

This directory contains configuration files and the ConfigManager for dynamic configuration management.

## Files

- `exchanges.yaml` - Exchange-specific settings (API keys, rate limits, etc.)
- `symbols.yaml` - Symbol configurations and timeframes
- `settings.py` - Application settings (database, Redis, etc.)
- `config_manager.py` - Configuration manager with hot-reload support

## ConfigManager

The ConfigManager provides:
- YAML configuration loading
- Nested key access with dot notation
- Hot-reload with file watching
- Callback system for configuration changes

### Basic Usage

```python
from config.config_manager import config_manager

# Load configuration
config = config_manager.load_config('exchanges.yaml')

# Get specific value with dot notation
api_key = config_manager.get('binance.api_key')
symbols = config_manager.get('binance.symbols', default=[])

# Get entire config
all_config = config_manager.get_all('exchanges.yaml')
```

### Hot-Reload

Enable hot-reload to automatically reload configuration when files change:

```python
from config.config_manager import config_manager

# Start watching for changes
config_manager.start_watching()

# Register callback for changes
def on_config_change(new_config):
    print(f"Configuration changed: {new_config}")
    # Update your service with new config

config_manager.on_config_change('exchanges.yaml', on_config_change)

# ... your application runs ...

# Stop watching when done
config_manager.stop_watching()
```

### Context Manager

Use as a context manager for automatic cleanup:

```python
from config.config_manager import config_manager

with config_manager:
    # File watching is automatically started
    config_manager.on_config_change('exchanges.yaml', my_callback)
    
    # Your application code
    run_application()
    
# File watching is automatically stopped
```

### Collector Integration

Example of integrating with a collector:

```python
from config.config_manager import config_manager
from collectors.binance_collector import BinanceCollector

class BinanceCollectorWithReload(BinanceCollector):
    def __init__(self):
        super().__init__()
        
        # Register reload callback
        config_manager.on_config_change(
            'exchanges.yaml',
            self._on_config_change
        )
    
    def _on_config_change(self, new_config):
        """Handle configuration changes"""
        binance_config = new_config.get('binance', {})
        new_symbols = binance_config.get('symbols', [])
        
        # Update subscriptions
        self.update_subscriptions(new_symbols)
        
        logger.info(f"Updated Binance subscriptions: {new_symbols}")

# Start collector with hot-reload
collector = BinanceCollectorWithReload()
config_manager.start_watching()
```

### Configuration File Format

#### exchanges.yaml

```yaml
binance:
  api_key: ${BINANCE_API_KEY}
  api_secret: ${BINANCE_API_SECRET}
  symbols:
    - BTCUSDT
    - ETHUSDT
  rate_limit: 1200  # requests per minute
  websocket_refresh_hours: 24

alpaca:
  api_key: ${ALPACA_API_KEY}
  secret_key: ${ALPACA_SECRET_KEY}
  symbols:
    - AAPL
    - GOOGL
  data_feed: iex  # or sip
  
yahoo:
  symbols:
    - THYAO.IS
    - GARAN.IS
  poll_interval_seconds: 300
```

#### symbols.yaml

```yaml
BTCUSDT:
  exchange: binance
  type: crypto
  timeframes:
    - 1m
    - 5m
    - 15m
    - 1h
  indicators:
    rsi:
      period: 14
    macd:
      fast: 12
      slow: 26
      signal: 9
    bollinger_bands:
      period: 20
      std_dev: 2
```

### Environment Variables

Configuration files support environment variable substitution:

```yaml
binance:
  api_key: ${BINANCE_API_KEY}
  api_secret: ${BINANCE_API_SECRET}
```

Set environment variables in `.env`:

```env
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
```

### Nested Key Access

Access nested configuration values using dot notation:

```python
# Get nested value
api_key = config_manager.get('binance.api_key')
rsi_period = config_manager.get('BTCUSDT.indicators.rsi.period')

# With default value
symbols = config_manager.get('binance.symbols', default=[])
```

### Manual Reload

Manually reload configuration without file watching:

```python
# Reload specific file
config_manager.reload('exchanges.yaml')

# This will trigger all registered callbacks
```

### Thread Safety

ConfigManager is thread-safe and can be used from multiple threads:

```python
import threading

def worker():
    value = config_manager.get('binance.api_key')
    # Use value...

threads = [threading.Thread(target=worker) for _ in range(10)]
for t in threads:
    t.start()
for t in threads:
    t.join()
```

### Error Handling

```python
try:
    config = config_manager.load_config('exchanges.yaml')
except FileNotFoundError:
    print("Configuration file not found")
except yaml.YAMLError as e:
    print(f"Invalid YAML: {e}")
except Exception as e:
    print(f"Error loading config: {e}")
```

### Best Practices

1. **Load Once**: Load configuration at startup, then use hot-reload for updates
2. **Use Callbacks**: Register callbacks for configuration changes instead of polling
3. **Default Values**: Always provide default values for optional configuration
4. **Validate**: Validate configuration after loading
5. **Environment Variables**: Use environment variables for sensitive data
6. **Documentation**: Document all configuration options
7. **Testing**: Test configuration changes in development before production

### Testing

Mock ConfigManager for testing:

```python
import pytest
from unittest.mock import Mock, patch

def test_collector_with_config():
    mock_config = {
        'binance': {
            'symbols': ['BTCUSDT', 'ETHUSDT']
        }
    }
    
    with patch('config.config_manager.config_manager') as mock_cm:
        mock_cm.get.return_value = mock_config
        
        # Test your code
        collector = BinanceCollector()
        assert collector.symbols == ['BTCUSDT', 'ETHUSDT']
```

### Troubleshooting

#### Configuration Not Reloading

- Check file watcher is started: `config_manager.start_watching()`
- Verify file path is correct
- Check file permissions
- Review logs for errors

#### Callback Not Triggered

- Ensure callback is registered before file changes
- Check callback function signature
- Review logs for callback errors

#### Performance Issues

- Limit number of callbacks
- Avoid heavy operations in callbacks
- Use debouncing for rapid changes (built-in)

### Performance

- File watching has minimal overhead
- Callbacks are executed synchronously
- Configuration access is thread-safe with locks
- Debouncing prevents rapid successive reloads (1 second)

### Limitations

- Only watches immediate config directory (not recursive)
- Callbacks are executed in order of registration
- File changes detected with ~1 second delay
- YAML parsing errors will prevent reload
