from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/order_routing"
    service_name: str = "order-api"
    temporal_address: str = "localhost:7233"
    temporal_task_queue: str = "order-routing-task-queue"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
