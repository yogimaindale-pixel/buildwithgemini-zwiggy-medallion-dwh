"""Silver layer transformation and conforming engine."""

import logging
from typing import Dict

from zwiggy_dwh.batch import Batch, step
from zwiggy_dwh.db import execute_sql, fetch_scalar, warehouse_connection

logger = logging.getLogger(__name__)


def load_slv_customer(batch: Batch) -> dict:
    """Transform br_customer into slv_customer and quarantine invalid records."""
    sql = """
    -- Quarantine missing customer_id
    INSERT INTO silver.slv_customer_quarantine (dw_batch_id, dw_quarantine_reason, dw_raw_payload)
    SELECT dw_batch_id, 'Missing customer_id', row_to_json(b)::jsonb
    FROM bronze.br_customer b
    WHERE dw_batch_id = %s AND (customer_id IS NULL OR customer_id = '');

    -- Load valid slv_customer
    INSERT INTO silver.slv_customer (customer_id, name, email_masked, phone_masked, created_at, updated_at, dw_batch_id)
    SELECT
        customer_id::bigint,
        name,
        silver.mask_pii(email),
        silver.mask_pii(phone),
        created_at::timestamptz,
        updated_at::timestamptz,
        dw_batch_id
    FROM bronze.br_customer
    WHERE dw_batch_id = %s AND customer_id IS NOT NULL AND customer_id <> ''
    ON CONFLICT (customer_id) DO UPDATE SET
        name = EXCLUDED.name,
        email_masked = EXCLUDED.email_masked,
        phone_masked = EXCLUDED.phone_masked,
        updated_at = EXCLUDED.updated_at,
        dw_batch_id = EXCLUDED.dw_batch_id;
    """
    with warehouse_connection() as conn:
        execute_sql(conn, sql, (batch.batch_id, batch.batch_id))
        written = fetch_scalar(conn, "SELECT COUNT(*) FROM silver.slv_customer WHERE dw_batch_id = %s", (batch.batch_id,)) or 0
        quarantined = fetch_scalar(conn, "SELECT COUNT(*) FROM silver.slv_customer_quarantine WHERE dw_batch_id = %s", (batch.batch_id,)) or 0
        return {"written": written, "quarantined": quarantined}


def load_slv_restaurant(batch: Batch) -> dict:
    """Transform br_restaurant into slv_restaurant."""
    sql = """
    INSERT INTO silver.slv_restaurant (restaurant_id, name, cuisine, city, is_active, created_at, updated_at, dw_batch_id)
    SELECT
        restaurant_id::bigint,
        name,
        cuisine,
        city,
        COALESCE(is_active::boolean, true),
        created_at::timestamptz,
        updated_at::timestamptz,
        dw_batch_id
    FROM bronze.br_restaurant
    WHERE dw_batch_id = %s AND restaurant_id IS NOT NULL AND restaurant_id <> ''
    ON CONFLICT (restaurant_id) DO UPDATE SET
        name = EXCLUDED.name,
        cuisine = EXCLUDED.cuisine,
        city = EXCLUDED.city,
        is_active = EXCLUDED.is_active,
        updated_at = EXCLUDED.updated_at,
        dw_batch_id = EXCLUDED.dw_batch_id;
    """
    with warehouse_connection() as conn:
        execute_sql(conn, sql, (batch.batch_id,))
        written = fetch_scalar(conn, "SELECT COUNT(*) FROM silver.slv_restaurant WHERE dw_batch_id = %s", (batch.batch_id,)) or 0
        return {"written": written, "quarantined": 0}


