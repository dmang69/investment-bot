"""Equity trading agent with market hours awareness."""

import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime, time
import pytz
from dataclasses import dataclass
from data.models import OHLCV
from data.stock_provider import StockDataProvider
from strategies.base_strategy import BaseStrategy, Signal
from agents.base_agent import BaseAgent
from core.logger import get_logger
from core.event_bus import EventBus
from core.exceptions import DataError


logger = get_logger(__name__)

# US Market hours (Eastern Time)
MARKET_OPEN = time(9, 30)  # 9:30 AM ET
MARKET_CLOSE = time(16, 0)  # 4:00 PM ET
US_TIMEZONE = pytz.timezone("US/Eastern")


@dataclass
class StrategyWeights:
    """Strategy weights by market regime."""

    trend_following: float = 0.5
    mean_reversion: float = 0.5


class EquityTradingAgent(BaseAgent):
    """
    Equity market trading agent with market hours awareness.

    Features:
    - Only trades during US market hours (9:30 AM - 4:00 PM ET)
    - Subscribes to regime_change events from RegimeAgent
    - Fetches data at intervals adjusted for market status
    - Applies multiple strategies with weighted aggregation
    - Generates trading signals with confidence scores
    - Adjusts strategy weights based on market regime
    """

    def __init__(
        self,
        event_bus: EventBus,
        data_provider: StockDataProvider,
        strategies: List[BaseStrategy],
        symbols: List[str] = None,
        market_hours_interval: int = 60,
        after_hours_interval: int = 300,
    ) -> None:
        """
        Initialize the equity trading agent.

        Args:
            event_bus: Event bus for communication
            data_provider: StockDataProvider for data fetching
            strategies: List of trading strategies to apply
            symbols: List of stock symbols to trade (default: AAPL, MSFT, GOOG)
            market_hours_interval: Seconds between updates during market hours (default: 60)
            after_hours_interval: Seconds between updates outside market hours (default: 300)
        """
        super().__init__()
        self.event_bus = event_bus
        self.data_provider = data_provider
        self.strategies = strategies
        self.symbols = symbols or ["AAPL", "MSFT", "GOOG"]
        self.market_hours_interval = market_hours_interval
        self.after_hours_interval = after_hours_interval

        # State management
        self._current_regime: Dict[str, str] = {}
        self._strategy_weights: Dict[str, StrategyWeights] = {
            sym: StrategyWeights() for sym in self.symbols
        }
        self._ohlcv_cache: Dict[str, List[OHLCV]] = {}

    @property
    def name(self) -> str:
        """Get agent name."""
        return "EquityTradingAgent"

    def _is_market_hours(self) -> bool:
        """
        Check if US stock market is currently open.

        Returns:
            True if market is open (Mon-Fri 9:30 AM - 4:00 PM ET), False otherwise
        """
        now = datetime.now(US_TIMEZONE)

        # Check if weekday (0=Monday, 4=Friday)
        if now.weekday() > 4:  # Saturday=5, Sunday=6
            return False

        # Check if within market hours
        current_time = now.time()
        return MARKET_OPEN <= current_time < MARKET_CLOSE

    def _adjust_weights_by_regime(self, regime: str) -> StrategyWeights:
        """
        Adjust strategy weights based on market regime.

        Args:
            regime: Market regime (TRENDING_UP, TRENDING_DOWN, CHOPPY, etc.)

        Returns:
            StrategyWeights with adjusted allocation
        """
        if regime == "TRENDING_UP" or regime == "TRENDING_DOWN":
            # Trend-following heavier in trending markets
            return StrategyWeights(trend_following=0.7, mean_reversion=0.3)
        elif regime == "CHOPPY":
            # Mean-reversion better in choppy/range-bound markets
            return StrategyWeights(trend_following=0.3, mean_reversion=0.7)
        elif regime == "HIGH_VOL":
            # Both useful in high volatility
            return StrategyWeights(trend_following=0.5, mean_reversion=0.5)
        elif regime == "LOW_VOL":
            # Mean-reversion in low volatility
            return StrategyWeights(trend_following=0.4, mean_reversion=0.6)
        else:
            # Default balanced
            return StrategyWeights(trend_following=0.5, mean_reversion=0.5)

    async def _aggregate_signals(
        self, symbol: str, signals: List[Signal]
    ) -> Signal:
        """
        Aggregate multiple strategy signals into one.

        Args:
            symbol: Trading symbol
            signals: List of signals from different strategies

        Returns:
            Aggregated signal
        """
        if not signals:
            return Signal(
                symbol=symbol,
                action="HOLD",
                confidence=0.0,
                metadata={"reason": "no_signals"},
            )

        # Get strategy weights for current regime
        regime = self._current_regime.get(symbol, "CHOPPY")
        weights = self._adjust_weights_by_regime(regime)

        # Map strategies to names for weight lookup
        strategy_names = []
        for strategy in self.strategies:
            strategy_name = strategy.__class__.__name__.lower()
            if "trend" in strategy_name:
                strategy_names.append("trend_following")
            elif "reversion" in strategy_name or "mean" in strategy_name:
                strategy_names.append("mean_reversion")
            else:
                strategy_names.append(strategy_name)

        # Aggregate signals with weights
        weighted_buy_confidence = 0.0
        weighted_sell_confidence = 0.0
        total_weight = 0.0

        for i, signal in enumerate(signals):
            strategy_name = strategy_names[i] if i < len(strategy_names) else "unknown"

            if strategy_name == "trend_following":
                weight = weights.trend_following
            elif strategy_name == "mean_reversion":
                weight = weights.mean_reversion
            else:
                weight = 0.5

            if signal.action == "BUY":
                weighted_buy_confidence += signal.confidence * weight
            elif signal.action == "SELL":
                weighted_sell_confidence += signal.confidence * weight

            total_weight += weight

        # Normalize by total weight
        if total_weight > 0:
            weighted_buy_confidence /= total_weight
            weighted_sell_confidence /= total_weight

        # Determine aggregated action
        if weighted_buy_confidence > weighted_sell_confidence and weighted_buy_confidence > 0.3:
            action = "BUY"
            confidence = weighted_buy_confidence
        elif weighted_sell_confidence > weighted_buy_confidence and weighted_sell_confidence > 0.3:
            action = "SELL"
            confidence = weighted_sell_confidence
        else:
            action = "HOLD"
            confidence = 0.0

        return Signal(
            symbol=symbol,
            action=action,
            confidence=confidence,
            metadata={
                "aggregation": "weighted_average",
                "regime": regime,
                "weights": {
                    "trend_following": weights.trend_following,
                    "mean_reversion": weights.mean_reversion,
                },
                "buy_confidence": weighted_buy_confidence,
                "sell_confidence": weighted_sell_confidence,
            },
        )

    async def _fetch_and_analyze(self, symbols: List[str]) -> None:
        """
        Fetch fresh data and generate signals for symbols.

        Args:
            symbols: List of symbols to analyze
        """
        for symbol in symbols:
            try:
                # Fetch fresh OHLCV data
                logger.debug("fetching_data", symbol=symbol)
                ohlcv_data = await self.data_provider.fetch_ohlcv(
                    symbol, timeframe="1h", limit=100
                )

                if not ohlcv_data:
                    logger.warning("no_ohlcv_data", symbol=symbol)
                    continue

                # Cache data
                self._ohlcv_cache[symbol] = ohlcv_data

                # Generate signals from each strategy
                signals: List[Signal] = []
                for strategy in self.strategies:
                    try:
                        signal = await strategy.generate_signal(ohlcv_data)
                        signals.append(signal)
                        logger.debug(
                            "strategy_signal",
                            symbol=symbol,
                            strategy=strategy.__class__.__name__,
                            action=signal.action,
                            confidence=signal.confidence,
                        )
                    except Exception as e:
                        logger.warning(
                            "strategy_signal_error",
                            symbol=symbol,
                            strategy=strategy.__class__.__name__,
                            error=str(e),
                        )
                        continue

                # Aggregate signals
                aggregated_signal = await self._aggregate_signals(symbol, signals)

                # Only emit non-HOLD signals or high confidence signals
                if aggregated_signal.action != "HOLD" or aggregated_signal.confidence > 0.7:
                    logger.info(
                        "equity_signal_generated",
                        symbol=symbol,
                        action=aggregated_signal.action,
                        confidence=aggregated_signal.confidence,
                    )

                    # Emit signal event
                    await self.event_bus.publish(
                        "equity_signal",
                        {
                            "symbol": symbol,
                            "signal": aggregated_signal,
                            "timestamp": ohlcv_data[-1].timestamp if ohlcv_data else None,
                        },
                    )

            except DataError as e:
                logger.warning(
                    "data_fetch_error",
                    symbol=symbol,
                    error=str(e),
                )
                continue
            except Exception as e:
                logger.error(
                    "signal_generation_error",
                    symbol=symbol,
                    error=str(e),
                )
                continue

    async def run(self) -> None:
        """
        Main agent loop - fetch data during market hours and generate signals.

        Updates equity signals more frequently during market hours,
        less frequently outside market hours. Stops updating completely on weekends.
        """
        logger.info(
            f"{self.name} started",
            symbols=self.symbols,
            market_hours_interval=self.market_hours_interval,
            after_hours_interval=self.after_hours_interval,
            num_strategies=len(self.strategies),
        )

        # Subscribe to regime changes
        await self.event_bus.subscribe("regime_change", self.on_event)

        try:
            while self._running:
                # Check market hours
                is_market_open = self._is_market_hours()

                if is_market_open:
                    # Update more frequently during market hours
                    await self._fetch_and_analyze(self.symbols)
                    await asyncio.sleep(self.market_hours_interval)
                else:
                    # Update less frequently outside market hours
                    logger.debug("market_closed", next_check=self.after_hours_interval)
                    await asyncio.sleep(self.after_hours_interval)

        except asyncio.CancelledError:
            logger.info(f"{self.name} cancelled")
        except Exception as e:
            logger.error(f"Error in {self.name}", error=str(e))

    async def on_event(self, topic: str, payload: Any) -> None:
        """
        Handle incoming events, primarily regime changes.

        Args:
            topic: Event topic
            payload: Event payload with regime information
        """
        if topic == "regime_change":
            symbol = payload.get("symbol")
            regime = payload.get("regime")

            if symbol and regime:
                self._current_regime[symbol] = regime
                logger.info(
                    "regime_updated",
                    symbol=symbol,
                    regime=regime,
                )

                # Adjust strategy weights for this symbol
                weights = self._adjust_weights_by_regime(regime)
                self._strategy_weights[symbol] = weights
                logger.debug(
                    "weights_adjusted",
                    symbol=symbol,
                    trend_following=weights.trend_following,
                    mean_reversion=weights.mean_reversion,
                )
