"""Mean reversion strategy using Z-score."""

import pandas as pd
import numpy as np
from typing import List
from data.models import OHLCV
from strategies.base_strategy import BaseStrategy, Signal
from core.logger import get_logger


logger = get_logger(__name__)


class MeanReversionStrategy(BaseStrategy):
    """
    Mean reversion strategy using Z-score analysis.

    Logic:
    - Calculate rolling mean and standard deviation (20-period window)
    - Calculate Z-score: (price - mean) / std
    - BUY when Z-score < -2.0 (oversold)
    - SELL when Z-score > 2.0 (overbought)
    - HOLD otherwise
    - Confidence based on magnitude of Z-score
    """

    def __init__(self, period: int = 20, z_threshold: float = 2.0) -> None:
        """
        Initialize mean reversion strategy.

        Args:
            period: Rolling window period (default 20)
            z_threshold: Z-score threshold for signals (default 2.0)
        """
        self.period = period
        self.z_threshold = z_threshold

    async def generate_signal(self, ohlcv_data: List[OHLCV]) -> Signal:
        """
        Generate signal using Z-score mean reversion logic.

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

        if len(ohlcv_data) < self.period:
            return Signal(
                symbol="UNKNOWN",
                action="HOLD",
                confidence=0.0,
                metadata={"reason": "insufficient_data", "required": self.period},
            )

        # Extract closes and calculate rolling mean and std
        closes = pd.Series([x.close for x in ohlcv_data])
        rolling_mean = closes.rolling(window=self.period).mean()
        rolling_std = closes.rolling(window=self.period).std()

        # Get current values
        current_price = closes.iloc[-1]
        current_mean = rolling_mean.iloc[-1]
        current_std = rolling_std.iloc[-1]

        # Calculate Z-score
        if current_std == 0 or pd.isna(current_std):
            z_score = 0.0
        else:
            z_score = (current_price - current_mean) / current_std

        # Confidence based on Z-score magnitude
        confidence = min(1.0, abs(z_score) / 3.0)

        # Determine signal based on Z-score
        if z_score < -self.z_threshold:
            # Oversold - buy
            action = "BUY"
            logger.info("mean_reversion_buy_signal", z_score=z_score)
        elif z_score > self.z_threshold:
            # Overbought - sell
            action = "SELL"
            logger.info("mean_reversion_sell_signal", z_score=z_score)
        else:
            # Within range - hold
            action = "HOLD"

        return Signal(
            symbol=ohlcv_data[0].__class__.__name__,
            action=action,
            confidence=confidence,
            metadata={
                "z_score": float(z_score),
                "rolling_mean": float(current_mean) if not pd.isna(current_mean) else 0.0,
                "rolling_std": float(current_std) if not pd.isna(current_std) else 0.0,
                "current_price": float(current_price),
                "strategy": "MeanReversion",
            },
        )
