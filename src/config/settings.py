import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from loguru import logger


class Settings:
    """Configuration management for Poker Assistant"""
    
    DEFAULT_CONFIG = {
        'site': 'pokerstars',
        'hero_name': 'Hero',
        
        'database': {
            'path': 'data/poker.db',
            'backup_enabled': True,
            'backup_interval': 86400  # 24 hours
        },
        
        'ocr': {
            'engine': 'pytesseract',
            'confidence_threshold': 0.85,
            'preprocessing': ['grayscale', 'threshold', 'denoise']
        },
        
        'capture': {
            'update_interval': 1.0,
            'monitor_index': 1,
            'save_screenshots': False,
            'screenshot_dir': 'data/screenshots'
        },
        
        'hand_history': {
            'auto_detect': True,
            'scan_interval': 1.0,
            'max_file_age_hours': 24,
            'directories': []
        },
        
        'hud': {
            'enabled': True,
            'update_interval': 2.0,
            'min_hands_for_stats': 30,
            'color_coding': {
                'nit': '#FF0000',      # Red
                'tag': '#00FF00',      # Green
                'lag': '#FFA500',      # Orange
                'fish': '#0000FF',     # Blue
                'reg': '#FFFFFF'       # White
            }
        },
        
        'overlay': {
            'enabled': True,
            'opacity': 0.8,
            'position': 'top-right',
            'hotkeys': {
                'toggle': 'F1',
                'refresh': 'F5',
                'screenshot': 'F12'
            }
        },
        
        'strategy': {
            'mode': 'balanced',  # 'gto', 'exploitative', 'balanced'
            'suggestion_threshold': 0.7,
            'show_ev': True,
            'show_ranges': True
        },
        
        'logging': {
            'level': 'INFO',
            'file_enabled': True,
            'file_path': 'logs/poker_assistant.log',
            'rotation': '1 day',
            'retention': '7 days'
        }
    }
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
        self.config = self._load_config()
        logger.info(f"Settings loaded from {self.config_path}")
    
    def _get_default_config_path(self) -> str:
        """Get default configuration file path"""
        # Check common locations
        locations = [
            'config/settings.yaml',
            'settings.yaml',
            os.path.expanduser('~/.poker_assistant/settings.yaml'),
            '/etc/poker_assistant/settings.yaml'
        ]
        
        for location in locations:
            if os.path.exists(location):
                return location
        
        # Create default config in current directory
        return 'config/settings.yaml'
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    user_config = yaml.safe_load(f) or {}
                
                # Merge with defaults
                config = self._deep_merge(self.DEFAULT_CONFIG.copy(), user_config)
                return config
                
            except Exception as e:
                logger.error(f"Failed to load config from {self.config_path}: {e}")
                return self.DEFAULT_CONFIG.copy()
        else:
            # Create default config file
            self._save_config(self.DEFAULT_CONFIG)
            return self.DEFAULT_CONFIG.copy()
    
    def _deep_merge(self, base: dict, update: dict) -> dict:
        """Deep merge two dictionaries"""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                base[key] = self._deep_merge(base[key], value)
            else:
                base[key] = value
        return base
    
    def _save_config(self, config: dict):
        """Save configuration to file"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key (supports dot notation)"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """Set configuration value by key (supports dot notation)"""
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
        self._save_config(self.config)
    
    def reload(self):
        """Reload configuration from file"""
        self.config = self._load_config()
        logger.info("Configuration reloaded")
    
    def validate(self) -> bool:
        """Validate configuration"""
        required_keys = ['site', 'database.path']
        
        for key in required_keys:
            if self.get(key) is None:
                logger.error(f"Missing required configuration: {key}")
                return False
        
        return True
    
    def export(self, filepath: str):
        """Export configuration to file"""
        try:
            with open(filepath, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
            logger.info(f"Configuration exported to {filepath}")
        except Exception as e:
            logger.error(f"Failed to export config: {e}")