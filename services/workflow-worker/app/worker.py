import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from app.activities import (
    authorize_payment,
    build_inventory_snapshot,
    compute_routing_plan,
    confirm_order,
    create_shipments,
    fail_order,
    load_order,
    record_event,
    release_inventory,
    reserve_inventory,
    save_routing_plan,
    update_order_status,
)
from app.config import settings
from app.db import Base, engine
from app.metrics import ensure_metrics_server
from app.workflows import OrderFulfillmentWorkflow


async def main() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_metrics_server(settings.metrics_port)
    client = await Client.connect(settings.temporal_address)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[OrderFulfillmentWorkflow],
        activities=[
            authorize_payment,
            build_inventory_snapshot,
            compute_routing_plan,
            confirm_order,
            create_shipments,
            fail_order,
            load_order,
            record_event,
            release_inventory,
            reserve_inventory,
            save_routing_plan,
            update_order_status,
        ],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
