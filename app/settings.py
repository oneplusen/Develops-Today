from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./travel_planner.db"
    artic_base_url: str = "https://api.artic.edu/api/v1"
    artic_timeout_seconds: float = 10.0
    artic_cache_ttl_seconds: int = 300


settings = Settings()

