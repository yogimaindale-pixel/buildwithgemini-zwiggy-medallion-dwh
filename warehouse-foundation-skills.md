---
skill_name: "Warehouse Foundation & Configuration"
agent_name: "Antigravity"
version: "1.0.0"
date_created: "2025-01-01"
skill_type: "infrastructure"
capability_domain: "data_warehouse_setup"
responsibility_level: "core"
---

# Warehouse Foundation & Configuration

## Overview

This skill owns the **complete setup, configuration, and foundational infrastructure** of the Zwiggy Medallion Data Warehouse. It is responsible for creating and maintaining a production-ready warehouse environment, establishing secure connectivity to the source OLTP system, configuring all operational metadata, and ensuring proper database initialization before any data movement occurs.

**Scope:** Warehouse initialization, schema creation, source connectivity, configuration management, database setup, credentials handling, environment configuration, and DDL generation.

**Status:** Core foundational layer—fully implemented and production-ready.

---

## Ownership Matrix

| Domain | Component | Files | Responsibility |
|--------|-----------|-------|-----------------|
| **Configuration** | Environment file parsing | `config.py` | Load and validate `.env` settings; externalize all secrets and tunable parameters |
| **Configuration** | Database targets | `config.py` (DbTarget dataclass) | Manage source and warehouse connection definitions with encryption/masking |
| **Connectivity** | Source connection | `db.py` (source_connection) | Open read-only, guarded source connections with statement timeout (X-3) |
| **Connectivity** | Warehouse connection | `db.py` (warehouse_connection) | Manage warehouse connections with auto-commit handling and retry logic |
| **Initialization** | Warehouse bootstrap | `init_db.py` (init_warehouse) | Create ctl/bronze/silver/gold schemas, all DDL, seeds, and indexes |
| **Initialization** | Schema creation | `init_db.py` + SQL files | Generate and execute DDL for all four schemas and their tables |
| **Initialization** | Reference data seeding | `sql/ctl/` + `sql/silver/` | Seed control tables (batch config, watermarks, DQ rules, reference mappings) |
| **Schema Design** | Control schema (ctl) | `sql/ctl/001-003.sql` | Batch state, watermarks, step logging, reconciliation results, DQ results |
| **Schema Design** | Bronze schema (br_*) | `bronze.py` + generated DDL | Raw, immutable, append-only tables with metadata columns (dw_*) |
| **Schema Design** | Silver schema (slv_*) | `sql/silver/` | Typed, conformed staging tables with quarantine siblings and reference tables |
| **Schema Design** | Gold schema (dim_*, fact_*, mart_*) | `sql/gold/` | Dimensional model: SCD2 dimensions, facts, marts, and semantic views |
| **Metadata** | Table configuration | `ctl.ctl_table_config` | Define extraction pattern, watermark column, lookback, load type per source table |
| **Metadata** | Watermark state | `ctl.ctl_watermark` | Track last-extracted value per table per batch; idempotency key |
| **Metadata** | Extract manifest | `ctl.ctl_extract_manifest` | Record row counts per table per batch for RC-1 validation |
| **Security** | Read-only source | `db.py` (source_connection) | Apply `SET default_transaction_read_only` to prevent any write to OLTP (X-3) |
| **Security** | Statement timeout | `config.py` + `db.py` | Enforce configurable timeout on source queries to prevent lock escalation (X-3) |
| **Resilience** | Retry logic | `db.py` (with_retry) | Exponential backoff for transient failures (connection loss, lock contention) |
| **Resilience** | Concurrent run prevention | `batch.py` (open_batch) | Refuse to start if another run is RUNNING; serialize one run at a time (§10.3) |
| **Observability** | Logging setup | `cli.py` (setup_logging) | Configure structured logging to stdout and file; format with batch ID and step name |

---

## Core Responsibilities

### 1. **Configuration Management (CD-1, CD-5, SEC-5)**

**What:** Read, validate, and expose configuration from the project-root `.env` file. All connection strings, timeouts, lookback windows, cohort boundaries, date ranges, and operational parameters must be externalised.

