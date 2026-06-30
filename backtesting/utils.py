"""Utility functions for backtesting metrics calculation."""

from typing import List, Tuple
import numpy as np
from datetime import datetime


def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.02) -> float:
    """
    Calculate annualized Sharpe ratio.

    The Sharpe ratio measures excess return per unit of risk (volatility).
    Assumes 252 trading days per year.

    Formula: (mean_return - risk_free_rate) / std_return * sqrt(252)

    Args:
        returns: List of daily returns (as decimals, e.g., 0.01 for 1% return)
        risk_free_rate: Annual risk-free rate (default 2%)

    Returns:
        Annualized Sharpe ratio (float). Returns 0 if insufficient data or zero volatility.

    Example:
        >>> returns = [0.01, -0.02, 0.015, 0.005]
        >>> sr = calculate_sharpe_ratio(returns)
    """
    if not returns or len(returns) < 2:
        return 0.0

    returns_array = np.array(returns)

    mean_return = np.mean(returns_array)
    std_return = np.std(returns_array, ddof=1)

    # Handle zero volatility
    if std_return == 0:
        return 0.0

    # Daily risk-free rate
    daily_risk_free = risk_free_rate / 252.0

    sharpe = (mean_return - daily_risk_free) / std_return * np.sqrt(252)

    return float(sharpe)


def calculate_sortino_ratio(returns: List[float], risk_free_rate: float = 0.02) -> float:
    """
    Calculate annualized Sortino ratio.

    Like Sharpe ratio, but only penalizes downside volatility (negative returns).
    This is preferred when return distribution is asymmetric.

    Formula: (mean_return - risk_free_rate) / downside_volatility * sqrt(252)

    Args:
        returns: List of daily returns (as decimals)
        risk_free_rate: Annual risk-free rate (default 2%)

    Returns:
        Annualized Sortino ratio (float). Returns 0 if insufficient data or no downside volatility.

    Example:
        >>> returns = [0.01, -0.02, 0.015, 0.005]
        >>> sr = calculate_sortino_ratio(returns)
    """
    if not returns or len(returns) < 2:
        return 0.0

    returns_array = np.array(returns)
    mean_return = np.mean(returns_array)

    # Extract only negative returns (downside)
    negative_returns = returns_array[returns_array < 0]

    if len(negative_returns) == 0:
        # No downside, excellent performance
        return float(mean_return / 0.001 * np.sqrt(252)) if mean_return > 0 else 0.0

    # Downside volatility (std of negative returns)
    downside_volatility = np.std(negative_returns, ddof=1)

    if downside_volatility == 0:
        return 0.0

    # Daily risk-free rate
    daily_risk_free = risk_free_rate / 252.0

    sortino = (mean_return - daily_risk_free) / downside_volatility * np.sqrt(252)

    return float(sortino)


def calculate_max_drawdown(equity_curve: List[float]) -> Tuple[float, int]:
    """
    Calculate maximum drawdown and its duration.

    Maximum drawdown is the worst peak-to-trough decline. Duration is measured
    in number of periods (e.g., days if equity_curve has daily values).

    Formula: max_drawdown = (peak - trough) / peak

    Args:
        equity_curve: List of portfolio values over time (in chronological order)

    Returns:
        Tuple of (max_drawdown as decimal, duration_in_periods)
        Example: (-0.25, 45) means -25% drawdown lasting 45 periods

    Example:
        >>> equity = [100, 110, 105, 95, 100, 120]
        >>> dd, duration = calculate_max_drawdown(equity)
        >>> print(f"{dd:.2%} over {duration} periods")
    """
    if not equity_curve or len(equity_curve) < 2:
        return 0.0, 0

    equity_array = np.array(equity_curve)

    # Running maximum
    running_max = np.maximum.accumulate(equity_array)

    # Drawdown at each point
    drawdown = (equity_array - running_max) / running_max

    # Max drawdown value
    max_drawdown_value = np.min(drawdown)

    # Find duration (from peak to trough)
    max_dd_idx = np.argmin(drawdown)
    peak_idx = np.argmax(running_max[: max_dd_idx + 1])

    duration = max_dd_idx - peak_idx

    return float(max_drawdown_value), int(duration)


