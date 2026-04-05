import json
import os
import random
from decimal import Decimal

import psycopg

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/order_routing")

WAREHOUSES = [
    {
        "code": "NJ",
        "name": "New Jersey Fulfillment Center",
        "supported_zones": ["east", "northeast", "central"],
        "shipping_cost_multiplier": Decimal("1.10"),
        "daily_capacity": 120,
        "current_load": 48,
    },
    {
        "code": "TX",
        "name": "Dallas Fulfillment Center",
        "supported_zones": ["east", "central", "south"],
        "shipping_cost_multiplier": Decimal("0.95"),
        "daily_capacity": 150,
        "current_load": 62,
    },
    {
        "code": "NV",
        "name": "Reno Fulfillment Center",
        "supported_zones": ["west", "southwest", "central"],
        "shipping_cost_multiplier": Decimal("1.05"),
        "daily_capacity": 90,
        "current_load": 35,
    },
]


def main() -> None:
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

            for warehouse in WAREHOUSES:
                cur.execute(
                    """
                    INSERT INTO warehouses (
                        id,
                        code,
                        name,
                        supported_zones,
                        shipping_cost_multiplier,
                        daily_capacity,
                        current_load,
                        active
                    )
                    VALUES (
                        gen_random_uuid(),
                        %(code)s,
                        %(name)s,
                        %(supported_zones)s::jsonb,
                        %(shipping_cost_multiplier)s,
                        %(daily_capacity)s,
                        %(current_load)s,
                        TRUE
                    )
                    ON CONFLICT (code) DO UPDATE SET
                        name = EXCLUDED.name,
                        supported_zones = EXCLUDED.supported_zones,
                        shipping_cost_multiplier = EXCLUDED.shipping_cost_multiplier,
                        daily_capacity = EXCLUDED.daily_capacity,
                        current_load = EXCLUDED.current_load,
                        active = EXCLUDED.active
                    """,
                    {
                        **warehouse,
                        "supported_zones": json.dumps(warehouse["supported_zones"]),
                    },
                )

            cur.execute("SELECT id, code FROM warehouses")
            warehouse_rows = cur.fetchall()

            for warehouse_id, code in warehouse_rows:
                for sku_number in range(1, 101):
                    cur.execute(
                        """
                        INSERT INTO inventory (id, warehouse_id, sku, available_qty, reserved_qty)
                        VALUES (gen_random_uuid(), %s, %s, %s, 0)
                        ON CONFLICT (warehouse_id, sku) DO UPDATE SET
                            available_qty = EXCLUDED.available_qty,
                            reserved_qty = inventory.reserved_qty
                        """,
                        (
                            warehouse_id,
                            f"SKU-{sku_number:03d}",
                            random.randint(20, 200) if code != "NV" else random.randint(10, 120),
                        ),
                    )

    print("Seeded warehouses and inventory.")


if __name__ == "__main__":
    main()
