"""
Quick Reference Guide for Data Layer Usage
===========================================

This file provides quick copy-paste examples for using the data layer.
"""

# ============================================================================
# SETUP & INITIALIZATION
# ============================================================================

"""
1. Install dependencies:
   pip install -r requirements.txt

2. Configure .env file:
   Copy .env.example to .env and add your API keys:
   - BINANCE_API_KEY=your_key
   - BINANCE_SECRET=your_secret
   - ALPACA_API_KEY=your_key
   - ALPACA_SECRET=your_secret

3. Import in your code:
"""

from data import CryptoDataProvider, StockDataProvider, DataFetcher, OHLCV
import asyncio


# ============================================================================
# CRYPTO PROVIDER EXAMPLES
# ============================================================================

async def crypto_examples():
    """Example usage of CryptoDataProvider."""
    
    # Initialize provider
    crypto = CryptoDataProvider()
    
    # Fetch OHLCV data
    try:
        ohlcv = await crypto.fetch_ohlcv(
            symbol="BTCUSDT",
            timeframe="1h",
            limit=100
        )
        print(f"Got {len(ohlcv)} candles for BTCUSDT")
        print(f"Latest close: {ohlcv[-1].close}")
    except Exception as e:
        print(f"Error fetching OHLCV: {e}")
    
    # Fetch ticker
    try:
        ticker = await crypto.fetch_ticker("ETHUSDT")
        print(f"ETH Price: ${ticker.price}")
        print(f"Bid/Ask: {ticker.bid}/{ticker.ask}")
        print(f"24h Volume: {ticker.volume_24h}")
    except Exception as e:
        print(f"Error fetching ticker: {e}")
    
    # Fetch order book
    try:
        orderbook = await crypto.fetch_orderbook("BTCUSDT", depth=5)
        print(f"BTC Order Book:")
        print(f"  Top bid: {orderbook.bids[0] if orderbook.bids else 'N/A'}")
        print(f"  Top ask: {orderbook.asks[0] if orderbook.asks else 'N/A'}")
    except Exception as e:
        print(f"Error fetching orderbook: {e}")


# ============================================================================
# STOCK PROVIDER EXAMPLES
# ============================================================================

async def stock_examples():
    """Example usage of StockDataProvider."""
    
    # Initialize provider
    stock = StockDataProvider()
    
    # Fetch OHLCV data
    try:
        ohlcv = await stock.fetch_ohlcv(
            symbol="AAPL",
            timeframe="1h",
            limit=50
        )
        print(f"Got {len(ohlcv)} bars for AAPL")
        if ohlcv:
            print(f"Latest close: ${ohlcv[-1].close}")
    except Exception as e:
        print(f"Error fetching OHLCV: {e}")
    
    # Fetch ticker
    try:
        ticker = await stock.fetch_ticker("MSFT")
        print(f"MSFT Price: ${ticker.price}")
        print(f"Bid/Ask: ${ticker.bid}/${ticker.ask}")
    except Exception as e:
        print(f"Error fetching ticker: {e}")
    
    # Fetch quote/orderbook
    try:
        orderbook = await stock.fetch_orderbook("AAPL")
        print(f"AAPL Quote:")
        print(f"  Bid: {orderbook.bids[0] if orderbook.bids else 'N/A'}")
        print(f"  Ask: {orderbook.asks[0] if orderbook.asks else 'N/A'}")
    except Exception as e:
        print(f"Error fetching orderbook: {e}")


# ============================================================================
# DATA FETCHER (MULTI-ASSET) EXAMPLES
# ============================================================================

