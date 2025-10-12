# ML Features Guide

Guide for data scientists and ML engineers working with the Crypto-Stock Platform's feature engineering pipeline.

## Overview

The platform automatically engineers 60+ features from raw market data, optimized for machine learning models. Features are calculated in real-time and stored for both training and inference.

## Feature Categories

### 1. Price Features

**Returns**:
- `return_1`: 1-period return
- `return_5`: 5-period return
- `return_10`: 10-period return
- `log_return`: Logarithmic return
- `price_momentum`: Price momentum indicator

**Calculation**:
```python
# Simple return
return_1 = (close - close.shift(1)) / close.shift(1)

# Logarithmic return
log_return = np.log(close / close.shift(1))

# Momentum
price_momentum = close - close.shift(10)
```

### 2. Volatility Features

**Rolling Standard Deviation**:
- `rolling_std_5`: 5-period rolling std
- `rolling_std_10`: 10-period rolling std
- `rolling_std_20`: 20-period rolling std

**Range Features**:
- `high_low_ratio`: High/Low ratio
- `high_low_range`: High - Low

**Calculation**:
```python
# Rolling volatility
rolling_std_20 = close.rolling(20).std()

# High-low ratio
high_low_ratio = high / low

# Range
high_low_range = high - low
```

### 3. Volume Features

**Volume Metrics**:
- `volume_change`: Volume change from previous period
- `volume_momentum`: Volume momentum
- `volume_ratio`: Current volume / average volume
- `volume_price_trend`: Volume-weighted price trend

**Calculation**:
```python
# Volume change
volume_change = (volume - volume.shift(1)) / volume.shift(1)

# Volume momentum
volume_momentum = volume - volume.rolling(10).mean()

# Volume ratio
volume_ratio = volume / volume.rolling(20).mean()

# Volume-price trend
volume_price_trend = (close - close.shift(1)) * volume
```

### 4. Technical Indicator Features

**RSI-based**:
- `rsi_zone`: RSI zone (oversold/neutral/overbought)
- `rsi_divergence`: RSI divergence from price

**MACD-based**:
- `macd_crossover`: MACD signal crossover
- `macd_histogram_change`: MACD histogram change

**Bollinger Bands**:
- `bb_position`: Price position within bands
- `bb_width`: Band width (volatility)
- `bb_squeeze`: Bollinger Band squeeze indicator

**Calculation**:
```python
# RSI zones
rsi_zone = pd.cut(rsi, bins=[0, 30, 70, 100], labels=[0, 1, 2])

# MACD crossover
macd_crossover = (macd > macd_signal).astype(int)

# BB position
bb_position = (close - bb_lower) / (bb_upper - bb_lower)

# BB width
bb_width = (bb_upper - bb_lower) / bb_middle

# BB squeeze
bb_squeeze = (bb_width < bb_width.rolling(20).mean()).astype(int)
```

### 5. Trend Features

**Moving Average Distance**:
- `sma_20_distance`: Distance from SMA(20)
- `sma_50_distance`: Distance from SMA(50)
- `price_above_sma_20`: Price above SMA(20)
- `price_above_sma_50`: Price above SMA(50)

**Calculation**:
```python
# SMA distance
sma_20_distance = (close - sma_20) / sma_20

# Price position
price_above_sma_20 = (close > sma_20).astype(int)
```

### 6. Time Features

**Temporal**:
- `hour`: Hour of day (0-23)
- `day_of_week`: Day of week (0-6)
- `is_market_open`: Market open indicator

**Calculation**:
```python
# Extract time features
hour = timestamp.hour
day_of_week = timestamp.dayofweek
is_market_open = is_within_market_hours(timestamp)
```

## Feature Engineering Pipeline

### Architecture

```
Raw Data → Feature Store → Engineer Features → Store Features → Serve Features
                                    ↓
                            TimescaleDB + Redis
```

### Implementation

