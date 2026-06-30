"""Stock data provider using Alpaca Trade API."""

from typing import List, Optional
from datetime import datetime
import httpx
from data.base import DataProvider
from data.models import OHLCV, Ticker, OrderBook, FundamentalData
from core.logger import get_logger
from core.exceptions import DataError
from config.settings import settings


logger = get_logger(__name__)


class StockDataProvider(DataProvider):
    """
    Stock market data provider using Alpaca Trade API.
    
    Supports real-time OHLCV, ticker, and quote data from US equities market.
    Includes market hours awareness, error handling, and comprehensive logging.
    """

    def __init__(self):
        """Initialize Alpaca REST client with API credentials."""
        try:
            api_key = settings.exchange.alpaca_api_key
            secret = settings.exchange.alpaca_secret
            base_url = settings.exchange.alpaca_base_url
            
            if not api_key or not secret:
                raise DataError("Alpaca API credentials not configured")
            
            self.api_key = api_key
            self.secret = secret
            self.base_url = base_url
            
            # Standard headers for Alpaca API
            self.headers = {
                "APCA-API-KEY-ID": api_key,
            }
            
            self._market_open_cache: Optional[bool] = None
            self._market_open_cache_time: Optional[datetime] = None
            
            logger.info(
                "Alpaca stock provider initialized",
                base_url=base_url,
            )
        except Exception as e:
            logger.error(
                "Failed to initialize Alpaca stock provider",
                error=str(e),
            )
            raise DataError(f"Failed to initialize Alpaca provider: {str(e)}")

    def _validate_symbol(self, symbol: str) -> bool:
        """
        Validate if symbol is a valid US equity ticker.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL")
            
        Returns:
            True if symbol format is valid, False otherwise
        """
        try:
            # Basic validation: uppercase letters, 1-5 characters typically
            if not symbol or not isinstance(symbol, str):
                return False
            
            symbol = symbol.strip().upper()
            
            # Alpaca typically uses 1-5 character symbols
            if len(symbol) < 1 or len(symbol) > 5:
                logger.warning("Symbol length outside typical range", symbol=symbol)
                return False
            
            # Must be alphanumeric (some symbols have dots or hyphens)
            if not symbol.replace(".", "").replace("-", "").isalnum():
                logger.warning("Symbol contains invalid characters", symbol=symbol)
                return False
            
            return True
        except Exception as e:
            logger.error(
                "Error validating symbol",
                symbol=symbol,
                error=str(e),
            )
            return False

    async def _is_market_open(self) -> bool:
        """
        Check if US stock market is currently open.
        
        Caches result to avoid excessive API calls (cache expires every 5 minutes).
        
        Returns:
            True if market is open, False otherwise
        """
        try:
            # Check cache (5 minute TTL)
            now = datetime.now()
            if (
                self._market_open_cache is not None
                and self._market_open_cache_time is not None
                and (now - self._market_open_cache_time).total_seconds() < 300
            ):
                return self._market_open_cache
            
            # Fetch market status from Alpaca
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/v1/market/status",
                    headers=self.headers,
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()
                
                market_open = data.get("market", "closed") == "open"
                self._market_open_cache = market_open
                self._market_open_cache_time = now
                
                logger.info("Market status checked", market_open=market_open)
                return market_open
                
        except Exception as e:
            logger.warning(
                "Failed to check market status, assuming market closed",
                error=str(e),
            )
            # Conservative default: assume market is closed if we can't check
            return False

    async def fetch_ohlcv(
        self, symbol: str, timeframe: str = "1h", limit: int = 100
    ) -> List[OHLCV]:
        """
        Fetch OHLCV candlestick data from Alpaca market data API.

        Args:
            symbol: Stock symbol (e.g., "AAPL")
            timeframe: Bar period (e.g., "1m", "5m", "15m", "1h", "1d")
            limit: Number of bars to fetch

        Returns:
            List of OHLCV objects sorted by timestamp ascending

        Raises:
            DataError: If fetch fails due to invalid symbol, auth error, etc.
        """
        if not self._validate_symbol(symbol):
            error_msg = f"Invalid symbol format: {symbol}"
            logger.error(error_msg, symbol=symbol)
            raise DataError(error_msg)
        
        try:
            logger.info(
                "Fetching OHLCV data from Alpaca",
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
            )
            
            # Map our timeframe names to Alpaca's frame parameter
            frame_map = {
                "1m": "1Min",
                "5m": "5Min",
                "15m": "15Min",
                "1h": "1Hour",
                "1d": "1Day",
            }
            
            alpaca_frame = frame_map.get(timeframe)
            if not alpaca_frame:
                error_msg = f"Unsupported timeframe: {timeframe}"
                logger.error(error_msg, timeframe=timeframe)
                raise DataError(error_msg)
            
            # Alpaca Data API v2 bars endpoint
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/v2/stocks/{symbol}/bars",
                    params={
                        "timeframe": alpaca_frame,
                        "limit": limit,
                        "sort": "asc",
                    },
                    headers=self.headers,
                    timeout=15.0,
                )
                
                if response.status_code == 401:
                    error_msg = "Authentication failed - check Alpaca API credentials"
                    logger.error(error_msg)
                    raise DataError(error_msg)
                
                if response.status_code == 404:
                    error_msg = f"Symbol not found: {symbol}"
                    logger.error(error_msg, symbol=symbol)
                    raise DataError(error_msg)
                
                response.raise_for_status()
                data = response.json()
                
                bars = data.get("bars", [])
                if not bars:
                    logger.warning(
                        "No bar data returned",
                        symbol=symbol,
                        timeframe=timeframe,
                    )
                    return []
                
                # Convert Alpaca bar format to OHLCV models
                result = []
                for bar in bars:
                    try:
                        # Alpaca bars have: t, o, h, l, c, v
                        timestamp_str = bar.get("t")
                        open_price = bar.get("o")
                        high_price = bar.get("h")
                        low_price = bar.get("l")
                        close_price = bar.get("c")
                        volume = bar.get("v", 0)
                        
                        # Parse ISO format timestamp
                        if isinstance(timestamp_str, str):
                            # Handle timezone-aware datetime
                            if timestamp_str.endswith("Z"):
                                timestamp = datetime.fromisoformat(timestamp_str[:-1])
                            else:
                                timestamp = datetime.fromisoformat(timestamp_str)
                        else:
                            timestamp = datetime.fromtimestamp(timestamp_str)
                        
                        # Validate data
                        if not (high_price >= low_price and high_price >= open_price and high_price >= close_price):
                            logger.warning(
                                "Invalid OHLCV data: high < other prices",
                                symbol=symbol,
                                high=high_price,
                                low=low_price,
                            )
                            continue
                        
                        if any(price < 0 for price in [open_price, high_price, low_price, close_price]):
                            logger.warning(
                                "Invalid OHLCV data: negative price",
                                symbol=symbol,
                            )
                            continue
                        
                        if volume < 0:
                            logger.warning(
                                "Invalid OHLCV data: negative volume",
                                symbol=symbol,
                            )
                            continue
                        
                        result.append(
                            OHLCV(
                                timestamp=timestamp,
                                open=float(open_price),
                                high=float(high_price),
                                low=float(low_price),
                                close=float(close_price),
                                volume=float(volume),
                            )
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to parse bar data",
                            symbol=symbol,
                            error=str(e),
                        )
                        continue
                
                # Ensure sorted by timestamp ascending
                result.sort(key=lambda x: x.timestamp)
                
                logger.info(
                    "Successfully fetched OHLCV data",
                    symbol=symbol,
                    count=len(result),
                    timeframe=timeframe,
                )
                return result
                
        except DataError:
            raise
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
        Fetch current ticker information from Alpaca.

        Includes latest quote data with bid/ask spreads.

        Args:
            symbol: Stock symbol (e.g., "AAPL")

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
            logger.info("Fetching ticker data from Alpaca", symbol=symbol)
            
            # Get latest quote and trade
            async with httpx.AsyncClient() as client:
                # Fetch latest quote (bid/ask)
                quote_response = await client.get(
                    f"{self.base_url}/v2/stocks/{symbol}/quotes/latest",
                    headers=self.headers,
                    timeout=10.0,
                )
                
                # Fetch latest trade (last price)
                trade_response = await client.get(
                    f"{self.base_url}/v2/stocks/{symbol}/trades/latest",
                    headers=self.headers,
                    timeout=10.0,
                )
                
                if quote_response.status_code == 401 or trade_response.status_code == 401:
                    error_msg = "Authentication failed"
                    logger.error(error_msg)
                    raise DataError(error_msg)
                
                if quote_response.status_code == 404 or trade_response.status_code == 404:
                    error_msg = f"Symbol not found: {symbol}"
                    logger.error(error_msg, symbol=symbol)
                    raise DataError(error_msg)
                
                quote_response.raise_for_status()
                trade_response.raise_for_status()
                
                quote_data = quote_response.json().get("quote", {})
                trade_data = trade_response.json().get("trade", {})
                
                # Extract values with fallbacks
                last_price = trade_data.get("p") or quote_data.get("ap", None)
                bid = quote_data.get("bp", last_price)
                ask = quote_data.get("ap", last_price)
                volume_24h = 0.0  # Alpaca doesn't provide direct 24h volume in quote
                
                if last_price is None:
                    error_msg = f"No price data available for {symbol}"
                    logger.error(error_msg, symbol=symbol)
                    raise DataError(error_msg)
                
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
                    bid=float(bid) if bid else float(last_price),
                    ask=float(ask) if ask else float(last_price),
                    volume_24h=volume_24h,
                )
                
        except DataError:
            raise
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
        Fetch current order book snapshot from Alpaca.

        Note: Alpaca's latest quote provides single bid/ask levels only.
        The returned OrderBook will have 1 bid and 1 ask level.

        Args:
            symbol: Stock symbol (e.g., "AAPL")
            depth: Requested depth (Alpaca returns 1 level regardless)

        Returns:
            OrderBook object with: symbol, bids [[bid_price, bid_size]], asks [[ask_price, ask_size]]

        Raises:
            DataError: If fetch fails
        """
        if not self._validate_symbol(symbol):
            error_msg = f"Invalid symbol format: {symbol}"
            logger.error(error_msg, symbol=symbol)
            raise DataError(error_msg)
        
        try:
            logger.info(
                "Fetching order book (quote) from Alpaca",
                symbol=symbol,
                depth=depth,
            )
            
            # Fetch latest quote which includes bid/ask with sizes
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/v2/stocks/{symbol}/quotes/latest",
                    headers=self.headers,
                    timeout=10.0,
                )
                
                if response.status_code == 401:
                    error_msg = "Authentication failed"
                    logger.error(error_msg)
                    raise DataError(error_msg)
                
                if response.status_code == 404:
                    error_msg = f"Symbol not found: {symbol}"
                    logger.error(error_msg, symbol=symbol)
                    raise DataError(error_msg)
                
                response.raise_for_status()
                
                quote_data = response.json().get("quote", {})
                
                # Extract bid/ask with sizes
                bid_price = quote_data.get("bp")
                bid_size = quote_data.get("bs", 0)
                ask_price = quote_data.get("ap")
                ask_size = quote_data.get("as", 0)
                
                if bid_price is None or ask_price is None:
                    logger.warning(
                        "Incomplete quote data",
                        symbol=symbol,
                        bid_price=bid_price,
                        ask_price=ask_price,
                    )
                
                # Alpaca provides single level bid/ask, so create lists with 1 element
                bids = [(float(bid_price), float(bid_size))] if bid_price else []
                asks = [(float(ask_price), float(ask_size))] if ask_price else []
                
                logger.info(
                    "Successfully fetched order book",
                    symbol=symbol,
                    bid_levels=len(bids),
                    ask_levels=len(asks),
                )
                
                return OrderBook(
                    symbol=symbol,
                    bids=bids,
                    asks=asks,
                )
                
        except DataError:
            raise
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
        Fetch fundamental data for a stock.

        Currently limited as Alpaca API doesn't provide fundamental data.
        For production use, integrate with Alpha Vantage, IEX, or similar service.

        Args:
            symbol: Stock symbol

        Returns:
            FundamentalData object (with placeholder values)

        Raises:
            DataError: Always, as fundamental data not available via Alpaca
        """
        logger.warning(
            "fetch_fundamentals called - Alpaca API does not provide fundamental data. "
            "Consider using Alpha Vantage, IEX Cloud, or Financial Modeling Prep API.",
            symbol=symbol,
        )
        
        raise DataError(
            "Stock fundamentals not available via Alpaca API. "
            "Use Alpha Vantage, IEX Cloud, or Financial Modeling Prep for fundamental data."
        )
