"""Warehouse initialization script."""

from datetime import date, timedelta
import logging
from pathlib import Path

from zwiggy_dwh.config import settings
from zwiggy_dwh.db import execute_sql, fetch_scalar, warehouse_connection

logger = logging.getLogger(__name__)


def run_sql_file(file_path: Path) -> None:
    """Read and execute a SQL file against warehouse database."""
    logger.info("Executing SQL file: %s", file_path.name)
    with open(file_path, "r", encoding="utf-8") as f:
        sql = f.read()
    with warehouse_connection() as conn:
        execute_sql(conn, sql)


def seed_dim_date() -> None:
    """Populate dim_date dimension for 2020 through 2030 if empty."""
    with warehouse_connection() as conn:
        count = fetch_scalar(conn, "SELECT COUNT(*) FROM gold.dim_date WHERE date_sk <> -1")
        if count and count > 0:
            logger.info("dim_date already seeded (%d rows)", count)
            return

        logger.info("Seeding dim_date (2020-2030)...")
        start_date = date(2020, 1, 1)
        end_date = date(2030, 12, 31)
        curr = start_date

        while curr <= end_date:
            date_sk = int(curr.strftime("%Y%m%d"))
            year = curr.year
            quarter = (curr.month - 1) // 3 + 1
            month = curr.month
            day_of_month = curr.day
            day_of_week = curr.isoweekday() # 1=Mon, 7=Sun
            is_weekend = day_of_week in (6, 7)

            execute_sql(
                conn,
                """
                INSERT INTO gold.dim_date (date_sk, full_date, year, quarter, month, day_of_month, day_of_week, is_weekend)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (date_sk) DO NOTHING;
                """,
                (date_sk, curr, year, quarter, month, day_of_month, day_of_week, is_weekend)
            )
            curr += timedelta(days=1)


def seed_dim_time() -> None:
    """Populate dim_time dimension for all 1440 minutes of day if empty."""
    with warehouse_connection() as conn:
        count = fetch_scalar(conn, "SELECT COUNT(*) FROM gold.dim_time WHERE time_sk <> -1")
        if count and count > 0:
            logger.info("dim_time already seeded (%d rows)", count)
            return

        logger.info("Seeding dim_time (1440 minutes)...")
        for hour in range(24):
            for minute in range(60):
                time_sk = hour * 100 + minute
                execute_sql(
                    conn,
                    """
                    INSERT INTO gold.dim_time (time_sk, hour, minute)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (time_sk) DO NOTHING;
                    """,
                    (time_sk, hour, minute)
                )


def init_warehouse() -> None:
    """Run full warehouse initialization sequence."""
    s = settings()
    sql_base = s.sql_dir

    sequence = [
        sql_base / "ctl" / "001_create_schemas.sql",
        sql_base / "ctl" / "002_ctl_tables.sql",
        sql_base / "ctl" / "003_seed_table_config.sql",
        sql_base / "silver" / "010_ref_tables.sql",
        sql_base / "silver" / "011_seed_ref_data.sql",
        sql_base / "silver" / "012_seed_dq_rules.sql",
        sql_base / "silver" / "015_functions.sql",
        sql_base / "silver" / "020_entity_ddl.sql",
        sql_base / "gold" / "001_functions.sql",
        sql_base / "gold" / "010_dimension_ddl.sql",
        sql_base / "gold" / "011_fact_ddl.sql",
        sql_base / "gold" / "020_semantic_layer.sql",
    ]

    logger.info("Starting warehouse initialization sequence...")
    for file_path in sequence:
        run_sql_file(file_path)

    # Seed static date/time dimensions
    seed_dim_date()
    seed_dim_time()

    logger.info("✓ Warehouse initialization completed successfully.")