def calculate_cagr(
    starting_value: float,
    ending_value: float,
    num_years: float,
) -> float:
    """
    Calculate Compound Annual Growth Rate (CAGR).

    CAGR represents the average annual growth rate of an investment.

    Formula: CAGR = (ending_value / starting_value) ^ (1 / num_years) - 1

    Args:
        starting_value: Initial investment value
        ending_value: Final investment value
        num_years: Time period in years (can be fractional)

    Returns:
        CAGR as decimal (e.g., 0.12 for 12% CAGR)

    Example:
        >>> cagr = calculate_cagr(100000, 150000, 5)
        >>> print(f"CAGR: {cagr:.2%}")
    """
    if starting_value <= 0 or ending_value <= 0 or num_years <= 0:
        return 0.0

    cagr = (ending_value / starting_value) ** (1 / num_years) - 1

    return float(cagr)


def calculate_calmar_ratio(returns: List[float], max_drawdown_pct: float) -> float:
    """
    Calculate Calmar ratio.

    Calmar ratio = annual_return / max_drawdown
    Measures return per unit of downside risk.

    Args:
        returns: List of daily returns
        max_drawdown_pct: Maximum drawdown as decimal (e.g., 0.25 for 25%)

    Returns:
        Calmar ratio (float)
    """
    if not returns or len(returns) < 252 or max_drawdown_pct <= 0:
        return 0.0

    annual_return = np.mean(returns) * 252
    calmar = annual_return / abs(max_drawdown_pct)

    return float(calmar)


def calculate_recovery_factor(total_pnl: float, max_drawdown: float) -> float:
    """
    Calculate Recovery Factor.

    Recovery Factor = total_profit / max_drawdown
    Higher is better. Indicates profit relative to max risk experienced.

    Args:
        total_pnl: Total profit/loss
        max_drawdown: Maximum drawdown in currency units

    Returns:
        Recovery factor (float)
    """
    if max_drawdown == 0:
        return 0.0

    return total_pnl / abs(max_drawdown)


def calculate_consecutive_wins_losses(trades: List[dict]) -> Tuple[int, int]:
    """
    Calculate consecutive wins and losses.

    Args:
        trades: List of trade dicts with 'return_pct' key

    Returns:
        Tuple of (max_consecutive_wins, max_consecutive_losses)
    """
    if not trades:
        return 0, 0

    max_wins = 0
    max_losses = 0
    current_wins = 0
    current_losses = 0

    for trade in trades:
        if trade.get("return_pct", 0) > 0:
            current_wins += 1
            current_losses = 0
            max_wins = max(max_wins, current_wins)
        else:
            current_losses += 1
            current_wins = 0
            max_losses = max(max_losses, current_losses)

    return max_wins, max_losses


def generate_trade_report(trades: List[dict]) -> dict:
    """
    Generate comprehensive trade report.

    Args:
        trades: List of trade dicts

    Returns:
        Dictionary with trade statistics
    """
    if not trades:
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "avg_return": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "avg_winner": 0.0,
            "avg_loser": 0.0,
            "profit_factor": 0.0,
        }

    returns = [t.get("return_pct", 0) for t in trades]
    winning = [r for r in returns if r > 0]
    losing = [r for r in returns if r < 0]

    total = len(trades)
    num_wins = len(winning)
    num_losses = len(losing)

    return {
        "total_trades": total,
        "winning_trades": num_wins,
        "losing_trades": num_losses,
        "win_rate": num_wins / total if total > 0 else 0.0,
        "avg_return": np.mean(returns) if returns else 0.0,
        "best_trade": max(returns) if returns else 0.0,
        "worst_trade": min(returns) if returns else 0.0,
        "avg_winner": np.mean(winning) if winning else 0.0,
        "avg_loser": np.mean(losing) if losing else 0.0,
        "profit_factor": (
            sum(winning) / abs(sum(losing)) if sum(losing) != 0 and sum(winning) > 0 else 0.0
        ),
    }
