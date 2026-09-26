"""Gold layer dimensional modeling (SCD2 dimensions, facts, and aggregate marts)."""

import logging
from typing import Dict

from zwiggy_dwh.batch import Batch, step
from zwiggy_dwh.db import execute_sql, fetch_scalar, warehouse_connection

logger = logging.getLogger(__name__)


def build_dim_customer(batch: Batch) -> int:
    """Build SCD2 dim_customer from slv_customer."""
    sql = """
    -- 1. Expire modified current rows
    UPDATE gold.dim_customer d
    SET valid_to = s.updated_at,
        dw_is_current = FALSE
    FROM silver.slv_customer s
    WHERE d.customer_id = s.customer_id
      AND d.dw_is_current = TRUE
      AND (d.name IS DISTINCT FROM s.name OR d.email_masked IS DISTINCT FROM s.email_masked);

    -- 2. Insert new version/current rows
    INSERT INTO gold.dim_customer (customer_id, name, email_masked, phone_masked, valid_from, dw_is_current, dw_version, dw_batch_id)
    SELECT
        s.customer_id,
        s.name,
        s.email_masked,
        s.phone_masked,
        COALESCE(s.updated_at, s.created_at, NOW()),
        TRUE,
        COALESCE((SELECT MAX(dw_version) + 1 FROM gold.dim_customer WHERE customer_id = s.customer_id), 1),
        s.dw_batch_id
    FROM silver.slv_customer s
    WHERE s.dw_batch_id = %s
      AND NOT EXISTS (
          SELECT 1 FROM gold.dim_customer d
          WHERE d.customer_id = s.customer_id AND d.dw_is_current = TRUE
            AND d.name IS NOT DISTINCT FROM s.name
            AND d.email_masked IS NOT DISTINCT FROM s.email_masked
      );
    """
    with warehouse_connection() as conn:
        execute_sql(conn, sql, (batch.batch_id,))
        return fetch_scalar(conn, "SELECT COUNT(*) FROM gold.dim_customer WHERE dw_batch_id = %s", (batch.batch_id,)) or 0


def build_dim_restaurant(batch: Batch) -> int:
    """Build SCD2 dim_restaurant from slv_restaurant."""
    sql = """
    UPDATE gold.dim_restaurant d
    SET valid_to = s.updated_at,
        dw_is_current = FALSE
    FROM silver.slv_restaurant s
    WHERE d.restaurant_id = s.restaurant_id
      AND d.dw_is_current = TRUE
      AND (d.name IS DISTINCT FROM s.name OR d.city IS DISTINCT FROM s.city);

    INSERT INTO gold.dim_restaurant (restaurant_id, name, cuisine, city, is_active, valid_from, dw_is_current, dw_version, dw_batch_id)
    SELECT
        s.restaurant_id,
        s.name,
        s.cuisine,
        s.city,
        s.is_active,
        COALESCE(s.updated_at, s.created_at, NOW()),
        TRUE,
        COALESCE((SELECT MAX(dw_version) + 1 FROM gold.dim_restaurant WHERE restaurant_id = s.restaurant_id), 1),
        s.dw_batch_id
    FROM silver.slv_restaurant s
    WHERE s.dw_batch_id = %s
      AND NOT EXISTS (
          SELECT 1 FROM gold.dim_restaurant d
          WHERE d.restaurant_id = s.restaurant_id AND d.dw_is_current = TRUE
            AND d.name IS NOT DISTINCT FROM s.name
            AND d.city IS NOT DISTINCT FROM s.city
      );
    """
    with warehouse_connection() as conn:
        execute_sql(conn, sql, (batch.batch_id,))
        return fetch_scalar(conn, "SELECT COUNT(*) FROM gold.dim_restaurant WHERE dw_batch_id = %s", (batch.batch_id,)) or 0


