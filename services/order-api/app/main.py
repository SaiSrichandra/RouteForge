import uuid
from uuid import UUID

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload
from temporalio.client import Client
from temporalio.exceptions import TemporalError

from app.config import settings
from app.db import Base, SessionLocal, engine, get_db
from app.models import Order, OrderItem, OrderStatus, Shipment, WorkflowEvent
from app.observability import (
    ORDERS_CREATED_TOTAL,
    WORKFLOW_START_FAILURES_TOTAL,
    instrument_http,
    render_prometheus_metrics,
)
from app.schemas import OrderCreate, OrderRead, ShipmentRead, WorkflowEventRead

app = FastAPI(
    title="Order API",
    version="0.1.0",
    description="Entry-point service for order intake and lifecycle lookup.",
)
app.middleware("http")(instrument_http)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    app.state.temporal_client = None


async def get_temporal_client() -> Client:
    client = getattr(app.state, "temporal_client", None)
    if client is None:
        client = await Client.connect(settings.temporal_address)
        app.state.temporal_client = client
    return client


async def start_order_workflow(order_id: UUID, workflow_id: str) -> None:
    db = SessionLocal()
    try:
        client = await get_temporal_client()
        await client.start_workflow(
            "OrderFulfillmentWorkflow",
            str(order_id),
            id=workflow_id,
            task_queue=settings.temporal_task_queue,
        )
        db.add(
            WorkflowEvent(
                order_id=order_id,
                workflow_id=workflow_id,
                event_type="workflow_started",
                payload={"task_queue": settings.temporal_task_queue},
            )
        )
        db.commit()
    except TemporalError as exc:
        order = db.query(Order).filter(Order.id == order_id).one_or_none()
        if order is not None:
            order.status = OrderStatus.failed
        WORKFLOW_START_FAILURES_TOTAL.inc()
        db.add(
            WorkflowEvent(
                order_id=order_id,
                workflow_id=workflow_id,
                event_type="workflow_start_failed",
                payload={"error": str(exc)},
            )
        )
        db.commit()
    finally:
        db.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "order-api"}


@app.post("/orders", response_model=OrderRead, status_code=201)
async def create_order(
    payload: OrderCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Order:
    workflow_id = f"wf-{uuid.uuid4()}"
    order = Order(
        customer_id=payload.customer_id,
        destination_zone=payload.destination_zone,
        workflow_id=workflow_id,
    )
    order.items = [
        OrderItem(sku=item.sku, quantity=item.quantity, unit_price=item.unit_price)
        for item in payload.line_items
    ]
    db.add(order)
    db.commit()
    db.refresh(order)
    ORDERS_CREATED_TOTAL.inc()
    created = (
        db.query(Order)
        .options(selectinload(Order.items))
        .filter(Order.id == order.id)
        .one()
    )

    db.add(
        WorkflowEvent(
            order_id=order.id,
            workflow_id=workflow_id,
            event_type="workflow_start_queued",
            payload={"task_queue": settings.temporal_task_queue},
        )
    )
    db.commit()
    background_tasks.add_task(start_order_workflow, order.id, workflow_id)
    return created


@app.get("/orders/{order_id}", response_model=OrderRead)
def get_order(order_id: UUID, db: Session = Depends(get_db)) -> Order:
    order = (
        db.query(Order)
        .options(selectinload(Order.items))
        .filter(Order.id == order_id)
        .one_or_none()
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.get("/orders", response_model=list[OrderRead])
def list_orders(limit: int = 25, db: Session = Depends(get_db)) -> list[Order]:
    return (
        db.query(Order)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
        .limit(min(max(limit, 1), 100))
        .all()
    )


@app.get("/orders/{order_id}/events", response_model=list[WorkflowEventRead])
def get_order_events(order_id: UUID, db: Session = Depends(get_db)) -> list[WorkflowEvent]:
    return (
        db.query(WorkflowEvent)
        .filter(WorkflowEvent.order_id == order_id)
        .order_by(WorkflowEvent.created_at.asc())
        .all()
    )


@app.get("/orders/{order_id}/shipments", response_model=list[ShipmentRead])
def get_order_shipments(order_id: UUID, db: Session = Depends(get_db)) -> list[Shipment]:
    return (
        db.query(Shipment)
        .filter(Shipment.order_id == order_id)
        .order_by(Shipment.created_at.asc())
        .all()
    )


@app.get("/metrics")
def metrics(db: Session = Depends(get_db)) -> dict[str, object]:
    return {
        "service": "order-api",
        "total_orders": db.query(func.count(Order.id)).scalar() or 0,
        "pending_orders": db.query(func.count(Order.id)).filter(Order.status == OrderStatus.pending).scalar() or 0,
        "routing_orders": db.query(func.count(Order.id)).filter(Order.status == OrderStatus.routing).scalar() or 0,
        "confirmed_orders": db.query(func.count(Order.id)).filter(Order.status == OrderStatus.confirmed).scalar() or 0,
        "failed_orders": db.query(func.count(Order.id)).filter(Order.status == OrderStatus.failed).scalar() or 0,
    }


@app.get("/prometheus")
def prometheus_metrics(db: Session = Depends(get_db)):
    return render_prometheus_metrics(db)
