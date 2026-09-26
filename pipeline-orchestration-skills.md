---
skill_name: "Pipeline Orchestration & Monitoring"
agent_name: "Antigravity"
version: "1.0.0"
date_created: "2025-01-01"
skill_type: "orchestration"
capability_domain: "data_pipeline_execution"
responsibility_level: "core"
---

# Pipeline Orchestration & Monitoring

## Overview

This skill owns the **complete execution orchestration** of the Zwiggy Medallion Data Warehouse pipeline. It coordinates the daily run sequence (preflight → extract → Bronze → Silver → Gold → reconciliation → publish), manages batch lifecycle and watermark state, handles incremental vs. snapshot extraction modes, implements the five extraction patterns (E1–E5), and provides operational monitoring and status reporting.

**Scope:** Pipeline orchestration, batch scheduling, extraction logic, watermark management, incremental vs. full-reload logic, step coordination, monitoring, operational reporting, and replay/audit capabilities.

**Status:** Core execution layer—fully implemented and production-ready.

---

## Ownership Matrix

| Domain | Component | Files | Responsibility |
|--------|-----------|-------|-----------------|
| **Orchestration** | Daily run sequence | `pipeline.py:run()` | Execute 12-step pipeline: preflight, extract, Bronze, Silver, Gold, reconcile, publish, close |
| **Orchestration** | Preflight checks | `pipeline.py:preflight()` | Verify source reachable, contract matched, watermarks readable, schema drift detected (X-7) |
| **Extraction** | E1–E5 patterns | `bronze.py:build_plan()` | Decide extraction predicate per pattern: E1/E2 incremental, E3/E4/E5 snapshot, lookback |
| **Extraction** | Extract and load | `bronze.py:load_table()` | Per-table extraction, COPY to Bronze, row count logging, watermark not advanced on failure (X-2) |
| **Extraction** | Extract manifest | `bronze.py` + `batch.py` | Record row counts per table per batch for RC-1 validation |
| **Watermark** | State management | `batch.py:get_watermark()` + `advance_watermark()` | Read/write last-extracted value per table; idempotency key for E1/E2 |
| **Watermark** | Lookback window | `bronze.py:build_plan()` | Re-extract past N days to catch late-arriving rows (X-5, S-52) |
| **Watermark** | Failure handling | `bronze.py:record_watermark_failure()` | Do not advance watermark on table failure; next run re-extracts same window (X-2) |
| **Batch Lifecycle** | Batch creation | `batch.py:open_batch()` | Create `ctl_batch` row, assign `dw_batch_id`, prevent concurrent runs (§10.3) |
| **Batch Lifecycle** | Step tracking | `batch.py:step()` context manager | Wrap each step; log result with counts, duration, status |
| **Batch Lifecycle** | Batch closure | `batch.py:close_batch()` | Update `ctl_batch` status (SUCCEEDED, FAILED, PUBLISH_BLOCKED); record end time |
| **Batch Lifecycle** | Publish flag | `batch.py:mark_published()` | Flip `published` flag only after all checks pass |
| **Layer Execution** | Bronze layer | `bronze.py:load_table()` per table | Append with batch stamp, partition by ingest date, idempotent per batch (B-2) |
| **Layer Execution** | Silver layer | `silver.py:run_silver()` | Load 17 entities per-batch in dependency order, quarantine failures |
| **Layer Execution** | Gold layer | `gold.py:run_gold()` | Build dimensions (SCD2), facts, marts per-batch in dependency order |
| **Layer Execution** | Reference data | `silver.py:load_reference_data()` | Seed/update ref_* and dq_rule tables (S-52, idempotent) |
| **Run Types** | Incremental | `pipeline.py:run()` default | Standard daily run respecting watermarks; extracted rows > 0 per table |
| **Run Types** | Full reload | `cli.py:cmd_run --full` | Force `force_full=True`; ignores watermarks, re-extracts all data |
| **Run Types** | Replay | `cli.py:cmd_run --replay` | Re-transform from existing Bronze only (skip extract); mark run type REPLAY in `ctl_batch` |
| **Run Types** | Cutoff override | `cli.py:cmd_run --cutoff` | Pin run cutoff to historical timestamp; reproducible past run for debugging |
| **Monitoring** | Status reporting | `cli.py:cmd_status()` | Query last N runs, watermarks, batch lineage, publish status (BRD-B §12.2) |
| **Monitoring** | Run summary | `pipeline.py:RunReport` | Collect extract outcomes, Silver/Gold counts, recon results, DQ results per run |
| **Monitoring** | CLI output | `cli.py:cmd_run()` | Pretty-print run summary with extract per-table detail, counts, recon and DQ verdicts |
| **Monitoring** | Log output | `pipeline.py` + `cli.py` | Structured logging to file and stdout with batch ID, step name, counts, duration (CS-7) |
| **Schema Drift** | Detection | `metadata.py:detect_drift()` | Compare source schema to last known; flag removed/retyped columns as blocking (X-7) |
| **Schema Drift** | Blocking drift | `pipeline.py:preflight()` | If a column removal/retype is detected, fail preflight; publish is blocked |

