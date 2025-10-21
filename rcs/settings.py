# rcs/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Manages the application's settings, loading from environment variables
    and .env files.
    """
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    # Application settings
    LOG_LEVEL: str = "INFO"

    # Server settings
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8080


# Create a single, globally accessible instance of the settings.
settings = Settings()
