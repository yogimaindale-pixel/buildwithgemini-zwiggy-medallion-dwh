"""Configuration management for Zwiggy Medallion Data Warehouse."""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""
    pass


@dataclass(frozen=True)
class DbTarget:
    """Database target credentials and connection configuration."""
    host: str
    port: int
    dbname: str
    user: str
    password: str

    def masked_repr(self) -> str:
        """Return human-readable connection string with password masked."""
        return f"postgresql://{self.user}:***@{self.host}:{self.port}/{self.dbname}"

    def __repr__(self) -> str:
        return self.masked_repr()


class Settings:
    """Settings loaded from environment variables and .env file."""

    def __init__(self, env_file: Optional[str] = None):
        # Resolve search path for .env file
        paths_to_check = []
        if env_file:
            paths_to_check.append(Path(env_file))
        if os.getenv("ZWIGGY_ENV_FILE"):
            paths_to_check.append(Path(os.getenv("ZWIGGY_ENV_FILE")))
        
        root_dir = Path(__file__).resolve().parent.parent.parent
        paths_to_check.extend([
            root_dir / ".env",
            root_dir.parent / ".env",
            Path(".env")
        ])

        for p in paths_to_check:
            if p.exists():
                load_dotenv(dotenv_path=p, override=False)
                break

        # Load Source DB credentials
        self.pg_host = os.getenv("PG_HOST", "localhost")
        self.pg_port = int(os.getenv("PG_PORT", "5432"))
        self.pg_database = os.getenv("PG_DATABASE", "zwiggy_db")
        self.pg_user = os.getenv("PG_USER", "postgres")
        self.pg_password = os.getenv("PG_PASSWORD", "postgres")

        # Load Warehouse DB credentials (default to source credentials if missing)
        self.warehouse_host = os.getenv("WAREHOUSE_HOST", self.pg_host)
        self.warehouse_port = int(os.getenv("WAREHOUSE_PORT", str(self.pg_port)))
        self.warehouse_database = os.getenv("WAREHOUSE_DATABASE", self.pg_database)
        self.warehouse_user = os.getenv("WAREHOUSE_USER", self.pg_user)
        self.warehouse_password = os.getenv("WAREHOUSE_PASSWORD", self.pg_password)

        # Operational Parameters
        self.default_lookback_days = int(os.getenv("DEFAULT_LOOKBACK_DAYS", "7"))
        self.batch_size = int(os.getenv("BATCH_SIZE", "10000"))
        self.business_timezone = os.getenv("BUSINESS_TIMEZONE", "UTC")
        self.code_version = os.getenv("CODE_VERSION", "1.0.0")
        self.statement_timeout_ms = int(os.getenv("STATEMENT_TIMEOUT_MS", "60000"))

        # Resilience & Thresholds
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        self.retry_backoff_seconds = float(os.getenv("RETRY_BACKOFF_SECONDS", "2"))
        self.unknown_sk_block_threshold = float(os.getenv("UNKNOWN_SK_BLOCK_THRESHOLD", "0.05"))

        # Path helper
        self.root_dir = root_dir
        self.sql_dir = root_dir / "src" / "zwiggy_dwh" / "sql"

    @property
    def source_target(self) -> DbTarget:
        """Get DbTarget for source database."""
        return DbTarget(
            host=self.pg_host,
            port=self.pg_port,
            dbname=self.pg_database,
            user=self.pg_user,
            password=self.pg_password
        )

    @property
    def warehouse_target(self) -> DbTarget:
        """Get DbTarget for warehouse database."""
        return DbTarget(
            host=self.warehouse_host,
            port=self.warehouse_port,
            dbname=self.warehouse_database,
            user=self.warehouse_user,
            password=self.warehouse_password
        )


_settings_instance: Optional[Settings] = None


def settings(reload: bool = False) -> Settings:
    """Singleton getter for Settings instance."""
    global _settings_instance
    if _settings_instance is None or reload:
        _settings_instance = Settings()
    return _settings_instance
