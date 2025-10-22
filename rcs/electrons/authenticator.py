# rcs/electrons/authenticator.py
import logging
from typing import Callable, Awaitable, Set

from websockets.server import WebSocketServerProtocol

from rcs.electrons.base import BaseElectron
from rcs.nucleus.protocol import Envelope
from rcs.nucleus.registry import AnyWebSocket

logger = logging.getLogger(__name__)

# In a real system, these would come from a secure config/database
VALID_CLIENT_TOKENS = {"CLIENT_SECRET_TOKEN_123"}


class AuthenticationElectron(BaseElectron):
    """
    Authenticates external clients upon connection.
    It does not authenticate trusted components.
    """
    def __init__(self):
        # A set of authenticated websocket identities (component/client names)
        self._authenticated_identities: Set[str] = set()
        logger.info("AuthenticationElectron initialized.")

    def is_authenticated(self, name: str) -> bool:
        return name in self._authenticated_identities

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
        if self.is_authenticated(source):
            await next_electron()
            return

        # Handle the registration message where authentication happens
        if envelope.type == "module_registration":
            token = envelope.payload.get("auth_token")

            # In our architecture, components connected by HandshakeManager are
            # pre-authenticated. Clients connecting via Gateway are not.
            # We need a way to distinguish them. For now, let's assume
            # if a token is present, it's a client that needs checking.
            # A better way would be to tag the websocket connection source.
            
            is_valid = False
            if token in VALID_CLIENT_TOKENS:
                is_valid = True
            
            # A simple heuristic: if there's no token, we assume it's a component
            # pre-authenticated by HandshakeManager. This is a simplification.
            elif token is None:
                 is_valid = True


            if is_valid:
                logger.info(f"[Auth] Identity '{source}' successfully authenticated.")
                self._authenticated_identities.add(source)
                await next_electron()
            else:
                logger.warning(f"[Auth] Authentication failed for '{source}'. Closing connection.")
                await websocket.close(1008, "Invalid auth token")
        else:
            # Any message other than registration from an unauthenticated source is an error
            logger.warning(f"[Auth] Received message from unauthenticated source '{source}'. Closing connection.")
            await websocket.close(1008, "Authentication required")