**How:**
- `config.py` reads `.env` (searched: `ZWIGGY_ENV_FILE`, `dwh/.env`, project root `.env`)
- Exports a frozen `settings()` singleton with all required and optional parameters
- Provides `DbTarget` dataclass for source and warehouse connections
- Masks sensitive values in logs and CLI output (password → `***`, etc.)

**Key Parameters:**
- Source: `PG_HOST`, `PG_PORT`, `PG_DATABASE`, `PG_USER`, `PG_PASSWORD`
- Warehouse: `WAREHOUSE_*` (or reuse source if not specified)
- Pipeline: `DEFAULT_LOOKBACK_DAYS` (default 7), `BATCH_SIZE` (default 10000), `BUSINESS_TIMEZONE`, `CODE_VERSION`
- Dates: `DATE_DIM_START`, `DATE_DIM_END`, `FISCAL_YEAR_START_MONTH` (Gold only)
- Thresholds: `ON_TIME_THRESHOLD_MINUTES`, `ACTIVE_CUSTOMER_WINDOW_DAYS`, `UNKNOWN_SK_BLOCK_THRESHOLD`
- Limits: `MAX_RETRIES`, `RETRY_BACKOFF_SECONDS`, statement timeout

**Outputs:**
- ✓ Validated, typed configuration object
- ✓ Connection parameters for source and warehouse
- ✓ Logging level and log directory path
- ✓ SQL and docs directories resolved
- ✓ Pipeline-tuning constants (batch size, lookback, cohort boundary, date ranges)

**Failures Detected:**
- Missing required credentials → raise `ConfigError`
- Malformed integers or booleans → raise `ConfigError`
- Missing `.env` file (if strict mode) → warning or error per caller

**Related Deliverables:** CD-1, CD-5, SEC-5

---

### 2. **Database Connectivity (X-3, CD-1)**

**What:** Establish secure, guarded connections to source (read-only) and warehouse (read/write). Apply session-level protections to prevent accidental writes to OLTP and runaway analytical queries.

**How:**
- `db.connect(DbTarget)` opens a psycopg2 connection
- `source_connection()` context manager applies `SET default_transaction_read_only = on` and statement timeout
- `warehouse_connection()` manages commit/rollback and optional autocommit
- `with_retry()` wraps transient failures (OperationalError, DeadlockDetected, LockNotAvailable, SerializationFailure) with exponential backoff

**Protections Applied:**
- **Source read-only:** Hard guarantee via `default_transaction_read_only = on`
- **Source timeout:** Configurable `statement_timeout_ms` (default 0 = no limit, override in `.env`)
- **Connection pooling:** No pooling; each context opens and closes explicitly (simple, audit-friendly)
- **Retry strategy:** Up to `MAX_RETRIES` attempts with delay `2^(attempt-1) * RETRY_BACKOFF_SECONDS`

**Outputs:**
- ✓ Open, guarded connection to source (READ-ONLY)
- ✓ Open, guarded connection to warehouse (READ/WRITE)
- ✓ Safe retry wrapper for transient failures
- ✓ Structured log messages for connection issues

**Failures Handled:**
- ✓ Source unreachable → caught by preflight check; blocks run
- ✓ Warehouse unreachable → caught during batch open; blocks run
- ✓ Transient lock/deadlock → retried with backoff; eventual success or timeout error
- ✓ Permanent auth failure → propagated immediately

**Related Deliverables:** X-3, CD-1, §4.4

---

### 3. **Warehouse Initialization (P-6, §15.5)**

**What:** Create a complete, empty warehouse from scratch: all four schemas, all tables and indexes, all reference data, all DQ rules, and all control plane metadata. Idempotent and safe to re-run.

**How:**
- `cli init` orchestrates the workflow
- `init_db.py:init_warehouse()` sequences the SQL files in dependency order:
  1. Drop existing schemas (if asked)
  2. Create `ctl` schema and tables (batch, watermarks, step logs, etc.)
  3. Create `bronze` schema and generate DDL for all 18 tables (from source shape)
  4. Create `silver` schema and load DQL for all 17 entities and reference tables
  5. Create `gold` schema and all dimensional/fact DDL
  6. Seed reference data: `ref_cohort_rule`, `ref_payment_method_map`, `dq_rule`, `ctl_table_config`
  7. Create all indexes and constraints
  8. Verify schema structure matches expected (counts, column names, etc.)

