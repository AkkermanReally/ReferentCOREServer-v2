# rcs/main.py
import asyncio
import logging
from websockets.server import serve

from rcs.settings import settings
from rcs.engine import PipelineEngine
from rcs.electrons.logger import LoggerElectron
from rcs.nucleus.router import nucleus_router


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

    # 2. Define the active electrons for our pipeline.
    # The order in this list is the order of execution.
    active_electrons = [
        LoggerElectron(),
        # In the future, we can add more electrons here:
        # AuthenticationElectron(),
        # CacheElectron(),
    ]

    # 3. Instantiate the pipeline engine.
    # It takes our list of electrons and the final nucleus handler.
    engine = PipelineEngine(
        electrons=active_electrons,
        nucleus_handler=nucleus_router
    )

    # 4. Start the WebSocket server.
    # The `engine.handle_connection` method will be called for each new client.
    logger.info(f"Starting RefferentCOREServer v2 on {settings.SERVER_HOST}:{settings.SERVER_PORT}")
    async with serve(
        engine.handle_connection,
        settings.SERVER_HOST,
        settings.SERVER_PORT,
        max_size=None # Allow large messages
    ):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server is shutting down.")