```python
# ai/feature_store.py
class FeatureStore:
    def __init__(self, db_manager, redis_manager):
        self.db = db_manager
        self.redis = redis_manager
        self.feature_version = "v1.0"
    
    async def engineer_features(self, bars: pd.DataFrame, indicators: pd.DataFrame) -> dict:
        """Engineer all features from bars and indicators"""
        
        # Merge bars and indicators
        df = bars.merge(indicators, on=['time', 'symbol', 'timeframe'])
        
        # Price features
        df['return_1'] = df['close'].pct_change(1)
        df['return_5'] = df['close'].pct_change(5)
        df['return_10'] = df['close'].pct_change(10)
        df['log_return'] = np.log(df['close'] / df['close'].shift(1))
        df['price_momentum'] = df['close'] - df['close'].shift(10)
        
        # Volatility features
        df['rolling_std_5'] = df['close'].rolling(5).std()
        df['rolling_std_10'] = df['close'].rolling(10).std()
        df['rolling_std_20'] = df['close'].rolling(20).std()
        df['high_low_ratio'] = df['high'] / df['low']
        df['high_low_range'] = df['high'] - df['low']
        
        # Volume features
        df['volume_change'] = df['volume'].pct_change(1)
        df['volume_momentum'] = df['volume'] - df['volume'].rolling(10).mean()
        df['volume_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
        df['volume_price_trend'] = (df['close'] - df['close'].shift(1)) * df['volume']
        
        # Technical features
        df['rsi_zone'] = pd.cut(df['rsi'], bins=[0, 30, 70, 100], labels=[0, 1, 2])
        df['macd_crossover'] = (df['macd'] > df['macd_signal']).astype(int)
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        
        # Trend features
        df['sma_20_distance'] = (df['close'] - df['sma_20']) / df['sma_20']
        df['sma_50_distance'] = (df['close'] - df['sma_50']) / df['sma_50']
        df['price_above_sma_20'] = (df['close'] > df['sma_20']).astype(int)
        df['price_above_sma_50'] = (df['close'] > df['sma_50']).astype(int)
        
        # Time features
        df['hour'] = df['time'].dt.hour
        df['day_of_week'] = df['time'].dt.dayofweek
        
        # Clean NaN values
        df = df.fillna(method='bfill')
        
        # Convert to dict
        features = df.iloc[-1].to_dict()
        
        return features
    
    async def store_features(self, symbol: str, timeframe: str, features: dict):
        """Store features in database and cache"""
        
        # Store in TimescaleDB
        await self.db.insert_features(
            symbol=symbol,
            timeframe=timeframe,
            feature_version=self.feature_version,
            features=features
        )
        
        # Cache in Redis
        await self.redis.cache_features(
            symbol=symbol,
            features=features,
            ttl=300  # 5 minutes
        )
    
    async def get_features_batch(self, symbol: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Get features for training (batch mode)"""
        
        features = await self.db.get_features_range(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date
        )
        
        return pd.DataFrame(features)
    
    async def get_features_realtime(self, symbol: str) -> dict:
        """Get latest features for inference (real-time mode)"""
        
        # Try cache first
        features = await self.redis.get_cached_features(symbol)
        
        if features is None:
            # Fallback to database
            features = await self.db.get_latest_features(symbol)
        
        return features
```

## Using Features for ML

### Training Data Preparation

```python
import pandas as pd
from datetime import datetime, timedelta

# Fetch training data
start_date = datetime.now() - timedelta(days=365)
end_date = datetime.now()

features_df = await feature_store.get_features_batch(
    symbol="BTCUSDT",
    start_date=start_date,
    end_date=end_date
)

# Prepare features and target
feature_columns = [
    'return_1', 'return_5', 'return_10',
    'rolling_std_5', 'rolling_std_10', 'rolling_std_20',
    'volume_change', 'volume_momentum', 'volume_ratio',
    'rsi', 'macd', 'bb_position',
    'sma_20_distance', 'sma_50_distance',
    'hour', 'day_of_week'
]

X = features_df[feature_columns]
y = (features_df['close'].shift(-1) > features_df['close']).astype(int)  # Binary: price up/down

# Split train/test
from sklearn.model_selection import train_test_split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
```

### Model Training

```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

# Train model
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Evaluate
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
print(f"Accuracy: {accuracy:.4f}")
print(classification_report(y_test, y_pred))

# Feature importance
feature_importance = pd.DataFrame({
    'feature': feature_columns,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)

print(feature_importance)
```

### Real-time Inference

```python
# Get latest features
features = await feature_store.get_features_realtime("BTCUSDT")

# Prepare input
X_input = pd.DataFrame([features])[feature_columns]

# Predict
prediction = model.predict(X_input)[0]
probability = model.predict_proba(X_input)[0]

print(f"Prediction: {'UP' if prediction == 1 else 'DOWN'}")
print(f"Probability: {probability[1]:.4f}")
```

## Feature Versioning

Features are versioned to ensure reproducibility:

```python
# Feature version in database
CREATE TABLE ml_features (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    feature_version VARCHAR(10),  -- e.g., "v1.0"
    features JSONB,
    PRIMARY KEY (time, symbol, timeframe)
);

# Query specific version
SELECT * FROM ml_features
WHERE symbol = 'BTCUSDT'
  AND feature_version = 'v1.0'
  AND time > NOW() - INTERVAL '30 days';
```

## Feature Quality

### Missing Values

```python
# Check missing values
missing = features_df.isnull().sum()
print(missing[missing > 0])

# Handle missing values
features_df = features_df.fillna(method='bfill')  # Backfill
features_df = features_df.fillna(0)  # Fill remaining with 0
```

### Outliers

```python
# Detect outliers using IQR
Q1 = features_df.quantile(0.25)
Q3 = features_df.quantile(0.75)
IQR = Q3 - Q1

outliers = ((features_df < (Q1 - 1.5 * IQR)) | (features_df > (Q3 + 1.5 * IQR))).sum()
print(outliers[outliers > 0])

# Cap outliers
features_df = features_df.clip(lower=Q1 - 1.5 * IQR, upper=Q3 + 1.5 * IQR)
```

