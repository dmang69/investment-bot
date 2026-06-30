"""Integration test for paper trading bot orchestration."""

import asyncio
import sys
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

# Add project to path
sys.path.insert(0, '.')

from config.settings import settings
from bot.config import BotConfig
from bot.orchestrator import PaperTradingBot
from agents.crypto_agent import CryptoTradingAgent
from agents.equity_agent import EquityTradingAgent
from core.logger import setup_logging, get_logger


logger = get_logger(__name__)


async def test_bot_initialization() -> bool:
    """Test bot initialization."""
    logger.info("Testing bot initialization...")
    try:
        bot_config = BotConfig(
            crypto_symbols=["BTC/USDT"],
            stock_symbols=["AAPL"],
            initial_cash=50000.0,
        )
        
        bot = PaperTradingBot(settings, bot_config)
        
        assert bot.bot_config.initial_cash == 50000.0
        assert "BTC/USDT" in bot.bot_config.crypto_symbols
        assert len(bot.agents) == 4  # regime, crypto, equity, risk
        assert bot.executor is not None
        assert bot.monitor is not None
        assert bot.session is not None
        
        logger.info("✓ Bot initialization test passed")
        return True
    except Exception as e:
        logger.error("✗ Bot initialization test failed", error=str(e))
        return False


async def test_agent_initialization() -> bool:
    """Test agent initialization."""
    logger.info("Testing agent initialization...")
    try:
        from core.event_bus import EventBus
        from strategies.trend_following import TrendFollowingStrategy
        from data.crypto_provider import CryptoDataProvider
        
        event_bus = EventBus()
        crypto_provider = CryptoDataProvider()
        strategies = [TrendFollowingStrategy()]
        
        crypto_agent = CryptoTradingAgent(
            event_bus=event_bus,
            data_provider=crypto_provider,
            strategies=strategies,
            symbols=["BTC/USDT"],
            update_interval=60,
        )
        
        assert crypto_agent.name == "CryptoTradingAgent"
        assert crypto_agent.symbols == ["BTC/USDT"]
        assert len(crypto_agent.strategies) == 1
        
        logger.info("✓ Agent initialization test passed")
        return True
    except Exception as e:
        logger.error("✗ Agent initialization test failed", error=str(e))
        return False


async def test_signal_aggregation() -> bool:
    """Test signal aggregation logic."""
    logger.info("Testing signal aggregation...")
    try:
        from core.event_bus import EventBus
        from strategies.trend_following import TrendFollowingStrategy
        from strategies.base_strategy import Signal
        from data.crypto_provider import CryptoDataProvider
        
        event_bus = EventBus()
        crypto_provider = CryptoDataProvider()
        strategies = [TrendFollowingStrategy()]
        
        crypto_agent = CryptoTradingAgent(
            event_bus=event_bus,
            data_provider=crypto_provider,
            strategies=strategies,
        )
        
        # Create test signals
        test_signals = [
            Signal(
                symbol="BTC/USDT",
                action="BUY",
                confidence=0.8,
                metadata={"test": True},
            ),
        ]
        
        aggregated = await crypto_agent._aggregate_signals("BTC/USDT", test_signals)
        
        assert aggregated.symbol == "BTC/USDT"
        assert aggregated.action == "BUY"
        assert aggregated.confidence > 0.0
        
        logger.info("✓ Signal aggregation test passed")
        return True
    except Exception as e:
        logger.error("✗ Signal aggregation test failed", error=str(e))
        return False


async def test_equity_market_hours() -> bool:
    """Test equity market hours detection."""
    logger.info("Testing equity market hours detection...")
    try:
        from core.event_bus import EventBus
        from strategies.trend_following import TrendFollowingStrategy
        from data.stock_provider import StockDataProvider
        
        event_bus = EventBus()
        stock_provider = StockDataProvider()
        strategies = [TrendFollowingStrategy()]
        
        equity_agent = EquityTradingAgent(
            event_bus=event_bus,
            data_provider=stock_provider,
            strategies=strategies,
        )
        
        # Test market hours check (may be outside market hours)
        is_open = equity_agent._is_market_hours()
        assert isinstance(is_open, bool)
        
        logger.info("✓ Equity market hours test passed")
        return True
    except Exception as e:
        logger.error("✗ Equity market hours test failed", error=str(e))
        return False


async def test_portfolio_monitor() -> bool:
    """Test portfolio monitor initialization."""
    logger.info("Testing portfolio monitor...")
    try:
        from execution.paper_executor import PaperExecutor
        from core.event_bus import EventBus
        from bot.monitor import PortfolioMonitor
        
        executor = PaperExecutor(initial_cash=100000.0)
        event_bus = EventBus()
        monitor = PortfolioMonitor(
            executor=executor,
            event_bus=event_bus,
            config=settings,
            initial_equity=100000.0,
        )
        
        assert monitor.initial_equity == 100000.0
        assert monitor.peak_equity == 100000.0
        
        logger.info("✓ Portfolio monitor test passed")
        return True
    except Exception as e:
        logger.error("✗ Portfolio monitor test failed", error=str(e))
        return False


async def test_trading_session() -> bool:
    """Test trading session tracking."""
    logger.info("Testing trading session...")
    try:
        from bot.session import TradingSession, TradeRecord
        from datetime import datetime
        
        session = TradingSession()
        session.set_initial_state(100000.0)
        
        # Record a trade
        session.record_trade(
            symbol="BTC/USDT",
            side="BUY",
            quantity=1.0,
            price=50000.0,
            commission=50.0,
        )
        
        # Get stats
        stats = session.get_session_stats()
        
        assert stats["total_trades"] == 1
        assert stats["buy_trades"] == 1
        assert stats["sell_trades"] == 0
        assert stats["total_commission"] == 50.0
        
        logger.info("✓ Trading session test passed")
        return True
    except Exception as e:
        logger.error("✗ Trading session test failed", error=str(e))
        return False


async def test_bot_config() -> bool:
    """Test bot configuration."""
    logger.info("Testing bot configuration...")
    try:
        from bot.config import BotConfig
        
        config = BotConfig(
            crypto_symbols=["BTC/USDT", "ETH/USDT"],
            stock_symbols=["AAPL", "MSFT"],
            initial_cash=250000.0,
            strategies_to_use=["trend_following"],
        )
        
        assert config.initial_cash == 250000.0
        assert len(config.crypto_symbols) == 2
        assert len(config.stock_symbols) == 2
        assert len(config.strategies_to_use) == 1
        
        logger.info("✓ Bot configuration test passed")
        return True
    except Exception as e:
        logger.error("✗ Bot configuration test failed", error=str(e))
        return False


async def run_all_tests() -> int:
    """Run all integration tests."""
    setup_logging("INFO")
    
    logger.info("="*70)
    logger.info("PAPER TRADING BOT ORCHESTRATION TESTS")
    logger.info("="*70)
    
    tests = [
        test_bot_config,
        test_bot_initialization,
        test_agent_initialization,
        test_signal_aggregation,
        test_equity_market_hours,
        test_portfolio_monitor,
        test_trading_session,
    ]
    
    results = []
    for test in tests:
        try:
            result = await test()
            results.append(result)
        except Exception as e:
            logger.error(f"Unexpected error in {test.__name__}", error=str(e))
            results.append(False)
    
    logger.info("="*70)
    passed = sum(results)
    total = len(results)
    logger.info(f"RESULTS: {passed}/{total} tests passed")
    logger.info("="*70)
    
    return 0 if all(results) else 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
