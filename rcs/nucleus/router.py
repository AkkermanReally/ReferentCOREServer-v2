# rcs/nucleus/router.py
import logging
from websockets.server import WebSocketServerProtocol
from rcs.nucleus.protocol import Envelope
from rcs.nucleus.state import BaseState
from rcs.nucleus.handshake import HandshakeManager

logger = logging.getLogger(__name__)


class Router:
    """
    The Nucleus Router. The final destination in the pipeline.
    It uses the state and handshake managers to forward messages.
    """
    def __init__(self, state: BaseState, handshake_manager: HandshakeManager):
        self._state = state
        self._handshake_manager = handshake_manager

    async def route(self, envelope: Envelope, websocket: WebSocketServerProtocol) -> None:
        """
        Routes the envelope to its destination.
        """
        target = envelope.return_to
        if not target:
            logger.warning(f"Message {envelope.message_id} has no 'return_to' address. Dropping.")
            return

        target_ws = self._handshake_manager.get_websocket_for_component(target)

        if target_ws:
            try:
                await target_ws.send(envelope.model_dump_json(by_alias=True))
                logger.info(f"Message {envelope.message_id} from '{envelope.return_from}' successfully routed to '{target}'.")
            except Exception as e:
                logger.error(f"Failed to send message to '{target}': {e}", exc_info=True)
        else:
            logger.warning(f"Could not find active local connection for target '{target}'. Message {envelope.message_id} dropped.")
