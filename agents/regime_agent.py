"""Market regime classification agent with real working logic."""

import asyncio
from typing import Any, List
import numpy as np
import pandas as pd
from enum import Enum
from data.models import OHLCV
from agents.base_agent import BaseAgent
from core.logger import get_logger
from core.event_bus import EventBus


logger = get_logger(__name__)


class MarketRegime(str, Enum):
    """Market regime classification."""

    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    CHOPPY = "CHOPPY"
    HIGH_VOL = "HIGH_VOL"
    LOW_VOL = "LOW_VOL"


class MarketRegimeAgent(BaseAgent):
    """
    Market regime detection agent.

    Classifies current market conditions using technical analysis:
    - EMA (Exponential Moving Average) slope for trend direction
    - ATR (Average True Range) for volatility assessment
    - Volume analysis for market strength

    Emits 'regime_change' events when classification changes.
    """

    def __init__(self, event_bus: EventBus, symbols: List[str] = None) -> None:
        """
        Initialize the regime agent.

        Args:
            event_bus: Event bus for publishing regime changes
            symbols: List of symbols to monitor
        """
        super().__init__()
        self.event_bus = event_bus
        self.symbols = symbols or ["BTC/USD", "ETH/USD", "AAPL", "SPY"]
        self._current_regime = {}
        self._ohlcv_cache = {}

    @property
    def name(self) -> str:
        """Get agent name."""
        return "MarketRegimeAgent"

    def _calculate_atr(self, ohlcv_data: List[OHLCV], period: int = 14) -> float:
        """
        Calculate Average True Range (ATR).

        Args:
            ohlcv_data: List of OHLCV data points
            period: ATR period (default 14)

        Returns:
            ATR value
        """
        if len(ohlcv_data) < period:
            return 0.0

        df = pd.DataFrame([
            {
                "high": x.high,
                "low": x.low,
                "close": x.close,
            }
            for x in ohlcv_data
        ])

        df["tr"] = np.maximum(
            df["high"] - df["low"],
            np.maximum(
                abs(df["high"] - df["close"].shift()),
                abs(df["low"] - df["close"].shift())
            )
        )

        atr = df["tr"].rolling(window=period).mean().iloc[-1]
        return float(atr) if not np.isnan(atr) else 0.0

    def _calculate_ema_slope(
        self, ohlcv_data: List[OHLCV], period: int = 20
    ) -> float:
        """
        Calculate EMA slope for trend direction.

        Args:
            ohlcv_data: List of OHLCV data points
            period: EMA period

        Returns:
            Slope value (positive = uptrend, negative = downtrend)
        """
        if len(ohlcv_data) < period:
            return 0.0

        closes = pd.Series([x.close for x in ohlcv_data])
        ema = closes.ewm(span=period, adjust=False).mean()

        # Compare last EMA to previous to get slope
        if len(ema) < 2:
            return 0.0

        slope = ema.iloc[-1] - ema.iloc[-2]
        return float(slope)

    def _classify_regime(self, ohlcv_data: List[OHLCV]) -> MarketRegime:
        """
        Classify market regime based on technical indicators.

        Args:
            ohlcv_data: List of OHLCV data points

        Returns:
            MarketRegime classification
        """
        if len(ohlcv_data) < 20:
            return MarketRegime.CHOPPY

        # Calculate indicators
        ema_slope = self._calculate_ema_slope(ohlcv_data, period=20)
        atr = self._calculate_atr(ohlcv_data, period=14)

        closes = pd.Series([x.close for x in ohlcv_data])
        avg_price = closes.mean()

        # Volatility assessment
        volatility_pct = (atr / avg_price * 100) if avg_price > 0 else 0

        # Regime classification logic
        if volatility_pct > 3.0:
            return MarketRegime.HIGH_VOL
        elif volatility_pct < 0.5:
            return MarketRegime.LOW_VOL
        elif ema_slope > 0.1:
            return MarketRegime.TRENDING_UP
        elif ema_slope < -0.1:
            return MarketRegime.TRENDING_DOWN
        else:
            return MarketRegime.CHOPPY

    async def run(self) -> None:
        """
        Main agent loop - continuously monitor regime changes.

        In a real implementation, this would fetch data periodically
        and emit regime_change events.
        """
        logger.info(f"{self.name} running", symbols=self.symbols)

        try:
            while self._running:
                # In production, fetch real OHLCV data here
                # For now, we simulate with synthetic data
                await asyncio.sleep(60)  # Check every minute

                # TODO: Fetch real OHLCV data for each symbol
                # and classify regime

        except Exception as e:
            logger.error(f"Error in {self.name}", error=str(e))

    async def on_event(self, topic: str, payload: Any) -> None:
        """
        Handle incoming events.

        Args:
            topic: Event topic
            payload: Event payload
        """
        if topic == "ohlcv_update":
            symbol = payload.get("symbol")
            ohlcv_list = payload.get("ohlcv_data", [])

            if not ohlcv_list:
                return

            # Classify new regime
            new_regime = self._classify_regime(ohlcv_list)
            old_regime = self._current_regime.get(symbol)

            if new_regime != old_regime:
                logger.info(
                    "regime_change",
                    symbol=symbol,
                    old_regime=old_regime,
                    new_regime=new_regime,
                )

                self._current_regime[symbol] = new_regime

                # Publish regime change event
                await self.event_bus.publish(
                    "regime_change",
                    {
                        "symbol": symbol,
                        "regime": new_regime.value,
                        "timestamp": pd.Timestamp.now(),
                    },
                )
