# rcs/main.py
import asyncio
import logging

from rcs.settings import settings
from rcs.engine import PipelineEngine
from rcs.electrons.logger import LoggerElectron
from rcs.nucleus.router import Router
from rcs.nucleus.state import RedisState
from rcs.nucleus.config import ConfigManager
from rcs.nucleus.handshake import HandshakeManager


async def main():
    """
    The main entry point for the RefferentCOREServer v2.
    """
    # 1. Configure logging
    logging.basicConfig(
        level=settings.LOG_LEVEL.upper(),
        format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s"
    )
    logger = logging.getLogger("RCs_Main")

    # 2. Initialize Nucleus components in the correct order
    logger.info("Initializing Nucleus components...")
    config_manager = ConfigManager()
    await config_manager.sync_on_startup() # Must be done before anything else

    state = RedisState()

    # The handshake manager will be created later, but the router needs it.
    handshake_manager_ref = {"instance": None}
    router = Router(state, handshake_manager_ref) # type: ignore

    # 3. Define active electrons and initialize the pipeline engine.
    active_electrons = [
        LoggerElectron(),
    ]
    pipeline_engine = PipelineEngine(
        electrons=active_electrons,
        nucleus_router=router
    )

    # 4. Create the Handshake Manager and resolve the reference for the router.
    handshake_manager = HandshakeManager(config_manager, state, pipeline_engine)
    handshake_manager_ref["instance"] = handshake_manager
    router._handshake_manager = handshake_manager # Now the router has the real instance

    # 5. Start the main application loop.
    logger.info("Starting RefferentCOREServer v2 in Active Orchestrator mode.")
    # This task runs forever, managing all outgoing connections.
    await handshake_manager.manage_all_connections()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer is shutting down.")
