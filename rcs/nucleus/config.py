# rcs/nucleus/config.py
import json
import logging
from typing import Dict, Any, Optional

from pydantic import BaseModel, Field
from rcs.utils.redis_client import get_redis_client

logger = logging.getLogger(__name__)


# --- Pydantic Models for Configuration ---
# By defining strict models, we ensure data integrity from the start.

class ConnectionConfig(BaseModel):
    uri: str
    auth_token: str

class ControlConfig(BaseModel):
    enabled: bool

class MetadataConfig(BaseModel):
    owner: Optional[str] = None
    description: Optional[str] = None

class ComponentConfig(BaseModel):
    """The canonical model for a component's full configuration."""
    connection: ConnectionConfig
    control: ControlConfig
    metadata: MetadataConfig


# --- The ConfigManager Itself ---

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
        Performs initial synchronization from a bootstrap file to Redis.
        This only has an effect if the configuration for a component does not
        already exist in Redis.
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
                try:
                    # Pydantic validates the structure of the data from the file
                    initial_config = ComponentConfig(**data)
                    # We store the config as a single JSON string in a Redis Hash
                    # to preserve its structure.
                    await self._redis.hset(key, "data", initial_config.model_dump_json())
                except Exception as e:
                    logger.error(f"Invalid data structure for '{name}' in bootstrap file: {e}")
                    continue

            # Load the current config from Redis into the in-memory cache
            stored_config_json = await self._redis.hget(key, "data")
            if stored_config_json:
                try:
                    self.configs[name] = ComponentConfig.model_validate_json(stored_config_json)
                except Exception as e:
                    logger.error(f"Could not parse config for '{name}' from Redis: {e}")
            else:
                logger.error(f"Config for '{name}' was expected in Redis but not found!")

        logger.info(f"Sync complete. Loaded {len(self.configs)} component configurations.")

    def get_all_components(self) -> Dict[str, ComponentConfig]:
        """Returns the cached dictionary of all component configurations."""
        return self.configs

    def get_component_config(self, name: str) -> Optional[ComponentConfig]:
        """Returns the cached configuration for a single component."""
        return self.configs.get(name)
