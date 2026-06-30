"""Main entry point for AI Investment Bot."""

import asyncio
import signal
import threading
import sys
from typing import List, Optional
from datetime import datetime

import uvicorn

from config.settings import settings
from core.logger import setup_logging, get_logger
from core.event_bus import EventBus
from core.exceptions import InvestmentBotError

from data.crypto_provider import CryptoDataProvider
from data.stock_provider import StockDataProvider

from agents.base_agent import BaseAgent
from agents.regime_agent import MarketRegimeAgent
from agents.crypto_agent import CryptoTradingAgent
from agents.equity_agent import EquityTradingAgent
from agents.risk_agent import RiskAgent

from execution.paper_executor import PaperExecutor
from dashboard.api import create_app

from bot.orchestrator import PaperTradingBot
from bot.config import BotConfig


logger = get_logger(__name__)


class InvestmentBot:
    """Main bot orchestrator (legacy mode)."""

    def __init__(self):
        """Initialize the investment bot."""
        # Initialize components
        self.event_bus = EventBus()
        self.executor = PaperExecutor()

        # Initialize agents
        self.agents: List[BaseAgent] = [
            MarketRegimeAgent(self.event_bus),
            CryptoTradingAgent(self.event_bus),
            EquityTradingAgent(self.event_bus),
            RiskAgent(
                self.event_bus,
                max_drawdown_pct=settings.risk.max_drawdown_pct,
                max_position_size_pct=settings.risk.max_position_size_pct,
                max_leverage=settings.risk.max_leverage,
            ),
        ]

        # Data providers
        self.crypto_provider = CryptoDataProvider()
        self.stock_provider = StockDataProvider()

        # API app
        risk_agent = next(
            (a for a in self.agents if isinstance(a, RiskAgent)), None
        )
        self.api_app = create_app(
            executor=self.executor,
            event_bus=self.event_bus,
            risk_agent=risk_agent,
        )

        self._running = False

    async def start(self) -> None:
        """Start the bot and all agents."""
        logger.info("Starting AI Investment Bot")

        try:
            # Start all agents
            for agent in self.agents:
                await agent.start()

            self._running = True

            # Run agent main loops concurrently
            await asyncio.gather(
                *[agent.run() for agent in self.agents],
                return_exceptions=True,
            )

        except Exception as e:
            logger.error("Bot startup error", error=str(e))
            await self.stop()
            raise

    async def stop(self) -> None:
        """Stop the bot and all agents."""
        logger.info("Stopping AI Investment Bot")

        self._running = False

        # Stop all agents
        for agent in self.agents:
            await agent.stop()

        # Clear event bus
        await self.event_bus.clear()

        logger.info("Bot stopped successfully")


def run_api_server(bot) -> None:
    """
    Run FastAPI server in background thread.

    Args:
        bot: Investment bot instance or PaperTradingBot
    """
    # Determine which executor to use
    if isinstance(bot, PaperTradingBot):
        executor = bot.executor
    else:
        executor = bot.executor

    # Determine which event_bus to use
    if isinstance(bot, PaperTradingBot):
        event_bus = bot.event_bus
    else:
        event_bus = bot.event_bus

    # Determine which risk_agent to use
    if isinstance(bot, PaperTradingBot):
        risk_agent = next(
            (a for a in bot.agents if isinstance(a, RiskAgent)), None
        )
    else:
        risk_agent = next(
            (a for a in bot.agents if isinstance(a, RiskAgent)), None
        )

    api_app = create_app(
        executor=executor,
        event_bus=event_bus,
        risk_agent=risk_agent,
    )

    config = uvicorn.Config(
        api_app,
        host="127.0.0.1",
        port=8000,
        log_level="info",
    )
    server = uvicorn.Server(config)
    asyncio.run(server.serve())


async def run_paper_trading_bot(bot_config: Optional[BotConfig] = None) -> None:
    """
    Run paper trading bot with full orchestration.

    Args:
        bot_config: Bot configuration (uses defaults if None)
    """
    if bot_config is None:
        bot_config = BotConfig()

    logger.info("Initializing paper trading bot", mode="orchestrated")

    # Create bot
    bot = PaperTradingBot(settings, bot_config)

    # Start API server in background thread
    api_thread = threading.Thread(
        target=run_api_server, args=(bot,), daemon=True
    )
    api_thread.start()

    logger.info("Dashboard API started at http://127.0.0.1:8000")

    # Run bot lifecycle
    try:
        await bot.execute_bot_lifecycle()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        await bot.stop()
    except Exception as e:
        logger.error("Unhandled error in paper trading bot", error=str(e))
        await bot.stop()
        raise


async def main() -> None:
    """Main entry point."""
    # Setup logging
    setup_logging(settings.logging.log_level)

    logger.info("Initializing AI Investment Bot", paper_trading=settings.trading.paper_trading)

    # Determine which mode to run
    use_orchestrated_bot = True  # Set to False to use legacy bot

    if use_orchestrated_bot:
        # Run new orchestrated paper trading bot
        logger.info("Starting orchestrated paper trading bot")
        await run_paper_trading_bot()
    else:
        # Run legacy bot
        logger.info("Starting legacy investment bot")
        bot = InvestmentBot()

        # Start API server in background thread
        api_thread = threading.Thread(
            target=run_api_server, args=(bot,), daemon=True
        )
        api_thread.start()

        logger.info("Dashboard API started at http://127.0.0.1:8000")

        # Handle graceful shutdown
        def signal_handler(signum, frame):
            logger.info("Shutdown signal received")
            asyncio.create_task(bot.stop())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Run bot
        try:
            await bot.start()
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            await bot.stop()
        except Exception as e:
            logger.error("Unhandled error in main loop", error=str(e))
            await bot.stop()
            sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error("Fatal error", error=str(e))
        sys.exit(1)
