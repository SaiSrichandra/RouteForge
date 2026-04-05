from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/order_routing"
    temporal_address: str = "temporal:7233"
    temporal_task_queue: str = "order-routing-task-queue"
    inventory_service_url: str = "http://inventory-service:8001"
    routing_service_url: str = "http://routing-engine:8002"
    default_sla_days: int = 3
    metrics_port: int = 9100

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
