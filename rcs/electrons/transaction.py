# rcs/electrons/transaction.py
import logging
from typing import Callable, Awaitable, Dict

from websockets.server import WebSocketServerProtocol

from rcs.electrons.base import BaseElectron
from rcs.nucleus.protocol import Envelope
from rcs.engine import PipelineEngine
from rcs.nucleus.registry import ConnectionRegistry, AnyWebSocket

logger = logging.getLogger(__name__)


class TransactionElectron(BaseElectron):
    """
    Manages requester-side validation for distributed transactions.
    """
    def __init__(self, pipeline: PipelineEngine, registry: ConnectionRegistry):
        self._pipeline = pipeline
        self._registry = registry
        self._pending_validation: Dict[str, Envelope] = {}
        logger.info("TransactionElectron initialized.")

    async def process(
        self,
        envelope: Envelope,
        websocket: WebSocketServerProtocol,
        next_electron: Callable[[], Awaitable[None]],
    ) -> None:
        """
        Intercepts messages to manage the validation lifecycle.
        """
        # --- Handle Verdicts First ---
        if envelope.type in ["validation_confirmed", "validation_failed"]:
            await self._handle_verdict(envelope)
            # Verdicts are terminal for this Electron; they don't proceed further.
            return

        # --- Handle Commands ---
        if envelope.type == "command" and envelope.meta and envelope.meta.get("requires_validation"):
            if not envelope.request_id:
                logger.error(f"Command {envelope.message_id} requires validation but has no request_id. Cannot track.")
            else:
                # Store a copy of the original request to be re-used if validation fails.
                self._pending_validation[envelope.request_id] = envelope.model_copy(deep=True)
                logger.info(f"[Transaction] Registered request {envelope.request_id} for validation.")
                # TODO: Implement a timeout mechanism to clean up stale pending validations.

        # All other messages pass through unimpeded.
        await next_electron()

    async def _handle_verdict(self, verdict_envelope: Envelope):
        """Processes the final verdict from the original requester."""
        request_id = verdict_envelope.request_id
        if not request_id or request_id not in self._pending_validation:
            logger.warning(f"Received verdict for unknown or already completed request_id: {request_id}")
            return

        original_request = self._pending_validation.pop(request_id)

        if verdict_envelope.type == "validation_confirmed":
            logger.info(f"[Transaction] Validation confirmed for request {request_id}. Transaction complete.")
        
        elif verdict_envelope.type == "validation_failed":
            logger.warning(f"[Transaction] Validation failed for request {request_id}. Re-queueing original request.")
            

            source_name = original_request.return_from
            source_websocket = self._registry.get(source_name)
            
            if not source_websocket or not source_websocket.open:
                logger.error(
                    f"[Transaction] Cannot re-queue request {request_id}. "
                    f"The original requester '{source_name}' is disconnected."
                )
                # Here we could potentially send an event to a monitoring system.
                return

            if original_request.meta is None: original_request.meta = {}
            original_request.meta["is_priority_retry"] = True

            logger.info(f"Re-injecting request {request_id} into the pipeline on behalf of '{source_name}'.")
            # Re-inject the original request message using the live websocket of the requester.
            await self._pipeline.process_message(
                original_request.model_dump_json(by_alias=True),
                source_websocket
            )
