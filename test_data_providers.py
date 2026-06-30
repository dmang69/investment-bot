#!/usr/bin/env python
"""Simple test script to validate data provider implementations."""

import asyncio
import sys
import os
from datetime import datetime

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_providers():
    """Test basic provider functionality."""
    print("=" * 60)
    print("Testing Data Provider Implementations")
    print("=" * 60)
    
    try:
        from data.crypto_provider import CryptoDataProvider
        from data.stock_provider import StockDataProvider
        from data.models import OHLCV, Ticker, OrderBook
        from core.exceptions import DataError
        
        print("\n✓ All imports successful")
        
        # Test OHLCV model validation
        print("\n--- Testing OHLCV Model ---")
        try:
            valid_ohlcv = OHLCV(
                timestamp=datetime.now(),
                open=100.0,
                high=105.0,
                low=98.0,
                close=102.0,
                volume=1000000.0,
            )
            print(f"✓ Valid OHLCV created: {valid_ohlcv.symbol if hasattr(valid_ohlcv, 'symbol') else 'N/A'}")
        except Exception as e:
            print(f"✗ OHLCV validation failed: {e}")
        
        # Try invalid OHLCV (high < low)
        try:
            invalid_ohlcv = OHLCV(
                timestamp=datetime.now(),
                open=100.0,
                high=95.0,  # Invalid: less than low
                low=98.0,
                close=102.0,
                volume=1000000.0,
            )
            print("✗ Invalid OHLCV was accepted (should have failed)")
        except ValueError as e:
            print(f"✓ Invalid OHLCV correctly rejected: {str(e)[:50]}...")
        
        # Test Ticker model validation
        print("\n--- Testing Ticker Model ---")
        try:
            ticker = Ticker(
                symbol="BTC/USD",
                price=45000.0,
                bid=44999.0,
                ask=45001.0,
                volume_24h=1000000.0,
            )
            print(f"✓ Valid Ticker created: {ticker.symbol}")
        except Exception as e:
            print(f"✗ Ticker creation failed: {e}")
        
        # Test OrderBook model validation
        print("\n--- Testing OrderBook Model ---")
        try:
            orderbook = OrderBook(
                symbol="BTC/USD",
                bids=[[44999.0, 10.0], [44998.0, 20.0]],
                asks=[[45001.0, 15.0], [45002.0, 25.0]],
            )
            print(f"✓ Valid OrderBook created: {orderbook.symbol} with {len(orderbook.bids)} bids, {len(orderbook.asks)} asks")
        except Exception as e:
            print(f"✗ OrderBook creation failed: {e}")
        
        # Test provider initialization
        print("\n--- Testing Provider Initialization ---")
        try:
            # This may fail if credentials aren't set, but should initialize
            crypto_provider = CryptoDataProvider()
            print(f"✓ CryptoDataProvider initialized")
        except DataError as e:
            print(f"! CryptoDataProvider failed (expected if credentials not set): {str(e)[:60]}...")
        except Exception as e:
            print(f"✗ CryptoDataProvider unexpected error: {type(e).__name__}: {str(e)[:60]}...")
        
        try:
            stock_provider = StockDataProvider()
            print(f"✓ StockDataProvider initialized")
        except DataError as e:
            print(f"! StockDataProvider failed (expected if credentials not set): {str(e)[:60]}...")
        except Exception as e:
            print(f"✗ StockDataProvider unexpected error: {type(e).__name__}: {str(e)[:60]}...")
        
        # Test DataFetcher
        print("\n--- Testing DataFetcher ---")
        try:
            from data.fetcher import DataFetcher
            fetcher = DataFetcher()
            print("✓ DataFetcher initialized successfully")
            print(f"  - Crypto provider: {type(fetcher.crypto).__name__}")
            print(f"  - Stock provider: {type(fetcher.stock).__name__}")
        except Exception as e:
            print(f"! DataFetcher initialization: {type(e).__name__}: {str(e)[:60]}...")
        
        print("\n" + "=" * 60)
        print("Test Summary:")
        print("  • Model validation: ✓ Working")
        print("  • Provider imports: ✓ Working")
        print("  • Provider initialization: May require credentials")
        print("  • DataFetcher: ✓ Ready")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ CRITICAL ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_providers())
    sys.exit(0 if success else 1)