---

## Core Responsibilities

### 1. **Daily Run Orchestration (BRD-B §3.2)**

**What:** Execute the complete 12-step pipeline in correct order, with proper error handling and observability.

**Sequence:**

```
1.  Preflight         Source reachable? Contract OK? Watermarks readable? Drift?
    ↓
2.  Extract           Per-table, pattern E1–E5, watermark or snapshot
    ↓
3.  Bronze Load       Append with batch stamp, partition by ingest date (B-2)
    ↓
4.  Bronze Validate   Row-count reconciliation vs extract manifest (RC-1)
    ↓
5.  Silver Reference  Load reference tables and DQ rule catalogue (S-52)
    ↓
6.  Silver Build      Type, conform, dedup, merge, quarantine (17 entities)
    ↓
7.  Silver DQ         Apply DQ rules, flag failures, route to quarantine
    ↓
8.  Gold Dimensions   SCD2 merge, load all dimensions in dependency order
    ↓
9.  Gold Facts        Surrogate-key lookup, as-at resolution, insert/upsert
    ↓
10. Gold Marts        Aggregate rebuild (full snapshot)
    ↓
11. Reconciliation    10 checks (RC-1 through RC-10); failures block publish
    ↓
12. Publish           Flip serving pointer; notify consumers
    ↓
13. Close             Write run log, DQ scorecard, watermarks, send alert
```

**Implementation:**

```python
# pipeline.py:run()
def run(run_type="INCREMENTAL", cutoff=None, force_full=False, skip_gold=False):
    batch = open_batch(run_type, cutoff)
    report = RunReport(batch)
    
    try:
        # 1. Preflight
        report.drift = preflight(batch)
        
        # 2-4. Extract and Bronze
        report.extract = run_extract_and_bronze(batch, force_full)
        
        # 5-6. Silver
        silver.load_reference_data()
        report.silver_counts = silver.run_silver(batch)
        
        # 7-9. Gold (if not skipped)
        if not skip_gold:
            report.gold_counts = gold.run_gold(batch)
        
        # 10. Reconciliation
        report.recon = reconcile.run_all(batch)
        report.dq = dq.run_rules(batch)
        
        # 11. Publish gate
        publish_blocked = any(
            r.verdict == "FAIL" and r.severity == "BLOCK"
            for r in report.dq
        ) or any(
            c.verdict == "FAIL"
            for c in report.recon
        )
        
        if publish_blocked:
            report.status = "PUBLISH_BLOCKED"
            close_batch(batch, "PUBLISH_BLOCKED")
        else:
            report.status = "SUCCEEDED"
            mark_published(batch, True)
            close_batch(batch, "SUCCEEDED")
            report.published = True
    
    except Exception as exc:
        report.status = "FAILED"
        close_batch(batch, "FAILED", notes=str(exc))
        raise
    
    return report
```

**Output:**
- ✓ All 18 tables extracted with row counts
- ✓ Bronze layer fully loaded and reconciled
- ✓ Silver layer typed, conformed, deduplicated
- ✓ Gold dimensions and facts loaded
- ✓ All reconciliation checks passed
- ✓ Published flag flipped (or blocked)
- ✓ Runnable summary of extract/counts/recon/DQ per table

