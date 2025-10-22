# rcs/gateway.py
import logging
from websockets.server import serve, WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed

from rcs.settings import settings
from rcs.engine import PipelineEngine
from rcs.nucleus.registry import ConnectionRegistry

import asyncio

logger = logging.getLogger(__name__)

class ClientGateway:
    def __init__(self, registry: ConnectionRegistry, pipeline: PipelineEngine):
        self._registry = registry
        self._pipeline = pipeline
        logger.info("ClientGateway initialized.")

    async def start(self):
        logger.info(f"ClientGateway starting on {settings.SERVER_HOST}:{settings.SERVER_PORT}")
        async with serve(self.handle_connection, settings.SERVER_HOST, settings.SERVER_PORT, max_size=None):
            await asyncio.Future()

    # ### ИЗМЕНЕНИЕ: Начало - Упрощенный обработчик ###
    async def handle_connection(self, websocket: WebSocketServerProtocol):
        """
        Manages a single client connection by feeding all its messages
        into the pipeline.
        """
        try:
            async for message in websocket:
                await self._pipeline.process_message(message, websocket)
        except ConnectionClosed:
            logger.info(f"Client connection {websocket.remote_address} closed.")
        except Exception as e:
            logger.error(f"Error on client connection {websocket.remote_address}: {e}", exc_info=True)
        finally:
            self._registry.unregister_by_websocket(websocket)
    