**SQL Files Executed (in order):**

| File | Responsibility |
|------|-----------------|
| `sql/ctl/001_create_schemas.sql` | Create `ctl`, `bronze`, `silver`, `gold` schemas |
| `sql/ctl/002_ctl_tables.sql` | Create `ctl_batch`, `ctl_step_log`, `ctl_watermark`, `ctl_extract_manifest`, `ctl_reconciliation`, `ctl_dq_result`, `ctl_table_config` |
| `sql/ctl/003_seed_table_config.sql` | Seed `ctl_table_config` (18 rows: extraction pattern, watermark column, lookback, expected rows) |
| `sql/silver/010_ref_tables.sql` | Create `ref_*` tables (reference dimensions, payment method map, cohort rule, DQ rule catalogue) |
| `sql/silver/011_seed_ref_data.sql` | Seed payment method mappings, cohort boundary, reference data |
| `sql/silver/012_seed_dq_rules.sql` | Seed `silver.dq_rule` (27 DQ rules with expressions, thresholds, severity) |
| `sql/silver/015_functions.sql` | Create PL/pgSQL functions for dedup logic, conformance, mask-on-read |
| `sql/silver/020_entity_ddl.sql` | Create all `slv_*` tables and quarantine siblings (17 entities + refs) |
| `sql/gold/001_functions.sql` | Create PL/pgSQL functions for SCD2, as-at resolution, mart aggregation |
| `sql/gold/010_dimension_ddl.sql` | Create all `dim_*` tables with SCD2 structure |
| `sql/gold/011_fact_ddl.sql` | Create all `fact_*` tables with grain and measures |
| `sql/gold/020_semantic_layer.sql` | Create views: `sem_trust_header`, `sem_dq_scorecard`, reporting-layer views |

**Outputs:**
- ✓ Four schemas: `ctl`, `bronze`, `silver`, `gold`
- ✓ 50+ tables with proper DDL and indexes
- ✓ 27 DQ rules seeded and active
- ✓ 18 source table configurations seeded
- ✓ Reference data (cohort, payment methods, etc.) seeded
- ✓ All functions and views created
- ✓ Baseline row counts logged for regression testing

**Idempotency:**
- All DDL uses `CREATE TABLE IF NOT EXISTS`
- All INSERTS use `ON CONFLICT ... DO NOTHING` or `DO UPDATE`
- Re-running `init` is safe; existing data in `ctl` is preserved unless `--reset` is used

**Related Deliverables:** P-6, §15.5

---

### 4. **Schema Design & DDL Generation**

**What:** Define the structure of the four medallion schemas and generate their DDL such that it is maintainable, documented, and auto-generated where possible (P-6, CS-2).

#### 4.1 Control Schema (`ctl`)

**Purpose:** Operational metadata and run state.

| Table | Rows per Run | Responsibility |
|-------|--------------|-----------------|
| `ctl_batch` | 1 | Run lifecycle: status (RUNNING, SUCCEEDED, FAILED, PUBLISH_BLOCKED), start/end times, batch ID, triggered-by, code version, notes |
| `ctl_step_log` | ~40 | Per-step execution: step name, target object, rows read/written/quarantined/rejected, duration, status, error text |
| `ctl_watermark` | 18 (incremental only) | Last-extracted value per table; idempotency key for E1/E2 patterns |
| `ctl_extract_manifest` | 18 | Row counts per table from Extract phase (for RC-1) |
| `ctl_reconciliation` | ~50 | Reconciliation check results (RC-1 through RC-10): expected vs actual, variance, verdict |
| `ctl_dq_result` | 50+ | Data quality rule results per rule per target object: rows evaluated/failed, verdict |
| `ctl_table_config` | 18 | Configuration: extraction pattern, watermark column, lookback days, load type, expected rows |

**Design Principles:**
- Immutable append-only (like Bronze) so audit trail is preserved
- Partitioned by `dw_batch_id` for quick lookups
- Readable and traceable by non-technical stakeholders

#### 4.2 Bronze Schema (`bronze.br_*`)

**Purpose:** Raw, immutable replay tape; immutable per-batch append-only.

