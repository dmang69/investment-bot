"""Quick integration verification for AI Investment Bot."""

import asyncio
import sys
from datetime import datetime

# Verify imports
try:
    from config.settings import settings
    from core.logger import get_logger, setup_logging
    from core.event_bus import EventBus
    from execution.paper_executor import PaperExecutor
    from bot.orchestrator import PaperTradingBot
    from bot.config import BotConfig
    from dashboard.api import create_app
    
    print("✅ All imports successful")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

logger = get_logger(__name__)

async def verify_components():
    """Verify all components initialize correctly."""
    
    print("\n" + "="*70)
    print("AI INVESTMENT BOT - INTEGRATION VERIFICATION")
    print("="*70 + "\n")
    
    # 1. Verify settings
    print("[1] Verifying Settings...")
    try:
        assert settings is not None
        print(f"    ✅ Settings loaded")
        print(f"       - Paper Trading: {settings.trading.paper_trading}")
        print(f"       - Initial Cash: ${settings.trading.initial_cash:,.2f}")
        print(f"       - Max Drawdown: {settings.risk.max_drawdown_pct}%")
    except Exception as e:
        print(f"    ❌ Settings error: {e}")
        return False
    
    # 2. Verify logging
    print("\n[2] Verifying Logging...")
    try:
        setup_logging()
        logger.info("Logging system initialized")
        print(f"    ✅ Logging configured")
    except Exception as e:
        print(f"    ❌ Logging error: {e}")
        return False
    
    # 3. Verify EventBus
    print("\n[3] Verifying EventBus...")
    try:
        event_bus = EventBus()
        
        # Test event subscription and publishing
        received_events = []
        
        async def test_handler(topic: str, payload: dict):
            received_events.append({"topic": topic, "payload": payload})
        
        await event_bus.subscribe("test_topic", test_handler)
        await event_bus.publish("test_topic", {"test": "data"})
        
        # Give it a moment to process
        await asyncio.sleep(0.1)
        
        assert len(received_events) == 1
        print(f"    ✅ EventBus working")
        print(f"       - Published and received events successfully")
    except Exception as e:
        print(f"    ❌ EventBus error: {e}")
        return False
    
    # 4. Verify PaperExecutor
    print("\n[4] Verifying PaperExecutor...")
    try:
        executor = PaperExecutor()
        portfolio = await executor.get_portfolio()
        assert portfolio is not None
        assert portfolio.cash > 0
        print(f"    ✅ PaperExecutor working")
        print(f"       - Initial Cash: ${portfolio.cash:,.2f}")
        print(f"       - Total Value: ${portfolio.total_value:,.2f}")
    except Exception as e:
        print(f"    ❌ PaperExecutor error: {e}")
        return False
    
    # 5. Verify Bot Configuration
    print("\n[5] Verifying BotConfig...")
    try:
        bot_config = BotConfig()
        assert len(bot_config.crypto_symbols) > 0
        assert len(bot_config.stock_symbols) > 0
        print(f"    ✅ BotConfig loaded")
        print(f"       - Crypto Symbols: {', '.join(bot_config.crypto_symbols)}")
        print(f"       - Stock Symbols: {', '.join(bot_config.stock_symbols)}")
        print(f"       - Strategies: {', '.join(bot_config.strategies_to_use)}")
    except Exception as e:
        print(f"    ❌ BotConfig error: {e}")
        return False
    
    # 6. Verify PaperTradingBot Initialization
    print("\n[6] Verifying PaperTradingBot...")
    try:
        bot = PaperTradingBot(settings, bot_config)
        assert bot is not None
        assert len(bot.agents) > 0
        assert bot.executor is not None
        assert bot.monitor is not None
        assert bot.session is not None
        print(f"    ✅ PaperTradingBot initialized")
        print(f"       - Agents: {len(bot.agents)}")
        for agent in bot.agents:
            print(f"         • {agent.name}")
        print(f"       - Monitor: {bot.monitor.__class__.__name__}")
        print(f"       - Session: {bot.session.__class__.__name__}")
    except Exception as e:
        print(f"    ❌ PaperTradingBot error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 7. Verify Dashboard API
    print("\n[7] Verifying Dashboard API...")
    try:
        app = create_app(
            executor=executor,
            event_bus=event_bus,
            risk_agent=None,
            bot=bot,
        )
        assert app is not None
        # Check that endpoints are registered
        routes = [route.path for route in app.routes]
        assert "/health" in routes
        assert "/portfolio" in routes
        assert "/risk" in routes
        assert "/signals" in routes
        print(f"    ✅ Dashboard API created")
        print(f"       - Routes registered: {len(routes)}")
        print(f"       - Key endpoints: /health, /portfolio, /risk, /signals")
    except Exception as e:
        print(f"    ❌ Dashboard API error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


async def main():
    """Run verification."""
    try:
        success = await verify_components()
        
        if success:
            print("\n" + "="*70)
            print("✅ ALL COMPONENTS VERIFIED - BOT IS READY FOR OPERATION")
            print("="*70)
            print("\n📍 Next Steps:")
            print("   1. Start bot: python main.py")
            print("   2. Open dashboard: http://127.0.0.1:8000")
            print("   3. Monitor trading activity")
            print("   4. Use API endpoints to control bot")
            print("\n")
            return 0
        else:
            print("\n" + "="*70)
            print("❌ VERIFICATION FAILED - CHECK ERRORS ABOVE")
            print("="*70 + "\n")
            return 1
            
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
