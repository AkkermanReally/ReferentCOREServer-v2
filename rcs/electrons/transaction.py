# rcs/electrons/transaction.py
import asyncio
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
    Manages requester-side validation for distributed transactions,
    including timeouts and retry limits.
    """
    def __init__(self, pipeline: PipelineEngine, registry: ConnectionRegistry):
        self._pipeline = pipeline
        self._registry = registry
        self._pending_validation: Dict[str, Envelope] = {}
        self._timeout_tasks: Dict[str, asyncio.Task] = {}
        logger.info("TransactionElectron initialized.")

    async def process(
        self,
        envelope: Envelope,
        websocket: AnyWebSocket,
        next_electron: Callable[[], Awaitable[None]],
    ) -> None:
        if envelope.type in ["validation_confirmed", "validation_failed"]:
            await self._handle_verdict(envelope)
            return

        if envelope.type == "command" and envelope.meta and envelope.meta.get("requires_validation"):
            if not envelope.request_id:
                logger.error(f"Command {envelope.message_id} has validation but no request_id.")
            else:
                self._register_transaction(envelope)

        await next_electron()

    def _register_transaction(self, envelope: Envelope):
        """Registers a new transaction and starts a timeout watcher."""
        request_id = envelope.request_id
        if not request_id: return

        # Initialize retry count if it's the first attempt
        if envelope.meta and "retry_count" not in envelope.meta:
            envelope.meta["retry_count"] = 0

        self._pending_validation[request_id] = envelope.model_copy(deep=True)
        
        timeout_seconds = envelope.meta.get("validation_timeout_seconds", 60)
        # Create a task that will automatically fail the transaction after a timeout
        timeout_task = asyncio.create_task(self._timeout_watcher(request_id, timeout_seconds))
        self._timeout_tasks[request_id] = timeout_task
        logger.info(f"[Transaction] Registered request {request_id} for validation (timeout: {timeout_seconds}s).")

    async def _timeout_watcher(self, request_id: str, delay: int):
        """Waits for a specified duration and fails the transaction if it's still pending."""
        await asyncio.sleep(delay)
        if request_id in self._pending_validation:
            logger.warning(f"[Transaction] Timeout reached for request {request_id}. Failing transaction.")
            # We create a synthetic "validation_failed" envelope to trigger the failure logic
            failed_verdict = Envelope(
                type="validation_failed",
                return_from="TransactionElectron", # System generated
                request_id=request_id,
                payload={"reason": "Validation verdict timeout"}
            )
            await self._handle_verdict(failed_verdict)


    async def _handle_verdict(self, verdict_envelope: Envelope):
        request_id = verdict_envelope.request_id
        if not request_id or request_id not in self._pending_validation:
            return

        # Cancel the timeout task as a verdict has been received
        if request_id in self._timeout_tasks:
            self._timeout_tasks.pop(request_id).cancel()

        original_request = self._pending_validation.pop(request_id)
        requester_name = original_request.return_from

        if verdict_envelope.type == "validation_confirmed":
            logger.info(f"[Transaction] Validation confirmed for request {request_id}. Transaction complete.")
        
        elif verdict_envelope.type == "validation_failed":
            max_retries = original_request.meta.get("max_retries", 2)
            retry_count = original_request.meta.get("retry_count", 0)

            if retry_count < max_retries:
                logger.warning(f"[Transaction] Validation failed for {request_id}. Retrying ({retry_count + 1}/{max_retries}).")
                original_request.meta["retry_count"] = retry_count + 1
                await self._re_inject_request(original_request)
            else:
                logger.error(f"[Transaction] Max retries ({max_retries}) reached for request {request_id}. Transaction failed permanently.")
                await self._notify_requester_of_failure(original_request)


    async def _re_inject_request(self, request_envelope: Envelope):
        source_websocket = self._registry.get(request_envelope.return_from)
        if not source_websocket or not source_websocket.open:
            logger.error(f"Cannot re-queue request {request_envelope.request_id}. Requester '{request_envelope.return_from}' is disconnected.")
            return

        request_envelope.meta["is_priority_retry"] = True
        logger.info(f"Re-injecting request {request_envelope.request_id} into pipeline.")
        # Re-register the transaction before re-injecting
        self._register_transaction(request_envelope)
        await self._pipeline.process_message(request_envelope.model_dump_json(by_alias=True), source_websocket)

    async def _notify_requester_of_failure(self, original_request: Envelope):
        """Sends a final 'error' message to the original requester."""
        requester_name = original_request.return_from
        requester_ws = self._registry.get(requester_name)
        if requester_ws and requester_ws.open:
            error_envelope = Envelope(
                type="error",
                return_from="TransactionElectron",
                return_to=requester_name,
                request_id=original_request.request_id,
                payload={
                    "error_message": "Transaction failed after maximum retries.",
                    "original_request": original_request.payload,
                }
            )
            await requester_ws.send(error_envelope.model_dump_json(by_alias=True))