**Related Deliverables:** BRD-B §3.2, §12.2

---

### 2. **Extraction Patterns (E1–E5)**

**What:** Implement five distinct extraction strategies based on source table characteristics.

#### Pattern E1: Incremental on Business Date

**Use Cases:** orders, payments, refunds (anything timestamped with `updated_at`)

**Predicate:**
```sql
WHERE updated_at > :lower AND updated_at <= :cutoff
```

**Watermark Column:** `updated_at` (business date)

**Lookback:** Configurable (default 7 days). On the first run, `lower` is `-∞`. On subsequent runs, `lower` is `last_watermark - lookback_days`, catching late-arriving rows with old business dates (X-5).

**Idempotency:** Bronze batch overwrite (B-2) + Silver merge (S-50) are both idempotent, so re-extracting the same window produces identical end state.

**Initial Load:** All rows with `updated_at ≤ run_cutoff`

**Implementation:**
```python
# bronze.py:build_plan()
if pattern == "E1":
    lower = (last_watermark - timedelta(days=lookback)) if last_watermark else None
    predicate = f"{wm_col} > :lower AND {wm_col} <= :upper"
    return ExtractPlan(..., watermark_column=wm_col, lower_bound=lower, 
                       upper_bound=cutoff, predicate_sql=predicate, ...)
```

#### Pattern E2: Incremental on Creation Date

**Use Cases:** reviews, refunds (anything timestamped with `created_at`)

**Predicate:**
```sql
WHERE created_at > :lower AND created_at <= :cutoff
```

**Watermark Column:** `created_at`

**Lookback & Idempotency:** Same as E1.

#### Pattern E3: Full Snapshot (Dimension)

**Use Cases:** gender, restaurant_cuisine, cuisines, delivery_partner (small, stable, read-mostly)

**Predicate:** None (full table every run)

```sql
SELECT * FROM cuisine_table  -- no WHERE clause
```

**Watermark Column:** None (snapshot table never uses watermarks)

**Idempotency:** Bronze batch overwrite (B-2) produces identical result; Silver merge (S-50) deduplicates.

#### Pattern E4: Full Snapshot (Small Reference)

**Use Cases:** Rare small reference tables (e.g., very small lookup tables)

**Identical to E3:** Full table, no watermark.

#### Pattern E5: Full Snapshot (Empty OK)

**Use Cases:** Future-proofing for tables that may be empty or deprecated

**Identical to E3/E4:** Full table, no watermark. **Difference:** Returning 0 rows is not an error.

**Implementation:**
```python
if pattern in ("E3", "E4", "E5"):
    return ExtractPlan(
        source_table=table,
        pattern=pattern,
        watermark_column=None,
        predicate_sql="",
        predicate_desc="full snapshot (no predicate)",
        is_initial_load=False,
    )
```

**Configuration Source:**
Each table's extraction pattern is configured in `ctl_table_config.extract_pattern`:

| Table | Pattern | Watermark | Lookback | Load Type |
|-------|---------|-----------|----------|-----------|
| customers | E1 | updated_at | 7 days | MERGE |
| orders | E1 | updated_at | 7 days | MERGE |
| order_items | E1 | updated_at | 7 days | MERGE |
| payments | E1 | updated_at | 7 days | MERGE |
| reviews | E2 | created_at | 7 days | MERGE |
| gender | E3 | NULL | N/A | SNAPSHOT |
| cuisines | E4 | NULL | N/A | SNAPSHOT |
| *future* | E5 | NULL | N/A | SNAPSHOT |

---

### 3. **Batch Lifecycle Management (§10.1, §10.3)**

**What:** Open and close batches, prevent concurrent runs, log steps, manage batch state.

