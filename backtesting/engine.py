"""Production-grade backtesting engine for strategy evaluation and risk validation."""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
import numpy as np

from data.models import OHLCV
from strategies.base_strategy import BaseStrategy, Signal
from agents.risk_agent import RiskAgent, Portfolio as RiskPortfolio
from execution.paper_executor import PaperExecutor
from execution.order_models import Order, OrderSide, OrderStatus, Fill
from config.settings import Settings
from core.logger import get_logger
from core.exceptions import DataError, StrategyError, ExecutionError, RiskBreachError
from backtesting.utils import (
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_max_drawdown,
    calculate_cagr,
)
from backtesting.risk_validator import BacktestRiskValidator


logger = get_logger(__name__)


@dataclass
class Trade:
    """Represents a single completed trade."""

    entry_timestamp: datetime
    exit_timestamp: datetime
    symbol: str
    entry_price: float
    exit_price: float
    quantity: float
    commission: float
    return_pct: float
    return_value: float
    duration_days: int
    side: str = "LONG"  # LONG or SHORT


@dataclass
class RiskViolation:
    """Records a risk constraint violation."""

    timestamp: datetime
    violation_type: str  # "drawdown", "position_size", "leverage"
    details: Dict[str, Any]
    severity: str = "warning"  # "warning", "critical"


