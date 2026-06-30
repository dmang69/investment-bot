"""Multi-asset data fetcher for concurrent data retrieval."""

import asyncio
from typing import Dict, List, Optional
from data.crypto_provider import CryptoDataProvider
from data.stock_provider import StockDataProvider
from data.models import OHLCV
from config.settings import settings
from core.logger import get_logger
from core.exceptions import DataError


logger = get_logger(__name__)


class DataFetcher:
    """
    Convenience wrapper managing both crypto and stock data providers.
    
    Supports concurrent multi-asset data fetching with proper error handling
    and logging for both cryptocurrency and equity assets.
    """

    def __init__(self, config: Optional[settings.__class__] = None):
        """
        Initialize DataFetcher with both providers.
        
        Args:
            config: Settings object (uses global settings if None)
        """
        try:
            self.crypto = CryptoDataProvider()
            self.stock = StockDataProvider()
            logger.info("DataFetcher initialized successfully")
        except Exception as e:
            logger.error(
                "Failed to initialize DataFetcher",
                error=str(e),
            )
            raise DataError(f"Failed to initialize data providers: {str(e)}")

    async def fetch_multi_asset(
        self,
        symbols: Dict[str, List[str]],
        timeframe: str = "1h",
        limit: int = 100,
    ) -> Dict[str, Dict[str, List[OHLCV]]]:
        """
        Fetch OHLCV data for multiple assets concurrently.
        
        Uses asyncio.gather for concurrent fetching across all assets,
        properly handling errors for individual assets while continuing
        with others.
        
        Args:
            symbols: Dictionary with asset type keys and symbol lists
                Expected format: {
                    'crypto': ['BTCUSDT', 'ETHUSDT'],
                    'stock': ['AAPL', 'MSFT']
                }
            timeframe: Timeframe for OHLCV data (e.g., '1h', '1d')
            limit: Number of candles/bars to fetch per asset
            
        Returns:
            Dictionary with fetched data organized by asset type and symbol
            Format: {
                'crypto': {'BTCUSDT': [OHLCV, ...], 'ETHUSDT': [OHLCV, ...]},
                'stock': {'AAPL': [OHLCV, ...], 'MSFT': [OHLCV, ...]}
            }
            
        Example:
            fetcher = DataFetcher()
            data = await fetcher.fetch_multi_asset({
                'crypto': ['BTCUSDT', 'ETHUSDT'],
                'stock': ['AAPL', 'MSFT']
            })
            btc_data = data['crypto']['BTCUSDT']
            aapl_data = data['stock']['AAPL']
        """
        logger.info(
            "Starting multi-asset fetch",
            asset_types=list(symbols.keys()),
            total_symbols=sum(len(syms) for syms in symbols.values()),
            timeframe=timeframe,
            limit=limit,
        )
        
        result: Dict[str, Dict[str, List[OHLCV]]] = {}
        tasks = []
        task_map = {}  # Map task to (asset_type, symbol) for error handling
        
        # Create crypto fetch tasks
        if "crypto" in symbols:
            result["crypto"] = {}
            for symbol in symbols["crypto"]:
                task = self.crypto.fetch_ohlcv(
                    symbol, timeframe=timeframe, limit=limit
                )
                tasks.append(task)
                task_map[id(task)] = ("crypto", symbol)
        
        # Create stock fetch tasks
        if "stock" in symbols:
            result["stock"] = {}
            for symbol in symbols["stock"]:
                task = self.stock.fetch_ohlcv(
                    symbol, timeframe=timeframe, limit=limit
                )
                tasks.append(task)
                task_map[id(task)] = ("stock", symbol)
        
        if not tasks:
            logger.warning("No symbols provided for fetching")
            return result
        
        # Execute all tasks concurrently
        try:
            responses = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(
                "Unexpected error during concurrent fetch",
                error=str(e),
            )
            raise DataError(f"Multi-asset fetch failed: {str(e)}")
        
        # Process responses and map back to symbols
        for task, response in zip(tasks, responses):
            asset_type, symbol = task_map[id(task)]
            
            if isinstance(response, Exception):
                logger.error(
                    "Failed to fetch asset",
                    asset_type=asset_type,
                    symbol=symbol,
                    error=str(response),
                )
                # Store empty list for failed assets
                result[asset_type][symbol] = []
            else:
                logger.info(
                    "Successfully fetched asset",
                    asset_type=asset_type,
                    symbol=symbol,
                    data_points=len(response),
                )
                result[asset_type][symbol] = response
        
        logger.info(
            "Multi-asset fetch completed",
            crypto_symbols_succeeded=len([
                s for s, d in result.get("crypto", {}).items() if d
            ]),
            stock_symbols_succeeded=len([
                s for s, d in result.get("stock", {}).items() if d
            ]),
        )
        
        return result

    async def fetch_crypto_batch(
        self,
        symbols: List[str],
        timeframe: str = "1h",
        limit: int = 100,
    ) -> Dict[str, List[OHLCV]]:
        """
        Fetch OHLCV data for multiple crypto assets concurrently.
        
        Convenience method for crypto-only batches.
        
        Args:
            symbols: List of crypto symbols (e.g., ['BTCUSDT', 'ETHUSDT'])
            timeframe: Timeframe for OHLCV data
            limit: Number of candles to fetch per asset
            
        Returns:
            Dictionary mapping symbol to OHLCV list
        """
        result = await self.fetch_multi_asset(
            {"crypto": symbols},
            timeframe=timeframe,
            limit=limit,
        )
        return result.get("crypto", {})

    async def fetch_stock_batch(
        self,
        symbols: List[str],
        timeframe: str = "1h",
        limit: int = 100,
    ) -> Dict[str, List[OHLCV]]:
        """
        Fetch OHLCV data for multiple stock assets concurrently.
        
        Convenience method for stock-only batches.
        
        Args:
            symbols: List of stock symbols (e.g., ['AAPL', 'MSFT'])
            timeframe: Timeframe for OHLCV data
            limit: Number of bars to fetch per asset
            
        Returns:
            Dictionary mapping symbol to OHLCV list
        """
        result = await self.fetch_multi_asset(
            {"stock": symbols},
            timeframe=timeframe,
            limit=limit,
        )
        return result.get("stock", {})