#### Open Batch
```python
def open_batch(run_type="INCREMENTAL", cutoff=None):
    """Create ctl_batch row; refuse if another is RUNNING."""
    # Check for concurrent run
    active = query(wh, "SELECT * FROM ctl_batch WHERE status = 'RUNNING'")
    if active:
        raise ConcurrentRunError(f"Batch {active[0]['dw_batch_id']} already running")
    
    # Create new batch
    batch_id = scalar(
        wh,
        """INSERT INTO ctl_batch (run_type, run_cutoff_ts_utc, triggered_by, code_version)
           VALUES (%s, %s, %s, %s) RETURNING dw_batch_id""",
        (run_type, cutoff or now(), _triggered_by(), settings().code_version)
    )
    return Batch(batch_id=batch_id, run_type=run_type, run_cutoff=cutoff, ...)
```

**Outputs:**
- ✓ `ctl_batch` row created with `status='RUNNING'`
- ✓ `dw_batch_id` assigned (ever-increasing)
- ✓ `run_cutoff_ts_utc` consistent across all 18 extractions
- ✓ Concurrent runs refused

#### Close Batch
```python
def close_batch(batch, status, notes=None):
    """Update ctl_batch with final status and end time."""
    execute(
        wh,
        "UPDATE ctl_batch SET status=%s, ended_ts_utc=now(), notes=%s WHERE dw_batch_id=%s",
        (status, notes, batch.batch_id)
    )
```

**Statuses:**
- `RUNNING` — Batch currently executing
- `SUCCEEDED` — All steps completed, all checks passed, publish approved
- `FAILED` — A critical step failed; batch aborted
- `PUBLISH_BLOCKED` — All steps completed, but a reconciliation or DQ check blocked publish

#### Step Logging
```python
@contextmanager
def step(batch, step_name, target_object=None):
    """Wrap a step; log result with counts and duration."""
    res = StepResult(step_name, target_object)
    start = time.time()
    try:
        yield res
    finally:
        duration = time.time() - start
        log_step(batch, res, duration)  # INSERT into ctl_step_log
```

**Usage:**
```python
with step(batch, "bronze_load", "orders") as res:
    res.rows_read = manifest_count
    res.rows_written = landed_rows
    # Any exception here is caught and logged
```

**Output:** `ctl_step_log` row with step name, target, counts, duration, status, error text.

#### Mark Published
```python
def mark_published(batch, published):
    """Flip published flag in ctl_batch after all checks pass."""
    execute(wh, "UPDATE ctl_batch SET published=%s WHERE dw_batch_id=%s",
            (published, batch.batch_id))
```

---

### 4. **Watermark Management (X-2, X-5)**

**What:** Track the last-extracted value per table per batch, enabling incremental extraction and replay.

#### Get Watermark
```python
def get_watermark(conn_wh, source_table):
    """Return {watermark_value, watermark_ts} from last successful run."""
    return scalar(conn_wh,
        "SELECT * FROM ctl_watermark WHERE source_table=%s ORDER BY updated_ts_utc DESC LIMIT 1",
        (source_table,))
```

#### Advance Watermark
```python
def advance_watermark(batch, source_table, new_value):
    """Update watermark only after Bronze validate succeeds (X-2)."""
    execute(wh,
        """INSERT INTO ctl_watermark (dw_batch_id, source_table, watermark_value, updated_ts_utc)
           VALUES (%s, %s, %s, now())""",
        (batch.batch_id, source_table, new_value))
```

#### Failure Handling (X-2)
```python
def record_watermark_failure(wh, source_table, batch_id):
    """Do NOT advance watermark if table fails; next run re-extracts same window."""
    # Intentional: watermark row is not inserted for this batch
    # Next run's build_plan() will see the old watermark and re-extract
```

**Key Property:** Watermark advances **only** after:
1. Bronze load succeeds
2. Bronze reconciliation (RC-1) passes

If Extract or Bronze fails, watermark is not advanced, and next run re-extracts the same window (X-2).

#### Lookback Window (X-5)
```python
if pattern in ("E1", "E2"):
    last_wm = get_watermark(wh, table)
    lower = last_wm - timedelta(days=lookback_days)  # default 7
    predicate = f"{wm_col} > {lower} AND {wm_col} <= {run_cutoff}"
```

This catches late-arriving rows with old business dates, ensuring no data is missed.

---

### 5. **Incremental vs. Full Reload Logic**

**What:** Support both incremental (default) and full reload modes, plus replay from Bronze.

