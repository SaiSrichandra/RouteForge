from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
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


@workflow.defn(name="OrderFulfillmentWorkflow")
class OrderFulfillmentWorkflow:
    @workflow.run
    async def run(self, order_id: str) -> dict[str, Any]:
        workflow_id = workflow.info().workflow_id
        reservations_created = False

        try:
            await workflow.execute_activity(
                record_event,
                args=[order_id, workflow_id, "workflow_execution_started", {}],
                start_to_close_timeout=timedelta(seconds=20),
            )
            await workflow.execute_activity(
                update_order_status,
                args=[order_id, "routing"],
                start_to_close_timeout=timedelta(seconds=20),
            )
            order = await workflow.execute_activity(
                load_order,
                args=[order_id],
                start_to_close_timeout=timedelta(seconds=20),
            )
            warehouses = await workflow.execute_activity(
                build_inventory_snapshot,
                args=[order],
                start_to_close_timeout=timedelta(seconds=30),
            )
            routing_result = await workflow.execute_activity(
                compute_routing_plan,
                args=[order, warehouses],
                start_to_close_timeout=timedelta(seconds=30),
            )
            await workflow.execute_activity(
                save_routing_plan,
                args=[order_id, workflow_id, routing_result],
                start_to_close_timeout=timedelta(seconds=20),
            )
            await workflow.execute_activity(
                reserve_inventory,
                args=[order_id, workflow_id, routing_result["selected_plan"]],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            reservations_created = True
            await workflow.execute_activity(
                authorize_payment,
                args=[order, workflow_id],
                start_to_close_timeout=timedelta(seconds=20),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            shipments = await workflow.execute_activity(
                create_shipments,
                args=[order, workflow_id, routing_result["selected_plan"]],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    backoff_coefficient=2.0,
                    maximum_attempts=3,
                ),
            )
            await workflow.execute_activity(
                confirm_order,
                args=[order_id, workflow_id],
                start_to_close_timeout=timedelta(seconds=20),
            )
            await workflow.execute_activity(
                record_event,
                args=[order_id, workflow_id, "workflow_execution_completed", {"shipments": shipments}],
                start_to_close_timeout=timedelta(seconds=20),
            )
            return {
                "order_id": order_id,
                "workflow_id": workflow_id,
                "status": "confirmed",
                "shipments": shipments,
            }
        except Exception as exc:
            if reservations_created:
                await workflow.execute_activity(
                    release_inventory,
                    args=[order_id, workflow_id],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(maximum_attempts=1),
                )
            await workflow.execute_activity(
                fail_order,
                args=[order_id, workflow_id, str(exc)],
                start_to_close_timeout=timedelta(seconds=20),
            )
            raise
