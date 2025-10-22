# rcs/electrons/transaction.py
import logging
from typing import Callable, Awaitable, Dict

from websockets.server import WebSocketServerProtocol

from rcs.electrons.base import BaseElectron
from rcs.nucleus.protocol import Envelope
from rcs.engine import PipelineEngine

logger = logging.getLogger(__name__)


class TransactionElectron(BaseElectron):
    """
    Manages requester-side validation for distributed transactions.
    """
    def __init__(self, pipeline: PipelineEngine):
        self._pipeline = pipeline
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
            
            # --- Prepare the request for retry ---
            # Mark it for high-priority queuing.
            if original_request.meta is None: original_request.meta = {}
            original_request.meta["is_priority_retry"] = True

            # TODO: Implement max_retries logic here.
            # We could increment a 'retry_count' in the meta field and check it.

            # Re-inject the original request at the beginning of the pipeline.
            # We need a websocket object. Since this verdict came from the original
            # requester, we can assume it's still connected.
            # This is a simplification; a more robust system would look up the websocket.
            # For now, we know the source of the verdict is the destination of the retry confirmation.
            # This is a conceptual simplification. In a real system, we'd need a way to get the websocket.
            # Let's assume for now that the pipeline has a way to handle this.
            # The easiest way is to re-route it back to the original client to re-send.
            # A better way is for the pipeline to handle it internally.
            
            # HACK: For now, we assume a websocket is not needed to re-process an internal message.
            # Let's adjust the pipeline to handle this.
            # For now, let's just log it. A proper re-injection needs more thought.
            
            # The correct way: Re-inject into the pipeline.
            # The original websocket isn't relevant because the message isn't coming from
            # a live socket, but from the TransactionElectron itself.
            # The pipeline needs to know how to route this.
            
            # The easiest implementation is for the transaction electron to put it directly
            # into the FlowControlElectron's queue. This creates coupling.
            
            # Let's stick to the pipeline. We will need to adapt the pipeline entrypoint.
            # For now, let's just log and prepare for the next step.
            logger.warning("RE-INJECTION LOGIC TO BE IMPLEMENTED IN PIPELINE")
