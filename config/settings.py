"""Settings configuration using Pydantic and environment variables."""

from pydantic_settings import BaseSettings
from typing import Optional


class ExchangeConfig(BaseSettings):
    """Exchange API configuration."""

    binance_api_key: Optional[str] = None
    binance_secret: Optional[str] = None
    alpaca_api_key: Optional[str] = None
    alpaca_secret: Optional[str] = None
    alpaca_base_url: str = "https://paper-api.alpaca.markets"

    class Config:
        """Pydantic config."""
        env_file = ".env"
        case_sensitive = False


class RiskConfig(BaseSettings):
    """Risk management configuration."""

    max_drawdown_pct: float = 20.0
    max_position_size_pct: float = 10.0
    max_leverage: float = 2.0

    class Config:
        """Pydantic config."""
        env_file = ".env"
        case_sensitive = False


class TradingConfig(BaseSettings):
    """Trading behavior configuration."""

    paper_trading: bool = True
    database_url: str = "sqlite:///./ai_investment_bot.db"

    class Config:
        """Pydantic config."""
        env_file = ".env"
        case_sensitive = False


class LoggingConfig(BaseSettings):
    """Logging configuration."""

    log_level: str = "INFO"

    class Config:
        """Pydantic config."""
        env_file = ".env"
        case_sensitive = False


class Settings(BaseSettings):
    """Main application settings combining all config sections."""

    exchange: ExchangeConfig = ExchangeConfig()
    risk: RiskConfig = RiskConfig()
    trading: TradingConfig = TradingConfig()
    logging: LoggingConfig = LoggingConfig()

    class Config:
        """Pydantic config."""
        env_file = ".env"


# Global settings instance
settings = Settings()
