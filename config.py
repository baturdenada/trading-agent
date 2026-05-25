"""
Configuration Management - Centralized config with environment variable support
Eliminates hardcoded paths and improves maintainability
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)
load_dotenv()

class Config:
    """Centralized configuration management"""

    # Base paths
    PROJECT_ROOT = Path(__file__).parent
    TRADING_MEMORY_PATH = Path(os.getenv("TRADING_MEMORY_PATH", "C:/trading-memory"))
    OBSIDIAN_VAULT_PATH = TRADING_MEMORY_PATH / "obsidian-vault"
    BACKUPS_PATH = PROJECT_ROOT / "backups"
    WORKFLOWS_PATH = PROJECT_ROOT / "workflows"

    # Create directories if they don't exist
    @staticmethod
    def ensure_directories():
        """Create all required directories"""
        for path in [Config.TRADING_MEMORY_PATH, Config.OBSIDIAN_VAULT_PATH,
                     Config.BACKUPS_PATH, Config.WORKFLOWS_PATH]:
            try:
                path.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Directory ready: {path}")
            except Exception as e:
                logger.error(f"Failed to create directory {path}: {e}")

    # MT5 Configuration
    MT5_PATH = os.getenv("MT5_PATH", "C:\\Program Files\\MetaTrader 5\\terminal64.exe")
    MT5_LOGIN = int(os.getenv("MT5_LOGIN", 0))
    MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
    MT5_SERVER = os.getenv("MT5_SERVER", "")

    # API Configuration
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_API_URL = "https://api.deepseek.com"

    # Telegram Configuration
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    # Trading Configuration
    TRADING_SYMBOLS = [
        {"name": "XAUUSD.s", "type": "gold", "base_risk": 0.02, "pip_value": 0.01, "volatility": 1.5},
        {"name": "XAGUSD.s", "type": "silver", "base_risk": 0.02, "pip_value": 0.01, "volatility": 2.0},
        {"name": "EURUSD.s", "type": "forex", "base_risk": 0.01, "pip_value": 0.0001, "volatility": 0.5},
        {"name": "USDCAD.s", "type": "forex", "base_risk": 0.01, "pip_value": 0.0001, "volatility": 0.4},
        {"name": "USDJPY.s", "type": "forex", "base_risk": 0.01, "pip_value": 0.01, "volatility": 0.3},
        {"name": "USDCHF.s", "type": "forex", "base_risk": 0.01, "pip_value": 0.0001, "volatility": 0.35},
        {"name": "USOUSD.s", "type": "oil", "base_risk": 0.02, "pip_value": 0.01, "volatility": 2.5},
        {"name": "SP500.s", "type": "index", "base_risk": 0.015, "pip_value": 0.1, "volatility": 1.0},
        {"name": "NAS100.s", "type": "index", "base_risk": 0.015, "pip_value": 0.1, "volatility": 1.2}
    ]

    # Risk Management Configuration
    RISK_CONFIG = {
        "daily_loss_limit_pct": 0.05,           # 5% daily loss limit
        "weekly_loss_limit_pct": 0.10,          # 10% weekly loss limit
        "max_position_size_pct": 0.10,          # 10% max position
        "max_risk_per_trade_pct": 0.02,         # 2% max risk per trade
        "max_concurrent_positions": 5,
        "max_correlated_positions": 2
    }

    # API Retry Configuration
    API_RETRY_CONFIG = {
        "max_retries": 3,
        "backoff_base": 2,
        "timeout": 10,
        "telegram_max_retries": 2
    }

    # MT5 Manager Configuration
    MT5_MANAGER_CONFIG = {
        "max_retries": 5,
        "backoff_base": 2,
        "circuit_timeout": 60
    }

    # File paths for data storage
    FILE_PATHS = {
        "trade_history": TRADING_MEMORY_PATH / "trade_history.db",
        "lessons_learned": TRADING_MEMORY_PATH / "lessons.json",
        "learnings": TRADING_MEMORY_PATH / "learnings.json",
        "strategies": TRADING_MEMORY_PATH / "strategies.json",
        "news_cache": TRADING_MEMORY_PATH / "news_cache.json",
        "analysis_reports": OBSIDIAN_VAULT_PATH / "Analysis_{date}.md",
        "daily_reports": OBSIDIAN_VAULT_PATH / "Daily-Logs",
        "workflow_logs": OBSIDIAN_VAULT_PATH / "Workflow-Logs",
        "comparison_reports": OBSIDIAN_VAULT_PATH / "Comparison_{date}.md",
        "workflows": PROJECT_ROOT / "workflows",
    }

    @staticmethod
    def validate_credentials():
        """Validate that all required credentials are configured"""
        required_creds = {
            "MT5_LOGIN": Config.MT5_LOGIN,
            "MT5_PASSWORD": Config.MT5_PASSWORD,
            "MT5_SERVER": Config.MT5_SERVER,
            "TELEGRAM_TOKEN": Config.TELEGRAM_TOKEN,
            "TELEGRAM_CHAT_ID": Config.TELEGRAM_CHAT_ID,
            "DEEPSEEK_API_KEY": Config.DEEPSEEK_API_KEY
        }

        missing = [k for k, v in required_creds.items() if not v or v == 0]
        if missing:
            raise ValueError(f"Missing required credentials in .env file: {', '.join(missing)}")

        logger.info("All credentials validated")
        return True

    @staticmethod
    def get_file_path(key: str, **kwargs) -> Path:
        """Get a file path with optional date formatting"""
        path = Config.FILE_PATHS.get(key)
        if not path:
            raise KeyError(f"Unknown file path key: {key}")

        if isinstance(path, str) and "{date}" in str(path):
            from datetime import datetime
            date_str = kwargs.get('date', datetime.now().strftime("%Y-%m-%d"))
            return Path(str(path).format(date=date_str))

        return path

    @staticmethod
    def get_config_summary() -> dict:
        """Get a summary of current configuration"""
        return {
            "project_root": str(Config.PROJECT_ROOT),
            "trading_memory": str(Config.TRADING_MEMORY_PATH),
            "obsidian_vault": str(Config.OBSIDIAN_VAULT_PATH),
            "mt5_server": Config.MT5_SERVER,
            "mt5_login": Config.MT5_LOGIN,
            "symbols_configured": len(Config.TRADING_SYMBOLS),
            "daily_loss_limit_pct": Config.RISK_CONFIG["daily_loss_limit_pct"],
            "max_concurrent_positions": Config.RISK_CONFIG["max_concurrent_positions"]
        }

# Initialize configuration on import
try:
    Config.ensure_directories()
    Config.validate_credentials()
    logger.info("Configuration initialized successfully")
except Exception as e:
    logger.error(f"Configuration error: {e}")
    raise
