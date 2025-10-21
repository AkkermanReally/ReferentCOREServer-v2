# rcs/engine.py
import json
import logging
from typing import List, Callable, Awaitable
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed

from rcs.nucleus.protocol import Envelope
from rcs.electrons.base import BaseElectron

logger = logging.getLogger(__name__)


class PipelineEngine:
    """
    The engine that runs the middleware pipeline for each connection.

    It takes a list of Electrons (middleware) and a final Nucleus handler,
    and chains them together to process incoming messages.
    """

    def __init__(
        self,
        electrons: List[BaseElectron],
        nucleus_handler: Callable[[Envelope, WebSocketServerProtocol], Awaitable[None]],
    ):
        self._electrons = electrons
        self._nucleus_handler = nucleus_handler
        logger.info(f"PipelineEngine initialized with {len(self._electrons)} electrons.")

    async def handle_connection(self, websocket: WebSocketServerProtocol) -> None:
        """
        Manages a single client connection, listening for messages and
        passing them through the electron pipeline.
        """
        logger.info(f"New connection established: {websocket.remote_address}")
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    envelope = Envelope.model_validate(data)
                    await self._execute_pipeline(envelope, websocket)
                except json.JSONDecodeError:
                    logger.warning(f"Received non-JSON message from {websocket.remote_address}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)

        except ConnectionClosed as e:
            logger.info(f"Connection closed: {websocket.remote_address} (code: {e.code}, reason: {e.reason})")
        except Exception as e:
            logger.error(f"An unexpected error occurred in connection handler: {e}", exc_info=True)


    async def _execute_pipeline(self, envelope: Envelope, websocket: WebSocketServerProtocol) -> None:
        """
        Constructs and executes the chain of electron calls for a single envelope.
        """
        # Start with the nucleus handler as the final step in the chain.
        next_handler = self._nucleus_handler

        # Wrap the handlers in reverse order. Each electron gets the *next*
        # handler in the chain as an argument.
        # This creates a nested structure of calls.
        for electron in reversed(self._electrons):
            # Create a closure to capture the current electron and the *next* handler
            def create_closure(current_electron, next_step):
                async def closure():
                    await current_electron.process(envelope, websocket, next_step)
                return closure

            next_handler = create_closure(electron, next_handler)

        # Execute the fully constructed pipeline from the beginning.
        await next_handler()