def load_slv_order(batch: Batch) -> dict:
    """Transform br_order into slv_order with status conformance and cohort rule mapping."""
    sql = """
    -- Quarantine missing order_id
    INSERT INTO silver.slv_order_quarantine (dw_batch_id, dw_quarantine_reason, dw_raw_payload)
    SELECT dw_batch_id, 'Missing order_id', row_to_json(b)::jsonb
    FROM bronze.br_order_header b
    WHERE dw_batch_id = %s AND (order_id IS NULL OR order_id = '');

    -- Load valid slv_order
    INSERT INTO silver.slv_order (
        order_id, customer_id, restaurant_id, order_status, total_amount,
        discount_amount, delivery_fee, cohort_id, created_at, updated_at, dw_batch_id
    )
    SELECT
        b.order_id::bigint,
        b.customer_id::bigint,
        b.restaurant_id::bigint,
        UPPER(COALESCE(b.status, 'PLACED')),
        COALESCE(b.total_amount::numeric(12,2), 0),
        COALESCE(b.discount_amount::numeric(12,2), 0),
        COALESCE(b.delivery_fee::numeric(12,2), 0),
        CASE
            WHEN b.order_id::bigint <= 50000 THEN 'COHORT_A'
            ELSE 'COHORT_B'
        END,
        b.created_at::timestamptz,
        b.updated_at::timestamptz,
        b.dw_batch_id
    FROM bronze.br_order_header b
    WHERE b.dw_batch_id = %s AND b.order_id IS NOT NULL AND b.order_id <> ''
    ON CONFLICT (order_id) DO UPDATE SET
        order_status = EXCLUDED.order_status,
        total_amount = EXCLUDED.total_amount,
        discount_amount = EXCLUDED.discount_amount,
        delivery_fee = EXCLUDED.delivery_fee,
        updated_at = EXCLUDED.updated_at,
        dw_batch_id = EXCLUDED.dw_batch_id;
    """
    with warehouse_connection() as conn:
        execute_sql(conn, sql, (batch.batch_id, batch.batch_id))
        written = fetch_scalar(conn, "SELECT COUNT(*) FROM silver.slv_order WHERE dw_batch_id = %s", (batch.batch_id,)) or 0
        quarantined = fetch_scalar(conn, "SELECT COUNT(*) FROM silver.slv_order_quarantine WHERE dw_batch_id = %s", (batch.batch_id,)) or 0
        return {"written": written, "quarantined": quarantined}


def load_slv_payment(batch: Batch) -> dict:
    """Transform br_order_payment into slv_payment using ref_payment_method_map."""
    sql = """
    INSERT INTO silver.slv_payment (payment_id, order_id, payment_method, status, amount, created_at, updated_at, dw_batch_id)
    SELECT
        b.payment_id::bigint,
        b.order_id::bigint,
        COALESCE(m.conformed_payment_method, UPPER(b.payment_method)),
        UPPER(COALESCE(b.status, 'COMPLETED')),
        COALESCE(b.amount::numeric(12,2), 0),
        b.created_at::timestamptz,
        b.updated_at::timestamptz,
        b.dw_batch_id
    FROM bronze.br_order_payment b
    LEFT JOIN silver.ref_payment_method_map m ON LOWER(b.payment_method) = LOWER(m.raw_payment_method)
    WHERE b.dw_batch_id = %s AND b.payment_id IS NOT NULL AND b.payment_id <> ''
    ON CONFLICT (payment_id) DO UPDATE SET
        payment_method = EXCLUDED.payment_method,
        status = EXCLUDED.status,
        amount = EXCLUDED.amount,
        updated_at = EXCLUDED.updated_at,
        dw_batch_id = EXCLUDED.dw_batch_id;
    """
    with warehouse_connection() as conn:
        execute_sql(conn, sql, (batch.batch_id,))
        written = fetch_scalar(conn, "SELECT COUNT(*) FROM silver.slv_payment WHERE dw_batch_id = %s", (batch.batch_id,)) or 0
        return {"written": written, "quarantined": 0}


def run_silver(batch: Batch) -> Dict[str, dict]:
    """Orchestrate Silver layer transformations for all entities."""
    results = {}

    loaders = [
        ("slv_customer", load_slv_customer),
        ("slv_restaurant", load_slv_restaurant),
        ("slv_order", load_slv_order),
        ("slv_payment", load_slv_payment),
    ]

    for name, fn in loaders:
        with step(batch, "silver_load", name) as res:
            out = fn(batch)
            res.rows_written = out.get("written", 0)
            res.rows_quarantined = out.get("quarantined", 0)
            results[name] = out

    return results
