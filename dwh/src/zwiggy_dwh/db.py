# Module docstring explaining purpose of database connectivity and connection management
"""Database connectivity and connection management for Zwiggy Medallion Data Warehouse."""

# Import contextmanager decorator for creating python context managers with yield
from contextlib import contextmanager
# Import logging for recording database operations and retry warnings
import logging
# Import time module for handling retry backoff sleep intervals
import time
# Import typing hints for function signatures, generics, and return types
from typing import Any, Callable, Generator, List, Optional, Tuple, TypeVar
# Import psycopg2 PostgreSQL driver library
import psycopg2
# Import psycopg2 error objects for granular exception catching
from psycopg2 import errors
# Import RealDictCursor to return query results as dictionaries instead of tuples
from psycopg2.extras import RealDictCursor

# Import DbTarget container class and settings getter
from zwiggy_dwh.config import DbTarget, settings

# Obtain logger instance for database events
logger = logging.getLogger(__name__)

# Type variable definition for generic return type in decorator/retry functions
T = TypeVar("T")

# Function establishing a low-level psycopg2 connection to PostgreSQL
def connect(target: DbTarget) -> psycopg2.extensions.connection:
    """Establish connection to PostgreSQL using target parameters."""
    return psycopg2.connect(
        host=target.host, # Host address
        port=target.port, # Port number
        dbname=target.dbname, # Database name
        user=target.user, # Username
        password=target.password # Password
    )

# Wrapper function executing an operation with exponential backoff for transient DB errors
def with_retry(
    func: Callable[..., T], # The function to attempt
    max_retries: Optional[int] = None, # Maximum number of retry attempts
    backoff: Optional[float] = None # Base backoff delay in seconds
) -> T: # Returns generic result type T
    """Execute function with exponential backoff for transient DB errors."""
    # Retrieve current configuration settings instance
    s = settings()
    # Resolve maximum retries count from parameter or settings default
    retries = max_retries if max_retries is not None else s.max_retries
    # Resolve base backoff delay from parameter or settings default
    delay = backoff if backoff is not None else s.retry_backoff_seconds

    # Tuple of transient error classes eligible for retry logic
    transient_errors = (
        psycopg2.OperationalError,
        errors.DeadlockDetected,
        errors.LockNotAvailable,
        errors.SerializationFailure,
    )

    # Initialize attempt counter
    attempt = 0
    # Retry loop
    while True:
        try:
            # Attempt function execution
            return func()
        except transient_errors as e:
            # Increment attempt counter on transient failure
            attempt += 1
            # If attempt exceeds max retries, log error and re-raise exception
            if attempt > retries:
                logger.error("Max retries (%d) exceeded. Last error: %s", retries, e)
                raise
            # Calculate exponential backoff sleep duration: delay * 2^(attempt - 1)
            sleep_time = delay * (2 ** (attempt - 1))
            logger.warning("Transient DB error (%s). Retrying in %.2fs (attempt %d/%d)...", e, sleep_time, attempt, retries)
            # Sleep before next attempt
            time.sleep(sleep_time)

# Context manager providing guarded read-only connection to source database
@contextmanager
def source_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """Context manager for source database (read-only guarded connection)."""
    s = settings()
    # Open connection to source database
    conn = connect(s.source_target)
    try:
        # Enforce read-only mode and statement timeout on connection session
        with conn.cursor() as cur:
            cur.execute("SET default_transaction_read_only = on;")
            if s.statement_timeout_ms > 0:
                cur.execute("SET statement_timeout = %s;", (s.statement_timeout_ms,))
        # Commit session settings
        conn.commit()
        # Yield connection to calling block
        yield conn
    finally:
        # Guarantee connection is closed upon exit
        conn.close()

# Context manager providing read/write connection to target warehouse database
@contextmanager
def warehouse_connection(autocommit: bool = False) -> Generator[psycopg2.extensions.connection, None, None]:
    """Context manager for warehouse database (read/write connection)."""
    s = settings()
    # Open connection to warehouse database
    conn = connect(s.warehouse_target)
    # Enable autocommit mode if requested
    if autocommit:
        conn.autocommit = True
    try:
        # Yield connection to caller
        yield conn
        # Automatically commit transaction if not in autocommit mode
        if not autocommit:
            conn.commit()
    except Exception:
        # Automatically rollback transaction on error if not in autocommit mode
        if not autocommit:
            conn.rollback()
        raise
    finally:
        # Guarantee connection is closed upon exit
        conn.close()

# Utility function executing DML/DDL statement and returning affected rowcount
def execute_sql(conn: psycopg2.extensions.connection, query: str, params: Optional[Tuple[Any, ...]] = None) -> int:
    """Execute SQL statement and return rowcount."""
    with conn.cursor() as cur:
        cur.execute(query, params)
        return cur.rowcount

# Utility function executing query and returning all rows as list of dictionaries
def fetch_all(conn: psycopg2.extensions.connection, query: str, params: Optional[Tuple[Any, ...]] = None) -> List[dict]:
    """Execute SQL query and return all rows as dictionaries."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]

# Utility function executing query and returning single row as dictionary or None
def fetch_one(conn: psycopg2.extensions.connection, query: str, params: Optional[Tuple[Any, ...]] = None) -> Optional[dict]:
    """Execute SQL query and return single row as dictionary."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        row = cur.fetchone()
        return dict(row) if row else None

# Utility function executing query and returning first column of first row
def fetch_scalar(conn: psycopg2.extensions.connection, query: str, params: Optional[Tuple[Any, ...]] = None) -> Any:
    """Execute SQL query and return first column of first row."""
    with conn.cursor() as cur:
        cur.execute(query, params)
        row = cur.fetchone()
        return row[0] if row else None

