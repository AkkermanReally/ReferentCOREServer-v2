# rcs/electrons/logger.py
import logging
from typing import Callable, Awaitable
from websockets.server import WebSocketServerProtocol

from rcs.electrons.base import BaseElectron
from rcs.nucleus.protocol import Envelope

logger = logging.getLogger(__name__)


class LoggerElectron(BaseElectron):
    """
    A simple electron that logs key information about each incoming envelope.
    """

    async def process(
        self,
        envelope: Envelope,
        websocket: WebSocketServerProtocol,
        next_electron: Callable[[], Awaitable[None]],
    ) -> None:
        """
        Logs the envelope details and passes control to the next electron.
        """
        logger.info(
            f"[LoggerElectron] Processing message {envelope.message_id} "
            f"(type: {envelope.type}, from: {envelope.return_from}) "
            f"for client {websocket.remote_address}"
        )

        # Crucial step: continue the pipeline execution.
        await next_electron()