### Feature Scaling

```python
from sklearn.preprocessing import StandardScaler, MinMaxScaler

# Standardization (mean=0, std=1)
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_train)

# Normalization (min=0, max=1)
scaler = MinMaxScaler()
X_scaled = scaler.fit_transform(X_train)
```

## Advanced Feature Engineering

### Custom Features

```python
# Add custom features to FeatureStore
class CustomFeatureStore(FeatureStore):
    async def engineer_features(self, bars: pd.DataFrame, indicators: pd.DataFrame) -> dict:
        # Call parent method
        features = await super().engineer_features(bars, indicators)
        
        # Add custom features
        df = bars.copy()
        
        # Custom feature 1: Price acceleration
        df['price_acceleration'] = df['close'].diff().diff()
        
        # Custom feature 2: Volume-weighted momentum
        df['vw_momentum'] = (df['close'] - df['close'].shift(10)) * df['volume']
        
        # Custom feature 3: Volatility ratio
        df['volatility_ratio'] = df['rolling_std_5'] / df['rolling_std_20']
        
        # Add to features dict
        features.update({
            'price_acceleration': df['price_acceleration'].iloc[-1],
            'vw_momentum': df['vw_momentum'].iloc[-1],
            'volatility_ratio': df['volatility_ratio'].iloc[-1]
        })
        
        return features
```

### Feature Selection

```python
from sklearn.feature_selection import SelectKBest, f_classif

# Select top K features
selector = SelectKBest(f_classif, k=20)
X_selected = selector.fit_transform(X_train, y_train)

# Get selected feature names
selected_features = [feature_columns[i] for i in selector.get_support(indices=True)]
print("Selected features:", selected_features)
```

### Feature Engineering Pipeline

```python
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

# Create pipeline
pipeline = Pipeline([
    ('scaler', StandardScaler()),
    ('pca', PCA(n_components=0.95)),  # Keep 95% variance
    ('classifier', RandomForestClassifier())
])

# Train pipeline
pipeline.fit(X_train, y_train)

# Predict
y_pred = pipeline.predict(X_test)
```

## Performance Optimization

### Batch Processing

```python
# Process multiple symbols in parallel
import asyncio

async def process_symbols(symbols: list):
    tasks = [
        feature_store.engineer_features(symbol)
        for symbol in symbols
    ]
    results = await asyncio.gather(*tasks)
    return results

# Usage
symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
features = await process_symbols(symbols)
```

### Caching

```python
# Cache features in Redis for fast access
await redis.cache_features(
    symbol="BTCUSDT",
    features=features,
    ttl=300  # 5 minutes
)

# Retrieve from cache
cached_features = await redis.get_cached_features("BTCUSDT")
```

### Vectorization

```python
# Use vectorized operations instead of loops
# ❌ Slow
for i in range(len(df)):
    df.loc[i, 'return'] = (df.loc[i, 'close'] - df.loc[i-1, 'close']) / df.loc[i-1, 'close']

# ✅ Fast
df['return'] = df['close'].pct_change()
```

## API Reference

### Get Features (Batch)

```bash
GET /api/v1/features/{symbol}?start_date=2024-01-01&end_date=2024-01-31

Response:
{
  "symbol": "BTCUSDT",
  "timeframe": "1h",
  "feature_version": "v1.0",
  "count": 744,
  "features": [
    {
      "time": "2024-01-01T00:00:00Z",
      "return_1": 0.0012,
      "return_5": 0.0045,
      "rolling_std_20": 0.023,
      ...
    }
  ]
}
```

### Get Features (Real-time)

```bash
GET /api/v1/features/{symbol}/latest

Response:
{
  "symbol": "BTCUSDT",
  "timeframe": "1h",
  "time": "2024-01-15T10:00:00Z",
  "feature_version": "v1.0",
  "features": {
    "return_1": 0.0012,
    "return_5": 0.0045,
    "rolling_std_20": 0.023,
    ...
  }
}
```

## Best Practices

1. **Version your features** - Track feature versions for reproducibility
2. **Handle missing values** - Use appropriate imputation strategies
3. **Scale features** - Normalize or standardize before training
4. **Monitor feature drift** - Track feature distributions over time
5. **Document features** - Maintain clear documentation of each feature
6. **Test features** - Validate feature calculations
7. **Optimize performance** - Use vectorization and caching
8. **Feature selection** - Remove redundant or low-importance features
9. **Cross-validation** - Use time-series cross-validation
10. **Monitor model performance** - Track accuracy and retrain as needed

## Resources

- [Feature Engineering for Machine Learning](https://www.oreilly.com/library/view/feature-engineering-for/9781491953235/)
- [Scikit-learn Feature Engineering](https://scikit-learn.org/stable/modules/preprocessing.html)
- [Pandas Time Series](https://pandas.pydata.org/docs/user_guide/timeseries.html)
- [TA-Lib Documentation](https://mrjbq7.github.io/ta-lib/)