**Design:**
- 18 tables (one per source table): `br_customer`, `br_order`, `br_payment`, etc.
- All source columns as `text` (permissive, no cast failures) (B-3, §5.3)
- Metadata columns appended: `dw_batch_id`, `dw_ingest_ts_utc`, `dw_source_table`, `dw_extract_pattern`, `dw_row_number`, `dw_raw_payload` (JSONB)
- Indexes: `(dw_batch_id)` for fast batch lookups, `(dw_ingest_date)` for partition pruning
- No PK (allow duplicates when re-extracted), no unique constraints

**DDL Generation:**
- Source schema introspection via `information_schema.columns`
- Dynamic DDL generation in `bronze.py:bronze_table_ddl()` (P-6, CS-2)
- Ensures Bronze DDL always matches source shape, no manual maintenance

#### 4.3 Silver Schema (`silver.slv_*`)

**Purpose:** Typed, conformed, deduplicated staging.

**Design:**
- 17 entity tables: `slv_customer`, `slv_order`, `slv_order_item`, `slv_payment`, `slv_delivery`, `slv_review`, etc.
- Quarantine siblings: `slv_customer_quarantine`, `slv_order_quarantine`, etc.
- Reference tables: `ref_cohort_rule`, `ref_payment_method_map`, `dq_rule`
- Columns: source business key + conformed columns + PII masked hash + `dw_*` metadata + `dw_is_deleted` flag
- Indexes: `(dw_batch_id)` for batch lookups, `(business_key)` for merge performance

**Type Safety & Conformance:**
- `customer_id::bigint`, `order_total::decimal(19,4)`, `order_date::date` (no casts at ingestion)
- Conformance via reference tables (e.g., `ref_payment_method_map` for status values)
- Conformance failures → quarantine + reason

#### 4.4 Gold Schema (`gold.dim_*, gold.fact_*, gold.mart_*`)

**Purpose:** Dimensional model, reporting-ready.

**Design:**
- **8 Dimensions (SCD2):** `dim_customer`, `dim_address`, `dim_restaurant`, `dim_menu_item`, `dim_delivery_partner`, `dim_restaurant_owner`, `dim_code`, `dim_order_flag`
- **8 Facts:** `fact_order`, `fact_order_item`, `fact_payment_attempt`, `fact_payment`, `fact_delivery`, `fact_review`, `fact_cart_item`, `fact_order_fulfilment`
- **3 Marts:** `mart_daily_business_summary`, `mart_daily_restaurant_performance`, `mart_daily_delivery_performance`
- **Semantic Views:** `sem_trust_header`, `sem_dq_scorecard`, `dim_*` (masked), `fact_*`, `mart_*`

**Dimension Structure (SCD2):**
- `*_sk` (surrogate key, `bigint`)
- `*_bk` (business key from Silver)
- Conformed dimension columns
- `valid_from`, `valid_to` (as-at resolution)
- `dw_is_current`, `dw_version` (SCD2 tracking)
- `dw_batch_id`, `dw_ingest_ts_utc`

**Fact Structure:**
- `*_sk` foreign keys to dimensions
- Measure columns (amounts, counts, flags)
- `_date`, `_time` surrogate keys
- `dw_batch_id`, `dw_ingest_ts_utc` (only for dimensions and facts, not SCD2 accumulators)

---

### 5. **Reference Data & Metadata Seeding**

**What:** Pre-populate metadata tables and reference dimensions so that the pipeline can operate without manual configuration.

**Tables Seeded:**

| Table | Purpose | Rows | Update Frequency |
|-------|---------|------|-------------------|
| `ctl_table_config` | Source table extraction config | 18 | Per schema change |
| `ref_cohort_rule` | Cohort boundary (order_id split) | 2 | Rare (stable for Cohort A/B) |
| `ref_payment_method_map` | Status conformance mappings | 10+ | Per source vocabulary change |
| `silver.dq_rule` | DQ rule catalogue | 27 | Per DQ rule addition |
| `dim_date` | Date dimension (2020–2030) | 3650+ | Once at init |
| `dim_time` | Time dimension (0:00–23:59 by minute) | 1440 | Once at init |
| `dim_code` | Static code dimensions | 1000+ | Per code table addition |