def build_fact_order(batch: Batch) -> int:
    """Load fact_order with surrogate key resolution (-1 fallback for unknown)."""
    sql = """
    INSERT INTO gold.fact_order (
        order_id, customer_sk, restaurant_sk, order_date_sk, order_time_sk,
        order_status, total_amount, discount_amount, delivery_fee, cohort_id, dw_batch_id
    )
    SELECT
        o.order_id,
        COALESCE(c.customer_sk, -1),
        COALESCE(r.restaurant_sk, -1),
        gold.to_date_sk(o.created_at),
        gold.to_time_sk(o.created_at),
        o.order_status,
        o.total_amount,
        o.discount_amount,
        o.delivery_fee,
        o.cohort_id,
        o.dw_batch_id
    FROM silver.slv_order o
    LEFT JOIN gold.dim_customer c
        ON o.customer_id = c.customer_id AND c.dw_is_current = TRUE
    LEFT JOIN gold.dim_restaurant r
        ON o.restaurant_id = r.restaurant_id AND r.dw_is_current = TRUE
    WHERE o.dw_batch_id = %s;
    """
    with warehouse_connection() as conn:
        execute_sql(conn, sql, (batch.batch_id,))
        return fetch_scalar(conn, "SELECT COUNT(*) FROM gold.fact_order WHERE dw_batch_id = %s", (batch.batch_id,)) or 0


def build_fact_payment(batch: Batch) -> int:
    """Load fact_payment with surrogate key resolution."""
    sql = """
    INSERT INTO gold.fact_payment (
        payment_id, order_sk, payment_method, status, amount, payment_date_sk, dw_batch_id
    )
    SELECT
        p.payment_id,
        COALESCE(o.order_sk, -1),
        p.payment_method,
        p.status,
        p.amount,
        gold.to_date_sk(p.created_at),
        p.dw_batch_id
    FROM silver.slv_payment p
    LEFT JOIN gold.fact_order o ON p.order_id = o.order_id
    WHERE p.dw_batch_id = %s;
    """
    with warehouse_connection() as conn:
        execute_sql(conn, sql, (batch.batch_id,))
        return fetch_scalar(conn, "SELECT COUNT(*) FROM gold.fact_payment WHERE dw_batch_id = %s", (batch.batch_id,)) or 0


def rebuild_marts(batch: Batch) -> None:
    """Rebuild aggregate mart tables for business reporting."""
    sql = """
    -- Rebuild mart_daily_business_summary
    INSERT INTO gold.mart_daily_business_summary (summary_date, total_orders, total_revenue, total_discounts, active_customers, dw_batch_id)
    SELECT
        d.full_date AS summary_date,
        COUNT(f.order_sk) AS total_orders,
        COALESCE(SUM(f.total_amount), 0) AS total_revenue,
        COALESCE(SUM(f.discount_amount), 0) AS total_discounts,
        COUNT(DISTINCT f.customer_sk) AS active_customers,
        %s AS dw_batch_id
    FROM gold.fact_order f
    JOIN gold.dim_date d ON f.order_date_sk = d.date_sk
    WHERE d.date_sk <> -1
    GROUP BY d.full_date
    ON CONFLICT (summary_date) DO UPDATE SET
        total_orders = EXCLUDED.total_orders,
        total_revenue = EXCLUDED.total_revenue,
        total_discounts = EXCLUDED.total_discounts,
        active_customers = EXCLUDED.active_customers,
        dw_batch_id = EXCLUDED.dw_batch_id,
        updated_ts_utc = NOW();
    """
    with warehouse_connection() as conn:
        execute_sql(conn, sql, (batch.batch_id,))


def run_gold(batch: Batch) -> Dict[str, int]:
    """Orchestrate Gold layer dimensions, facts, and marts."""
    results = {}

    with step(batch, "gold_dim_customer", "dim_customer") as res:
        cnt = build_dim_customer(batch)
        res.rows_written = cnt
        results["dim_customer"] = cnt

    with step(batch, "gold_dim_restaurant", "dim_restaurant") as res:
        cnt = build_dim_restaurant(batch)
        res.rows_written = cnt
        results["dim_restaurant"] = cnt

    with step(batch, "gold_fact_order", "fact_order") as res:
        cnt = build_fact_order(batch)
        res.rows_written = cnt
        results["fact_order"] = cnt

    with step(batch, "gold_fact_payment", "fact_payment") as res:
        cnt = build_fact_payment(batch)
        res.rows_written = cnt
        results["fact_payment"] = cnt

    with step(batch, "gold_marts", "marts") as res:
        rebuild_marts(batch)

    return results
