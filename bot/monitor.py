"""Real-time portfolio monitoring and alerting."""

import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from execution.paper_executor import PaperExecutor
from core.event_bus import EventBus
from core.logger import get_logger
from config.settings import Settings


logger = get_logger(__name__)


@dataclass
class PortfolioMetrics:
    """Portfolio performance metrics."""

    timestamp: datetime
    equity: float
    cash: float
    total_positions: int
    unrealized_pnl: float
    realized_pnl: float
    total_pnl: float
    return_pct: float
    max_drawdown_pct: float = 0.0
    current_drawdown_pct: float = 0.0


class PortfolioMonitor:
    """
    Real-time portfolio monitoring and alerting system.

    Tracks portfolio metrics, detects anomalies, and emits alerts.
    """

    def __init__(
        self,
        executor: PaperExecutor,
        event_bus: EventBus,
        config: Settings,
        initial_equity: float = 100000.0,
    ) -> None:
        """
        Initialize portfolio monitor.

        Args:
            executor: PaperExecutor for portfolio state
            event_bus: EventBus for publishing events
            config: Application settings
            initial_equity: Starting equity for tracking returns
        """
        self.executor = executor
        self.event_bus = event_bus
        self.config = config
        self.initial_equity = initial_equity
        self.peak_equity = initial_equity
        self.metrics_history: List[PortfolioMetrics] = []

    async def monitor_portfolio(self) -> Optional[PortfolioMetrics]:
        """
        Perform comprehensive portfolio monitoring.

        Calculates metrics, detects violations, and emits events.

        Returns:
            Current portfolio metrics
        """
        try:
            # Get current portfolio state
            portfolio = await self.executor.get_portfolio()
            positions = await self.executor.get_positions()

            # Calculate metrics
            current_equity = portfolio.total_value
            cash = portfolio.cash
            unrealized_pnl = portfolio.unrealized_pnl
            realized_pnl = portfolio.realized_pnl
            total_pnl = unrealized_pnl + realized_pnl
            return_pct = (
                ((current_equity - self.initial_equity) / self.initial_equity * 100)
                if self.initial_equity > 0
                else 0.0
            )

            # Update peak equity
            if current_equity > self.peak_equity:
                self.peak_equity = current_equity

            # Calculate drawdowns
            max_drawdown_pct = (
                ((self.peak_equity - self.initial_equity) / self.initial_equity * 100)
                if self.initial_equity > 0
                else 0.0
            )
            current_drawdown_pct = (
                ((self.peak_equity - current_equity) / self.peak_equity * 100)
                if self.peak_equity > 0
                else 0.0
            )

            # Create metrics object
            metrics = PortfolioMetrics(
                timestamp=datetime.utcnow(),
                equity=current_equity,
                cash=cash,
                total_positions=len(positions),
                unrealized_pnl=unrealized_pnl,
                realized_pnl=realized_pnl,
                total_pnl=total_pnl,
                return_pct=return_pct,
                max_drawdown_pct=max_drawdown_pct,
                current_drawdown_pct=current_drawdown_pct,
            )

            # Record metrics
            self.metrics_history.append(metrics)

            # Check for alerts
            await self._check_drawdown_alert(current_drawdown_pct)
            await self._check_position_alerts(positions)
            await self._check_return_alert(return_pct)

            # Emit portfolio updated event
            await self.event_bus.publish(
                "portfolio_updated",
                {
                    "metrics": metrics,
                    "positions": [
                        {
                            "symbol": p.symbol,
                            "quantity": p.quantity,
                            "entry_price": p.entry_price,
                        }
                        for p in positions
                    ],
                },
            )

            logger.info(
                "portfolio_monitored",
                equity=current_equity,
                cash=cash,
                positions=len(positions),
                return_pct=return_pct,
                current_drawdown=current_drawdown_pct,
            )

            return metrics

        except Exception as e:
            logger.error("portfolio_monitoring_error", error=str(e))
            return None

    async def _check_drawdown_alert(self, current_drawdown_pct: float) -> None:
        """
        Check for significant drawdown and alert if threshold exceeded.

        Args:
            current_drawdown_pct: Current drawdown percentage
        """
        max_drawdown_threshold = self.config.risk.max_drawdown_pct

        if current_drawdown_pct > max_drawdown_threshold * 0.8:  # Alert at 80% of limit
            logger.warning(
                "drawdown_warning",
                current_drawdown=current_drawdown_pct,
                max_threshold=max_drawdown_threshold,
            )
            await self.event_bus.publish(
                "alert_drawdown",
                {
                    "current_drawdown": current_drawdown_pct,
                    "threshold": max_drawdown_threshold,
                    "severity": "high" if current_drawdown_pct > max_drawdown_threshold else "medium",
                },
            )

    async def _check_position_alerts(self, positions) -> None:
        """
        Check for unusually large positions.

        Args:
            positions: List of current positions
        """
        portfolio = await self.executor.get_portfolio()
        max_position_pct = self.config.risk.max_position_size_pct

        for position in positions:
            if portfolio.total_value > 0:
                position_value = position.quantity * position.entry_price
                position_pct = (position_value / portfolio.total_value) * 100

                if position_pct > max_position_pct:
                    logger.warning(
                        "position_size_alert",
                        symbol=position.symbol,
                        position_pct=position_pct,
                        max_threshold=max_position_pct,
                    )
                    await self.event_bus.publish(
                        "alert_position_size",
                        {
                            "symbol": position.symbol,
                            "position_pct": position_pct,
                            "threshold": max_position_pct,
                        },
                    )

    async def _check_return_alert(self, return_pct: float) -> None:
        """
        Check for exceptional returns (positive or negative).

        Args:
            return_pct: Current return percentage
        """
        if return_pct > 10.0:
            logger.info("exceptional_return_alert", return_pct=return_pct)
            await self.event_bus.publish(
                "alert_exceptional_return",
                {"return_pct": return_pct, "direction": "positive"},
            )
        elif return_pct < -10.0:
            logger.warning("exceptional_loss_alert", return_pct=return_pct)
            await self.event_bus.publish(
                "alert_exceptional_loss",
                {"return_pct": return_pct, "direction": "negative"},
            )

    def get_current_metrics(self) -> Optional[PortfolioMetrics]:
        """
        Get most recent portfolio metrics.

        Returns:
            Latest metrics or None if no metrics recorded
        """
        return self.metrics_history[-1] if self.metrics_history else None

    def generate_session_summary(self) -> Dict[str, Any]:
        """
        Generate comprehensive session summary.

        Returns:
            Dictionary with session summary metrics
        """
        if not self.metrics_history:
            return {"error": "No metrics recorded"}

        first_metrics = self.metrics_history[0]
        last_metrics = self.metrics_history[-1]

        # Calculate statistics
        equities = [m.equity for m in self.metrics_history]
        returns = [m.return_pct for m in self.metrics_history]
        drawdowns = [m.current_drawdown_pct for m in self.metrics_history]

        return {
            "start_time": first_metrics.timestamp.isoformat(),
            "end_time": last_metrics.timestamp.isoformat(),
            "initial_equity": self.initial_equity,
            "final_equity": last_metrics.equity,
            "peak_equity": self.peak_equity,
            "total_return_pct": last_metrics.return_pct,
            "realized_pnl": last_metrics.realized_pnl,
            "unrealized_pnl": last_metrics.unrealized_pnl,
            "max_drawdown_pct": max(drawdowns) if drawdowns else 0.0,
            "avg_return_pct": sum(returns) / len(returns) if returns else 0.0,
            "num_snapshots": len(self.metrics_history),
            "final_positions": last_metrics.total_positions,
            "final_cash": last_metrics.cash,
        }