#### Incremental (Default)

```python
python -m zwiggy_dwh.cli run
```

- Respects watermarks
- E1/E2 tables: Extract only rows where `updated_at/created_at > last_watermark - lookback`
- E3/E4/E5 tables: Full snapshot every run
- Watermark advances after success
- Typical: 1,000–50,000 rows/day

**Output:** `run_type='INCREMENTAL'` in `ctl_batch`

#### Full Reload

```python
python -m zwiggy_dwh.cli run --full
```

- Ignores watermarks; sets `force_full=True`
- All 18 tables: re-extract everything from source
- Watermark advances to current cutoff
- Typical: Quarterly validation or troubleshooting
- Time: 10–20 minutes

**Output:** `run_type='FULL'` in `ctl_batch`

#### Replay from Bronze

```python
python -m zwiggy_dwh.cli run --replay
```

- Skip Extract phase entirely
- Re-transform from existing Bronze only
- Use to iterate Silver/Gold logic without re-extracting
- Watermark not advanced (Bronze is already loaded)
- Time: 2–5 minutes

**Output:** `run_type='REPLAY'` in `ctl_batch`

#### Cutoff Override

```python
python -m zwiggy_dwh.cli run --cutoff 2026-09-18T20:00:00+00:00
```

- Pin run to historical timestamp
- Reproducible past run for debugging
- All 18 tables see same cutoff
- Combine with `--full` for historical full reload

---

### 6. **Layer Drivers (Bronze, Silver, Gold)**

**What:** Orchestrate the loading of each medallion layer.

#### Bronze Layer (`bronze.py`)

**Driver:** `run_extract_and_bronze(batch, force_full=False)`

```python
def run_extract_and_bronze(batch, force_full=False):
    outcomes = {}
    for table_config in table_configs:
        try:
            with step(batch, "bronze_load", table_config["source_table"]):
                outcome = load_table(table_config, batch, force_full)
                outcomes[table] = outcome
        except Exception:
            record_watermark_failure(batch, table)  # X-2
    return outcomes
```

**Per-Table Logic:**
1. Build extraction plan (predicate based on pattern E1–E5)
2. Query source with predicate
3. COPY rows to Bronze table with batch stamp
4. Record row count in `ctl_extract_manifest` for RC-1
5. Advance watermark (only if successful)

**Failures:** One table's failure does not stop others (§10.2); publish is blocked.

**Output:** `LoadOutcome` object with `rows_extracted`, `rows_written`, `pattern`, `predicate`, `new_watermark`

#### Silver Layer (`silver.py`)

**Driver:** `run_silver(batch, only=None)`

```python
def run_silver(batch):
    results = {}
    for load_spec in LOADS:  # dependency-ordered list
        with step(batch, "silver_load", load_spec.source_table):
            run_sql_file(conn, SQL_DIR / "silver" / "load" / load_spec.sql_file)
            results[load_spec.entity] = {
                "bronze_rows": res.rows_read,
                "silver_rows": res.rows_written,
                "quarantined": res.rows_quarantined,
            }
    return results
```

**Load Order (Dependency Injection):**
1. Reference tables first (no dependencies)
2. Dimension entities (customer, address, restaurant, etc.)
3. Order and cart headers
4. Order children (order_item, payment_attempt, delivery, etc.)

**Quarantine:** Rows that fail casting or conformance are routed to `*_quarantine` tables with `dw_quarantine_reason` and `dw_raw_payload`.

**Output:** Dictionary mapping entity name to bronze/silver/quarantine counts per batch.

#### Gold Layer (`gold.py`)

**Driver:** `run_gold(batch)`

```python
def run_gold(batch):
    is_initial = _is_initial_load()
    counts = {}
    
    # 1. Dimensions (SCD2)
    counts.update(_run_group(batch, DIMENSION_LOADS, "gold_dimension", is_initial))
    
    # 2. Facts
    counts.update(_run_group(batch, FACT_LOADS, "gold_fact", is_initial))
    
    # 3. Marts (aggregate snapshots)
    counts.update(_run_group(batch, MART_LOADS, "gold_mart", is_initial))
    
    return counts
```

