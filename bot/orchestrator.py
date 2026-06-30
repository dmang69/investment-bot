"""Main paper trading bot orchestrator."""

import asyncio
import signal
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional
from execution.order_models import Order, OrderSide
from execution.paper_executor import PaperExecutor
from agents.base_agent import BaseAgent
from agents.regime_agent import MarketRegimeAgent
from agents.crypto_agent import CryptoTradingAgent
from agents.equity_agent import EquityTradingAgent
from agents.risk_agent import RiskAgent
from data.crypto_provider import CryptoDataProvider
from data.stock_provider import StockDataProvider
from strategies.trend_following import TrendFollowingStrategy
from strategies.mean_reversion import MeanReversionStrategy
from core.event_bus import EventBus
from core.logger import get_logger
from config.settings import Settings
from bot.config import BotConfig
from bot.monitor import PortfolioMonitor
from bot.session import TradingSession


logger = get_logger(__name__)


class PaperTradingBot:
    """
    Main orchestrator for paper trading bot.

    Coordinates all agents, strategies, and execution in real-time.
    Manages portfolio state, risk monitoring, and session tracking.
    """

    def __init__(self, config: Settings, bot_config: BotConfig) -> None:
        """
        Initialize the paper trading bot.

        Args:
            config: Global application settings
            bot_config: Bot-specific configuration
        """
        self.config = config
        self.bot_config = bot_config
        self._running = False

        # Initialize core components
        self.event_bus = EventBus()
        self.executor = PaperExecutor(
            initial_cash=bot_config.initial_cash,
            slippage_bps=5.0,
        )

        # Initialize data providers
        self.crypto_provider = CryptoDataProvider()
        self.stock_provider = StockDataProvider()

        # Initialize strategies
        self.strategies = []
        if "trend_following" in bot_config.strategies_to_use:
            self.strategies.append(TrendFollowingStrategy())
            logger.info("trend_following_strategy_initialized")
        if "mean_reversion" in bot_config.strategies_to_use:
            self.strategies.append(MeanReversionStrategy())
            logger.info("mean_reversion_strategy_initialized")

        # Initialize agents
        self.agents: List[BaseAgent] = [
            MarketRegimeAgent(self.event_bus, symbols=bot_config.crypto_symbols + bot_config.stock_symbols),
            CryptoTradingAgent(
                event_bus=self.event_bus,
                data_provider=self.crypto_provider,
                strategies=self.strategies,
                symbols=bot_config.crypto_symbols,
                update_interval=bot_config.crypto_update_interval,
            ),
            EquityTradingAgent(
                event_bus=self.event_bus,
                data_provider=self.stock_provider,
                strategies=self.strategies,
                symbols=bot_config.stock_symbols,
                market_hours_interval=bot_config.equity_update_interval,
            ),
            RiskAgent(
                event_bus=self.event_bus,
                max_drawdown_pct=config.risk.max_drawdown_pct,
                max_position_size_pct=config.risk.max_position_size_pct,
                max_leverage=config.risk.max_leverage,
            ),
        ]

        # Initialize monitoring
        self.monitor = PortfolioMonitor(
            executor=self.executor,
            event_bus=self.event_bus,
            config=config,
            initial_equity=bot_config.initial_cash,
        )

        # Initialize session tracking
        self.session = TradingSession()
        self.session.set_initial_state(bot_config.initial_cash)

        # State tracking
        self._kill_switch_triggered = False
        self._signal_received = False

    @property
    def running(self) -> bool:
        """Check if bot is running."""
        return self._running

    async def start(self) -> None:
        """
        Start the bot and all components.

        Initializes all agents, subscribes to events, and begins main loop.
        """
        logger.info(
            "starting_paper_trading_bot",
            initial_cash=self.bot_config.initial_cash,
            crypto_symbols=self.bot_config.crypto_symbols,
            stock_symbols=self.bot_config.stock_symbols,
            strategies=self.bot_config.strategies_to_use,
        )

        try:
            # Start all agents
            for agent in self.agents:
                await agent.start()
                logger.info("agent_started", agent=agent.name)

            # Subscribe to critical events
            await self.event_bus.subscribe("kill_switch", self._on_kill_switch)
            await self.event_bus.subscribe("crypto_signal", self._on_crypto_signal)
            await self.event_bus.subscribe("equity_signal", self._on_equity_signal)
            await self.event_bus.subscribe("signal_approved", self._on_signal_approved)
            await self.event_bus.subscribe("trade_executed", self._on_trade_executed)

            self._running = True
            logger.info("paper_trading_bot_started_successfully")

        except Exception as e:
            logger.error("bot_startup_failed", error=str(e))
            await self.stop()
            raise

    async def stop(self) -> None:
        """
        Stop the bot gracefully.

        Stops all agents, finalizes session, and generates report.
        """
        logger.info("stopping_paper_trading_bot")
        self._running = False

        try:
            # Stop all agents
            for agent in self.agents:
                await agent.stop()
                logger.info("agent_stopped", agent=agent.name)

            # Clear event bus
            await self.event_bus.clear()

            # End session
            self.session.end_session()

            # Generate and log final report
            report = self.session.generate_session_report()
            logger.info("session_report", report=report)

            logger.info("paper_trading_bot_stopped_successfully")

        except Exception as e:
            logger.error("bot_shutdown_error", error=str(e))

    async def run(self) -> None:
        """
        Main coordination loop.

        Monitors portfolio, manages risk, and handles events until stopped.
        """
        logger.info("entering_main_coordination_loop")

        monitor_interval = self.bot_config.portfolio_monitor_interval

        try:
            while self._running and not self._kill_switch_triggered:
                # Monitor portfolio
                metrics = await self.monitor.monitor_portfolio()

                if metrics:
                    logger.debug(
                        "portfolio_metrics",
                        equity=metrics.equity,
                        cash=metrics.cash,
                        positions=metrics.total_positions,
                        return_pct=metrics.return_pct,
                    )

                # Sleep before next monitoring cycle
                await asyncio.sleep(monitor_interval)

        except asyncio.CancelledError:
            logger.info("main_loop_cancelled")
        except Exception as e:
            logger.error("main_loop_error", error=str(e))
        finally:
            if self._kill_switch_triggered:
                logger.critical("kill_switch_triggered_halting_all_trading")

    async def _on_crypto_signal(self, topic: str, payload: Dict[str, Any]) -> None:
        """
        Handle crypto trading signals.

        Args:
            topic: Event topic
            payload: Signal payload
        """
        try:
            symbol = payload.get("symbol")
            signal = payload.get("signal")

            logger.info(
                "crypto_signal_received",
                symbol=symbol,
                action=signal.action,
                confidence=signal.confidence,
            )

            # Only process BUY/SELL signals
            if signal.action != "HOLD":
                await self._validate_and_execute_signal(symbol, signal)

        except Exception as e:
            logger.error("crypto_signal_processing_error", error=str(e))

    async def _on_equity_signal(self, topic: str, payload: Dict[str, Any]) -> None:
        """
        Handle equity trading signals.

        Args:
            topic: Event topic
            payload: Signal payload
        """
        try:
            symbol = payload.get("symbol")
            signal = payload.get("signal")

            logger.info(
                "equity_signal_received",
                symbol=symbol,
                action=signal.action,
                confidence=signal.confidence,
            )

            # Only process BUY/SELL signals
            if signal.action != "HOLD":
                await self._validate_and_execute_signal(symbol, signal)

        except Exception as e:
            logger.error("equity_signal_processing_error", error=str(e))

    async def _validate_and_execute_signal(
        self, symbol: str, signal
    ) -> None:
        """
        Validate signal via risk agent and execute.

        Args:
            symbol: Trading symbol
            signal: Trading signal to validate
        """
        try:
            # Get current portfolio state
            portfolio = await self.executor.get_portfolio()

            # Create Signal object for risk validation
            from agents.risk_agent import Signal as RiskSignal, Portfolio as RiskPortfolio

            # Estimate position size (conservative approach)
            position_size = (
                portfolio.cash * 0.05 / signal.confidence
                if signal.confidence > 0
                else 0
            )

            risk_signal = RiskSignal(
                symbol=symbol,
                action=signal.action,
                quantity=position_size,
                entry_price=1.0,  # Will be adjusted by current price
                metadata={"confidence": signal.confidence},
            )

            risk_portfolio = RiskPortfolio(
                cash=portfolio.cash,
                positions={p.symbol: p.quantity for p in await self.executor.get_positions()},
                entry_prices={
                    p.symbol: p.entry_price for p in await self.executor.get_positions()
                },
                timestamp=datetime.utcnow(),
            )

            # Publish for risk validation
            await self.event_bus.publish(
                "trading_signal",
                {
                    "signal": risk_signal,
                    "portfolio": risk_portfolio,
                },
            )

        except Exception as e:
            logger.error(
                "signal_validation_error",
                symbol=symbol,
                error=str(e),
            )

    async def _on_signal_approved(self, topic: str, payload: Dict[str, Any]) -> None:
        """
        Execute approved trading signals.

        Args:
            topic: Event topic
            payload: Approval payload with signal
        """
        try:
            signal = payload.get("signal")
            symbol = signal.symbol
            action = signal.action
            quantity = signal.quantity

            if quantity <= 0:
                logger.warning("invalid_quantity", symbol=symbol, quantity=quantity)
                return

            # Get current price (simplified - use entry_price from signal)
            current_price = signal.entry_price

            # Create order
            order = Order(
                symbol=symbol,
                side=OrderSide.BUY if action == "BUY" else OrderSide.SELL,
                quantity=quantity,
                limit_price=current_price,
            )

            logger.info(
                "executing_approved_signal",
                symbol=symbol,
                action=action,
                quantity=quantity,
                price=current_price,
            )

            # Execute order
            fill = await self.executor.place_order(order)

            # Record trade in session
            self.session.record_trade(
                symbol=symbol,
                side=action,
                quantity=quantity,
                price=fill.fill_price,
                commission=fill.commission,
                order_id=fill.order_id,
            )

            # Emit execution event
            await self.event_bus.publish(
                "trade_executed",
                {
                    "symbol": symbol,
                    "side": action,
                    "quantity": quantity,
                    "fill_price": fill.fill_price,
                    "timestamp": fill.fill_timestamp,
                    "order_id": fill.order_id,
                },
            )

        except Exception as e:
            logger.error(
                "signal_execution_error",
                error=str(e),
            )

    async def _on_trade_executed(self, topic: str, payload: Dict[str, Any]) -> None:
        """
        Handle executed trades for tracking.

        Args:
            topic: Event topic
            payload: Trade execution payload
        """
        try:
            symbol = payload.get("symbol")
            side = payload.get("side")
            quantity = payload.get("quantity")
            fill_price = payload.get("fill_price")

            logger.info(
                "trade_execution_confirmed",
                symbol=symbol,
                side=side,
                quantity=quantity,
                fill_price=fill_price,
            )

        except Exception as e:
            logger.error("trade_execution_tracking_error", error=str(e))

    async def _on_kill_switch(self, topic: str, payload: Dict[str, Any]) -> None:
        """
        Handle kill switch event (halt trading).

        Args:
            topic: Event topic
            payload: Kill switch payload
        """
        reason = payload.get("reason", "unknown")
        logger.critical("kill_switch_activated", reason=reason)
        self._kill_switch_triggered = True
        await self.stop()

    async def _setup_signal_handlers(self) -> None:
        """Setup SIGINT/SIGTERM handlers for graceful shutdown."""

        def signal_handler(signum, frame):
            logger.info("shutdown_signal_received", signal=signum)
            self._signal_received = True
            asyncio.create_task(self.stop())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def execute_bot_lifecycle(self) -> None:
        """
        Execute complete bot lifecycle: start, run, stop.

        This is the main entry point for running the bot.
        """
        await self._setup_signal_handlers()

        try:
            # Start bot
            await self.start()

            # Run main loop
            await self.run()

        except KeyboardInterrupt:
            logger.info("keyboard_interrupt_received")
            await self.stop()
        except Exception as e:
            logger.error("unhandled_error", error=str(e))
            await self.stop()
            raise
