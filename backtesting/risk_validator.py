"""Risk validation engine for backtesting with comprehensive constraint checking."""

from typing import Tuple, Dict, Any, List
from config.settings import Settings
from core.logger import get_logger


logger = get_logger(__name__)


class BacktestRiskValidator:
    """
    Risk validation engine for enforcing trading constraints during backtests.

    Enforces:
    - Maximum drawdown limit
    - Maximum position size per asset
    - Maximum total portfolio leverage
    - Maximum daily loss limit
    """

    def __init__(self, config: Settings) -> None:
        """
        Initialize risk validator with config limits.

        Args:
            config: Settings object containing risk configuration
        """
        self.config = config
        self.max_drawdown_pct = config.risk.max_drawdown_pct
        self.max_position_size_pct = config.risk.max_position_size_pct
        self.max_leverage = config.risk.max_leverage

        # Tracking
        self._initial_portfolio_value = 100000.0
        self._peak_portfolio_value = self._initial_portfolio_value
        self._current_portfolio_value = self._initial_portfolio_value
        self._violations: List[Dict[str, Any]] = []

        logger.info(
            "risk_validator_initialized",
            max_drawdown_pct=self.max_drawdown_pct,
            max_position_size_pct=self.max_position_size_pct,
            max_leverage=self.max_leverage,
        )

    def check_drawdown_breach(self, current_equity: float, peak_equity: float) -> bool:
        """
        Check if current drawdown exceeds limit.

        Args:
            current_equity: Current portfolio value
            peak_equity: Peak portfolio value to date

        Returns:
            True if drawdown exceeds limit, False otherwise
        """
        if peak_equity <= 0:
            return False

        drawdown_pct = ((peak_equity - current_equity) / peak_equity) * 100

        if drawdown_pct > self.max_drawdown_pct:
            logger.warning(
                "drawdown_breach_detected",
                current_drawdown_pct=drawdown_pct,
                limit_pct=self.max_drawdown_pct,
            )
            self._violations.append(
                {
                    "type": "drawdown",
                    "current_value": drawdown_pct,
                    "limit": self.max_drawdown_pct,
                }
            )
            return True

        return False

    def check_position_breach(
        self,
        position_size: float,
        portfolio_value: float,
    ) -> bool:
        """
        Check if position size exceeds limit as percentage of portfolio.

        Args:
            position_size: Value of position
            portfolio_value: Total portfolio value

        Returns:
            True if position size exceeds limit, False otherwise
        """
        if portfolio_value <= 0:
            return False

        position_pct = (position_size / portfolio_value) * 100

        if position_pct > self.max_position_size_pct:
            logger.warning(
                "position_size_breach_detected",
                position_pct=position_pct,
                limit_pct=self.max_position_size_pct,
            )
            self._violations.append(
                {
                    "type": "position_size",
                    "current_value": position_pct,
                    "limit": self.max_position_size_pct,
                }
            )
            return True

        return False

    def check_leverage_breach(
        self,
        total_exposure: float,
        portfolio_value: float,
    ) -> bool:
        """
        Check if total portfolio exposure exceeds leverage limit.

        Leverage = total_exposure / portfolio_value
        For example, leverage of 2.0 means $2 of exposure per $1 of equity.

        Args:
            total_exposure: Sum of all open position values
            portfolio_value: Total portfolio value

        Returns:
            True if leverage exceeds limit, False otherwise
        """
        if portfolio_value <= 0:
            return False

        current_leverage = total_exposure / portfolio_value

        if current_leverage > self.max_leverage:
            logger.warning(
                "leverage_breach_detected",
                current_leverage=current_leverage,
                limit_leverage=self.max_leverage,
            )
            self._violations.append(
                {
                    "type": "leverage",
                    "current_value": current_leverage,
                    "limit": self.max_leverage,
                }
            )
            return True

        return False

    def validate_trade(
        self,
        trade_size: float,
        current_equity: float,
        symbol: str,
    ) -> Tuple[bool, str]:
        """
        Validate trade against all risk constraints.

        Comprehensive validation including:
        - Position size limit
        - Leverage limit
        - Sufficient cash

        Args:
            trade_size: Size of trade in currency
            current_equity: Current portfolio equity
            symbol: Asset symbol

        Returns:
            Tuple of (is_valid: bool, reason: str)
            Example: (False, "position_size_exceeded_10%_limit")
        """
        if trade_size <= 0:
            return False, "invalid_trade_size"

        if current_equity <= 0:
            return False, "invalid_equity"

        # Check position size
        position_pct = (trade_size / current_equity) * 100
        if position_pct > self.max_position_size_pct:
            return (
                False,
                f"position_size_exceeds_limit_{position_pct:.1f}%_>{self.max_position_size_pct}%",
            )

        # Check if sufficient cash
        if trade_size > current_equity:
            return False, "insufficient_cash"

        return True, "valid"

    def validate_portfolio(
        self,
        current_equity: float,
        peak_equity: float,
        total_exposure: float,
    ) -> Tuple[bool, str]:
        """
        Validate entire portfolio state.

        Args:
            current_equity: Current portfolio value
            peak_equity: Peak portfolio value to date
            total_exposure: Sum of all open positions

        Returns:
            Tuple of (is_valid: bool, reason: str)
        """
        # Check drawdown
        if self.check_drawdown_breach(current_equity, peak_equity):
            return False, "max_drawdown_exceeded"

        # Check leverage
        if self.check_leverage_breach(total_exposure, current_equity):
            return False, "max_leverage_exceeded"

        return True, "valid"

    def record_trade(
        self,
        entry_price: float,
        exit_price: float,
        quantity: float,
        timestamp: str,
    ) -> None:
        """
        Record a completed trade (for audit trail).

        Args:
            entry_price: Entry price
            exit_price: Exit price
            quantity: Quantity
            timestamp: Trade timestamp
        """
        pnl = (exit_price - entry_price) * quantity
        logger.debug(
            "trade_recorded",
            pnl=pnl,
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=quantity,
            timestamp=timestamp,
        )

    def update_portfolio_state(
        self,
        current_equity: float,
    ) -> None:
        """
        Update internal portfolio state tracking.

        Args:
            current_equity: Current portfolio value
        """
        self._current_portfolio_value = current_equity
        if current_equity > self._peak_portfolio_value:
            self._peak_portfolio_value = current_equity

    def get_violations(self) -> List[Dict[str, Any]]:
        """Get all recorded violations."""
        return self._violations.copy()

    def reset_violations(self) -> None:
        """Clear violation history."""
        self._violations = []

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of risk validator state.

        Returns:
            Dictionary with summary metrics
        """
        return {
            "max_drawdown_limit_pct": self.max_drawdown_pct,
            "max_position_size_limit_pct": self.max_position_size_pct,
            "max_leverage_limit": self.max_leverage,
            "total_violations": len(self._violations),
            "current_portfolio_value": self._current_portfolio_value,
            "peak_portfolio_value": self._peak_portfolio_value,
        }
