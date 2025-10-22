# rcs/nucleus/registry.py
import logging
from typing import Dict
from websockets.server import WebSocketServerProtocol
from websockets.client import WebSocketClientProtocol

logger = logging.getLogger(__name__)

# A union type to represent both client and server websockets
AnyWebSocket = WebSocketServerProtocol | WebSocketClientProtocol

class ConnectionRegistry:
    """
    A simple in-memory registry for all active websocket connections
    (both from clients and to components) on this server instance.
    """
    def __init__(self):
        self._connections: Dict[str, AnyWebSocket] = {}
        logger.info("ConnectionRegistry initialized.")

    def register(self, name: str, websocket: AnyWebSocket):
        """Registers a named connection."""
        self._connections[name] = websocket
        logger.info(f"[Registry] Connection '{name}' registered.")

    def unregister(self, name: str) -> AnyWebSocket | None:
        """Removes a named connection and returns it if it existed."""
        if name in self._connections:
            ws = self._connections.pop(name)
            logger.info(f"[Registry] Connection '{name}' unregistered.")
            return ws
        return None

    def get(self, name: str) -> AnyWebSocket | None:
        """Retrieves a connection by its name."""
        return self._connections.get(name)
