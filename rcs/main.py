# rcs/main.py
import asyncio
import logging

from rcs.settings import settings
from rcs.engine import PipelineEngine
from rcs.electrons.logger import LoggerElectron
from rcs.electrons.flow_control import FlowControlElectron
from rcs.nucleus.router import Router
from rcs.nucleus.state import RedisState
from rcs.nucleus.config import ConfigManager
from rcs.nucleus.handshake import HandshakeManager
from rcs.nucleus.registry import ConnectionRegistry
from rcs.gateway import ClientGateway


async def main():
    """
    The main entry point for the RefferentCOREServer v2.
    """
    logging.basicConfig(
        level=settings.LOG_LEVEL.upper(),
        format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s"
    )
    logger = logging.getLogger("RCs_Main")

    # 1. Initialize all Nucleus components
    logger.info("Initializing Nucleus components...")
    config_manager = ConfigManager()
    await config_manager.sync_on_startup()

    state = RedisState()
    registry = ConnectionRegistry()
    router = Router(state, registry)

    # 2. Create electrons first, but leave dependencies that are not yet created as None.
    # FlowControlElectron needs the pipeline engine, but it's not created yet.
    # Мы передадим None и установим его позже.
    flow_control_electron = FlowControlElectron(config_manager, None) # type: ignore

    # 3. Define the list of active electrons.
    active_electrons = [
        LoggerElectron(),
        flow_control_electron, # Flow control should be near the end of the chain.
    ]

    # 4. Now, create the pipeline engine, passing it the fully formed list of electrons.
    pipeline_engine = PipelineEngine(
        electrons=active_electrons,
        nucleus_router=router
    )

    # 5. Finally, inject the created pipeline engine back into the electron that needs it.
    # This completes the dependency circle correctly.
    flow_control_electron._pipeline = pipeline_engine
    # ### ИЗМЕНЕНИЕ: Конец ###


    # 6. Initialize the main operational managers
    handshake_manager = HandshakeManager(config_manager, state, registry, pipeline_engine)
    client_gateway = ClientGateway(registry, pipeline_engine)

    # 7. Create tasks for the main operational loops
    handshake_task = asyncio.create_task(handshake_manager.manage_all_connections())
    gateway_task = asyncio.create_task(client_gateway.start())

    logger.info("Starting RefferentCOREServer v2... Now accepting client and component connections.")
    await asyncio.gather(handshake_task, gateway_task)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer is shutting down.")
