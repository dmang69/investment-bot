"""Abstract base class for data providers."""

from abc import ABC, abstractmethod
from typing import List
from data.models import OHLCV, Ticker, OrderBook, FundamentalData


class DataProvider(ABC):
    """Abstract base class for market data providers."""

    @abstractmethod
    async def fetch_ohlcv(
        self, symbol: str, timeframe: str = "1h", limit: int = 100
    ) -> List[OHLCV]:
        """
        Fetch OHLCV candlestick data.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USD")
            timeframe: Candle period (e.g., "1m", "5m", "1h", "1d")
            limit: Number of candles to fetch

        Returns:
            List of OHLCV objects
        """
        pass

    @abstractmethod
    async def fetch_ticker(self, symbol: str) -> Ticker:
        """
        Fetch current ticker information.

        Args:
            symbol: Trading pair symbol

        Returns:
            Ticker object with current prices and volume
        """
        pass

    @abstractmethod
    async def fetch_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        """
        Fetch current order book snapshot.

        Args:
            symbol: Trading pair symbol
            depth: Number of levels to fetch on each side

        Returns:
            OrderBook object with bids and asks
        """
        pass

    @abstractmethod
    async def fetch_fundamentals(self, symbol: str) -> FundamentalData:
        """
        Fetch fundamental data for an asset.

        Args:
            symbol: Asset symbol

        Returns:
            FundamentalData object
        """
        pass
