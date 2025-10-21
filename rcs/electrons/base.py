# rcs/electrons/base.py
from abc import ABC, abstractmethod
from typing import Callable, Awaitable
from websockets.server import WebSocketServerProtocol

from rcs.nucleus.protocol import Envelope


class BaseElectron(ABC):
    """
    Abstract base class for all "Electrons" (middleware components).

    An Electron is a processing unit in the pipeline that can inspect, modify,
    or halt a message before it reaches the Nucleus (the core router).

    This class defines the contract that every electron must adhere to.
    """

    @abstractmethod
    async def process(
        self,
        envelope: Envelope,
        websocket: WebSocketServerProtocol,
        next_electron: Callable[[], Awaitable[None]],
    ) -> None:
        """
        Processes an incoming message envelope.

        This method must be implemented by all concrete Electron classes.

        Args:
            envelope: The message envelope to be processed.
            websocket: The active websocket connection, allowing for direct
                       communication if needed (e.g., sending an immediate error).
            next_electron: An awaitable callable that invokes the next electron
                           in the pipeline. It is the responsibility of the
                           current electron to call `await next_electron()` to
                           continue the processing chain. If it is not called,
                           the chain is halted.
        """
        pass
