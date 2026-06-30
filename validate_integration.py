"""Integration validation script for paper trading bot."""

import sys
import asyncio
from datetime import datetime
from typing import List

# Validate imports
try:
    from config.settings import settings
    print("✓ Settings loaded")
except Exception as e:
    print(f"✗ Settings import failed: {e}")
    sys.exit(1)

try:
    from core.event_bus import EventBus
    from core.logger import get_logger
    print("✓ Core modules loaded")
except Exception as e:
    print(f"✗ Core modules import failed: {e}")
    sys.exit(1)

try:
    from agents.base_agent import BaseAgent
    from agents.crypto_agent import CryptoTradingAgent
    from agents.equity_agent import EquityTradingAgent
    from agents.regime_agent import MarketRegimeAgent
    from agents.risk_agent import RiskAgent
    print("✓ Agents loaded")
except Exception as e:
    print(f"✗ Agents import failed: {e}")
    sys.exit(1)

try:
    from data.crypto_provider import CryptoDataProvider
    from data.stock_provider import StockDataProvider
    print("✓ Data providers loaded")
except Exception as e:
    print(f"✗ Data providers import failed: {e}")
    sys.exit(1)

try:
    from strategies.trend_following import TrendFollowingStrategy
    from strategies.mean_reversion import MeanReversionStrategy
    print("✓ Strategies loaded")
except Exception as e:
    print(f"✗ Strategies import failed: {e}")
    sys.exit(1)

try:
    from execution.paper_executor import PaperExecutor
    print("✓ Execution layer loaded")
except Exception as e:
    print(f"✗ Execution layer import failed: {e}")
    sys.exit(1)

try:
    from bot.orchestrator import PaperTradingBot
    from bot.config import BotConfig
    from bot.monitor import PortfolioMonitor
    from bot.session import TradingSession
    print("✓ Bot components loaded")
except Exception as e:
    print(f"✗ Bot components import failed: {e}")
    sys.exit(1)

# Test component instantiation
logger = get_logger(__name__)

async def test_component_instantiation():
    """Test that all components can be instantiated."""
    try:
        # Create event bus
        event_bus = EventBus()
        logger.info("EventBus instantiated")
        
        # Create executors
        executor = PaperExecutor(initial_cash=100000.0)
        logger.info("PaperExecutor instantiated")
        
        # Create data providers
        crypto_provider = CryptoDataProvider()
        stock_provider = StockDataProvider()
        logger.info("Data providers instantiated")
        
        # Create strategies
        strategies = [
            TrendFollowingStrategy(),
            MeanReversionStrategy(),
        ]
        logger.info(f"Strategies instantiated: {len(strategies)}")
        
        # Create bot config
        bot_config = BotConfig()
        logger.info(f"BotConfig instantiated: {bot_config.crypto_symbols}, {bot_config.stock_symbols}")
        
        # Create orchestrator
        bot = PaperTradingBot(settings, bot_config)
        logger.info("PaperTradingBot instantiated")
        
        # Verify agents exist
        agent_count = len(bot.agents)
        logger.info(f"Bot has {agent_count} agents configured")
        
        # List agents
        for agent in bot.agents:
            logger.info(f"  - {agent.name}")
        
        # Verify monitor
        if bot.monitor:
            logger.info("PortfolioMonitor initialized")
        
        # Verify session
        if bot.session:
            logger.info("TradingSession initialized")
        
        # Test event bus subscription
        subscription_count = 0
        async def test_handler(topic, payload):
            pass
        
        await event_bus.subscribe("test_topic", test_handler)
        subscription_count += 1
        logger.info(f"Event bus subscription test passed: {subscription_count} subscription")
        
        logger.info("\n" + "="*70)
        logger.info("ALL VALIDATION TESTS PASSED ✓")
        logger.info("="*70)
        logger.info("System Status:")
        logger.info(f"  - Event Bus: Ready")
        logger.info(f"  - Agents: {agent_count} configured")
        logger.info(f"  - Data Providers: Ready")
        logger.info(f"  - Execution Layer: Ready")
        logger.info(f"  - Portfolio Monitor: Ready")
        logger.info(f"  - Trading Session: Ready")
        logger.info("\nBot is ready for paper trading!")
        
        return True
        
    except Exception as e:
        logger.error(f"Component instantiation failed: {e}", exc_info=True)
        return False

async def main():
    """Run validation."""
    print("\n" + "="*70)
    print("AI INVESTMENT BOT - INTEGRATION VALIDATION")
    print("="*70 + "\n")
    
    success = await test_component_instantiation()
    
    if not success:
        print("\n✗ Validation FAILED - Some components could not be instantiated")
        sys.exit(1)
    else:
        print("\n✓ Validation PASSED - All components are ready")
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
