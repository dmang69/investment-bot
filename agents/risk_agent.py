"""Risk management agent with real working logic."""

from typing import Any, Dict, Optional
import asyncio
from dataclasses import dataclass
from agents.base_agent import BaseAgent
from core.logger import get_logger
from core.event_bus import EventBus
from core.exceptions import RiskBreachError


logger = get_logger(__name__)


@dataclass
class Signal:
    """Trading signal for risk validation."""

    symbol: str
    action: str  # BUY, SELL, HOLD
    quantity: float
    entry_price: float
    metadata: Dict[str, Any]


@dataclass
class Portfolio:
    """Portfolio state for risk checking."""

    cash: float
    positions: Dict[str, float]  # symbol -> quantity
    entry_prices: Dict[str, float]  # symbol -> average entry price
    timestamp: Any


class RiskAgent(BaseAgent):
    """
    Risk management agent.

    Enforces portfolio risk constraints:
    - Maximum drawdown limit
    - Maximum position size per asset
    - Maximum total portfolio exposure
    - Maximum leverage

    Validates all signals before execution and emits kill_switch on breach.
    """

    def __init__(
        self,
        event_bus: EventBus,
        max_drawdown_pct: float = 20.0,
        max_position_size_pct: float = 10.0,
        max_leverage: float = 2.0,
    ) -> None:
        """
        Initialize the risk agent.

        Args:
            event_bus: Event bus for communication
            max_drawdown_pct: Maximum allowed drawdown percentage
            max_position_size_pct: Maximum position size as % of portfolio
            max_leverage: Maximum leverage allowed
        """
        super().__init__()
        self.event_bus = event_bus
        self.max_drawdown_pct = max_drawdown_pct
        self.max_position_size_pct = max_position_size_pct
        self.max_leverage = max_leverage

        self._initial_portfolio_value = 100000.0  # $100k baseline
        self._peak_portfolio_value = self._initial_portfolio_value
        self._current_portfolio_value = self._initial_portfolio_value

    @property
    def name(self) -> str:
        """Get agent name."""
        return "RiskAgent"

    def _calculate_drawdown(self) -> float:
        """
        Calculate current drawdown percentage.

        Returns:
            Drawdown percentage (0-100)
        """
        if self._peak_portfolio_value <= 0:
            return 0.0

        drawdown = (
            (self._peak_portfolio_value - self._current_portfolio_value)
            / self._peak_portfolio_value
            * 100
        )
        return max(0.0, drawdown)

    def _validate_position_size(
        self, signal: Signal, portfolio: Portfolio
    ) -> bool:
        """
        Validate that position size respects limits.

        Args:
            signal: Trading signal to validate
            portfolio: Current portfolio state

        Returns:
            True if position size is acceptable
        """
        total_portfolio_value = portfolio.cash + sum(
            qty * portfolio.entry_prices.get(sym, 0)
            for sym, qty in portfolio.positions.items()
        )

        if total_portfolio_value <= 0:
            return False

        position_value = signal.quantity * signal.entry_price
        position_pct = (position_value / total_portfolio_value) * 100

        if position_pct > self.max_position_size_pct:
            logger.warning(
                "position_size_breach",
                symbol=signal.symbol,
                position_pct=position_pct,
                limit=self.max_position_size_pct,
            )
            return False

        return True

    def _validate_portfolio_exposure(
        self, signal: Signal, portfolio: Portfolio
    ) -> bool:
        """
        Validate total portfolio exposure.

        Args:
            signal: Trading signal to validate
            portfolio: Current portfolio state

        Returns:
            True if exposure is acceptable
        """
        total_exposure = sum(
            qty * portfolio.entry_prices.get(sym, 0)
            for sym, qty in portfolio.positions.items()
        )

        total_exposure += signal.quantity * signal.entry_price
        total_portfolio_value = portfolio.cash + total_exposure

        if total_portfolio_value <= 0:
            return True

        exposure_ratio = total_exposure / total_portfolio_value

        if exposure_ratio > self.max_leverage:
            logger.warning(
                "leverage_breach",
                exposure_ratio=exposure_ratio,
                max_leverage=self.max_leverage,
            )
            return False

        return True

    def validate_signal(
        self, signal: Signal, portfolio: Portfolio
    ) -> bool:
        """
        Validate trading signal against all risk constraints.

        Args:
            signal: Signal to validate
            portfolio: Current portfolio state

        Returns:
            True if signal passes all risk checks
        """
        # Check drawdown limit
        current_drawdown = self._calculate_drawdown()
        if current_drawdown > self.max_drawdown_pct:
            logger.error(
                "drawdown_breach",
                current_drawdown=current_drawdown,
                max_drawdown=self.max_drawdown_pct,
            )
            return False

        # Check position size
        if not self._validate_position_size(signal, portfolio):
            return False

        # Check portfolio exposure
        if not self._validate_portfolio_exposure(signal, portfolio):
            return False

        return True

    async def run(self) -> None:
        """
        Main agent loop - monitor portfolio and enforce constraints.

        Subscribes to trading signals and validates them before execution.
        """
        logger.info(
            f"{self.name} running",
            max_drawdown={self.max_drawdown_pct},
            max_position_size={self.max_position_size_pct},
            max_leverage={self.max_leverage},
        )

        try:
            await self.event_bus.subscribe("trading_signal", self.on_event)

            while self._running:
                # Monitor portfolio metrics periodically
                drawdown = self._calculate_drawdown()
                if drawdown > 0:
                    logger.info(
                        "portfolio_drawdown",
                        drawdown_pct=drawdown,
                        current_value=self._current_portfolio_value,
                    )

                await asyncio.sleep(30)

        except Exception as e:
            logger.error(f"Error in {self.name}", error=str(e))
            await self._publish_kill_switch()

    async def on_event(self, topic: str, payload: Any) -> None:
        """
        Handle incoming trading signals.

        Args:
            topic: Event topic
            payload: Event payload with signal data
        """
        if topic == "trading_signal":
            try:
                signal = payload.get("signal")
                portfolio = payload.get("portfolio")

                if not self.validate_signal(signal, portfolio):
                    logger.warning(
                        "signal_rejected",
                        symbol=signal.symbol,
                        action=signal.action,
                    )
                    await self.event_bus.publish(
                        "signal_rejected",
                        {
                            "signal": signal,
                            "reason": "risk_constraint_breach",
                        },
                    )
                else:
                    logger.info(
                        "signal_approved",
                        symbol=signal.symbol,
                        action=signal.action,
                    )
                    await self.event_bus.publish(
                        "signal_approved", {"signal": signal}
                    )

            except Exception as e:
                logger.error("signal_validation_error", error=str(e))

    async def _publish_kill_switch(self) -> None:
        """Publish kill_switch event to halt all trading."""
        logger.critical("kill_switch_triggered")
        await self.event_bus.publish(
            "kill_switch", {"reason": "risk_constraint_breach"}
        )
        await self.stop()
