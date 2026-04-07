from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    litellm_base_url: str = "http://litellm:4000"
    litellm_api_key: str = "sk-assist2"
    backend_base_url: str = "http://backend:8000"
    langgraph_api_key: str = "dev-langgraph-secret"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
