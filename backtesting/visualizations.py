"""ASCII and text-based visualizations for backtest results."""

from typing import List
from datetime import datetime


def plot_equity_curve_ascii(
    equity_curve: List[float],
    width: int = 80,
    height: int = 20,
) -> str:
    """
    Generate ASCII art plot of equity curve.

    Args:
        equity_curve: List of portfolio values
        width: Chart width in characters
        height: Chart height in characters

    Returns:
        ASCII chart as multi-line string
    """
    if not equity_curve or len(equity_curve) < 2:
        return "Not enough data for chart"

    # Normalize values to height
    min_val = min(equity_curve)
    max_val = max(equity_curve)
    value_range = max_val - min_val if max_val > min_val else 1

    # Sample data to fit width
    step = max(1, len(equity_curve) // width)
    sampled = equity_curve[::step]

    # Create chart
    lines = []
    for h in range(height, -1, -1):
        line = ""

        for val in sampled:
            if (val - min_val) / value_range >= (h / height):
                line += "█"
            else:
                line += " "

        # Add scale on left
        scale_val = min_val + (h / height) * value_range
        lines.append(f"{scale_val:>8.0f} | {line}")

    lines.append(" " * 8 + "+" + "-" * width)

    return "\n".join(lines)


def plot_drawdown_ascii(
    drawdown_curve: List[float],
    width: int = 80,
    height: int = 15,
) -> str:
    """
    Generate ASCII art plot of drawdown curve.

    Args:
        drawdown_curve: List of drawdown percentages (as decimals)
        width: Chart width in characters
        height: Chart height in characters

    Returns:
        ASCII chart as multi-line string
    """
    if not drawdown_curve:
        return "No drawdown data"

    # Convert to percentages
    dd_pcts = [d * 100 for d in drawdown_curve]
    max_dd = max(dd_pcts) if dd_pcts else 0

    # Sample data
    step = max(1, len(drawdown_curve) // width)
    sampled = dd_pcts[::step]

    # Create chart
    lines = []
    for h in range(height, -1, -1):
        line = ""
        threshold = (h / height) * max_dd

        for val in sampled:
            if val >= threshold:
                line += "▓"
            elif val > 0:
                line += "░"
            else:
                line += " "

        lines.append(f"{threshold:>6.1f}% | {line}")

    lines.append(" " * 8 + "+" + "-" * width)

    return "\n".join(lines)


def format_metrics_table(metrics: dict) -> str:
    """
    Format backtest metrics as readable table.

    Args:
        metrics: Dictionary of metric_name -> value

    Returns:
        Formatted table as multi-line string
    """
    lines = []
    lines.append("╔" + "═" * 50 + "╗")
    lines.append("║" + " BACKTEST RESULTS ".center(50) + "║")
    lines.append("╠" + "═" * 50 + "╣")

    for key, value in metrics.items():
        # Format key
        formatted_key = key.replace("_", " ").title()

        # Format value
        if isinstance(value, float):
            if "ratio" in key.lower() or "return" in key.lower() or "drawdown" in key.lower():
                formatted_value = f"{value:.2%}"
            else:
                formatted_value = f"{value:.2f}"
        else:
            formatted_value = str(value)

        # Pad to fit
        line_content = f" {formatted_key}: {formatted_value}"
        line = "║" + line_content.ljust(50) + "║"
        lines.append(line)

    lines.append("╚" + "═" * 50 + "╝")

    return "\n".join(lines)


def create_summary_report(
    total_return: float,
    annual_return: float,
    sharpe_ratio: float,
    sortino_ratio: float,
    max_drawdown: float,
    num_trades: int,
    win_rate: float,
    profit_factor: float,
    final_value: float,
    initial_cash: float,
) -> str:
    """
    Create comprehensive text summary report.

    Args:
        Various backtest metrics

    Returns:
        Formatted report as multi-line string
    """
    lines = []

    lines.append("╔" + "═" * 78 + "╗")
    lines.append("║" + " BACKTEST SUMMARY REPORT ".center(78) + "║")
    lines.append("╠" + "═" * 78 + "╣")

    # Returns Section
    lines.append("║ RETURNS".ljust(79) + "║")
    lines.append(f"║   Total Return: {total_return:>10.2%}    Annual Return: {annual_return:>10.2%}".ljust(79) + "║")
    lines.append(f"║   Portfolio Value: ${final_value:>12,.0f}    Initial Capital: ${initial_cash:>10,.0f}".ljust(79) + "║")

    lines.append("║" + "-" * 78 + "║")

    # Risk Section
    lines.append("║ RISK METRICS".ljust(79) + "║")
    lines.append(f"║   Max Drawdown: {max_drawdown:>10.2%}    Sharpe Ratio: {sharpe_ratio:>10.2f}".ljust(79) + "║")
    lines.append(f"║   Sortino Ratio: {sortino_ratio:>10.2f}".ljust(79) + "║")

    lines.append("║" + "-" * 78 + "║")

    # Trading Activity
    lines.append("║ TRADING ACTIVITY".ljust(79) + "║")
    lines.append(f"║   Total Trades: {num_trades:>10d}    Win Rate: {win_rate:>10.2%}    Profit Factor: {profit_factor:>8.2f}".ljust(79) + "║")

    lines.append("╚" + "═" * 78 + "╝")

    return "\n".join(lines)


def create_trade_log_table(trades: List[dict], max_rows: int = 20) -> str:
    """
    Create formatted table of trades.

    Args:
        trades: List of trade dicts
        max_rows: Maximum rows to display

    Returns:
        Formatted table as multi-line string
    """
    if not trades:
        return "No trades executed"

    lines = []
    lines.append("╔" + "═" * 120 + "╗")
    lines.append("║ " + f"TRADE LOG ({len(trades)} total)".ljust(118) + " ║")
    lines.append("╠" + "═" * 120 + "╣")

    # Header
    header = "║ # │ Entry │ Exit │ Entry Price │ Exit Price │ Return % │ Duration │"
    lines.append(header.ljust(120) + "║")
    lines.append("╠" + "═" * 120 + "╣")

    # Display trades (show most recent first, limit to max_rows)
    display_trades = trades[-max_rows:]

    for i, trade in enumerate(display_trades, 1):
        entry_time = trade.get("entry_timestamp", "")
        exit_time = trade.get("exit_timestamp", "")

        if isinstance(entry_time, datetime):
            entry_time = entry_time.strftime("%Y-%m-%d")
        if isinstance(exit_time, datetime):
            exit_time = exit_time.strftime("%Y-%m-%d")

        entry_price = trade.get("entry_price", 0)
        exit_price = trade.get("exit_price", 0)
        return_pct = trade.get("return_pct", 0)
        duration = trade.get("duration_days", 0)

        row = (
            f"║ {i:>2} │ {str(entry_time):>5} │ {str(exit_time):>5} │ "
            f"${entry_price:>10.2f} │ ${exit_price:>9.2f} │ {return_pct:>7.2%} │ {duration:>7} │"
        )
        lines.append(row.ljust(120) + "║")

    lines.append("╚" + "═" * 120 + "╝")

    return "\n".join(lines)
