# rcs/gateway.py
import json
import logging
from websockets.server import serve, WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed
import asyncio

from rcs.settings import settings
from rcs.engine import PipelineEngine
from rcs.nucleus.registry import ConnectionRegistry
from rcs.nucleus.protocol import Envelope

logger = logging.getLogger(__name__)

class ClientGateway:
    """
    The entry point for external clients. It listens for incoming connections
    and funnels their messages into the pipeline engine.
    """
    def __init__(self, registry: ConnectionRegistry, pipeline: PipelineEngine):
        self._registry = registry
        self._pipeline = pipeline
        logger.info("ClientGateway initialized.")

    async def start(self):
        """Starts the WebSocket server to listen for client connections."""
        logger.info(f"ClientGateway starting on {settings.SERVER_HOST}:{settings.SERVER_PORT}")
        async with serve(
            self.handle_connection,
            settings.SERVER_HOST,
            settings.SERVER_PORT,
            max_size=None
        ):
            await asyncio.Future() # Run forever

    async def handle_connection(self, websocket: WebSocketServerProtocol):
        """
        Manages a single client connection. For now, we assume clients
        also send a 'module_registration' message to identify themselves.
        """
        client_name = None
        try:
            message = await websocket.recv()
            data = json.loads(message)
            envelope = Envelope.model_validate(data)

            if envelope.type == "module_registration":
                client_name = envelope.return_from
                self._registry.register(client_name, websocket)

                async for message in websocket:
                    await self._pipeline.process_message(message, websocket)
            else:
                logger.warning(f"First message from client {websocket.remote_address} was not 'module_registration'.")
                await websocket.close(1008, "Registration required.")

        except (ConnectionClosed, json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Client connection from {websocket.remote_address} ended. Error: {e}")
        finally:
            if client_name:
                self._registry.unregister(client_name)
