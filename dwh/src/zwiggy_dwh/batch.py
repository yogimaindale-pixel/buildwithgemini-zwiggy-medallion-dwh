"""Batch lifecycle management, watermarking, and step logging."""

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import time
from typing import Generator, Optional

from zwiggy_dwh.config import settings
from zwiggy_dwh.db import execute_sql, fetch_one, fetch_scalar, warehouse_connection

logger = logging.getLogger(__name__)


class ConcurrentRunError(Exception):
    """Raised when attempting to open a batch while another batch is RUNNING."""
    pass


@dataclass
class Batch:
    """Represents an active data pipeline batch execution."""
    batch_id: int
    run_type: str
    cutoff: datetime
    start_ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class StepResult:
    """Collector for step execution metrics."""
    step_name: str
    target_object: Optional[str] = None
    rows_read: int = 0
    rows_written: int = 0
    rows_quarantined: int = 0
    rows_rejected: int = 0
    status: str = "SUCCEEDED"
    error_text: Optional[str] = None


def open_batch(run_type: str = "INCREMENTAL", cutoff: Optional[datetime] = None) -> Batch:
    """Open new pipeline batch in ctl_batch table; prevents concurrent runs."""
    s = settings()
    effective_cutoff = cutoff or datetime.now(timezone.utc)

    with warehouse_connection() as conn:
        # Check for any existing batch currently marked RUNNING
        running_batch = fetch_scalar(conn, "SELECT dw_batch_id FROM ctl.ctl_batch WHERE status = 'RUNNING' LIMIT 1")
        if running_batch is not None:
            raise ConcurrentRunError(f"Cannot start batch: Batch ID {running_batch} is currently RUNNING.")

        # Create new batch record
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
        return Batch(batch_id=batch_id, run_type=run_type, cutoff=effective_cutoff)


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


def mark_published(batch: Batch, published: bool = True) -> None:
    """Flip published flag in ctl_batch."""
    with warehouse_connection() as conn:
        execute_sql(
            conn,
            "UPDATE ctl.ctl_batch SET published = %s WHERE dw_batch_id = %s",
            (published, batch.batch_id)
        )
    logger.info("Marked batch ID %d published=%s", batch.batch_id, published)


@contextmanager
def step(batch: Batch, step_name: str, target_object: Optional[str] = None) -> Generator[StepResult, None, None]:
    """Wrap step execution, calculating duration and logging to ctl_step_log."""
    res = StepResult(step_name=step_name, target_object=target_object)
    start_time = time.time()
    try:
        yield res
    except Exception as e:
        res.status = "FAILED"
        res.error_text = str(e)
        logger.error("Step '%s' (%s) failed: %s", step_name, target_object, e)
        raise
    finally:
        duration_ms = int((time.time() - start_time) * 1000)
        try:
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
            logger.error("Failed to insert step log for step '%s': %s", step_name, log_err)


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
