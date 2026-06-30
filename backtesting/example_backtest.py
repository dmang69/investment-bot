"""Example backtest demonstrating the complete backtesting engine."""

import asyncio
from datetime import datetime, timedelta
from data.models import OHLCV
from strategies.base_strategy import BaseStrategy, Signal
from agents.risk_agent import RiskAgent
from core.event_bus import EventBus
from config.settings import Settings
from backtesting.engine import BacktestEngine
from backtesting.visualizations import (
    plot_equity_curve_ascii,
    plot_drawdown_ascii,
    format_metrics_table,
    create_summary_report,
    create_trade_log_table,
)


class SimpleMovingAverageStrategy(BaseStrategy):
    """
    Simple moving average crossover strategy for demonstration.

    Buy when short MA crosses above long MA.
    Sell when short MA crosses below long MA.
    """

    def __init__(self, short_period: int = 10, long_period: int = 20):
        """Initialize strategy parameters."""
        self.short_period = short_period
        self.long_period = long_period

    async def generate_signal(self, ohlcv_data: list) -> Signal:
        """
        Generate trading signal based on MA crossover.

        Args:
            ohlcv_data: List of OHLCV candles

        Returns:
            Trading signal (BUY, SELL, or HOLD)
        """
        if len(ohlcv_data) < self.long_period:
            return Signal(symbol="TEST", action="HOLD", confidence=0.0, metadata={})

        # Calculate moving averages
        closes = [candle.close for candle in ohlcv_data]
        short_ma = sum(closes[-self.short_period :]) / self.short_period
        long_ma = sum(closes[-self.long_period :]) / self.long_period

        # Previous values for crossover detection
        prev_closes = closes[:-1]
        prev_short_ma = sum(prev_closes[-self.short_period :]) / self.short_period
        prev_long_ma = sum(prev_closes[-self.long_period :]) / self.long_period

        # Detect crossovers
        if prev_short_ma <= prev_long_ma and short_ma > long_ma:
            return Signal(
                symbol="TEST",
                action="BUY",
                confidence=0.8,
                metadata={"short_ma": short_ma, "long_ma": long_ma},
            )

        elif prev_short_ma >= prev_long_ma and short_ma < long_ma:
            return Signal(
                symbol="TEST",
                action="SELL",
                confidence=0.8,
                metadata={"short_ma": short_ma, "long_ma": long_ma},
            )

        return Signal(symbol="TEST", action="HOLD", confidence=0.5, metadata={})


def generate_sample_data(num_candles: int = 250) -> list:
    """
    Generate sample OHLCV data for testing.

    Creates synthetic price data with realistic price movements.

    Args:
        num_candles: Number of candles to generate

    Returns:
        List of OHLCV objects
    """
    ohlcv_list = []
    base_price = 100.0
    timestamp = datetime(2024, 1, 1)

    for _ in range(num_candles):
        # Generate realistic price movement
        import random

        daily_return = random.gauss(0.0005, 0.015)  # Mean 0.05%, std 1.5%
        new_price = base_price * (1 + daily_return)

        # Intraday variation
        open_price = base_price
        close_price = new_price
        high_price = max(open_price, close_price) * (1 + abs(random.gauss(0, 0.01)))
        low_price = min(open_price, close_price) * (1 - abs(random.gauss(0, 0.01)))
        volume = random.uniform(1000000, 5000000)

        ohlcv = OHLCV(
            timestamp=timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
        )

        ohlcv_list.append(ohlcv)
        base_price = new_price
        timestamp += timedelta(days=1)

    return ohlcv_list