async def fetcher_examples():
    """Example usage of DataFetcher for concurrent multi-asset fetching."""
    
    # Initialize fetcher
    fetcher = DataFetcher()
    
    # Fetch multiple assets at once (crypto AND stocks)
    try:
        data = await fetcher.fetch_multi_asset(
            symbols={
                'crypto': ['BTCUSDT', 'ETHUSDT'],
                'stock': ['AAPL', 'MSFT']
            },
            timeframe='1h',
            limit=100
        )
        
        # Access crypto data
        btc_data = data['crypto']['BTCUSDT']
        eth_data = data['crypto']['ETHUSDT']
        print(f"BTC: {len(btc_data)} candles")
        print(f"ETH: {len(eth_data)} candles")
        
        # Access stock data
        aapl_data = data['stock']['AAPL']
        msft_data = data['stock']['MSFT']
        print(f"AAPL: {len(aapl_data)} bars")
        print(f"MSFT: {len(msft_data)} bars")
        
    except Exception as e:
        print(f"Error fetching multi-asset: {e}")
    
    # Fetch only crypto
    try:
        crypto_data = await fetcher.fetch_crypto_batch(
            symbols=['BTCUSDT', 'ETHUSDT', 'BNBUSDT'],
            timeframe='1d',
            limit=30
        )
        for symbol, candles in crypto_data.items():
            print(f"{symbol}: {len(candles)} candles")
    except Exception as e:
        print(f"Error fetching crypto batch: {e}")
    
    # Fetch only stocks
    try:
        stock_data = await fetcher.fetch_stock_batch(
            symbols=['AAPL', 'MSFT', 'GOOGL', 'AMZN'],
            timeframe='1h',
            limit=50
        )
        for symbol, bars in stock_data.items():
            print(f"{symbol}: {len(bars)} bars")
    except Exception as e:
        print(f"Error fetching stock batch: {e}")


# ============================================================================
# WORKING WITH OHLCV DATA
# ============================================================================

async def ohlcv_processing_examples():
    """Example data processing on OHLCV candles."""
    
    crypto = CryptoDataProvider()
    
    # Fetch data
    ohlcv_list = await crypto.fetch_ohlcv("BTCUSDT", timeframe="1h", limit=20)
    
    if not ohlcv_list:
        print("No data returned")
        return
    
    # Simple analysis
    prices = [candle.close for candle in ohlcv_list]
    print(f"BTC Statistics:")
    print(f"  Close prices: {prices}")
    print(f"  Highest: ${max(candle.high for candle in ohlcv_list):.2f}")
    print(f"  Lowest: ${min(candle.low for candle in ohlcv_list):.2f}")
    print(f"  Latest Close: ${ohlcv_list[-1].close:.2f}")
    print(f"  Total Volume: {sum(candle.volume for candle in ohlcv_list):.0f}")
    
    # Access individual candle
    latest_candle = ohlcv_list[-1]
    print(f"\nLatest Candle Details:")
    print(f"  Time: {latest_candle.timestamp}")
    print(f"  Open: ${latest_candle.open:.2f}")
    print(f"  High: ${latest_candle.high:.2f}")
    print(f"  Low: ${latest_candle.low:.2f}")
    print(f"  Close: ${latest_candle.close:.2f}")
    print(f"  Volume: {latest_candle.volume:.0f}")


# ============================================================================
# ERROR HANDLING
# ============================================================================

async def error_handling_examples():
    """Example error handling patterns."""
    
    from core.exceptions import DataError
    
    crypto = CryptoDataProvider()
    
    # Handle specific data errors
    try:
        # Invalid symbol
        data = await crypto.fetch_ohlcv("INVALID_SYMBOL", timeframe="1h")
    except DataError as e:
        print(f"Data error (expected): {e}")
    
    # Handle rate limiting gracefully
    try:
        # Make many requests quickly
        for i in range(100):
            try:
                await crypto.fetch_ticker("BTCUSDT")
            except DataError as e:
                if "Rate limit" in str(e):
                    print(f"Rate limit hit, waiting...")
                    await asyncio.sleep(1)
    except Exception as e:
        print(f"Unexpected error: {e}")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

async def main():
    """Run all examples."""
    
    print("=" * 60)
    print("CRYPTO EXAMPLES")
    print("=" * 60)
    await crypto_examples()
    
    print("\n" + "=" * 60)
    print("STOCK EXAMPLES")
    print("=" * 60)
    await stock_examples()
    
    print("\n" + "=" * 60)
    print("MULTI-ASSET FETCHER EXAMPLES")
    print("=" * 60)
    await fetcher_examples()
    
    print("\n" + "=" * 60)
    print("OHLCV PROCESSING EXAMPLES")
    print("=" * 60)
    await ohlcv_processing_examples()
    
    print("\n" + "=" * 60)
    print("ERROR HANDLING EXAMPLES")
    print("=" * 60)
    await error_handling_examples()


if __name__ == "__main__":
    # Run examples
    asyncio.run(main())
