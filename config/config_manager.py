"""
Configuration Manager
Handles YAML configuration loading and hot-reload support
"""

import yaml
import os
from pathlib import Path
from typing import Any, Dict, Callable, List, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
from loguru import logger
import threading


class ConfigFileHandler(FileSystemEventHandler):
    """File system event handler for configuration files"""
    
    def __init__(self, config_manager: 'ConfigManager'):
        self.config_manager = config_manager
        self.last_modified = {}
        
    def on_modified(self, event: FileModifiedEvent):
        """Handle file modification events"""
        if event.is_directory:
            return
            
        file_path = event.src_path
        
        # Debounce: ignore rapid successive modifications
        import time
        current_time = time.time()
        if file_path in self.last_modified:
            if current_time - self.last_modified[file_path] < 1.0:
                return
        
        self.last_modified[file_path] = current_time
        
        # Check if it's a config file we're watching
        if file_path.endswith('.yaml') or file_path.endswith('.yml'):
            logger.info(f"Configuration file modified: {file_path}")
            self.config_manager._reload_config(file_path)


class ConfigManager:
    """
    Configuration Manager with hot-reload support
    
    Features:
    - Load YAML configuration files
    - Nested key access with dot notation
    - Hot-reload with file watching
    - Callback system for config changes
    """
    
    def __init__(self, config_dir: str = 'config'):
        self.config_dir = Path(config_dir)
        self.configs: Dict[str, Dict] = {}
        self.callbacks: Dict[str, List[Callable]] = {}
        self.observer: Optional[Observer] = None
        self._lock = threading.Lock()
        
        logger.info(f"ConfigManager initialized with directory: {self.config_dir}")
    
    def load_config(self, filename: str) -> Dict[str, Any]:
        """
        Load a YAML configuration file
        
        Args:
            filename: Name of the config file (e.g., 'exchanges.yaml')
            
        Returns:
            Dictionary with configuration data
        """
        file_path = self.config_dir / filename
        
        try:
            with open(file_path, 'r') as f:
                config = yaml.safe_load(f)
                
            with self._lock:
                self.configs[filename] = config
                
            logger.info(f"Loaded configuration from {file_path}")
            return config
            
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {file_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML file {file_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading configuration from {file_path}: {e}")
            raise
    
    def get(self, key: str, filename: str = 'exchanges.yaml', default: Any = None) -> Any:
        """
        Get configuration value using dot notation
        
        Args:
            key: Configuration key (supports dot notation, e.g., 'binance.symbols')
            filename: Configuration file name
            default: Default value if key not found
            
        Returns:
            Configuration value or default
            
        Examples:
            >>> config.get('binance.api_key')
            >>> config.get('symbols.BTCUSDT.timeframes')
        """
        # Load config if not already loaded
        if filename not in self.configs:
            try:
                self.load_config(filename)
            except Exception:
                return default
        
        with self._lock:
            config = self.configs.get(filename, {})
        
        # Navigate nested keys
        keys = key.split('.')
        value = config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value
    
    def get_all(self, filename: str = 'exchanges.yaml') -> Dict[str, Any]:
        """
        Get entire configuration file
        
        Args:
            filename: Configuration file name
            
        Returns:
            Complete configuration dictionary
        """
        if filename not in self.configs:
            self.load_config(filename)
        
        with self._lock:
            return self.configs.get(filename, {}).copy()
    
    def reload(self, filename: str) -> None:
        """
        Manually reload a configuration file
        
        Args:
            filename: Configuration file name
        """
        logger.info(f"Manually reloading configuration: {filename}")
        self.load_config(filename)
        self._trigger_callbacks(filename)
    
    def _reload_config(self, file_path: str) -> None:
        """
        Internal method to reload configuration
        
        Args:
            file_path: Full path to the configuration file
        """
        filename = os.path.basename(file_path)
        
        try:
            self.load_config(filename)
            self._trigger_callbacks(filename)
            logger.success(f"Configuration reloaded: {filename}")
        except Exception as e:
            logger.error(f"Failed to reload configuration {filename}: {e}")
    
    def on_config_change(self, filename: str, callback: Callable[[Dict], None]) -> None:
        """
        Register a callback for configuration changes
        
        Args:
            filename: Configuration file to watch
            callback: Function to call when config changes (receives new config as argument)
            
        Example:
            >>> def on_exchange_config_change(config):
            ...     print(f"Exchange config changed: {config}")
            >>> config_manager.on_config_change('exchanges.yaml', on_exchange_config_change)
        """
        if filename not in self.callbacks:
            self.callbacks[filename] = []
        
        self.callbacks[filename].append(callback)
        logger.info(f"Registered callback for {filename}")
    
    def _trigger_callbacks(self, filename: str) -> None:
        """
        Trigger all callbacks for a configuration file
        
        Args:
            filename: Configuration file that changed
        """
        if filename not in self.callbacks:
            return
        
        with self._lock:
            config = self.configs.get(filename, {}).copy()
        
        for callback in self.callbacks[filename]:
            try:
                callback(config)
            except Exception as e:
                logger.error(f"Error in config change callback: {e}")
    
    def start_watching(self) -> None:
        """
        Start watching configuration directory for changes
        """
        if self.observer is not None:
            logger.warning("File watcher already started")
            return
        
        self.observer = Observer()
        event_handler = ConfigFileHandler(self)
        self.observer.schedule(event_handler, str(self.config_dir), recursive=False)
        self.observer.start()
        
        logger.info(f"Started watching configuration directory: {self.config_dir}")
    
    def stop_watching(self) -> None:
        """
        Stop watching configuration directory
        """
        if self.observer is None:
            return
        
        self.observer.stop()
        self.observer.join()
        self.observer = None
        
        logger.info("Stopped watching configuration directory")
    
    def __enter__(self):
        """Context manager entry"""
        self.start_watching()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop_watching()


# Global instance
config_manager = ConfigManager()
