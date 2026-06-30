"""Cryptocurrency data provider using CCXT."""

from typing import List, Optional
from datetime import datetime
import ccxt
from data.base import DataProvider
from data.models import OHLCV, Ticker, OrderBook, FundamentalData
from core.logger import get_logger
from core.exceptions import DataError
from config.settings import settings


logger = get_logger(__name__)


class CryptoDataProvider(DataProvider):
    """
    Cryptocurrency data provider using CCXT for multi-exchange support.
    
    Supports real-time OHLCV, ticker, and order book data from Binance.
    Includes error handling, rate limiting awareness, and comprehensive logging.
    """

    def __init__(self):
        """Initialize CCXT exchange instance with Binance."""
        try:
            api_key = settings.exchange.binance_api_key
            secret = settings.exchange.binance_secret
            
            exchange_config = {
                "enableRateLimit": True,
                "options": {
                    "defaultType": "spot",
                },
            }
            
            if api_key and secret:
                exchange_config["apiKey"] = api_key
                exchange_config["secret"] = secret
                logger.info("Initializing Binance exchange with API credentials")
            else:
                logger.warning(
                    "Initializing Binance exchange without API credentials - "
                    "read-only operations only"
                )
            
            self.exchange = ccxt.binance(exchange_config)
            logger.info("CCXT Binance exchange initialized successfully")
        except Exception as e:
            logger.error(
                "Failed to initialize CCXT exchange",
                error=str(e),
                exchange="binance",
            )
            raise DataError(f"Failed to initialize CCXT exchange: {str(e)}")

    def _validate_symbol(self, symbol: str) -> bool:
        """
        Validate if symbol is a valid trading pair on the exchange.
        
        Args:
            symbol: Trading pair symbol (e.g., "BTC/USDT")
            
        Returns:
            True if symbol is valid, False otherwise
        """
        try:
            if not self.exchange.has["fetchOHLCV"]:
                logger.warning("Exchange does not support OHLCV fetching")
                return False
            
            # Simple format validation
            if "/" not in symbol:
                logger.warning("Invalid symbol format", symbol=symbol)
                return False
            
            return True
        except Exception as e:
            logger.error(
                "Error validating symbol",
                symbol=symbol,
                error=str(e),
            )
            return False

    async def fetch_ohlcv(
        self, symbol: str, timeframe: str = "1h", limit: int = 100
    ) -> List[OHLCV]:
        """
        Fetch OHLCV candlestick data from Binance via CCXT.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USDT")
            timeframe: Candle period (e.g., "1m", "5m", "15m", "1h", "4h", "1d")
            limit: Number of candles to fetch (max ~1000 depending on exchange)

        Returns:
            List of OHLCV objects sorted by timestamp ascending

        Raises:
            DataError: If fetch fails due to invalid symbol, network error, rate limit, etc.
        """
        if not self._validate_symbol(symbol):
            error_msg = f"Invalid symbol format: {symbol}"
            logger.error(error_msg, symbol=symbol)
            raise DataError(error_msg)
        
        try:
            logger.info(
                "Fetching OHLCV data",
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
            )
            
            # CCXT returns OHLCV as [[timestamp, o, h, l, c, v], ...]
            ohlcv_data = await self.exchange.fetch_ohlcv(
                symbol, timeframe=timeframe, limit=limit
            )
            
            if not ohlcv_data:
                logger.warning(
                    "No OHLCV data returned",
                    symbol=symbol,
                    timeframe=timeframe,
                )
                return []
            
            # Convert to OHLCV model objects
            result = []
            for candle in ohlcv_data:
                timestamp_ms, o, h, l, c, v = candle
                timestamp = datetime.fromtimestamp(timestamp_ms / 1000.0)
                
                # Validate data integrity
                if not (h >= l and h >= o and h >= c):
                    logger.warning(
                        "Invalid OHLCV data: high < other prices",
                        symbol=symbol,
                        high=h,
                        low=l,
                        open=o,
                        close=c,
                    )
                    continue
                
                if any(price < 0 for price in [o, h, l, c]):
                    logger.warning(
                        "Invalid OHLCV data: negative price",
                        symbol=symbol,
                    )
                    continue
                
                if v < 0:
                    logger.warning(
                        "Invalid OHLCV data: negative volume",
                        symbol=symbol,
                    )
                    continue
                
                result.append(
                    OHLCV(
                        timestamp=timestamp,
                        open=float(o),
                        high=float(h),
                        low=float(l),
                        close=float(c),
                        volume=float(v),
                    )
                )
            
            # Ensure sorted by timestamp ascending
            result.sort(key=lambda x: x.timestamp)
            
            logger.info(
                "Successfully fetched OHLCV data",
                symbol=symbol,
                count=len(result),
                timeframe=timeframe,
            )
            return result
            
        except ccxt.RateLimitExceeded as e:
            error_msg = f"Rate limit exceeded for {symbol}"
            logger.warning(
                error_msg,
                symbol=symbol,
                retry_after=getattr(e, "retry_after", None),
            )
            raise DataError(error_msg)
        except ccxt.ExchangeNotAvailable as e:
            error_msg = f"Exchange not available: {str(e)}"
            logger.error(error_msg, symbol=symbol)
            raise DataError(error_msg)
        except ccxt.InvalidSymbol as e:
            error_msg = f"Invalid symbol: {symbol}"
            logger.error(error_msg, symbol=symbol)
            raise DataError(error_msg)
        except Exception as e:
            error_msg = f"Failed to fetch OHLCV for {symbol}: {str(e)}"
            logger.error(
                error_msg,
                symbol=symbol,
                timeframe=timeframe,
                error_type=type(e).__name__,
            )
            raise DataError(error_msg)

    async def fetch_ticker(self, symbol: str) -> Ticker:
        """
        Fetch current ticker information from Binance.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USDT")

        Returns:
            Ticker object with: symbol, price (last), bid, ask, volume_24h

        Raises:
            DataError: If fetch fails
        """
        if not self._validate_symbol(symbol):
            error_msg = f"Invalid symbol format: {symbol}"
            logger.error(error_msg, symbol=symbol)
            raise DataError(error_msg)
        
        try:
            logger.info("Fetching ticker data", symbol=symbol)
            
            ticker = await self.exchange.fetch_ticker(symbol)
            
            # Extract required fields
            last_price = ticker.get("last")
            bid = ticker.get("bid")
            ask = ticker.get("ask")
            volume_24h = ticker.get("quoteVolume", 0)
            
            if last_price is None:
                error_msg = f"No price data available for {symbol}"
                logger.error(error_msg, symbol=symbol)
                raise DataError(error_msg)
            
            # Handle missing bid/ask (use last price as fallback)
            if bid is None:
                bid = last_price
            if ask is None:
                ask = last_price
            
            logger.info(
                "Successfully fetched ticker",
                symbol=symbol,
                price=last_price,
                bid=bid,
                ask=ask,
            )
            
            return Ticker(
                symbol=symbol,
                price=float(last_price),
                bid=float(bid),
                ask=float(ask),
                volume_24h=float(volume_24h) if volume_24h else 0.0,
            )
            
        except ccxt.RateLimitExceeded as e:
            error_msg = f"Rate limit exceeded for {symbol}"
            logger.warning(error_msg, symbol=symbol)
            raise DataError(error_msg)
        except ccxt.InvalidSymbol as e:
            error_msg = f"Invalid symbol: {symbol}"
            logger.error(error_msg, symbol=symbol)
            raise DataError(error_msg)
        except Exception as e:
            error_msg = f"Failed to fetch ticker for {symbol}: {str(e)}"
            logger.error(
                error_msg,
                symbol=symbol,
                error_type=type(e).__name__,
            )
            raise DataError(error_msg)

    async def fetch_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        """
        Fetch L2 order book snapshot from Binance.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USDT")
            depth: Number of levels to fetch on each side

        Returns:
            OrderBook object with: symbol, bids (list of [price, qty]), asks (list of [price, qty])

        Raises:
            DataError: If fetch fails
        """
        if not self._validate_symbol(symbol):
            error_msg = f"Invalid symbol format: {symbol}"
            logger.error(error_msg, symbol=symbol)
            raise DataError(error_msg)
        
        try:
            logger.info(
                "Fetching order book",
                symbol=symbol,
                depth=depth,
            )
            
            # Fetch order book from exchange
            orderbook = await self.exchange.fetch_order_book(
                symbol, limit=depth
            )
            
            # Extract bids and asks
            bids = orderbook.get("bids", [])
            asks = orderbook.get("asks", [])
            
            if not bids or not asks:
                logger.warning(
                    "Empty order book data",
                    symbol=symbol,
                    bids_count=len(bids),
                    asks_count=len(asks),
                )
            
            # Convert to tuples of (price, quantity)
            bid_list = [(float(b[0]), float(b[1])) for b in bids[:depth]]
            ask_list = [(float(a[0]), float(a[1])) for a in asks[:depth]]
            
            logger.info(
                "Successfully fetched order book",
                symbol=symbol,
                bid_levels=len(bid_list),
                ask_levels=len(ask_list),
            )
            
            return OrderBook(
                symbol=symbol,
                bids=bid_list,
                asks=ask_list,
            )
            
        except ccxt.RateLimitExceeded as e:
            error_msg = f"Rate limit exceeded for {symbol}"
            logger.warning(error_msg, symbol=symbol)
            raise DataError(error_msg)
        except ccxt.InvalidSymbol as e:
            error_msg = f"Invalid symbol: {symbol}"
            logger.error(error_msg, symbol=symbol)
            raise DataError(error_msg)
        except Exception as e:
            error_msg = f"Failed to fetch order book for {symbol}: {str(e)}"
            logger.error(
                error_msg,
                symbol=symbol,
                error_type=type(e).__name__,
            )
            raise DataError(error_msg)

    async def fetch_fundamentals(self, symbol: str) -> FundamentalData:
        """
        Fetch fundamental data for a cryptocurrency.

        Currently limited as CCXT doesn't provide fundamental data.
        For production use, integrate with CoinGecko or CoinMarketCap API.

        Args:
            symbol: Asset symbol

        Returns:
            FundamentalData object (with placeholder values)

        Raises:
            DataError: If fetch fails
        """
        logger.warning(
            "fetch_fundamentals called - CCXT does not provide fundamental data. "
            "Consider using CoinGecko or CoinMarketCap API.",
            symbol=symbol,
        )
        
        raise DataError(
            "Cryptocurrency fundamentals not available via CCXT. "
            "Use CoinGecko or CoinMarketCap API for fundamental data."
        )
