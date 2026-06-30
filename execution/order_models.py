"""Order and portfolio models for execution."""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime


class OrderSide(str, Enum):
    """Order side enumeration."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type enumeration."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(str, Enum):
    """Order status enumeration."""

    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class Order:
    """Trading order."""

    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING
    metadata: Dict = field(default_factory=dict)


@dataclass
class Fill:
    """Executed order fill."""

    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    fill_price: float
    fill_timestamp: datetime
    commission: float = 0.0
    metadata: Dict = field(default_factory=dict)


@dataclass
class Position:
    """Asset position in portfolio."""

    symbol: str
    quantity: float
    entry_price: float
    entry_timestamp: datetime
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0


@dataclass
class Portfolio:
    """Portfolio state."""

    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)
    total_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    trade_history: List[Fill] = field(default_factory=list)