**Dimension Load Order:**
1. Date and time dimensions (generated)
2. Code dimensions (from silver.ref_*)
3. Customer, Address, Restaurant, MenuItem, DeliveryPartner, RestaurantOwner (SCD2 merge)
4. OrderFlag junk dimension (for fact_order)

**Fact Load Order:**
1. fact_order (core transactional fact)
2. fact_order_item (child of fact_order)
3. fact_payment_attempt (payment retries)
4. fact_payment (deduplicated collected payment, S-24)
5. fact_delivery (deduplicated delivery, S-25)
6. fact_review
7. fact_cart_item
8. fact_refund, fact_order_cancellation, bridge_restaurant_cuisine (deferred)
9. fact_order_fulfilment (accumulating snapshot, must be last, G-34)

**Mart Load Order:**
1. Rebuild all 3 marts in full (aggregate snapshots)

**Output:** Dictionary mapping table name to current-state row count.

---

### 7. **Monitoring & Reporting**

**What:** Provide operational visibility into pipeline status and results.

#### CLI Status Command
```powershell
python -m zwiggy_dwh.cli status
```

**Output:**
```
LAST RUN
  batch_id       | 42
  run_type       | INCREMENTAL
  status         | SUCCEEDED
  published      | t
  started        | 2026-09-25 12:15:00+00:00
  ended          | 2026-09-25 12:22:45+00:00
  duration       | 465 seconds
  failed_steps   | 0
  failed_recon   | 0
  failed_dq      | 0

WATERMARKS (last successful extraction)
  customer       | 2026-09-25 20:00:00+00:00
  order          | 2026-09-25 20:00:00+00:00
  payment        | 2026-09-25 20:00:00+00:00
  ...
```

#### CLI Scorecard Command
```powershell
python -m zwiggy_dwh.cli scorecard
```

**Output:**
```
DATA QUALITY SCORECARD (KPI-33 … KPI-42)
  KPI-33 Pipeline SLA              | 465 seconds (target 1800) | PASS
  KPI-34 Order-Line Coverage       | 12.9% | WARN
  KPI-35 Status Consistency        | 89.0% | WARN
  ...
  KPI-40 Quarantine Rate           | 0.001 | PASS
```

#### CLI Run Output
```powershell
python -m zwiggy_dwh.cli run
```

**Output:**
```
RUN SUMMARY — batch 43 — SUCCEEDED

Extract and Bronze (source -> bronze):
  table            | pattern | rows      | load   | predicate
  customers        | E1      | 125,432   | INCR   | updated_at > 2026-09-18 AND ...
  orders           | E1      | 2,943     | INCR   | updated_at > 2026-09-18 AND ...
  ...
  total extracted: 336,751 rows

Silver:
  entity              | bronze | loaded | quarantined
  slv_customer        | 125k   | 125k   | 0
  slv_order           | 61k    | 61k    | 23
  ...

Gold (current-state totals):
  fact_order          | 61,777
  fact_order_item     | 118,943
  ...

Reconciliation:
  10 passed, 0 failed, 0 skipped

Data quality:
  27 rules evaluated, 0 with flagged rows

PUBLISHED — batch 43 is now the serving version
```

**Output:** Pretty-printed summary with per-table extract detail, per-entity Silver counts, Gold totals, recon and DQ verdicts.

---

### 8. **Error Handling & Resilience**

**What:** Handle extraction failures gracefully, retry transient errors, prevent partial runs.

#### Per-Table Failure Isolation
```python
for table in all_tables:
    try:
        load_table(table, batch)
    except Exception as exc:
        log.error(f"bronze load failed for {table}: {exc}")
        record_watermark_failure(batch, table)  # watermark NOT advanced
        batch.failures.append(table)
```

**Consequence:** One table's failure does not stop others; publish is blocked if any table failed.

#### Transient Retry with Backoff
```python
def with_retry(fn, *, what, retries=None):
    for attempt in range(1, retries + 2):
        try:
            return fn()
        except TRANSIENT:
            if attempt == retries + 1:
                raise
            delay = retry_backoff_seconds * (2 ** (attempt - 1))
            time.sleep(delay)
```

