# rcs/electrons/flow_control.py
import asyncio
import logging
from collections import deque
from typing import Callable, Awaitable, Dict
from websockets.server import WebSocketServerProtocol

from rcs.electrons.base import BaseElectron
from rcs.nucleus.protocol import Envelope
from rcs.nucleus.config import ConfigManager
from rcs.engine import PipelineEngine

logger = logging.getLogger(__name__)


class FlowControlElectron(BaseElectron):
    """
    Manages the flow of commands to components, enforcing concurrency limits.
    """
    def __init__(self, config_manager: ConfigManager, pipeline: PipelineEngine):
        self._config_manager = config_manager
        self._pipeline = pipeline # Needed to re-process queued items
        self._queues: Dict[str, deque] = {}
        self._active_requests: Dict[str, int] = {}
        logger.info("FlowControlElectron initialized.")

    async def process(
        self,
        envelope: Envelope,
        websocket: WebSocketServerProtocol,
        next_electron: Callable[[], Awaitable[None]],
    ) -> None:
        """
        Intercepts commands and responses to manage queues and concurrency.
        """
        if envelope.type == "command":
            target = envelope.return_to
            if not target:
                await next_electron()
                return

            # Initialize queue and counter for the target if not present
            self._queues.setdefault(target, deque())
            self._active_requests.setdefault(target, 0)

            limit = self._config_manager.get_component_config(target).policy.max_concurrent_requests

            if self._active_requests[target] < limit:
                    self._active_requests[target] += 1
                    logger.info(f"[FlowControl] Forwarding command to '{target}'. Active: {self._active_requests[target]}/{limit}")
                    await next_electron()
            else:
                # Check if this is a high-priority retry from the TransactionElectron
                is_priority = envelope.meta and envelope.meta.get("is_priority_retry")
                
                if is_priority:
                    self._queues[target].appendleft((envelope, websocket))
                    logger.warning(
                        f"[FlowControl] Prioritizing and queueing retry for '{target}'. Limit of {limit} reached. "
                        f"Queue size: {len(self._queues[target])}"
                    )
                else:
                    self._queues[target].append((envelope, websocket))
                    logger.warning(
                        f"[FlowControl] Queueing command for '{target}'. Limit of {limit} reached. "
                        f"Queue size: {len(self._queues[target])}"
                    )
                # We DO NOT call next_electron() here, halting the pipeline for this message

        elif envelope.type in ["response", "error"]:
            source = envelope.return_from
            if source in self._active_requests and self._active_requests[source] > 0:
                self._active_requests[source] -= 1
                limit = self._config_manager.get_component_config(source).policy.max_concurrent_requests
                logger.info(f"[FlowControl] Completion from '{source}'. Active: {self._active_requests[source]}/{limit}")
                # After a request completes, try to process the queue for that component
                asyncio.create_task(self._process_queue(source))

            await next_electron() # Responses and errors always pass through

        else:
            # For any other message type, just let it pass
            await next_electron()

    async def _process_queue(self, component_name: str):
        """Checks the queue for a component and processes the next item if a slot is free."""
        if component_name not in self._queues or not self._queues[component_name]:
            return

        limit = self._config_manager.get_component_config(component_name).policy.max_concurrent_requests

        if self._active_requests.get(component_name, 0) < limit:
            envelope, websocket = self._queues[component_name].popleft()
            self._active_requests[component_name] += 1
            logger.info(
                f"[FlowControl] Dequeuing command for '{component_name}'. Active: {self._active_requests[component_name]}/{limit}"
            )
            # Re-inject the message at the start of the pipeline
            await self._pipeline.process_message(envelope.model_dump_json(by_alias=True), websocket)
