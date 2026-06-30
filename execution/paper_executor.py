"""Paper trading executor with in-memory portfolio simulation."""

import uuid
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from execution.base_executor import BaseExecutor
from execution.order_models import (
    Order,
    Fill,
    Position,
    Portfolio,
    OrderSide,
    OrderStatus,
)
from core.logger import get_logger
from core.exceptions import ExecutionError


logger = get_logger(__name__)


class PaperExecutor(BaseExecutor):
    """
    Paper trading executor with full in-memory portfolio simulation.

    Features:
    - In-memory portfolio tracking
    - Simulated market fills with configurable slippage
    - Complete trade history
    - Unrealized and realized P&L tracking
    - Position average price calculation
    """

    def __init__(
        self, initial_cash: float = 100000.0, slippage_bps: float = 5.0
    ) -> None:
        """
        Initialize paper executor.

        Args:
            initial_cash: Starting cash balance (default $100k)
            slippage_bps: Slippage in basis points (default 5 bps)
        """
        self._cash = initial_cash
        self._initial_cash = initial_cash
        self._positions: Dict[str, Position] = {}
        self._trade_history: List[Fill] = []
        self._order_counter = 0
        self._slippage_bps = slippage_bps / 10000.0  # Convert to decimal

    async def place_order(self, order: Order) -> Fill:
        """
        Simulate order execution.

        Args:
            order: Order to execute

        Returns:
            Fill with simulated execution

        Raises:
            ExecutionError: If order validation fails
        """
        # Validate order
        if order.quantity <= 0:
            raise ExecutionError("Order quantity must be positive")

        if order.side == OrderSide.BUY and order.quantity * order.limit_price > self._cash:
            raise ExecutionError("Insufficient cash for order")

        # Generate order ID
        order_id = f"ORDER-{self._order_counter}-{uuid.uuid4().hex[:8]}"
        self._order_counter += 1

        # Simulate fill with slippage
        slippage = order.limit_price * self._slippage_bps
        if order.side == OrderSide.BUY:
            fill_price = order.limit_price + slippage
        else:
            fill_price = order.limit_price - slippage

        # Calculate commission (0.1% of order value)
        commission = order.quantity * fill_price * 0.001

        # Create fill
        fill = Fill(
            order_id=order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            fill_price=fill_price,
            fill_timestamp=datetime.utcnow(),
            commission=commission,
            metadata={
                "slippage": slippage,
                "requested_price": order.limit_price,
            },
        )

        # Update portfolio
        await self._apply_fill(fill)

        # Record trade
        self._trade_history.append(fill)

        logger.info(
            "order_filled",
            order_id=order_id,
            symbol=order.symbol,
            side=order.side.value,
            quantity=order.quantity,
            fill_price=fill_price,
            commission=commission,
        )

        return fill

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order (no-op in paper trading).

        Args:
            order_id: Order ID to cancel

        Returns:
            True (always succeeds in paper trading)
        """
        logger.info("order_cancelled", order_id=order_id)
        return True

    async def get_positions(self) -> List[Position]:
        """
        Get current positions.

        Returns:
            List of open positions
        """
        return list(self._positions.values())

    async def get_portfolio(self) -> Portfolio:
        """
        Get current portfolio state with full P&L calculations.

        Returns:
            Portfolio object with all metrics
        """
        # Calculate current value and P&L for each position
        # (In real implementation, would use current market prices)
        unrealized_pnl = 0.0
        total_position_value = 0.0

        for position in self._positions.values():
            position_value = position.quantity * position.entry_price
            total_position_value += position_value
            # unrealized_pnl would update based on current prices

        realized_pnl = sum(
            (f.fill_price * f.quantity) - (f.fill_price * f.quantity * 0.001)
            if f.side == OrderSide.SELL
            else 0
            for f in self._trade_history
        )

        total_value = self._cash + total_position_value + unrealized_pnl

        return Portfolio(
            cash=self._cash,
            positions={sym: pos for sym, pos in self._positions.items()},
            total_value=total_value,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=realized_pnl,
            timestamp=datetime.utcnow(),
            trade_history=self._trade_history.copy(),
        )

    def get_equity_history(self) -> List[Tuple[datetime, float]]:
        """
        Get historical equity values at each trade execution.

        Returns:
            List of tuples (timestamp, equity_value)
        """
        equity_history = []

        current_cash = self._initial_cash
        positions_cost = {}

        for fill in self._trade_history:
            symbol = fill.symbol

            if fill.side == OrderSide.BUY:
                # Update cash
                cost = fill.quantity * fill.fill_price + fill.commission
                current_cash -= cost

                # Update position cost
                if symbol not in positions_cost:
                    positions_cost[symbol] = 0
                positions_cost[symbol] += cost

            elif fill.side == OrderSide.SELL:
                # Update cash
                proceeds = fill.quantity * fill.fill_price - fill.commission
                current_cash += proceeds

                # Update position cost
                if symbol in positions_cost:
                    positions_cost[symbol] -= fill.quantity * fill.fill_price

            # Calculate total equity (cash + position values)
            total_equity = current_cash + sum(positions_cost.values())
            equity_history.append((fill.fill_timestamp, total_equity))

        return equity_history

    def get_trades_history(self) -> List[dict]:
        """
        Get all executed trades with detailed information.

        Returns:
            List of trade dicts with keys:
            - order_id, symbol, side, quantity, fill_price, timestamp, commission
        """
        trades = []

        for fill in self._trade_history:
            trades.append(
                {
                    "order_id": fill.order_id,
                    "symbol": fill.symbol,
                    "side": fill.side.value,
                    "quantity": fill.quantity,
                    "fill_price": fill.fill_price,
                    "timestamp": fill.fill_timestamp,
                    "commission": fill.commission,
                }
            )

        return trades

    async def _apply_fill(self, fill: Fill) -> None:
        """
        Apply fill to portfolio.

        Args:
            fill: Fill to apply
        """
        symbol = fill.symbol

        if fill.side == OrderSide.BUY:
            # Update cash
            cost = fill.quantity * fill.fill_price + fill.commission
            self._cash -= cost

            # Update or create position
            if symbol in self._positions:
                pos = self._positions[symbol]
                total_quantity = pos.quantity + fill.quantity
                avg_price = (
                    (pos.quantity * pos.entry_price + fill.quantity * fill.fill_price)
                    / total_quantity
                )
                pos.quantity = total_quantity
                pos.entry_price = avg_price
            else:
                self._positions[symbol] = Position(
                    symbol=symbol,
                    quantity=fill.quantity,
                    entry_price=fill.fill_price,
                    entry_timestamp=fill.fill_timestamp,
                )

        elif fill.side == OrderSide.SELL:
            # Update cash
            proceeds = fill.quantity * fill.fill_price - fill.commission
            self._cash += proceeds

            # Update position
            if symbol in self._positions:
                pos = self._positions[symbol]
                pos.quantity -= fill.quantity
                pos.realized_pnl += (fill.fill_price - pos.entry_price) * fill.quantity

                # Remove position if fully closed
                if pos.quantity <= 0:
                    del self._positions[symbol]
