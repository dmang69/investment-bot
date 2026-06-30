"""Async event bus for pub/sub communication between agents."""

import asyncio
from typing import Callable, Dict, List, Any
from core.logger import get_logger


logger = get_logger(__name__)


class EventBus:
    """
    Simple async pub/sub event bus for agent communication.

    Topics are strings, and callbacks are async functions that receive
    the payload as an argument.
    """

    def __init__(self) -> None:
        """Initialize the event bus with empty subscriptions."""
        self._subscriptions: Dict[str, List[Callable]] = {}

    async def subscribe(self, topic: str, callback: Callable) -> None:
        """
        Subscribe to a topic.

        Args:
            topic: Topic name to subscribe to
            callback: Async callable that receives (topic, payload)
        """
        if topic not in self._subscriptions:
            self._subscriptions[topic] = []
        self._subscriptions[topic].append(callback)
        logger.info("subscribed", topic=topic, callback=callback.__name__)

    async def unsubscribe(self, topic: str, callback: Callable) -> None:
        """
        Unsubscribe from a topic.

        Args:
            topic: Topic name to unsubscribe from
            callback: Callback to remove
        """
        if topic in self._subscriptions:
            self._subscriptions[topic].remove(callback)
            logger.info("unsubscribed", topic=topic, callback=callback.__name__)

    async def publish(self, topic: str, payload: Any) -> None:
        """
        Publish an event to all subscribers of a topic.

        Args:
            topic: Topic name to publish to
            payload: Event payload (any type)
        """
        if topic not in self._subscriptions:
            logger.debug("no_subscribers", topic=topic)
            return

        logger.info("publishing_event", topic=topic, payload=payload)

        # Call all subscribers concurrently
        tasks = [
            callback(topic, payload)
            for callback in self._subscriptions[topic]
        ]
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def clear(self) -> None:
        """Clear all subscriptions."""
        self._subscriptions.clear()
