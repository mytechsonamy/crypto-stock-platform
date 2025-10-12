"""
Centralized configuration management for Crypto-Stock Platform.

This module provides configuration settings loaded from environment variables
and YAML configuration files.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass


# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass
class DatabaseConfig:
    """TimescaleDB configuration."""
    host: str
    port: int
    database: str
    user: str
    password: str
    min_pool_size: int = 10
    max_pool_size: int = 50


@dataclass
class RedisConfig:
    """Redis configuration."""
    host: str
    port: int
    password: Optional[str] = None
    db: int = 0
    max_connections: int = 50


@dataclass
class APIConfig:
    """FastAPI configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list = None
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60


@dataclass
class MonitoringConfig:
    """Prometheus monitoring configuration."""
    enabled: bool = True
    port: int = 9090
    scrape_interval: int = 15


class Settings:
    """Application settings loaded from environment variables."""
    
    def __init__(self):
        # Database
        self.database = DatabaseConfig(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "crypto_stock"),
            user=os.getenv("DB_USER", "admin"),
            password=os.getenv("DB_PASSWORD", ""),
            min_pool_size=int(os.getenv("DB_MIN_POOL_SIZE", "10")),
            max_pool_size=int(os.getenv("DB_MAX_POOL_SIZE", "50"))
        )
        
        # Redis
        self.redis = RedisConfig(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            password=os.getenv("REDIS_PASSWORD"),
            db=int(os.getenv("REDIS_DB", "0")),
            max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "50"))
        )
        
        # API
        self.api = APIConfig(
            host=os.getenv("API_HOST", "0.0.0.0"),
            port=int(os.getenv("API_PORT", "8000")),
            cors_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
            jwt_secret=os.getenv("JWT_SECRET", ""),
            jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
            jwt_expiration_minutes=int(os.getenv("JWT_EXPIRATION_MINUTES", "60"))
        )
        
        # Monitoring
        self.monitoring = MonitoringConfig(
            enabled=os.getenv("MONITORING_ENABLED", "true").lower() == "true",
            port=int(os.getenv("METRICS_PORT", "9090")),
            scrape_interval=int(os.getenv("SCRAPE_INTERVAL", "15"))
        )
        
        # Exchange API Keys
        self.binance_api_key = os.getenv("BINANCE_API_KEY", "")
        self.binance_api_secret = os.getenv("BINANCE_API_SECRET", "")
        
        self.alpaca_api_key = os.getenv("ALPACA_API_KEY", "")
        self.alpaca_secret_key = os.getenv("ALPACA_SECRET_KEY", "")
        
        # Environment
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        
        # Logging
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.log_format = os.getenv("LOG_FORMAT", "json")
        
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"


# Global settings instance
settings = Settings()
