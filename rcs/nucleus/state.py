# rcs/nucleus/state.py
from abc import ABC, abstractmethod
import logging
from rcs.utils.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class BaseState(ABC):
    """Abstract base class for state management."""
    @abstractmethod
    async def register_component(self, component_name: str):
        pass

    @abstractmethod
    async def unregister_component(self, component_name: str):
        pass

    @abstractmethod
    async def is_component_active(self, component_name: str) -> bool:
        pass


class RedisState(BaseState):
    """Manages the shared state of connected components using Redis."""
    _ACTIVE_COMPONENTS_KEY = "rcs:active_components"

    def __init__(self):
        self._redis = get_redis_client()

    async def register_component(self, component_name: str):
        """Adds a component to the set of active components."""
        await self._redis.sadd(self._ACTIVE_COMPONENTS_KEY, component_name)
        logger.info(f"[State] Component '{component_name}' has been registered as active.")

    async def unregister_component(self, component_name: str):
        """Removes a component from the set of active components."""
        await self._redis.srem(self._ACTIVE_COMPONENTS_KEY, component_name)
        logger.warning(f"[State] Component '{component_name}' has been unregistered.")

    async def is_component_active(self, component_name: str) -> bool:
        """Checks if a component is currently listed as active."""
        return await self._redis.sismember(self._ACTIVE_COMPONENTS_KEY, component_name)
