"""Database connectivity and connection management for Zwiggy Medallion Data Warehouse."""

from contextlib import contextmanager
import logging
import time
from typing import Any, Callable, Generator, List, Optional, Tuple, TypeVar
import psycopg2
from psycopg2 import errors
from psycopg2.extras import RealDictCursor

from zwiggy_dwh.config import DbTarget, settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


def connect(target: DbTarget) -> psycopg2.extensions.connection:
    """Establish connection to PostgreSQL using target parameters."""
    return psycopg2.connect(
        host=target.host,
        port=target.port,
        dbname=target.dbname,
        user=target.user,
        password=target.password
    )


def with_retry(
    func: Callable[..., T],
    max_retries: Optional[int] = None,
    backoff: Optional[float] = None
) -> T:
    """Execute function with exponential backoff for transient DB errors."""
    s = settings()
    retries = max_retries if max_retries is not None else s.max_retries
    delay = backoff if backoff is not None else s.retry_backoff_seconds

    transient_errors = (
        psycopg2.OperationalError,
        errors.DeadlockDetected,
        errors.LockNotAvailable,
        errors.SerializationFailure,
    )

    attempt = 0
    while True:
        try:
            return func()
        except transient_errors as e:
            attempt += 1
            if attempt > retries:
                logger.error("Max retries (%d) exceeded. Last error: %s", retries, e)
                raise
            sleep_time = delay * (2 ** (attempt - 1))
            logger.warning("Transient DB error (%s). Retrying in %.2fs (attempt %d/%d)...", e, sleep_time, attempt, retries)
            time.sleep(sleep_time)


@contextmanager
def source_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """Context manager for source database (read-only guarded connection)."""
    s = settings()
    conn = connect(s.source_target)
    try:
        with conn.cursor() as cur:
            cur.execute("SET default_transaction_read_only = on;")
            if s.statement_timeout_ms > 0:
                cur.execute("SET statement_timeout = %s;", (s.statement_timeout_ms,))
        conn.commit()
        yield conn
    finally:
        conn.close()


@contextmanager
def warehouse_connection(autocommit: bool = False) -> Generator[psycopg2.extensions.connection, None, None]:
    """Context manager for warehouse database (read/write connection)."""
    s = settings()
    conn = connect(s.warehouse_target)
    if autocommit:
        conn.autocommit = True
    try:
        yield conn
        if not autocommit:
            conn.commit()
    except Exception:
        if not autocommit:
            conn.rollback()
        raise
    finally:
        conn.close()


def execute_sql(conn: psycopg2.extensions.connection, query: str, params: Optional[Tuple[Any, ...]] = None) -> int:
    """Execute SQL statement and return rowcount."""
    with conn.cursor() as cur:
        cur.execute(query, params)
        return cur.rowcount


def fetch_all(conn: psycopg2.extensions.connection, query: str, params: Optional[Tuple[Any, ...]] = None) -> List[dict]:
    """Execute SQL query and return all rows as dictionaries."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]


def fetch_one(conn: psycopg2.extensions.connection, query: str, params: Optional[Tuple[Any, ...]] = None) -> Optional[dict]:
    """Execute SQL query and return single row as dictionary."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        row = cur.fetchone()
        return dict(row) if row else None


def fetch_scalar(conn: psycopg2.extensions.connection, query: str, params: Optional[Tuple[Any, ...]] = None) -> Any:
    """Execute SQL query and return first column of first row."""
    with conn.cursor() as cur:
        cur.execute(query, params)
        row = cur.fetchone()
        return row[0] if row else None
