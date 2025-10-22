# rcs/nucleus/registry.py
import logging
from typing import Dict, Any, TYPE_CHECKING
from websockets.server import WebSocketServerProtocol
from websockets.client import WebSocketClientProtocol

if TYPE_CHECKING:
    from rcs.electrons.authenticator import AuthenticationElectron
    
logger = logging.getLogger(__name__)
AnyWebSocket = WebSocketServerProtocol | WebSocketClientProtocol

class ConnectionRegistry:

    def __init__(self, auth_electron: "AuthenticationElectron"):
        self._connections: Dict[str, AnyWebSocket] = {}
        self._ws_to_name: Dict[AnyWebSocket, str] = {}
        self._auth_electron = auth_electron
        logger.info("ConnectionRegistry initialized.")

    def register(self, name: str, websocket: AnyWebSocket):
        self._connections[name] = websocket
        self._ws_to_name[websocket] = name # ### ИЗМЕНЕНИЕ ###
        logger.info(f"[Registry] Connection '{name}' registered.")

    def unregister(self, name: str) -> AnyWebSocket | None:
        if name in self._connections:
            ws = self._connections.pop(name)
            self._ws_to_name.pop(ws, None)
            self._auth_electron.handle_disconnect(name)
            logger.info(f"[Registry] Connection '{name}' unregistered.")
            return ws
        return None

    def get(self, name: str) -> AnyWebSocket | None:
        return self._connections.get(name)

    def unregister_by_websocket(self, websocket: AnyWebSocket):
        """Finds the name associated with a websocket and unregisters it."""
        name = self._ws_to_name.get(websocket)
        if name:
            self.unregister(name)
