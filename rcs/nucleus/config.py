# rcs/nucleus/config.py
import json
import logging
from typing import Dict, Any, Optional

from pydantic import BaseModel, Field
from rcs.utils.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class ComponentConfig(BaseModel):
    """Pydantic model for a single remote component's configuration."""
    uri: str
    auth_token: str
    disabled: bool = False
    # We can add more component-specific settings here in the future
    # max_concurrent_requests: int = 5


class ConfigManager:
    """
    Manages the dynamic configuration of components, using Redis as the source of truth.
    """
    def __init__(self):
        self._redis = get_redis_client()
        # In-memory cache for fast access to configurations
        self.configs: Dict[str, ComponentConfig] = {}
        logger.info("ConfigManager initialized.")

    async def sync_on_startup(self, bootstrap_file_path: str = "remote_components.json"):
        """
        Performs initial synchronization.
        Reads a bootstrap file. If a component's config doesn't exist in Redis,
        it creates it using the data from the file.
        """
        logger.info("Starting initial configuration sync with Redis...")
        try:
            with open(bootstrap_file_path, "r") as f:
                bootstrap_configs = json.load(f)
        except FileNotFoundError:
            logger.error(f"CRITICAL: Bootstrap config file '{bootstrap_file_path}' not found! Shutting down.")
            exit(1)
        except json.JSONDecodeError:
            logger.error(f"CRITICAL: Could not parse '{bootstrap_file_path}'. Make sure it's valid JSON.")
            exit(1)

        for name, data in bootstrap_configs.items():
            key = f"rcs:config:{name}"

            if not await self._redis.exists(key):
                logger.warning(f"Config for '{name}' not found in Redis. Creating from bootstrap file...")
                # Pydantic model validates the data from the file
                try:
                    initial_config = ComponentConfig(**data)
                    await self._redis.hset(key, mapping=initial_config.model_dump())
                except Exception as e:
                    logger.error(f"Invalid data for '{name}' in bootstrap file: {e}")
                    continue

            # Load the current config from Redis into the in-memory cache
            stored_config_raw = await self._redis.hgetall(key)
            if stored_config_raw:
                # Redis stores bools as "True"/"False", so we need to parse them
                stored_config_raw["disabled"] = stored_config_raw.get("disabled", "false").lower() == "true"
                self.configs[name] = ComponentConfig(**stored_config_raw)


        logger.info(f"Sync complete. Loaded {len(self.configs)} component configurations.")

    def get_all_components(self) -> Dict[str, ComponentConfig]:
        """Returns the cached dictionary of all component configurations."""
        return self.configs

    def get_component_config(self, name: str) -> Optional[ComponentConfig]:
        """Returns the cached configuration for a single component."""
        return self.configs.get(name)