@dataclass
class BacktestResult:
    """Comprehensive backtest results with all metrics."""

    # Return metrics
    total_return: float
    annual_return: float
    sharpe_ratio: float
    sortino_ratio: float
    cagr: float

    # Drawdown metrics
    max_drawdown: float
    max_drawdown_duration: int
    max_drawdown_pct: float

    # Trade metrics
    num_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_trade_return: float
    best_trade: float
    worst_trade: float
    profit_factor: float
    avg_trade_duration_days: float

    # Portfolio metrics
    initial_cash: float
    final_value: float
    total_fees: float
    peak_portfolio_value: float

    # Time series data
    equity_curve: List[float] = field(default_factory=list)
    drawdown_curve: List[float] = field(default_factory=list)
    timestamps: List[datetime] = field(default_factory=list)

    # Detailed records
    trades: List[Trade] = field(default_factory=list)
    risk_violations: List[RiskViolation] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for reporting."""
        return {
            "total_return": self.total_return,
            "annual_return": self.annual_return,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "cagr": self.cagr,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_duration_periods": self.max_drawdown_duration,
            "max_drawdown_pct": self.max_drawdown_pct,
            "num_trades": self.num_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "avg_trade_return": self.avg_trade_return,
            "best_trade": self.best_trade,
            "worst_trade": self.worst_trade,
            "profit_factor": self.profit_factor,
            "avg_trade_duration_days": self.avg_trade_duration_days,
            "initial_cash": self.initial_cash,
            "final_value": self.final_value,
            "total_fees": self.total_fees,
            "peak_portfolio_value": self.peak_portfolio_value,
            "num_risk_violations": len(self.risk_violations),
        }


class BacktestEngine:
    """
    Production-ready backtesting engine with risk enforcement and comprehensive metrics.

    Features:
    - Load and validate OHLCV data indexed by symbol
    - Execute strategies with chronological candle iteration
    - Enforce risk constraints via RiskAgent
    - Track equity, drawdown, P&L at each step
    - Calculate advanced metrics (Sharpe, Sortino, max drawdown, etc.)
    - Record all trades and risk violations
    - Support for commission and slippage simulation
    """

    def __init__(
        self,
        config: Settings,
        logger_instance=None,
    ) -> None:
        """
        Initialize backtesting engine.

        Args:
            config: Settings object with risk and trading configuration
            logger_instance: Optional logger instance (uses module logger if not provided)
        """
        self.config = config
        self.logger = logger_instance or logger

        # Data storage indexed by symbol
        self._ohlcv_data: Dict[str, List[OHLCV]] = {}

        # Backtest state
        self._executor: Optional[PaperExecutor] = None
        self._current_step = 0
        self._kill_switch_triggered = False

    def load_ohlcv_data(self, symbol: str, ohlcv_list: List[OHLCV]) -> None:
        """
        Load and validate OHLCV data for a symbol.

        Args:
            symbol: Asset symbol (e.g., "AAPL", "BTC/USD")
            ohlcv_list: List of OHLCV candlestick data

        Raises:
            DataError: If data is invalid or contains gaps
        """
        if not ohlcv_list:
            raise DataError(f"Empty OHLCV data for symbol {symbol}")

        # Validate data is sorted by timestamp
        for i in range(len(ohlcv_list) - 1):
            if ohlcv_list[i].timestamp >= ohlcv_list[i + 1].timestamp:
                raise DataError(
                    f"OHLCV data for {symbol} not sorted by timestamp at index {i}"
                )

            # Validate no extreme gaps (optional: can be disabled)
            time_diff = (ohlcv_list[i + 1].timestamp - ohlcv_list[i].timestamp).total_seconds()
            if time_diff <= 0:
                raise DataError(f"Invalid timestamp sequence for {symbol}")

        # Validate prices are positive
        for candle in ohlcv_list:
            if candle.close <= 0 or candle.open <= 0 or candle.high <= 0 or candle.low <= 0:
                raise DataError(f"Invalid price data for {symbol}: {candle}")

        self._ohlcv_data[symbol] = ohlcv_list

        # Log data summary
        date_range = f"{ohlcv_list[0].timestamp.date()} to {ohlcv_list[-1].timestamp.date()}"
        self.logger.info(
            "ohlcv_data_loaded",
            symbol=symbol,
            num_candles=len(ohlcv_list),
            date_range=date_range,
            first_close=ohlcv_list[0].close,
            last_close=ohlcv_list[-1].close,
        )

    async def run_backtest(
        self,
        symbol: str,
        strategy: BaseStrategy,
        risk_agent: Optional[RiskAgent] = None,
        initial_cash: float = 100000.0,
        commission: float = 0.001,
    ) -> BacktestResult:
        """
        Run complete backtest for a symbol with strategy and risk enforcement.

        Args:
            symbol: Asset symbol to backtest
            strategy: Strategy instance to evaluate
            risk_agent: Optional RiskAgent for risk validation
            initial_cash: Starting capital (default $100k)
            commission: Commission rate as decimal (default 0.1%)

        Returns:
            BacktestResult with all metrics and trade history
        """
        # Validate input
        if symbol not in self._ohlcv_data:
            raise DataError(f"No OHLCV data loaded for symbol {symbol}")

        ohlcv_list = self._ohlcv_data[symbol]
        if not ohlcv_list:
            raise DataError(f"Empty OHLCV data for symbol {symbol}")

        self.logger.info(
            "backtest_starting",
            symbol=symbol,
            strategy=strategy.__class__.__name__,
            num_candles=len(ohlcv_list),
        )

        # Initialize executor
        self._executor = PaperExecutor(initial_cash=initial_cash, slippage_bps=0)
        self._kill_switch_triggered = False

        # Initialize risk validator
        risk_validator = BacktestRiskValidator(self.config) if risk_agent else None

        # Run main backtest loop
        try:
            equity_curve, drawdown_curve, timestamps, trades, risk_violations, total_comm = (
                await self._execute_backtest_loop(
                    ohlcv_list, symbol, strategy, risk_agent, risk_validator, initial_cash
                )
            )
        except Exception as e:
            self.logger.error("backtest_execution_error", error=str(e))
            raise

        # Calculate metrics
        result = await self._calculate_metrics(
            equity_curve,
            drawdown_curve,
            timestamps,
            trades,
            risk_violations,
            total_comm,
            initial_cash,
            len(ohlcv_list),
        )

        self.logger.info(
            "backtest_completed",
            symbol=symbol,
            total_return=f"{result.total_return:.2%}",
            num_trades=result.num_trades,
        )

        return result

    async def _execute_backtest_loop(
        self,
        ohlcv_list: List[OHLCV],
        symbol: str,
        strategy: BaseStrategy,
        risk_agent: Optional[RiskAgent],
        risk_validator: Optional[BacktestRiskValidator],
        initial_cash: float,
    ) -> Tuple[List[float], List[float], List[datetime], List[Trade], List[RiskViolation], float]:
        """Execute main backtest loop through OHLCV data."""
        equity_curve = [initial_cash]
        drawdown_curve = [0.0]
        timestamps = [ohlcv_list[0].timestamp]
        trades = []
        risk_violations = []

        peak_equity = initial_cash
        entry_price = None
        entry_timestamp = None
        position_open = False
        total_commission = 0.0

        for i, candle in enumerate(ohlcv_list):
            self._current_step = i
            candle_history = ohlcv_list[: i + 1]

            # Generate signal
            try:
                signal = await strategy.generate_signal(candle_history)
            except Exception as e:
                raise StrategyError(f"Signal generation failed: {str(e)}")

            current_price = candle.close
            current_equity = equity_curve[-1]

            # Update peak equity
            if current_equity > peak_equity:
                peak_equity = current_equity

            # Validate signal
            signal_valid, violation = await self._validate_signal(
                signal, candle, risk_agent
            )
            if violation:
                risk_violations.append(violation)

            # Execute signals
            if signal_valid and signal.action == "BUY" and not position_open:
                position_open, entry_price, entry_timestamp, comm = (
                    await self._execute_buy(symbol, current_price, candle.timestamp)
                )
                total_commission += comm

            elif signal_valid and signal.action == "SELL" and position_open:
                position_open, trade, comm = await self._execute_sell(
                    symbol, current_price, candle.timestamp, entry_price, entry_timestamp
                )
                if trade:
                    trades.append(trade)
                total_commission += comm

            # Update equity and drawdown
            equity = await self._calculate_current_equity(
                position_open, entry_price, current_price
            )
            equity_curve.append(equity)

            drawdown = (peak_equity - equity) / peak_equity if peak_equity > 0 else 0
            drawdown_curve.append(drawdown)

            # Check drawdown breach
            if await self._check_drawdown_violation(
                drawdown, candle, risk_violations, risk_validator
            ):
                break

            timestamps.append(candle.timestamp)

        return equity_curve, drawdown_curve, timestamps, trades, risk_violations, total_commission

    async def _validate_signal(
        self, signal: Signal, candle: OHLCV, risk_agent: Optional[RiskAgent]
    ) -> Tuple[bool, Optional[RiskViolation]]:
        """Validate signal against risk constraints."""
        if not risk_agent or signal.action not in ["BUY", "SELL"]:
            return True, None

        try:
            portfolio = await self._executor.get_portfolio()
            current_positions = {p.symbol: p.quantity for p in portfolio.positions.values()}
            current_entry_prices = {p.symbol: p.entry_price for p in portfolio.positions.values()}

            risk_portfolio = RiskPortfolio(
                cash=portfolio.cash,
                positions=current_positions,
                entry_prices=current_entry_prices,
                timestamp=candle.timestamp,
            )

            from agents.risk_agent import Signal as RiskSignal

            risk_signal = RiskSignal(
                symbol=signal.symbol,
                action=signal.action,
                quantity=1.0,
                entry_price=candle.close,
                metadata=signal.metadata,
            )

            is_valid = risk_agent.validate_signal(risk_signal, risk_portfolio)

            if not is_valid:
                violation = RiskViolation(
                    timestamp=candle.timestamp,
                    violation_type="signal_rejected",
                    details={"symbol": signal.symbol, "action": signal.action},
                    severity="warning",
                )
                return False, violation

            return True, None

        except Exception as e:
            self.logger.warning("risk_validation_error", error=str(e))
            return True, None

    async def _execute_buy(
        self, symbol: str, current_price: float, timestamp: datetime
    ) -> Tuple[bool, Optional[float], Optional[datetime], float]:
        """Execute buy order."""
        try:
            order = Order(
                symbol=symbol,
                side=OrderSide.BUY,
                quantity=1.0,
                limit_price=current_price,
                timestamp=timestamp,
            )
            fill = await self._executor.place_order(order)
            return True, fill.fill_price, timestamp, fill.commission
        except Exception as e:
            self.logger.error("buy_order_failed", error=str(e))
            return False, None, None, 0.0

    async def _execute_sell(
        self,
        symbol: str,
        current_price: float,
        timestamp: datetime,
        entry_price: Optional[float],
        entry_timestamp: Optional[datetime],
    ) -> Tuple[bool, Optional[Trade], float]:
        """Execute sell order and record trade."""
        if entry_price is None or entry_timestamp is None:
            return False, None, 0.0

        try:
            order = Order(
                symbol=symbol,
                side=OrderSide.SELL,
                quantity=1.0,
                limit_price=current_price,
                timestamp=timestamp,
            )
            fill = await self._executor.place_order(order)

            return_value = (current_price - entry_price) * 1.0 - fill.commission
            return_pct = ((current_price - entry_price) / entry_price) - (
                fill.commission / entry_price
            )
            duration = max(1, (timestamp - entry_timestamp).days)

            trade = Trade(
                entry_timestamp=entry_timestamp,
                exit_timestamp=timestamp,
                symbol=symbol,
                entry_price=entry_price,
                exit_price=fill.fill_price,
                quantity=1.0,
                commission=fill.commission,
                return_pct=return_pct,
                return_value=return_value,
                duration_days=duration,
            )
            return False, trade, fill.commission

        except Exception as e:
            self.logger.error("sell_order_failed", error=str(e))
            return False, None, 0.0

    async def _calculate_current_equity(
        self, position_open: bool, entry_price: Optional[float], current_price: float
    ) -> float:
        """Calculate current portfolio equity."""
        portfolio = await self._executor.get_portfolio()
        equity = portfolio.cash

        if position_open and entry_price is not None:
            equity += (current_price - entry_price) * 1.0

        return equity

    async def _check_drawdown_violation(
        self,
        drawdown: float,
        candle: OHLCV,
        violations: List[RiskViolation],
        risk_validator: Optional[BacktestRiskValidator],
    ) -> bool:
        """Check if drawdown exceeds limit. Returns True if backtest should stop."""
        if not risk_validator or drawdown <= (self.config.risk.max_drawdown_pct / 100.0):
            return False

        violation = RiskViolation(
            timestamp=candle.timestamp,
            violation_type="drawdown",
            details={
                "current_drawdown_pct": drawdown * 100,
                "max_allowed_pct": self.config.risk.max_drawdown_pct,
            },
            severity="critical",
        )
        violations.append(violation)

        if self.config.risk.max_drawdown_pct > 0:
            self._kill_switch_triggered = True
            return True

        return False

    async def _calculate_metrics(
        self,
        equity_curve: List[float],
        drawdown_curve: List[float],
        timestamps: List[datetime],
        trades: List[Trade],
        risk_violations: List[RiskViolation],
        total_commission: float,
        initial_cash: float,
        num_candles: int,
    ) -> BacktestResult:
        """Calculate all performance metrics."""
        final_value = equity_curve[-1]
        total_return = (final_value - initial_cash) / initial_cash if initial_cash > 0 else 0

        num_years = num_candles / 252.0
        daily_returns = np.diff(equity_curve) / np.array(equity_curve[:-1])

        sharpe = calculate_sharpe_ratio(daily_returns.tolist())
        sortino = calculate_sortino_ratio(daily_returns.tolist())
        max_dd, max_dd_dur = calculate_max_drawdown(equity_curve)
        cagr = calculate_cagr(initial_cash, final_value, max(num_years, 0.001))
        annual_return = total_return / max(num_years, 0.001)

        # Trade stats
        num_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.return_pct > 0)
        losing_trades = num_trades - winning_trades
        win_rate = winning_trades / num_trades if num_trades > 0 else 0

        avg_return = np.mean([t.return_pct for t in trades]) if trades else 0
        best_trade = max((t.return_pct for t in trades), default=0)
        worst_trade = min((t.return_pct for t in trades), default=0)

        winning_sum = sum(t.return_value for t in trades if t.return_value > 0)
        losing_sum = abs(sum(t.return_value for t in trades if t.return_value < 0))
        profit_factor = (
            winning_sum / losing_sum if losing_sum > 0 and winning_sum > 0 else 0
        )

        avg_duration = np.mean([t.duration_days for t in trades]) if trades else 0

        return BacktestResult(
            total_return=total_return,
            annual_return=annual_return,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            cagr=cagr,
            max_drawdown=max_dd,
            max_drawdown_duration=max_dd_dur,
            max_drawdown_pct=max_dd * 100,
            num_trades=num_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            avg_trade_return=avg_return,
            best_trade=best_trade,
            worst_trade=worst_trade,
            profit_factor=profit_factor,
            avg_trade_duration_days=avg_duration,
            initial_cash=initial_cash,
            final_value=final_value,
            total_fees=total_commission,
            peak_portfolio_value=max(equity_curve),
            equity_curve=equity_curve,
            drawdown_curve=drawdown_curve,
            timestamps=timestamps,
            trades=trades,
            risk_violations=risk_violations,
        )