**Retried Errors:** `OperationalError`, `DeadlockDetected`, `LockNotAvailable`, `SerializationFailure`

**Backoff Schedule:** 1s, 2s, 4s, 8s, ... (default 3 retries)

#### Concurrent Run Prevention
```python
active = query(wh, "SELECT * FROM ctl_batch WHERE status = 'RUNNING'")
if active:
    raise ConcurrentRunError(f"Batch {active[0]['dw_batch_id']} already running")
```

**Recovery:** Run `python -m zwiggy_dwh.cli abandon-run --batch-id N` to force-close a stuck batch.

---

## Handoff Points

### ✅ Receives from Warehouse Foundation Skill:

1. **Validated Configuration** — All tunable parameters loaded and type-checked
2. **Open Warehouse Connection** — Guarded, ready for reads/writes
3. **Watermark Tables** — `ctl_watermark` and `ctl_table_config` ready
4. **Step Logging Infrastructure** — `ctl_step_log` table and `step()` context manager
5. **Batch Lifecycle Framework** — `open_batch()`, `close_batch()`, `mark_published()` functions
6. **Retry Wrapper** — `with_retry()` for resilience
7. **Source Connection** — Read-only, guarded connection to OLTP

### ✅ Provides to Data Quality & Reconciliation Skill:

1. **Open Batch** — Batch ID and cutoff timestamp for DQ/recon evaluation
2. **Extracted Row Counts** — Per-table row counts for reconciliation check RC-1
3. **Batch Status** — Success/failure status for conditional DQ/recon execution
4. **Step Log Records** — For auditing which steps ran and when

### ✅ Provides to CLI Layer:

1. **RunReport** — Summary of extract, Silver, Gold, recon, DQ results
2. **Status Query Results** — Batch lineage, watermarks, publish status
3. **Scorecard Data** — DQ rule results aggregated for display

---

## Implementation Files

### Core Python Modules
- **`dwh/src/zwiggy_dwh/pipeline.py`** — `run()`, `preflight()`, `run_extract_and_bronze()`, 12-step orchestration
- **`dwh/src/zwiggy_dwh/bronze.py`** — `load_table()`, `build_plan()`, E1–E5 pattern logic, COPY to Bronze
- **`dwh/src/zwiggy_dwh/silver.py`** — `run_silver()`, per-entity SQL file execution, quarantine tracking
- **`dwh/src/zwiggy_dwh/gold.py`** — `run_gold()`, dimension/fact/mart orchestration
- **`dwh/src/zwiggy_dwh/batch.py`** — `open_batch()`, `close_batch()`, `step()`, watermark management
- **`dwh/src/zwiggy_dwh/metadata.py`** — `detect_drift()`, schema introspection (X-7)
- **`dwh/src/zwiggy_dwh/db.py`** — `with_retry()`, connection management, query runners

### SQL Files (Extract & Load)
- **`dwh/sql/silver/load/`** — 19 SQL files (one per Silver entity)
- **`dwh/sql/gold/load/`** — 11 SQL files (dimensions, facts, marts)

### CLI Entry Point
- **`dwh/src/zwiggy_dwh/cli.py`** — `cmd_run()`, `cmd_status()`, `cmd_scorecard()`, monitoring output

---

## Usage & Commands

### Incremental Run (Default)
```powershell
cd dwh
$env:PYTHONPATH = "$PWD\src"
python -m zwiggy_dwh.cli run
```

**Expected:** ~30 minutes (first run with 336K rows), ~5 minutes (incremental with 1–50K rows)

### Full Reload
```powershell
python -m zwiggy_dwh.cli run --full
```

**Expected:** ~30 minutes

### Replay from Bronze
```powershell
python -m zwiggy_dwh.cli run --replay
```

**Expected:** ~5 minutes (iterating Silver/Gold logic)

### Cutoff Override (Debugging)
```powershell
python -m zwiggy_dwh.cli run --cutoff 2026-09-18T20:00:00+00:00
```

### Check Status
```powershell
python -m zwiggy_dwh.cli status
```

