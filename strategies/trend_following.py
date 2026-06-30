"""Trend-following strategy with EMA crossover."""

import pandas as pd
from typing import List
from data.models import OHLCV
from strategies.base_strategy import BaseStrategy, Signal
from core.logger import get_logger


logger = get_logger(__name__)


class TrendFollowingStrategy(BaseStrategy):
    """
    Trend-following strategy using EMA (Exponential Moving Average) crossovers.

    Logic:
    - Fast EMA (20 period) crosses above Slow EMA (50 period) -> BUY signal
    - Fast EMA crosses below Slow EMA -> SELL signal
    - Otherwise -> HOLD
    - Confidence based on EMA spread (larger spread = higher confidence)
    """

    def __init__(self, fast_period: int = 20, slow_period: int = 50) -> None:
        """
        Initialize trend-following strategy.

        Args:
            fast_period: Fast EMA period (default 20)
            slow_period: Slow EMA period (default 50)
        """
        self.fast_period = fast_period
        self.slow_period = slow_period

    async def generate_signal(self, ohlcv_data: List[OHLCV]) -> Signal:
        """
        Generate signal using EMA crossover logic.

        Args:
            ohlcv_data: List of OHLCV data points

        Returns:
            Trading signal with BUY/SELL/HOLD action
        """
        if not ohlcv_data:
            return Signal(
                symbol="UNKNOWN",
                action="HOLD",
                confidence=0.0,
                metadata={"reason": "no_data"},
            )

        if len(ohlcv_data) < self.slow_period:
            return Signal(
                symbol="UNKNOWN",
                action="HOLD",
                confidence=0.0,
                metadata={"reason": "insufficient_data", "required": self.slow_period},
            )

        # Extract closes and calculate EMAs
        closes = pd.Series([x.close for x in ohlcv_data])
        fast_ema = closes.ewm(span=self.fast_period, adjust=False).mean()
        slow_ema = closes.ewm(span=self.slow_period, adjust=False).mean()

        # Get current and previous EMA values
        current_fast = fast_ema.iloc[-1]
        current_slow = slow_ema.iloc[-1]
        prev_fast = fast_ema.iloc[-2]
        prev_slow = slow_ema.iloc[-2]

        # Calculate spread for confidence
        spread = abs(current_fast - current_slow)
        current_price = closes.iloc[-1]
        spread_pct = (spread / current_price) * 100 if current_price > 0 else 0

        # Confidence increases with larger spread (up to 1.0)
        confidence = min(1.0, spread_pct / 2.0)

        # Determine signal based on crossover
        if prev_fast <= prev_slow and current_fast > current_slow:
            # Golden cross - bullish crossover
            action = "BUY"
            logger.info("trend_following_buy_signal", ema_spread=spread_pct)
        elif prev_fast >= prev_slow and current_fast < current_slow:
            # Death cross - bearish crossover
            action = "SELL"
            logger.info("trend_following_sell_signal", ema_spread=spread_pct)
        else:
            # No crossover
            action = "HOLD"

        return Signal(
            symbol=ohlcv_data[0].__class__.__name__,
            action=action,
            confidence=confidence,
            metadata={
                "fast_ema": float(current_fast),
                "slow_ema": float(current_slow),
                "ema_spread": float(spread),
                "spread_pct": float(spread_pct),
                "strategy": "TrendFollowing",
            },
        )
