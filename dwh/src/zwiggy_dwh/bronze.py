# Module docstring explaining Bronze layer extraction and ingestion engine
"""Bronze layer extraction and ingestion engine."""

# Import dataclass for structuring extraction plans
from dataclasses import dataclass
# Import datetime, timedelta, and timezone for timestamp math during incremental extraction
from datetime import datetime, timedelta, timezone
# Import logging module for operational execution logs
import logging
# Import typing hints for dictionaries, lists, and optional parameters
from typing import Dict, List, Optional

# Import batch context manager, watermark utilities, database query execution, and metadata inspection helpers
from zwiggy_dwh.batch import Batch, advance_watermark, get_watermark, step
from zwiggy_dwh.db import execute_sql, fetch_all, fetch_one, source_connection, warehouse_connection
from zwiggy_dwh.metadata import get_source_columns

# Obtain logger instance for Bronze layer events
logger = logging.getLogger(__name__)

# Dataclass holding extraction predicate query string and target metadata
@dataclass
class ExtractionPlan:
    """Extraction predicate and plan metadata."""
    source_table: str # Name of the source OLTP table
    pattern: str # Extraction pattern code (e.g. 'E1', 'E2', 'E3')
    predicate: str # SQL WHERE clause predicate (e.g., "created_at > '2026-01-01'")
    watermark_column: Optional[str] # Column used for tracking watermark timestamp/ID
    new_watermark_val: Optional[str] # Updated watermark value to record after successful extraction

# Function creating bronze.br_<source_table> database table if not present
def bronze_table_ddl(source_table: str) -> None:
    """Dynamically generate and execute DDL for bronze.br_<source_table>."""
    # Fetch source column definitions from control metadata
    cols = get_source_columns(source_table)
    if not cols:
        logger.warning("No columns found for source table %s; skipping DDL generation.", source_table)
        return

    # Convert source columns to TEXT data types in Bronze layer to safely land raw data
    col_defs = [f'"{c["column_name"]}" TEXT' for c in cols]
    # Add audit metadata columns to track lineage and ingestion time
    col_defs.extend([
        "dw_batch_id BIGINT NOT NULL",
        "dw_ingest_ts_utc TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "dw_source_table VARCHAR(100) NOT NULL",
        "dw_extract_pattern VARCHAR(10) NOT NULL",
        "dw_row_number BIGSERIAL"
    ])

    # Construct DDL CREATE TABLE and INDEX statements
    ddl = f"""
    CREATE TABLE IF NOT EXISTS bronze.br_{source_table} (
        {", ".join(col_defs)}
    );
    CREATE INDEX IF NOT EXISTS idx_br_{source_table}_batch ON bronze.br_{source_table}(dw_batch_id);
    """
    # Execute DDL statement on warehouse database
    with warehouse_connection() as conn:
        execute_sql(conn, ddl)

# Function constructing the extraction SQL WHERE clause predicate based on pattern (E1-E5)
def build_extraction_plan(table_config: dict, force_full: bool, batch: Batch) -> ExtractionPlan:
    """Construct SQL extraction predicate based on table extraction pattern (E1–E5)."""
    table = table_config["source_table"]
    pattern = table_config["extraction_pattern"]
    wm_col = table_config["watermark_column"]
    lookback_days = table_config.get("lookback_days", 0) or 0

    # If force_full flag is set or pattern is snapshot (E3, E4, E5), select all rows (1=1)
    if force_full or pattern in ("E3", "E4", "E5"):
        return ExtractionPlan(
            source_table=table,
            pattern=pattern,
            predicate="1=1",
            watermark_column=wm_col,
            new_watermark_val=batch.cutoff.isoformat()
        )

    # Handle incremental extraction (E1 or E2)
    last_wm = get_watermark(table)
    if not last_wm or not last_wm.get("watermark_value"):
        # Initial run with no prior watermark: select all records up to cutoff timestamp
        return ExtractionPlan(
            source_table=table,
            pattern=pattern,
            predicate=f'"{wm_col}" <= \'{batch.cutoff.isoformat()}\'',
            watermark_column=wm_col,
            new_watermark_val=batch.cutoff.isoformat()
        )

    # Calculate lower bound with optional lookback window for safety against late-arriving data
    wm_val_str = last_wm["watermark_value"]
    if pattern == "E1" and wm_col and lookback_days > 0:
        try:
            wm_dt = datetime.fromisoformat(wm_val_str)
            lower_bound = (wm_dt - timedelta(days=lookback_days)).isoformat()
        except ValueError:
            lower_bound = wm_val_str
        predicate = f'"{wm_col}" > \'{lower_bound}\' AND "{wm_col}" <= \'{batch.cutoff.isoformat()}\''
    elif wm_col:
        predicate = f'"{wm_col}" > \'{wm_val_str}\''
    else:
        predicate = "1=1"

    return ExtractionPlan(
        source_table=table,
        pattern=pattern,
        predicate=predicate,
        watermark_column=wm_col,
        new_watermark_val=batch.cutoff.isoformat()
    )