async def run_example_backtest():
    """Run complete example backtest with all components."""

    print("=" * 80)
    print("BACKTESTING ENGINE EXAMPLE")
    print("=" * 80)

    # Initialize configuration
    settings = Settings()
    print("\n✓ Settings loaded")
    print(f"  - Max Drawdown: {settings.risk.max_drawdown_pct}%")
    print(f"  - Max Position Size: {settings.risk.max_position_size_pct}%")
    print(f"  - Max Leverage: {settings.risk.max_leverage}x")

    # Generate sample data
    print("\n✓ Generating sample market data...")
    ohlcv_data = generate_sample_data(num_candles=250)
    print(f"  - Generated {len(ohlcv_data)} candles")
    print(f"  - Date Range: {ohlcv_data[0].timestamp.date()} to {ohlcv_data[-1].timestamp.date()}")
    print(f"  - Price Range: ${ohlcv_data[0].close:.2f} to ${ohlcv_data[-1].close:.2f}")

    # Initialize engine
    print("\n✓ Initializing BacktestEngine...")
    engine = BacktestEngine(config=settings)

    # Load data
    print("✓ Loading OHLCV data for TEST symbol...")
    engine.load_ohlcv_data("TEST", ohlcv_data)

    # Initialize strategy
    print("✓ Initializing strategy (SMA crossover 10/20)...")
    strategy = SimpleMovingAverageStrategy(short_period=10, long_period=20)

    # Initialize risk agent
    print("✓ Initializing RiskAgent...")
    event_bus = EventBus()
    risk_agent = RiskAgent(
        event_bus=event_bus,
        max_drawdown_pct=settings.risk.max_drawdown_pct,
        max_position_size_pct=settings.risk.max_position_size_pct,
        max_leverage=settings.risk.max_leverage,
    )

    # Run backtest
    print(f"\n{'Backtesting...':.<50}", end="", flush=True)
    result = await engine.run_backtest(
        symbol="TEST",
        strategy=strategy,
        risk_agent=risk_agent,
        initial_cash=100000.0,
        commission=0.001,
    )
    print(" ✓")

    # Display results
    print("\n" + "=" * 80)
    print("BACKTEST RESULTS")
    print("=" * 80)

    # Summary report
    print("\n" + create_summary_report(
        total_return=result.total_return,
        annual_return=result.annual_return,
        sharpe_ratio=result.sharpe_ratio,
        sortino_ratio=result.sortino_ratio,
        max_drawdown=result.max_drawdown,
        num_trades=result.num_trades,
        win_rate=result.win_rate,
        profit_factor=result.profit_factor,
        final_value=result.final_value,
        initial_cash=result.initial_cash,
    ))

    # Metrics table
    metrics = result.to_dict()
    print("\n" + format_metrics_table(metrics))

    # Trade log
    if result.trades:
        print("\n" + create_trade_log_table(
            [
                {
                    "entry_timestamp": t.entry_timestamp,
                    "exit_timestamp": t.exit_timestamp,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "return_pct": t.return_pct,
                    "duration_days": t.duration_days,
                }
                for t in result.trades
            ]
        ))
    else:
        print("\n⚠ No trades executed during backtest")

    # Charts
    print("\n" + "=" * 80)
    print("EQUITY CURVE")
    print("=" * 80)
    print(plot_equity_curve_ascii(result.equity_curve, width=80, height=15))

    print("\n" + "=" * 80)
    print("DRAWDOWN CURVE")
    print("=" * 80)
    print(plot_drawdown_ascii(result.drawdown_curve, width=80, height=12))

    # Risk violations
    if result.risk_violations:
        print("\n" + "=" * 80)
        print(f"RISK VIOLATIONS ({len(result.risk_violations)})")
        print("=" * 80)
        for violation in result.risk_violations[:10]:  # Show first 10
            print(f"  [{violation.timestamp.strftime('%Y-%m-%d %H:%M')}] "
                  f"{violation.violation_type.upper()}: {violation.details}")
        if len(result.risk_violations) > 10:
            print(f"  ... and {len(result.risk_violations) - 10} more violations")

    print("\n✓ Backtest complete!")


if __name__ == "__main__":
    asyncio.run(run_example_backtest())