**Seeding Strategy:**
- `ctl_table_config`: Seeded once at init; represents the fixed structure
- `ref_*`: Seeded at init, updatable via manual `UPDATE` (data-driven approach, §9.1)
- `dq_rule`: Seeded at init with all 27 rules; disable via `is_active = false`

**Related Deliverables:** S-52, §9.1

---

### 6. **Database Resilience & Concurrency Control**

**What:** Prevent concurrent runs, detect half-committed batches, and lock the warehouse properly.

**Mechanisms:**
- **Concurrent run prevention:** `open_batch()` queries `ctl_batch` for any `RUNNING` status; raises `ConcurrentRunError` if found (§10.3)
- **Force-close:** `cli abandon-run --batch-id N` manually closes a stuck batch (after verifying no process is actually running)
- **Auto-rollback:** If a Python step raises an exception, `warehouse_connection()` rolls back the transaction unless autocommit is used
- **Idempotent re-run:** Because all Bronze/Silver/Gold operations are keyed by `dw_batch_id` and merge-based, re-running the same batch produces identical state (B-2, S-50)

---

## Handoff Points

### ✅ Provides to Pipeline Orchestration Skill:

1. **Validated Configuration** — All `.env` settings parsed and validated
2. **Open Warehouse Connection** — Guarded connection ready for reading/writing
3. **Initialized Warehouse** — All four schemas, tables, indexes, reference data
4. **Watermark Tables** — `ctl_watermark` and `ctl_table_config` ready for lookup
5. **Step Logging Infrastructure** — `ctl_step_log` table and `step()` context manager
6. **Batch Lifecycle Framework** — `open_batch()`, `close_batch()`, `mark_published()` functions
7. **Retry Wrapper** — `with_retry()` for resilience
8. **Logging Setup** — Structured logging to file and stdout
9. **Control Plane Readiness** — All control tables prepared and seeded

### ✅ Receives from Pipeline Orchestration Skill:

1. **Batch Lifecycle Events** — When a batch opens/closes, to log in `ctl_batch`
2. **Step Execution Results** — Rows read/written/failed, for logging in `ctl_step_log`
3. **Extraction Manifest** — Row counts from Extract phase, for logging in `ctl_extract_manifest`
4. **Watermark Advances** — New high-water-mark values after successful extract, to update `ctl_watermark`

---

## Implementation Files

### Core Python Modules
- **`dwh/src/zwiggy_dwh/config.py`** — Configuration reading, DbTarget, settings singleton
- **`dwh/src/zwiggy_dwh/db.py`** — Connection management, query runners, retry logic
- **`dwh/src/zwiggy_dwh/batch.py`** — Batch lifecycle, step logging, concurrent run prevention
- **`dwh/src/zwiggy_dwh/init_db.py`** — Warehouse initialization, reset, schema creation

### SQL Files (DDL & Seeds)
- **`dwh/sql/ctl/`** — Control plane DDL and seed scripts
  - `001_create_schemas.sql` — Schema creation
  - `002_ctl_tables.sql` — Control tables
  - `003_seed_table_config.sql` — Table configuration
- **`dwh/sql/silver/`** — Reference tables and seeds
  - `010_ref_tables.sql` — Reference dimension DDL
  - `011_seed_ref_data.sql` — Reference data
  - `012_seed_dq_rules.sql` — DQ rule seed
  - `015_functions.sql` — PL/pgSQL functions
  - `020_entity_ddl.sql` — Silver entity tables
- **`dwh/sql/gold/`** — Gold layer DDL
  - `001_functions.sql` — Gold PL/pgSQL functions
  - `010_dimension_ddl.sql` — Dimension table creation
  - `011_fact_ddl.sql` — Fact table creation
  - `020_semantic_layer.sql` — Views

### CLI Entry Point
- **`dwh/src/zwiggy_dwh/cli.py`** — `cmd_init()` and logging setup

---

## Usage & Commands

### Initialize a Warehouse (First Run)
```powershell
cd dwh
$env:PYTHONPATH = "$PWD\src"
python -m zwiggy_dwh.cli init
```

