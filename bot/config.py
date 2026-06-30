"""Bot-specific configuration for paper trading."""

from pydantic import BaseSettings, Field
from typing import List


class BotConfig(BaseSettings):
    """
    Configuration for the paper trading bot.

    Includes trading symbols, update intervals, and strategy settings.
    """

    # Cryptocurrency trading
    crypto_symbols: List[str] = Field(
        default=["BTC/USDT", "ETH/USDT"],
        description="Cryptocurrency pairs to trade",
    )

    # Equity trading
    stock_symbols: List[str] = Field(
        default=["AAPL", "MSFT", "GOOG"],
        description="Stock symbols to trade",
    )

    # Update intervals
    crypto_update_interval: int = Field(
        default=60,
        description="Seconds between crypto market data updates",
    )

    equity_update_interval: int = Field(
        default=60,
        description="Seconds between equity market data updates (during market hours)",
    )

    portfolio_monitor_interval: int = Field(
        default=30,
        description="Seconds between portfolio monitoring checks",
    )

    # Portfolio settings
    initial_cash: float = Field(
        default=100000.0,
        description="Starting cash balance in USD",
    )

    # Strategy selection
    strategies_to_use: List[str] = Field(
        default=["trend_following", "mean_reversion"],
        description="Which trading strategies to activate",
    )

    # Trading mode
    paper_trading: bool = Field(
        default=True,
        description="Enable paper trading (simulation mode)",
    )

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_prefix = "BOT_"
        case_sensitive = False
