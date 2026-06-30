"""Abstract base agent class."""

import asyncio
from abc import ABC, abstractmethod
from typing import Any
from core.logger import get_logger


logger = get_logger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all trading agents.

    Agents are autonomous components that listen to events,
    process market data, and generate trading signals.
    """

    def __init__(self) -> None:
        """Initialize the agent."""
        self._running = False

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Get the agent's name.

        Returns:
            Unique identifier for this agent
        """
        pass

    @property
    def running(self) -> bool:
        """Check if the agent is currently running."""
        return self._running

    async def start(self) -> None:
        """
        Start the agent and begin processing.

        Should be called before run() is invoked.
        """
        self._running = True
        logger.info(f"Agent {self.name} started")

    async def stop(self) -> None:
        """Stop the agent and clean up resources."""
        self._running = False
        logger.info(f"Agent {self.name} stopped")

    @abstractmethod
    async def run(self) -> None:
        """
        Main agent loop. Should continuously process data and generate signals.

        This method is responsible for the agent's core business logic.
        """
        pass

    @abstractmethod
    async def on_event(self, topic: str, payload: Any) -> None:
        """
        Handle incoming events from the event bus.

        Args:
            topic: Event topic name
            payload: Event payload (type depends on topic)
        """
        pass
