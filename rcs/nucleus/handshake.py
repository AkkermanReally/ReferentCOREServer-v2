# rcs/nucleus/handshake.py
import asyncio
import json
import logging
from typing import Dict, Any, TYPE_CHECKING  # ### ИЗМЕНЕНИЕ: Добавляем TYPE_CHECKING
import websockets
from websockets.exceptions import ConnectionClosed

from rcs.nucleus.config import ConfigManager, ComponentConfig
from rcs.nucleus.protocol import Envelope
from rcs.nucleus.registry import ConnectionRegistry
from rcs.nucleus.state import BaseState

# ### ИЗМЕНЕНИЕ: Начало ###
# Прячем импорт PipelineEngine от исполнителя Python, оставляя его для проверки типов.
if TYPE_CHECKING:
    from rcs.engine import PipelineEngine
# ### ИЗМЕНЕНИЕ: Конец ###

logger = logging.getLogger(__name__)


class HandshakeManager:
    """
    Actively manages the lifecycle of connections to remote components.
    """

    # ### ИЗМЕНЕНИЕ: Начало ###
    # Используем строковый "Forward Reference" для аннотации типа.
    def __init__(
        self,
        config_manager: ConfigManager,
        state: BaseState,
        registry: ConnectionRegistry,
        pipeline: "PipelineEngine"
    ):
        self.config_manager = config_manager
        self.state = state
        self.registry = registry
        self.pipeline = pipeline
        # self.active_connections больше не нужен, так как мы используем registry
        self.connection_tasks: Dict[str, asyncio.Task] = {}
        logger.info("HandshakeManager (Active Orchestrator) initialized.")

    async def manage_all_connections(self):
        """
        Starts connection management tasks for all enabled components.
        """
        all_components = self.config_manager.get_all_components()
        for name, config in all_components.items():
            if config.control.enabled:
                self._start_connection_task_for(name)

        await asyncio.Future()

    def _start_connection_task_for(self, name: str):
        """Creates and starts a background task to manage a single connection."""
        if name in self.connection_tasks:
            return
        logger.info(f"Starting connection management task for component '{name}'.")
        task = asyncio.create_task(self._manage_connection_loop(name))
        self.connection_tasks[name] = task
        task.add_done_callback(lambda _: self.connection_tasks.pop(name, None))

    async def _manage_connection_loop(self, component_name: str):
        """
        An infinite loop that tries to connect to a component, perform a
        handshake, and listen for messages until it's cancelled.
        """
        while True:
            reconnect_delay = 10 # Default delay
            try:
                config = self.config_manager.get_component_config(component_name)
                if not config or not config.control.enabled:
                    logger.warning(f"Stopping connection loop for '{component_name}' as it is now disabled.")
                    break

                async with websockets.connect(config.connection.uri) as websocket:
                    logger.info(f"[{component_name}] Connection established.")
                    is_successful = await self._perform_handshake(websocket, component_name, config.connection.auth_token)

                    if is_successful:
                        # ### ИЗМЕНЕНИЕ ###: Используем реестр
                        self.registry.register(component_name, websocket)
                        await self.state.register_component(component_name)
                        logger.info(f"[{component_name}] Handshake successful. Listening for messages...")

                        async for message in websocket:
                            try:
                                data = json.loads(message)
                                if data.get("type") == "policy_advertisement":
                                    payload = data.get("payload")
                                    logger.info(f"[{component_name}] Received policy advertisement: {payload}")
                                    # ### ИЗМЕНЕНИЕ: Начало ###
                                    if isinstance(payload, dict):
                                        await self.config_manager.update_component_policy(component_name, payload)
                                    # ### ИЗМЕНЕНИЕ: Конец ###
                                    continue
                            except (json.JSONDecodeError, TypeError):
                                pass
                            await self.pipeline.process_message(message, websocket)

            except asyncio.CancelledError:
                logger.info(f"Connection loop for '{component_name}' is being cancelled.")
                break
            except (ConnectionRefusedError, ConnectionClosed, OSError) as e:
                logger.warning(f"[{component_name}] Connection error: {type(e).__name__}. Retrying in {reconnect_delay} seconds.")
            except Exception as e:
                logger.error(f"[{component_name}] Unexpected error in connection loop: {e}", exc_info=True)
            finally:
                # ### ИЗМЕНЕНИЕ ###: Используем реестр
                if self.registry.get(component_name):
                    self.registry.unregister(component_name)
                    await self.state.unregister_component(component_name)

            await asyncio.sleep(reconnect_delay)
        logger.info(f"Connection management loop for '{component_name}' has terminated.")


    async def _perform_handshake(self, websocket, component_name: str, auth_token: str) -> bool:
        """Performs the handshake protocol with a newly connected component."""
        try:
            handshake_msg = Envelope(
                type="handshake",
                return_from="RefferentCOREServer",
                payload={"auth_token": auth_token},
            )
            await websocket.send(handshake_msg.model_dump_json(by_alias=True))

            response_raw = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            response = Envelope.model_validate(json.loads(response_raw))

            if response.type == "handshake_confirmed":
                return True
            else:
                logger.warning(f"[{component_name}] Handshake failed. Unexpected response type: {response.type}")
                return False

        except asyncio.TimeoutError:
            logger.error(f"[{component_name}] Handshake timed out. No response from component.")
            return False
        except Exception as e:
            logger.error(f"[{component_name}] Error during handshake: {e}", exc_info=True)
            return False

    def get_websocket_for_component(self, component_name: str) -> websockets.WebSocketClientProtocol | None:
        """Retrieves the active websocket for a connected component."""
        return self.active_connections.get(component_name)
