# Module docstring explaining purpose of configuration management for Zwiggy Medallion Data Warehouse
"""Configuration management for Zwiggy Medallion Data Warehouse."""

# Import dataclass decorator for immutable data containers
from dataclasses import dataclass
# Import os module for accessing environment variables
import os
# Import Path class for object-oriented filesystem paths
from pathlib import Path
# Import Optional type hint for variables that can be None
from typing import Optional
# Import load_dotenv to read key-value pairs from .env file into environment
from dotenv import load_dotenv

# Exception class raised when configuration is missing or invalid
class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""
    pass

# Dataclass storing connection parameters for a target database
@dataclass(frozen=True)
class DbTarget:
    """Database target credentials and connection configuration."""
    host: str # Database hostname or IP address
    port: int # Database port number (e.g., 5432)
    dbname: str # Database name
    user: str # Database connection username
    password: str # Database connection password

    # Method returning a safe string representation with password hidden
    def masked_repr(self) -> str:
        """Return human-readable connection string with password masked."""
        return f"postgresql://{self.user}:***@{self.host}:{self.port}/{self.dbname}"

    # Override standard string representation to call masked_repr for security
    def __repr__(self) -> str:
        return self.masked_repr()

# Settings class loading environment variables and config options
class Settings:
    """Settings loaded from environment variables and .env file."""

    # Constructor resolving environment variables and file search paths
    def __init__(self, env_file: Optional[str] = None):
        # List of potential paths to search for .env files
        paths_to_check = []
        # Check explicit env_file argument if provided
        if env_file:
            paths_to_check.append(Path(env_file))
        # Check ZWIGGY_ENV_FILE environment variable if set
        if os.getenv("ZWIGGY_ENV_FILE"):
            paths_to_check.append(Path(os.getenv("ZWIGGY_ENV_FILE")))
        
        # Determine root project directory path relative to this file
        root_dir = Path(__file__).resolve().parent.parent.parent
        # Add default candidate .env paths
        paths_to_check.extend([
            root_dir / ".env",
            root_dir.parent / ".env",
            Path(".env")
        ])

        # Loop through candidate paths and load the first existing .env file
        for p in paths_to_check:
            if p.exists():
                load_dotenv(dotenv_path=p, override=False)
                break

        # Load Source PostgreSQL DB credentials with sensible defaults
        self.pg_host = os.getenv("PG_HOST", "localhost")
        self.pg_port = int(os.getenv("PG_PORT", "5432"))
        self.pg_database = os.getenv("PG_DATABASE", "zwiggy_db")
        self.pg_user = os.getenv("PG_USER", "postgres")
        self.pg_password = os.getenv("PG_PASSWORD", "postgres")

        # Load Warehouse DB credentials (defaulting to source credentials if not separately configured)
        self.warehouse_host = os.getenv("WAREHOUSE_HOST", self.pg_host)
        self.warehouse_port = int(os.getenv("WAREHOUSE_PORT", str(self.pg_port)))
        self.warehouse_database = os.getenv("WAREHOUSE_DATABASE", self.pg_database)
        self.warehouse_user = os.getenv("WAREHOUSE_USER", self.pg_user)
        self.warehouse_password = os.getenv("WAREHOUSE_PASSWORD", self.pg_password)

        # Operational parameters for extraction and execution
        self.default_lookback_days = int(os.getenv("DEFAULT_LOOKBACK_DAYS", "7"))
        self.batch_size = int(os.getenv("BATCH_SIZE", "10000"))
        self.business_timezone = os.getenv("BUSINESS_TIMEZONE", "UTC")
        self.code_version = os.getenv("CODE_VERSION", "1.0.0")
        self.statement_timeout_ms = int(os.getenv("STATEMENT_TIMEOUT_MS", "60000"))

        # Resilience, retry limits, and anomaly block thresholds
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        self.retry_backoff_seconds = float(os.getenv("RETRY_BACKOFF_SECONDS", "2"))
        self.unknown_sk_block_threshold = float(os.getenv("UNKNOWN_SK_BLOCK_THRESHOLD", "0.05"))

        # Store directory paths for SQL script access
        self.root_dir = root_dir
        self.sql_dir = root_dir / "src" / "zwiggy_dwh" / "sql"

    # Property returning DbTarget object for source database
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

    # Property returning DbTarget object for warehouse database
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

# Internal global variable holding singleton instance of Settings
_settings_instance: Optional[Settings] = None

# Singleton function returning global Settings instance
def settings(reload: bool = False) -> Settings:
    """Singleton getter for Settings instance."""
    global _settings_instance
    # Instantiate Settings if not yet created or if reload flag is True
    if _settings_instance is None or reload:
        _settings_instance = Settings()
    return _settings_instance