# Function extracting raw rows from source OLTP database and appending to Bronze table
def load_table(table_config: dict, batch: Batch, force_full: bool = False) -> int:
    """Extract rows from source OLTP and append to bronze table."""
    source_table = table_config["source_table"]

    # 1. Ensure target Bronze table exists in warehouse schema
    bronze_table_ddl(source_table)

    # 2. Build extraction plan predicate
    plan = build_extraction_plan(table_config, force_full, batch)

    # 3. Query source database using read-only guarded connection
    query = f'SELECT * FROM public."{source_table}" WHERE {plan.predicate}'
    with source_connection() as src_conn:
        rows = fetch_all(src_conn, query)

    landed_count = len(rows)
    logger.info("Extracted %d rows from source %s (pattern=%s)", landed_count, source_table, plan.pattern)

    # 4. Append extracted rows into target Bronze table
    if rows:
        cols = list(rows[0].keys())
        target_cols = [f'"{c}"' for c in cols] + ["dw_batch_id", "dw_source_table", "dw_extract_pattern"]
        placeholders = ", ".join(["%s"] * len(target_cols))

        insert_sql = f"""
        INSERT INTO bronze.br_{source_table} ({", ".join(target_cols)})
        VALUES ({placeholders})
        """

        # Convert dictionary values to text strings and append audit column metadata
        records = [
            tuple(str(r[c]) if r[c] is not None else None for c in cols) + (batch.batch_id, source_table, plan.pattern)
            for r in rows
        ]

        # Execute bulk insert into warehouse Bronze table
        with warehouse_connection() as wh_conn:
            with wh_conn.cursor() as cur:
                cur.executemany(insert_sql, records)

    # 5. Record extraction details in control extract manifest table
    with warehouse_connection() as wh_conn:
        execute_sql(
            wh_conn,
            """
            INSERT INTO ctl.ctl_extract_manifest (dw_batch_id, source_table, pattern, extracted_rows, watermark_value)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (batch.batch_id, source_table, plan.pattern, landed_count, plan.new_watermark_val)
        )

    # 6. Advance watermark if extraction succeeded
    if plan.new_watermark_val:
        advance_watermark(batch, source_table, plan.new_watermark_val)

    return landed_count

# Master orchestrator function running Bronze layer extraction across all active source tables
def run_extract_and_bronze(batch: Batch, force_full: bool = False) -> Dict[str, int]:
    """Execute Bronze layer extraction for all active source tables."""
    # Fetch active table configuration records from control database
    with warehouse_connection() as conn:
        table_configs = fetch_all(conn, "SELECT * FROM ctl.ctl_table_config WHERE is_active = true ORDER BY source_table")

    results = {}
    # Iterate through configured active tables and process extraction
    for cfg in table_configs:
        table_name = cfg["source_table"]
        with step(batch, "bronze_load", table_name) as res:
            rows = load_table(cfg, batch, force_full)
            res.rows_read = rows
            res.rows_written = rows
            results[table_name] = rows

    return results

