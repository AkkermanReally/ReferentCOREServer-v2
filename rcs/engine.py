# rcs/engine.py
import json
import logging
from typing import List, Callable, Awaitable
from websockets.server import WebSocketServerProtocol

from rcs.nucleus.protocol import Envelope
from rcs.electrons.base import BaseElectron
from rcs.nucleus.router import Router

logger = logging.getLogger(__name__)


class PipelineEngine:
    """
    The engine that runs the middleware pipeline for each message.
    """
    def __init__(
        self,
        electrons: List[BaseElectron],
        nucleus_router: Router,
    ):
        self._electrons = electrons
        self._nucleus_router = nucleus_router
        logger.info(f"PipelineEngine initialized with {len(self._electrons)} electrons.")

    async def process_message(self, message: str, websocket: WebSocketServerProtocol) -> None:
        """Processes a single message through the electron pipeline."""
        try:
            data = json.loads(message)
            envelope = Envelope.model_validate(data)
            # The final step of the pipeline is now the router's method
            final_handler = lambda: self._nucleus_router.route(envelope, websocket)
            await self._execute_pipeline(envelope, websocket, final_handler)
        except json.JSONDecodeError:
            logger.warning(f"Received non-JSON message from {websocket.remote_address}")
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)

    async def _execute_pipeline(
        self,
        envelope: Envelope,
        websocket: WebSocketServerProtocol,
        final_handler: Callable[[], Awaitable[None]]
    ) -> None:
        """Constructs and executes the chain of electron calls for a single envelope."""
        next_handler = final_handler
        for electron in reversed(self._electrons):
            def create_closure(current_electron, next_step):
                async def closure():
                    await current_electron.process(envelope, websocket, next_step)
                return closure
            next_handler = create_closure(electron, next_handler)
        await next_handler()
