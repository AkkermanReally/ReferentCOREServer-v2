# rcs/electrons/authenticator.py
import logging
from typing import Callable, Awaitable, Set

from websockets.server import WebSocketServerProtocol

from rcs.electrons.base import BaseElectron
from rcs.nucleus.protocol import Envelope
from rcs.nucleus.registry import AnyWebSocket, ConnectionRegistry
from rcs.nucleus.config import ConfigManager

logger = logging.getLogger(__name__)

# In a real system, these would come from a secure config/database
VALID_CLIENT_TOKENS = {"CLIENT_SECRET_TOKEN_123"}


class AuthenticationElectron(BaseElectron):
    """
    Authenticates external clients upon connection.
    It does not authenticate trusted components.
    """
    def __init__(self, registry: ConnectionRegistry, config_manager: ConfigManager):
        self._registry = registry
        self._config_manager = config_manager
        self._authenticated_clients: Set[str] = set()
        logger.info("AuthenticationElectron initialized.")

    def is_authenticated(self, name: str) -> bool:
        return name in self._authenticated_identities

    def handle_disconnect(self, name: str):
        """Callback to clean up the authenticated state when a client disconnects."""
        self._authenticated_clients.discard(name)
        logger.info(f"[Auth] Cleaned up session for disconnected client '{name}'.")

    async def process(
        self,
        envelope: Envelope,
        websocket: AnyWebSocket,
        next_electron: Callable[[], Awaitable[None]],
    ) -> None:
        """
        Checks for authentication on the first message from a client.
        """
        source = envelope.return_from

        # If already authenticated, just pass through
        if source in self._config_manager.get_all_components():
            # Это VIP-гость, он уже прошел проверку. Пропускаем.
            await next_electron()
            return
        
        # Шаг 2: Проверяем, является ли источник уже аутентифицированным клиентом.
        if source in self._authenticated_clients:
            await next_electron()
            return
        # ### ИЗМЕНЕНИЕ: Конец ###

        # Шаг 3: Если нет, то это новый клиент, который должен представиться.
        if envelope.type == "module_registration":
            token = envelope.payload.get("auth_token")
            if token in VALID_CLIENT_TOKENS:
                logger.info(f"[Auth] Client '{source}' successfully authenticated.")
                self._authenticated_clients.add(source)
                self._registry.register(source, websocket)
                # Регистрационное сообщение дальше не передаем.
                return
            else:
                logger.warning(f"[Auth] Authentication failed for client '{source}'. Closing.")
                await websocket.close(1008, "Invalid auth token")
        else:
            logger.warning(f"[Auth] Received non-registration message from unauthenticated client '{source}'. Closing.")
            await websocket.close(1008, "Authentication required")
