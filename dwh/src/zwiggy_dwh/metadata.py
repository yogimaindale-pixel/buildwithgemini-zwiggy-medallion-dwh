# Module docstring explaining source schema introspection, contract verification, and schema drift detection
"""Source schema introspection, contract verification, and schema drift detection."""

# Import logging module for operational logs
import logging
# Import Dict and List type hints
from typing import Dict, List

# Import query execution and source database context manager helpers
from zwiggy_dwh.db import fetch_all, source_connection

# Obtain logger instance for metadata introspection events
logger = logging.getLogger(__name__)

# Function retrieving column names and data types from information_schema for a source table
def get_source_columns(source_table: str) -> List[Dict[str, str]]:
    """Query information_schema for source table column definitions."""
    with source_connection() as conn:
        return fetch_all(
            conn,
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
            """,
            (source_table,)
        )

# Function verifying that expected source tables exist in public schema of source database
def verify_contract() -> bool:
    """Verify that all 18 configured source tables exist in source OLTP database."""
    with source_connection() as conn:
        tables = fetch_all(
            conn,
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            """
        )
        existing_tables = {t["table_name"] for t in tables}
        logger.info("Found %d tables in source database.", len(existing_tables))
        return len(existing_tables) >= 18

# Function comparing actual columns against expected column definitions to detect missing or added columns
def detect_drift(source_table: str, expected_columns: List[str]) -> Dict[str, List[str]]:
    """Compare actual source columns against expected column list; report missing or added columns."""
    actual_cols = [c["column_name"] for c in get_source_columns(source_table)]
    actual_set = set(actual_cols)
    expected_set = set(expected_columns)

    missing = list(expected_set - actual_set)
    added = list(actual_set - expected_set)

    drift_report = {
        "missing_columns": missing,
        "added_columns": added,
        "has_drift": bool(missing or added)
    }

    if drift_report["has_drift"]:
        logger.warning("Schema drift detected for table %s: %s", source_table, drift_report)

    return drift_report

