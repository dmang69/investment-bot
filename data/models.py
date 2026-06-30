"""Data models for market information and orders."""

from pydantic import BaseModel, Field
from typing import List, Tuple
from datetime import datetime


class OHLCV(BaseModel):
    """Open-High-Low-Close-Volume candlestick data."""

    timestamp: datetime = Field(..., description="Candlestick open time")
    open: float = Field(..., gt=0, description="Opening price (must be positive)")
    high: float = Field(..., gt=0, description="Highest price in period (must be positive)")
    low: float = Field(..., gt=0, description="Lowest price in period (must be positive)")
    close: float = Field(..., gt=0, description="Closing price (must be positive)")
    volume: float = Field(default=0.0, ge=0, description="Trading volume (must be >= 0)")

    def __init__(self, **data):
        """Validate OHLCV constraints on initialization."""
        super().__init__(**data)
        
        # Validate high >= low
        if self.high < self.low:
            raise ValueError(f"High ({self.high}) must be >= Low ({self.low})")
        
        # Validate high >= open and high >= close
        if self.high < self.open:
            raise ValueError(f"High ({self.high}) must be >= Open ({self.open})")
        if self.high < self.close:
            raise ValueError(f"High ({self.high}) must be >= Close ({self.close})")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "timestamp": "2024-01-01T00:00:00",
                "open": 100.0,
                "high": 105.0,
                "low": 98.0,
                "close": 102.0,
                "volume": 1000000.0,
            }
        }


class Ticker(BaseModel):
    """Current ticker information for a symbol."""

    symbol: str = Field(..., description="Asset symbol")
    price: float = Field(..., gt=0, description="Current price (must be positive)")
    bid: float = Field(..., ge=0, description="Current bid price (must be >= 0)")
    ask: float = Field(..., ge=0, description="Current ask price (must be >= 0)")
    volume_24h: float = Field(default=0.0, ge=0, description="24-hour trading volume (must be >= 0)")

    def __init__(self, **data):
        """Validate Ticker constraints on initialization."""
        super().__init__(**data)
        
        # Bid should typically be <= ask
        if self.bid > self.ask and self.ask > 0:
            import warnings
            warnings.warn(f"Bid ({self.bid}) > Ask ({self.ask}), which is unusual", stacklevel=2)

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "symbol": "BTC/USD",
                "price": 45000.0,
                "bid": 44999.0,
                "ask": 45001.0,
                "volume_24h": 1000000.0,
            }
        }


class OrderBook(BaseModel):
    """Order book snapshot for a symbol."""

    symbol: str = Field(..., description="Asset symbol")
    bids: List[Tuple[float, float]] = Field(
        ..., description="List of [price, size] bids (sorted descending by price)"
    )
    asks: List[Tuple[float, float]] = Field(
        ..., description="List of [price, size] asks (sorted ascending by price)"
    )

    def __init__(self, **data):
        """Validate OrderBook constraints on initialization."""
        super().__init__(**data)
        
        # Validate all prices are positive and sizes are non-negative
        for price, size in self.bids + self.asks:
            if price <= 0:
                raise ValueError(f"Order price must be positive, got {price}")
            if size < 0:
                raise ValueError(f"Order size must be non-negative, got {size}")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "symbol": "BTC/USD",
                "bids": [[44999.0, 10.0], [44998.0, 20.0]],
                "asks": [[45001.0, 15.0], [45002.0, 25.0]],
            }
        }


class FundamentalData(BaseModel):
    """Fundamental data for an asset."""

    symbol: str = Field(..., description="Asset symbol")
    market_cap: float = Field(default=0.0, ge=0, description="Market capitalization (must be >= 0)")
    pe_ratio: float = Field(default=0.0, ge=0, description="Price-to-earnings ratio (must be >= 0)")
    revenue: float = Field(default=0.0, ge=0, description="Annual revenue (must be >= 0)")
    description: str = Field(default="", description="Asset description")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "symbol": "AAPL",
                "market_cap": 2800000000000,
                "pe_ratio": 28.5,
                "revenue": 394328000000,
                "description": "Apple Inc.",
            }
        }
