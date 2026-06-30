"""Exception hierarchy for AI Investment Bot."""


class InvestmentBotError(Exception):
    """Base exception for all AI Investment Bot errors."""

    pass


class DataError(InvestmentBotError):
    """Raised when data provider fails to fetch or process data."""

    pass


class RiskBreachError(InvestmentBotError):
    """Raised when risk constraints are violated."""

    pass


class ExecutionError(InvestmentBotError):
    """Raised when order execution fails."""

    pass


class StrategyError(InvestmentBotError):
    """Raised when strategy signal generation fails."""

    pass


class AgentError(InvestmentBotError):
    """Raised when agent execution fails."""

    pass
