# rcs/nucleus/router.py
import logging
from rcs.nucleus.protocol import Envelope
from rcs.nucleus.state import BaseState
from rcs.nucleus.registry import ConnectionRegistry, AnyWebSocket

logger = logging.getLogger(__name__)


class Router:
    """
    The Nucleus Router. The final destination in the pipeline.
    It uses the state and connection registry to forward messages.
    """
    def __init__(self, state: BaseState, registry: ConnectionRegistry):
        self._state = state
        self._registry = registry # ### ИЗМЕНЕНИЕ ###

    async def route(self, envelope: Envelope, websocket: AnyWebSocket) -> None:
        """
        Routes the envelope to its destination.
        """
        target = envelope.return_to
        if not target:
            logger.warning(f"Message {envelope.message_id} has no 'return_to' address. Dropping.")
            return

        # ### ИЗМЕНЕНИЕ ###: Ищем в едином реестре
        target_ws = self._registry.get(target)

        if target_ws:
            try:
                await target_ws.send(envelope.model_dump_json(by_alias=True))
                logger.info(f"Message {envelope.message_id} from '{envelope.return_from}' successfully routed to '{target}'.")
            except Exception as e:
                logger.error(f"Failed to send message to '{target}': {e}", exc_info=True)
        else:
            logger.warning(f"Could not find active connection for target '{target}'. Message {envelope.message_id} dropped.")
