# Module docstring explaining batch lifecycle management, watermarking, and step execution logging
"""Batch lifecycle management, watermarking, and step logging."""

# Import contextmanager decorator to wrap pipeline step logging logic
from contextlib import contextmanager
# Import dataclass and field helpers for structured metric object definition
from dataclasses import dataclass, field
# Import datetime and timezone for timestamp management
from datetime import datetime, timezone
# Import logging module for operational logs
import logging
# Import time module for measuring step duration in milliseconds
import time
# Import typing hints for generator types and optional parameters
from typing import Generator, Optional

# Import configuration settings and database connection/query helpers
from zwiggy_dwh.config import settings
from zwiggy_dwh.db import execute_sql, fetch_one, fetch_scalar, warehouse_connection

# Obtain logger for batch management events
logger = logging.getLogger(__name__)

# Custom exception class raised when a batch execution is attempted while another is RUNNING
class ConcurrentRunError(Exception):
    """Raised when attempting to open a batch while another batch is RUNNING."""
    pass

# Dataclass representing an active data pipeline batch execution instance
@dataclass
class Batch:
    """Represents an active data pipeline batch execution."""
    batch_id: int # Unique database identifier for the batch (ctl_batch.dw_batch_id)
    run_type: str # Type of pipeline execution ('FULL', 'INCREMENTAL', 'REPLAY')
    cutoff: datetime # Upper boundary cutoff timestamp for incremental extraction
    start_ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc)) # Execution start timestamp

# Dataclass collecting metrics for a single pipeline step execution
@dataclass
class StepResult:
    """Collector for step execution metrics."""
    step_name: str # Name of the step (e.g., 'Bronze_Extract_Orders')
    target_object: Optional[str] = None # Target table or schema object name
    rows_read: int = 0 # Number of source rows read/extracted
    rows_written: int = 0 # Number of target rows inserted/updated
    rows_quarantined: int = 0 # Number of malformed rows sent to quarantine
    rows_rejected: int = 0 # Number of rows rejected by business rules
    status: str = "SUCCEEDED" # Step execution status ('SUCCEEDED' or 'FAILED')
    error_text: Optional[str] = None # Error message string if step failed

# Function opening a new batch in ctl.ctl_batch table; enforces single-concurrency rule
def open_batch(run_type: str = "INCREMENTAL", cutoff: Optional[datetime] = None) -> Batch:
    """Open new pipeline batch in ctl_batch table; prevents concurrent runs."""
    # Retrieve configuration settings singleton
    s = settings()
    # Use provided cutoff timestamp or default to current UTC timestamp
    effective_cutoff = cutoff or datetime.now(timezone.utc)

    with warehouse_connection() as conn:
        # Check for any active batch currently in 'RUNNING' status
        running_batch = fetch_scalar(conn, "SELECT dw_batch_id FROM ctl.ctl_batch WHERE status = 'RUNNING' LIMIT 1")
        if running_batch is not None:
            # Raise exception if another batch is running to prevent concurrency issues
            raise ConcurrentRunError(f"Cannot start batch: Batch ID {running_batch} is currently RUNNING.")

        # Insert new record into control batch table and return generated dw_batch_id
        batch_id = fetch_scalar(
            conn,
            """
            INSERT INTO ctl.ctl_batch (run_type, cutoff_ts_utc, code_version, status, start_ts_utc)
            VALUES (%s, %s, %s, 'RUNNING', now())
            RETURNING dw_batch_id
            """,
            (run_type, effective_cutoff, s.code_version)
        )
        logger.info("Opened batch ID %d (type=%s, cutoff=%s)", batch_id, run_type, effective_cutoff)
        # Return initialized Batch object
        return Batch(batch_id=batch_id, run_type=run_type, cutoff=effective_cutoff)

# Function closing an active batch and updating final status and notes
def close_batch(batch: Batch, status: str, notes: Optional[str] = None) -> None:
    """Close active batch updating status and end timestamp."""
    with warehouse_connection() as conn:
        execute_sql(
            conn,
            """
            UPDATE ctl.ctl_batch
            SET status = %s, end_ts_utc = now(), notes = %s
            WHERE dw_batch_id = %s
            """,
            (status, notes, batch.batch_id)
        )
    logger.info("Closed batch ID %d with status %s", batch.batch_id, status)

# Function toggling the published flag for a batch in ctl.ctl_batch
def mark_published(batch: Batch, published: bool = True) -> None:
    """Flip published flag in ctl_batch."""
    with warehouse_connection() as conn:
        execute_sql(
            conn,
            "UPDATE ctl.ctl_batch SET published = %s WHERE dw_batch_id = %s",
            (published, batch.batch_id)
        )
    logger.info("Marked batch ID %d published=%s", batch.batch_id, published)

# Context manager measuring step execution duration and inserting audit metric record into ctl_step_log
@contextmanager
def step(batch: Batch, step_name: str, target_object: Optional[str] = None) -> Generator[StepResult, None, None]:
    """Wrap step execution, calculating duration and logging to ctl_step_log."""
    # Instantiate StepResult collector object
    res = StepResult(step_name=step_name, target_object=target_object)
    # Record wall-clock start time
    start_time = time.time()
    try:
        # Yield StepResult to caller for metric tracking
        yield res
    except Exception as e:
        # On failure, mark status as FAILED and capture exception error string
        res.status = "FAILED"
        res.error_text = str(e)
        logger.error("Step '%s' (%s) failed: %s", step_name, target_object, e)
        raise
    finally:
        # Calculate step duration in milliseconds
        duration_ms = int((time.time() - start_time) * 1000)
        try:
            # Insert audit record into control step log table
            with warehouse_connection() as conn:
                execute_sql(
                    conn,
                    """
                    INSERT INTO ctl.ctl_step_log (
                        dw_batch_id, step_name, target_object, rows_read, rows_written,
                        rows_quarantined, rows_rejected, duration_ms, status, error_text
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        batch.batch_id, res.step_name, res.target_object,
                        res.rows_read, res.rows_written, res.rows_quarantined,
                        res.rows_rejected, duration_ms, res.status, res.error_text
                    )
                )
        except Exception as log_err:
            # Log error if step log insertion fails to avoid masking primary exception
            logger.error("Failed to insert step log for step '%s': %s", step_name, log_err)

# Function fetching the most recent watermark record for a source table
def get_watermark(source_table: str) -> Optional[dict]:
    """Get last updated watermark for a source table."""
    with warehouse_connection() as conn:
        return fetch_one(
            conn,
            """
            SELECT source_table, watermark_value, updated_ts_utc
            FROM ctl.ctl_watermark
            WHERE source_table = %s
            ORDER BY updated_ts_utc DESC LIMIT 1
            """,
            (source_table,)
        )

# Function inserting an advanced watermark record for a source table
def advance_watermark(batch: Batch, source_table: str, watermark_value: str) -> None:
    """Record advanced watermark for a source table."""
    with warehouse_connection() as conn:
        execute_sql(
            conn,
            """
            INSERT INTO ctl.ctl_watermark (dw_batch_id, source_table, watermark_value, updated_ts_utc)
            VALUES (%s, %s, %s, now())
            """,
            (batch.batch_id, source_table, str(watermark_value))
        )
    logger.debug("Advanced watermark for table %s to %s (batch %d)", source_table, watermark_value, batch.batch_id)