**Output:**
- All schemas created
- All tables and indexes created
- Reference data and DQ rules seeded
- Ready for first pipeline run

### Reset Warehouse (Destructive)
```powershell
python -m zwiggy_dwh.cli reset --yes
```

**Output:**
- All four schemas dropped
- Next `init` will recreate from scratch

### Verify Configuration
```powershell
python -c "from zwiggy_dwh.config import settings; s = settings(); print(f'Source: {s.source.masked()}'); print(f'Warehouse: {s.warehouse.masked()}')"
```

---

## Test Coverage

### Unit Tests (`tests/test_unit.py`)
- ✓ `TestStatementSplitter` — SQL statement parsing preserves strings, comments, dollar quotes
- ✓ `TestNamedParameters` — `:param` conversion doesn't break `::type` casts
- ✓ `TestCopyEscaping` — COPY format escaping for NULL, tabs, backslashes
- ✓ Configuration loading and validation

### Integration Tests (Pending)
- Warehouse initialization from scratch
- Source connectivity and read-only guarantee
- Watermark state management
- Batch lifecycle (open → close)
- Concurrent run prevention

---

## Error Handling & Recovery

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Missing `.env` | `ConfigError` raised | Provide `.env` with required credentials |
| Source unreachable | `preflight()` step fails | Verify source database is running and accessible |
| Warehouse unreachable | `open_batch()` raises `OperationalError` | Verify warehouse database is running |
| Timeout on source | `statement_timeout` fires | Increase `STATEMENT_TIMEOUT_MS` in `.env` or optimize query |
| Concurrent run | `open_batch()` raises `ConcurrentRunError` | Run `abandon-run --batch-id N` then retry |
| Stuck batch in RUNNING | Manual inspection of `ctl_batch` | Run `abandon-run --batch-id N` to force close |

---

## Traceability to BRD-B

| BRD-B §Section | Requirement | Implementation |
|---|---|---|
| §3.0 | Externalised configuration | `config.py` reads `.env` |
| §4.1 | Read-only source | `db.source_connection()` sets `default_transaction_read_only` |
| §4.4 | Connection guards | Statement timeout + read-only applied per `DbTarget` |
| §10.1 | Batch lifecycle | `batch.py`: `open_batch()`, `close_batch()`, `mark_published()` |
| §10.3 | Single run at a time | `open_batch()` checks `ctl_batch` for RUNNING status |
| §15.5 | Warehouse initialization | `init_db.py`: `init_warehouse()` orchestrates full setup |
| P-6 | Auto-generated DDL | `bronze.py`: `bronze_table_ddl()` generates from source schema |
| CD-1 | Configuration externalised | All tunable parameters in `.env` |
| CD-5 | Code version tracking | `ctl_batch.code_version` and `CONFIG.code_version` |
| SEC-5 | Credentials not in code | All passwords in `.env` (gitignored) |
| CS-2 | Auto-generated DDL | Bronze DDL from source introspection |
| CS-7 | Structured logging | `batch.py:log_step()` records counts and duration |
| X-3 | Runaway query protection | Source timeout + read-only on source connection |

---

## Success Criteria

✓ Warehouse initialization completes without error  
✓ All four schemas exist with correct table counts  
✓ `ctl_batch` and `ctl_watermark` are empty and ready  
✓ Reference data (27 DQ rules, 18 table configs) seeded  
✓ Source connection is read-only and guarded  
✓ Warehouse connection is open and writable  
✓ Step logging infrastructure ready  
✓ Logging configured to file and stdout  
✓ Configuration validated and no errors  
✓ `.env` is honored (not hardcoded credentials)  

---

## Related Skills

- **Pipeline Orchestration & Monitoring** — Consumes warehouse foundation; orchestrates extract → Bronze → Silver → Gold
- **Data Quality & Reconciliation** — Uses control plane tables for DQ rule execution and reconciliation checks

---

## References

- BRD-B: Business Requirements Document, Zwiggy Medallion Warehouse
- README.md: Project overview, quick start, key features
- RUNBOOK.md: Operational procedures for daily runs and troubleshooting
- `dwh/src/zwiggy_dwh/`: Core Python modules
- `dwh/sql/`: All DDL and transformation SQL