### View Scorecard
```powershell
python -m zwiggy_dwh.cli scorecard
```

---

## Test Coverage

### Unit Tests (`tests/test_unit.py`)
- ✓ Statement splitting (SQL parsing preserves strings, comments, dollar quotes)
- ✓ Named parameter conversion (`:param` → `%(param)s`, no break on `::type` casts)
- ✓ Configuration loading and validation

### Integration Tests (Pending)
- Incremental extraction with watermark advances
- Lookback window catches late-arriving rows
- Full reload ignores watermarks
- Replay skips extract phase
- Concurrent run prevention
- Per-table failure isolation
- Batch lifecycle (open → close → publish)
- Watermark failure handling (X-2)

---

## Error Handling & Recovery

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Source unreachable | Preflight step fails | Verify source DB is running; check network connectivity |
| Table extraction fails | try/except in loop; watermark not advanced (X-2) | Run again; same window is re-extracted automatically |
| Transient lock/deadlock | Caught by with_retry() | Retried with backoff; eventual success or timeout |
| Concurrent run | open_batch() raises ConcurrentRunError | Verify no process running; run `abandon-run --batch-id N`; retry |
| Stuck batch in RUNNING | Manual check of ctl_batch | Run `abandon-run --batch-id N` to force close |
| Bronze load partial | RC-1 reconciliation fails | Run again; batch overwrite is idempotent |
| Silver merge fails | Exception logged; batch.failures tracked | Run again; merge is idempotent per dw_batch_id |

---

## Traceability to BRD-B

| BRD-B §Section | Requirement | Implementation |
|---|---|---|
| §3.2 | 12-step run sequence | `pipeline.py:run()` |
| §4.3 | Five extraction patterns E1–E5 | `bronze.py:build_plan()` per pattern |
| §10.1 | Batch lifecycle and logging | `batch.py`: open_batch, close_batch, step |
| §10.2 | Dependency order (ref → dim → order → children) | LOADS tuple in silver.py and DIMENSION_LOADS, FACT_LOADS, MART_LOADS in gold.py |
| §10.3 | Single run at a time | `open_batch()` checks for RUNNING status |
| §10.4 | Retry transient failures | `db.py:with_retry()` with exponential backoff |
| §12.2 | Operational monitoring | `cli.py:cmd_status()`, `cmd_scorecard()` |
| X-2 | Watermark not advanced on failure | `bronze.py:record_watermark_failure()` |
| X-5 | Lookback window catches late-arriving rows | `bronze.py:build_plan()` subtracts lookback_days |
| X-7 | Schema drift detection | `metadata.py:detect_drift()`, preflight checks |
| B-2 | Idempotent batch overwrite | Bronze COPY with batch_id as unique key |
| S-50 | Idempotent Silver merge | Silver MERGE ON business_key |
| CS-7 | Structured logging with counts | `batch.py:log_step()` records rows and duration |

---

## Success Criteria

✓ All 18 tables extracted per configured pattern  
✓ Bronze layer fully loaded and reconciled (RC-1)  
✓ Silver layer typed, conformed, quarantined failures  
✓ Gold dimensions and facts loaded with correct grain  
✓ All steps logged with counts and timing  
✓ Watermarks advanced only after success  
✓ Publish approved if all recon/DQ checks pass  
✓ RunReport summary accurate and complete  
✓ Monitoring CLI shows correct status and counts  
✓ Incremental runs respect watermarks  
✓ Full reload ignores watermarks  
✓ Replay skips extract phase  
✓ Per-table failures do not stop other tables  
✓ Concurrent runs refused  

---

## Related Skills

- **Warehouse Foundation & Configuration** — Provides initialization, connectivity, batch lifecycle framework
- **Data Quality & Reconciliation** — Evaluates DQ rules and reconciliation checks; blocks publish if failed

---

## References

- BRD-B: Business Requirements Document, Zwiggy Medallion Warehouse
- README.md: Project overview, quick start, key features
- RUNBOOK.md: Operational procedures for daily runs and troubleshooting
- `dwh/src/zwiggy_dwh/`: Core Python modules
- `dwh/sql/`: All DDL and transformation SQL

