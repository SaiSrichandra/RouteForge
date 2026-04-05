from __future__ import annotations

import importlib
import statistics
import sys
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from types import ModuleType
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

REPO_ROOT = Path(__file__).resolve().parents[1]
INVENTORY_SERVICE_ROOT = REPO_ROOT / "services" / "inventory-service"


def _load_inventory_modules() -> tuple[ModuleType, Any, Any, type[Any], type[Any]]:
    inventory_root = str(INVENTORY_SERVICE_ROOT)
    if inventory_root not in sys.path:
        sys.path.insert(0, inventory_root)

    main_module = importlib.import_module("app.main")
    cache_module = importlib.import_module("app.cache")
    config_module = importlib.import_module("app.config")
    models_module = importlib.import_module("app.models")

    return (
        main_module,
        cache_module.inventory_read_cache,
        config_module.settings,
        models_module.Inventory,
        models_module.Warehouse,
    )


main, inventory_read_cache, settings, Inventory, Warehouse = _load_inventory_modules()


def _override_database(database_url: str):
    engine = create_engine(
        database_url,
        future=True,
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    main.engine = engine
    main.Base.metadata.drop_all(bind=engine)
    main.Base.metadata.create_all(bind=engine)
    inventory_read_cache.clear()

    def override_get_db():
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[main.get_db] = override_get_db
    return session_local


def _seed_inventory(session_local: sessionmaker[Session]) -> None:
    with session_local() as db:
        warehouses: list[Warehouse] = []
        for index in range(75):
            warehouse = Warehouse(
                id=uuid.uuid4(),
                code=f"W{index:03d}",
                name=f"Warehouse {index:03d}",
                supported_zones=["east", "central", "west"],
                shipping_cost_multiplier="1.00",
                daily_capacity=500,
                current_load=index % 50,
                active=True,
            )
            warehouses.append(warehouse)
        db.add_all(warehouses)
        db.flush()

        inventory_rows: list[Inventory] = []
        for warehouse in warehouses:
            inventory_rows.append(
                Inventory(
                    warehouse_id=warehouse.id,
                    sku="SKU-HOT",
                    available_qty=150,
                    reserved_qty=0,
                )
            )
            for suffix in range(20):
                inventory_rows.append(
                    Inventory(
                        warehouse_id=warehouse.id,
                        sku=f"SKU-{suffix:03d}",
                        available_qty=50,
                        reserved_qty=0,
                    )
                )
        db.add_all(inventory_rows)
        db.commit()


def _run_pass(client: TestClient, *, cached: bool, iterations: int = 250) -> dict[str, float]:
    settings.inventory_cache_enabled = cached
    inventory_read_cache.clear()
    timings_ms: list[float] = []

    for _ in range(iterations):
        started_at = perf_counter()
        response = client.get("/inventory/SKU-HOT")
        response.raise_for_status()
        timings_ms.append((perf_counter() - started_at) * 1000)

    return {
        "mean_ms": round(statistics.fmean(timings_ms), 2),
        "p50_ms": round(statistics.median(timings_ms), 2),
        "p95_ms": round(statistics.quantiles(timings_ms, n=20)[18], 2),
    }


def main_benchmark() -> None:
    with TemporaryDirectory() as temp_dir:
        database_url = f"sqlite:///{Path(temp_dir) / 'inventory-benchmark.db'}"
        session_local = _override_database(database_url)
        _seed_inventory(session_local)

        with TestClient(main.app) as client:
            without_cache = _run_pass(client, cached=False)
            with_cache = _run_pass(client, cached=True)

    mean_improvement = round(
        ((without_cache["mean_ms"] - with_cache["mean_ms"]) / without_cache["mean_ms"]) * 100,
        1,
    )
    p95_improvement = round(
        ((without_cache["p95_ms"] - with_cache["p95_ms"]) / without_cache["p95_ms"]) * 100,
        1,
    )

    print("Inventory read benchmark")
    print(f"without cache: {without_cache}")
    print(f"with cache:    {with_cache}")
    print(f"mean improvement: {mean_improvement}%")
    print(f"p95 improvement:  {p95_improvement}%")


if __name__ == "__main__":
    main_benchmark()
