# rcs/nucleus/connection.py
import json
import logging
from typing import Dict, Any, TYPE_CHECKING
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed

from rcs.nucleus.state import BaseState
from rcs.nucleus.protocol import Envelope

# ### ИЗМЕНЕНИЕ: Начало ###
# Мы используем TYPE_CHECKING, чтобы избежать циклического импорта во время выполнения.
# Этот блок кода будет виден только инструментам проверки типов (Mypy, PyCharm, VS Code),
# но не будет исполняться Python.
if TYPE_CHECKING:
    from rcs.engine import PipelineEngine
# ### ИЗМЕНЕНИЕ: Конец ###

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Handles the lifecycle of a websocket connection."""

    # ### ИЗМЕНЕНИЕ: Начало ###
    # Мы используем строку 'PipelineEngine' в качестве type hint.
    # Это называется "Forward Reference" и позволяет ссылаться на типы,
    # которые еще не были определены.
    def __init__(self, state: BaseState, pipeline: "PipelineEngine"):
    # ### ИЗМЕНЕНИЕ: Конец ###
        self._state = state
        self._pipeline = pipeline
        # In-memory mapping for the current server instance
        self.local_connections: Dict[str, WebSocketServerProtocol] = {}

    async def handle_new_connection(self, websocket: WebSocketServerProtocol):
        """
        Manages a new, unauthenticated connection until it is registered
        or disconnected.
        """
        component_name = None
        try:
            # The first message from a component MUST be a registration message.
            message = await websocket.recv()
            data = json.loads(message)
            envelope = Envelope.model_validate(data)

            if envelope.type == "module_registration":
                component_name = envelope.return_from
                self.local_connections[component_name] = websocket
                await self._state.register_component(component_name)
                logger.info(f"Component '{component_name}' registered from {websocket.remote_address}")

                # Now that the component is registered, listen for more messages.
                await self._listen_for_messages(websocket, component_name)
            else:
                logger.warning(f"First message from {websocket.remote_address} was not 'module_registration'. Closing connection.")
                await websocket.close(1008, "Registration required")

        except (ConnectionClosed, json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning(f"Connection lost or invalid message before registration from {websocket.remote_address}. Error: {e}")
        finally:
            if component_name:
                await self.handle_disconnect(websocket, component_name)

    async def _listen_for_messages(self, websocket: WebSocketServerProtocol, component_name: str):
        """Continuously listen for messages and pass them to the pipeline."""
        try:
            async for message in websocket:
                await self._pipeline.process_message(message, websocket)
        except ConnectionClosed:
            # This is an expected exception when the client disconnects.
            pass


    async def handle_disconnect(self, websocket: WebSocketServerProtocol, component_name: str):
        """Handles the cleanup when a component disconnects."""
        if component_name in self.local_connections:
            # Make sure we are cleaning up the correct websocket instance
            if self.local_connections[component_name] == websocket:
                del self.local_connections[component_name]
                await self._state.unregister_component(component_name)


    def get_websocket_for_component(self, component_name: str) -> WebSocketServerProtocol | None:
        """Retrieves the websocket object for a locally connected component."""
        return self.local_connections.get(component_name)
