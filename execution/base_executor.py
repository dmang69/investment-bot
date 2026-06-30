"""Abstract base executor class."""

from abc import ABC, abstractmethod
from typing import List
from execution.order_models import Order, Fill, Position, Portfolio


class BaseExecutor(ABC):
    """
    Abstract base class for order execution.

    Executors handle order placement, cancellation, and portfolio tracking.
    """

    @abstractmethod
    async def place_order(self, order: Order) -> Fill:
        """
        Place an order and return fill information.

        Args:
            order: Order to execute

        Returns:
            Fill object with execution details

        Raises:
            ExecutionError: If order placement fails
        """
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.

        Args:
            order_id: Order ID to cancel

        Returns:
            True if cancellation succeeded
        """
        pass

    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """
        Get current positions.

        Returns:
            List of open positions
        """
        pass

    @abstractmethod
    async def get_portfolio(self) -> Portfolio:
        """
        Get current portfolio state.

        Returns:
            Portfolio with cash, positions, and P&L
        """
        pass
