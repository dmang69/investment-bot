"""Session management and trade tracking."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
import json
from core.logger import get_logger


logger = get_logger(__name__)


@dataclass
class TradeRecord:
    """Record of a single executed trade."""

    timestamp: datetime
    symbol: str
    side: str  # BUY or SELL
    quantity: float
    price: float
    commission: float = 0.0
    order_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "commission": self.commission,
            "order_id": self.order_id,
            "metadata": self.metadata,
        }


class TradingSession:
    """
    Trading session manager for tracking and reporting.

    Tracks all trades, portfolio state changes, and generates session summaries.
    """

    def __init__(self) -> None:
        """Initialize trading session."""
        self.session_start: datetime = datetime.utcnow()
        self.session_end: Optional[datetime] = None
        self.initial_cash: float = 0.0
        self.trades: List[TradeRecord] = []
        self.portfolio_snapshots: List[Dict[str, Any]] = []

    def set_initial_state(self, initial_cash: float) -> None:
        """
        Set initial portfolio state.

        Args:
            initial_cash: Starting cash amount
        """
        self.initial_cash = initial_cash
        logger.info(
            "session_initialized",
            start_time=self.session_start,
            initial_cash=initial_cash,
        )

    def record_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        commission: float = 0.0,
        order_id: str = "",
        metadata: Dict[str, Any] = None,
    ) -> None:
        """
        Record an executed trade.

        Args:
            symbol: Asset symbol
            side: BUY or SELL
            quantity: Trade quantity
            price: Execution price
            commission: Trading commission
            order_id: Order identifier
            metadata: Additional metadata
        """
        trade = TradeRecord(
            timestamp=datetime.utcnow(),
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            commission=commission,
            order_id=order_id,
            metadata=metadata or {},
        )
        self.trades.append(trade)
        logger.info(
            "trade_recorded",
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_id=order_id,
        )

    def record_portfolio_snapshot(
        self, cash: float, positions: Dict[str, float], equity: float
    ) -> None:
        """
        Record a portfolio state snapshot.

        Args:
            cash: Current cash balance
            positions: Current positions {symbol: quantity}
            equity: Total equity value
        """
        snapshot = {
            "timestamp": datetime.utcnow().isoformat(),
            "cash": cash,
            "positions": positions.copy(),
            "total_equity": equity,
        }
        self.portfolio_snapshots.append(snapshot)

    def end_session(self) -> None:
        """Mark session as ended."""
        self.session_end = datetime.utcnow()
        logger.info(
            "session_ended",
            end_time=self.session_end,
            total_trades=len(self.trades),
        )

    def get_session_stats(self) -> Dict[str, Any]:
        """
        Calculate comprehensive session statistics.

        Returns:
            Dictionary with session metrics
        """
        if not self.trades:
            return {
                "total_trades": 0,
                "buy_trades": 0,
                "sell_trades": 0,
                "total_commission": 0.0,
                "gross_pnl": 0.0,
                "net_pnl": 0.0,
                "win_rate": 0.0,
                "duration_seconds": 0,
            }

        # Count trades by side
        buy_trades = [t for t in self.trades if t.side == "BUY"]
        sell_trades = [t for t in self.trades if t.side == "SELL"]

        # Total commission
        total_commission = sum(t.commission for t in self.trades)

        # Calculate realized P&L (simplified)
        gross_pnl = 0.0
        for sell in sell_trades:
            # Find matching buys
            matching_buys = [b for b in buy_trades if b.symbol == sell.symbol]
            if matching_buys:
                avg_buy_price = sum(b.price for b in matching_buys) / len(matching_buys)
                gross_pnl += (sell.price - avg_buy_price) * sell.quantity

        net_pnl = gross_pnl - total_commission

        # Win rate (trades with positive P&L)
        winning_trades = 0
        for sell in sell_trades:
            matching_buys = [b for b in buy_trades if b.symbol == sell.symbol]
            if matching_buys:
                avg_buy_price = sum(b.price for b in matching_buys) / len(matching_buys)
                if sell.price > avg_buy_price:
                    winning_trades += 1

        win_rate = (
            (winning_trades / len(self.trades) * 100) if self.trades else 0.0
        )

        # Duration
        duration = (
            (self.session_end - self.session_start).total_seconds()
            if self.session_end
            else (datetime.utcnow() - self.session_start).total_seconds()
        )

        return {
            "total_trades": len(self.trades),
            "buy_trades": len(buy_trades),
            "sell_trades": len(sell_trades),
            "total_commission": total_commission,
            "gross_pnl": gross_pnl,
            "net_pnl": net_pnl,
            "win_rate": win_rate,
            "duration_seconds": duration,
            "start_time": self.session_start.isoformat(),
            "end_time": self.session_end.isoformat() if self.session_end else None,
        }

    def save_session(self, filepath: str) -> None:
        """
        Export session data to JSON file.

        Args:
            filepath: Path to save session JSON
        """
        session_data = {
            "session_start": self.session_start.isoformat(),
            "session_end": self.session_end.isoformat() if self.session_end else None,
            "initial_cash": self.initial_cash,
            "trades": [t.to_dict() for t in self.trades],
            "portfolio_snapshots": self.portfolio_snapshots,
            "statistics": self.get_session_stats(),
        }

        try:
            with open(filepath, "w") as f:
                json.dump(session_data, f, indent=2)
            logger.info("session_saved", filepath=filepath)
        except Exception as e:
            logger.error("session_save_error", filepath=filepath, error=str(e))

    def generate_session_report(self) -> str:
        """
        Generate formatted text report of session.

        Returns:
            Formatted session report string
        """
        stats = self.get_session_stats()

        report = f"""
{'='*70}
TRADING SESSION REPORT
{'='*70}

Session Duration: {stats.get('duration_seconds', 0)} seconds
Start Time: {stats.get('start_time', 'N/A')}
End Time: {stats.get('end_time', 'N/A')}

TRADING ACTIVITY:
  Total Trades: {stats.get('total_trades', 0)}
  Buy Trades: {stats.get('buy_trades', 0)}
  Sell Trades: {stats.get('sell_trades', 0)}

FINANCIAL METRICS:
  Gross P&L: ${stats.get('gross_pnl', 0):,.2f}
  Total Commission: ${stats.get('total_commission', 0):,.2f}
  Net P&L: ${stats.get('net_pnl', 0):,.2f}
  Return %: {(stats.get('net_pnl', 0) / self.initial_cash * 100) if self.initial_cash > 0 else 0:.2f}%

TRADE QUALITY:
  Win Rate: {stats.get('win_rate', 0):.2f}%

TRADE HISTORY:
"""

        for i, trade in enumerate(self.trades, 1):
            report += f"\n{i}. {trade.symbol} {trade.side} {trade.quantity} @ ${trade.price}"
            if trade.commission > 0:
                report += f" (Commission: ${trade.commission:.2f})"

        report += f"\n{'='*70}\n"

        return report
