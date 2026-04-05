from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/order_routing"
    service_name: str = "inventory-service"
    inventory_cache_enabled: bool = True
    inventory_cache_ttl_seconds: float = 5.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
