---
skill_name: "Data Quality & Reconciliation"
agent_name: "Antigravity"
version: "1.0.0"
date_created: "2025-01-01"
skill_type: "validation"
capability_domain: "data_quality_governance"
responsibility_level: "core"
---

# Data Quality & Reconciliation

## Overview

This skill owns the **complete data quality validation and reconciliation governance** of the Zwiggy Medallion Data Warehouse. It implements 27 data quality rules across Bronze, Silver, and Gold layers; executes 10 critical reconciliation checks (RC-1 through RC-10); manages the quarantine mechanism for invalid rows; publishes operational scorecards; and enforces the publish gate—blocking unsafe data from reaching consumers until all quality and integrity checks pass.

**Scope:** DQ rule engine, reconciliation checks, quarantine mechanism, scorecard generation, publish gate logic, blocking rule severity, threshold enforcement, and audit trail.

**Status:** Core governance layer—fully implemented and production-ready.

---

## Ownership Matrix

| Domain | Component | Files | Responsibility |
|--------|-----------|-------|-----------------|
| **DQ Rules** | Rule catalogue | `silver.dq_rule` table + `dq.py` | Define 27 rules with expressions, thresholds, severity, and active status |
| **DQ Rules** | Rule engine | `dq.py:run_rules()` | Execute each active rule; evaluate expression against target object (Silver entity) |
| **DQ Rules** | Row-level evaluation | `dq.py` (SQL expressions) | For each rule, count total rows and rows failing the expression (TRUE = pass, FALSE/NULL = fail) |
| **DQ Rules** | Batch-level evaluation | `dq.py:_batch_rules()` | DQ-R09 … DQ-R24: uniqueness, join cardinality, source-to-Gold counts (e.g., payment duplicates, dimension resolution) |
| **DQ Rules** | Threshold enforcement | `dq.py:run_rules()` | Apply rule-specific threshold; verdict PASS if failure rate ≤ threshold, FAIL otherwise |
| **DQ Rules** | Severity classification | `dq.py` (via dq_rule.severity column) | BLOCK (publish failure), QUARANTINE (row-level flag), WARN (informational, counted only) |
| **DQ Results** | Result recording | `dq.py:_record()` | INSERT/UPDATE `ctl_dq_result` per rule per batch: rows evaluated/failed, verdict, detail |
| **DQ Results** | Blocking logic | `pipeline.py:run()` | Check for any DQ rule with verdict='FAIL' AND severity='BLOCK'; if found, block publish |
| **Quarantine** | Quarantine siblings | `silver.sql` + DDL | Create `*_quarantine` table for each Silver entity to hold rejected rows |
| **Quarantine** | Quarantine routing | Silver load SQL | MERGE with LEFT JOIN check; rows with missing/null business key → quarantine |
| **Quarantine** | Quarantine payload | `silver.sql` (dw_quarantine_reason, dw_raw_payload JSONB) | Store reason code and full raw row for replay |
| **Quarantine** | Quarantine replay | `silver.sql` (case-by-case) | Re-apply transformations to quarantine rows when reference data fixed or logic corrected (no re-extract) |
| **Reconciliation** | Check suite | `reconcile.py` (10 checks) | RC-1 through RC-10: integrity checks across Extract → Bronze → Silver → Gold |
| **Reconciliation** | RC-1 check | `reconcile.py` | Extract row count equals Bronze row count per table per batch (exact match) |
| **Reconciliation** | RC-2 check | `reconcile.py` | Bronze rows accounted for: loaded + quarantined + rejected ≥ bronze (nothing lost) |
| **Reconciliation** | RC-3 check | `reconcile.py` | Silver rows at declared grain equal fact rows (dedup rules documented, e.g., S-24, S-25) |
| **Reconciliation** | RC-6 check | `reconcile.py` | Fact foreign keys resolved (≤ threshold share of SKs = -1 for unknown) |
| **Reconciliation** | RC-7 check | `reconcile.py` | No duplicates at fact grain (merge key is unique per the assertion) |
| **Reconciliation** | RC-8 check | `reconcile.py` | SCD2 dimensions have non-overlapping effective/end dates (no gaps or overlaps) |
| **Reconciliation** | RC-9 check | `reconcile.py` | Mart row counts agree with underlying facts (mart_daily_summary ≈ fact_order grouped) |
| **Reconciliation** | RC-10 check | `reconcile.py` | Gold freshness: Gold cutoff ≥ source watermark (no regress) |
| **Reconciliation** | Verdict logic | `reconcile.py:Check` | verdict = 'PASS' / 'FAIL' / 'SKIP'; blocking if verdict='FAIL' |
| **Publish Gate** | Gate logic | `pipeline.py:run()` | Block if any DQ BLOCK verdict='FAIL' OR any reconciliation check verdict='FAIL' |
| **Publish Gate** | Status assignment | `pipeline.py:run()` | If blocked: `status='PUBLISH_BLOCKED'`, `published=False`; else `status='SUCCEEDED'`, `published=True` |
| **Scorecard** | Scorecard compilation | `dq.py` + SQL view | KPI-33 … KPI-42: pipeline SLA, data quality metrics, cohort mix, concentration |
| **Scorecard** | Scorecard view | `gold.sem_dq_scorecard` | Query-friendly view of current-run DQ results per rule |
| **Scorecard** | CLI output | `cli.py:cmd_scorecard()` | Pretty-print DQ scorecard with KPI-33 … KPI-42 and verdicts |

---

## Core Responsibilities

### 1. **Data Quality Rule Engine (BRD-B §9)**

**What:** Catalog 27 data quality rules and evaluate each one every run, measuring business logic compliance and data integrity.

#### Rule Definition

All rules are **data-driven** (§9.1): rows in the `silver.dq_rule` table, not hard-coded in Python.

| Field | Example | Purpose |
|-------|---------|---------|
| `rule_id` | DQ-R01 | Unique rule identifier |
| `layer` | silver | Which layer the rule applies to (bronze, silver, gold) |
| `target_object` | slv_order | Table the rule evaluates (or `*` for batch-level) |
| `expression` | `order_status NOT IN ('ACTIVE', 'CANCELLED')` | SQL boolean (TRUE=pass, FALSE/NULL=fail) |
| `severity` | BLOCK | Consequence if rule fails: BLOCK (publish fail), QUARANTINE (flag row), WARN (count only) |
| `threshold` | 0.05 | Failure rate threshold (e.g., 5%); `NULL` means 0 failures allowed |
| `is_active` | true | Enable/disable rule without code change |
| `linked_finding` | BR-R3 | Link to BRD-B requirement or finding |
| `description` | Order status must be known value | Human-readable description |

#### The 27 Rules

**Casting & Conformance (DQ-R01 through DQ-R08):**
- **DQ-R01:** Numeric columns cast without error (delegated to Silver load; cast failures → quarantine)
- **DQ-R02:** Date columns parse and are valid (no future dates, no before-1900)
- **DQ-R03:** Business keys (customer_id, order_id, etc.) are not null
- **DQ-R04:** Status conformance: only known values in `ref_payment_method_map`
- **DQ-R05:** Email format validation (if present)
- **DQ-R06:** Phone format validation (if present)
- **DQ-R07:** Currency amounts non-negative (where expected)
- **DQ-R08:** Percentages in [0, 100]

**Uniqueness & Cardinality (DQ-R09 through DQ-R12):**
- **DQ-R09:** Exactly one collected payment per order after S-24 (batch-level, delegated)
- **DQ-R12:** Order headers have at least one line item (cardinality check)

**Referential Integrity (DQ-R13 through DQ-R16):**
- **DQ-R13:** Every order references a known customer (foreign key validation)
- **DQ-R14:** Every order line references a known restaurant
- **DQ-R15:** Every payment references a known order
- **DQ-R16:** Every delivery references a known order

**Business Logic (DQ-R17 through DQ-R20):**
- **DQ-R17:** Order total ≥ line item sum (amounts reconcile)
- **DQ-R18:** No duplicate rows at line item grain (delegated to fact grain check RC-3)
- **DQ-R19:** Delivery date ≥ order date (timeline validity, see BR-R6)
- **DQ-R20:** Dimension foreign keys resolved (≤ threshold share unknown, delegated to RC-6)

**Batch-Level (DQ-R21 through DQ-R24):**
- **DQ-R21:** Row counts across Bronze/Silver/Gold match dedup logic (delegated to RC-2/RC-3)
- **DQ-R22:** Watermarks advanced (if extraction succeeded)
- **DQ-R23:** No data regression (Gold cutoff ≥ prior run, delegated to RC-10)
- **DQ-R24:** SCD2 dimension intervals non-overlapping (delegated to RC-8)

**PII & Masking (DQ-R25 through DQ-R27):**
- **DQ-R25:** Unmasked PII (first_name, last_name) only in Silver, not in Gold
- **DQ-R26:** Email hash consistent with unmasked email in Silver
- **DQ-R27:** Phone masked in Gold as `***-****`

#### Rule Evaluation

**Implementation:**

```python
# dq.py:run_rules()
def run_rules(batch):
    results = []
    rules = query(wh, "SELECT * FROM silver.dq_rule WHERE is_active AND expression IS NOT NULL")
    
    for rule in rules:
        if rule["target_object"] == "*":
            continue  # batch-level, handled separately
        
        table = f"silver.{rule['target_object']}"
        total = scalar(wh, f"SELECT count(*) FROM {table}") or 0
        
        # Expression TRUE = pass, FALSE/NULL = fail
        failed = scalar(
            wh,
            f"SELECT count(*) FROM {table} "
            f"WHERE NOT ({rule['expression']}) OR ({rule['expression']}) IS NULL"
        ) or 0
        
        share = Decimal(failed) / Decimal(total) if total else Decimal(0)
        threshold = rule["threshold"]
        
        if rule["severity"] == "WARN":
            verdict = "PASS"  # WARN never fails
        elif threshold is not None:
            verdict = "PASS" if share <= Decimal(str(threshold)) else "FAIL"
        else:
            verdict = "PASS" if failed == 0 else "FAIL"
        
        results.append(RuleResult(
            rule_id=rule["rule_id"],
            target_object=rule["target_object"],
            severity=rule["severity"],
            rows_evaluated=total,
            rows_failed=failed,
            verdict=verdict,
            detail=f"{failed} of {total} rows fail: {rule['expression']}"
        ))
    
    results.extend(_batch_rules(wh, batch))
    _record(wh, batch, results)
    return results
```

**Output:**
- ✓ `ctl_dq_result` row per rule per target object per batch
- ✓ Counts: total rows evaluated, rows failed
- ✓ Verdict: PASS or FAIL
- ✓ Detail: SQL expression and failure count

#### Delegated Rules (Not Evaluated by Engine)

Some rules are enforced during the Silver load or reconciliation phase rather than as a row-level predicate:

- **DQ-R01 to DQ-R03:** Enforced during Silver load with MERGE and quarantine (rows that fail are diverted)
- **DQ-R09, DQ-R12:** Batch-level uniqueness and cardinality (counted in `_batch_rules()`)
- **DQ-R18, DQ-R19, DQ-R20:** Boundary conditions enforced in reconciliation (RC-3, RC-6, RC-8)
- **DQ-R21 to DQ-R24:** Batch-level (row counts, watermarks, regression, SCD2)
- **DQ-R25 to DQ-R27:** PII masking verified in Gold layer view (SELECT checks, not INSERT-time)

**Reason:** Row predicates are too expensive for gigantic tables, or require cross-table joins that reconciliation checks can do more efficiently.

---

### 2. **Reconciliation Checks (BRD-B §9.4, BR-11)**

**What:** Execute 10 critical reconciliation checks that validate end-to-end data integrity across Extract → Bronze → Silver → Gold.

#### RC-1: Extract → Bronze Row Count Equality

**Check:** Rows extracted per table must equal rows landed in Bronze exactly.

```python
for row in query(wh, """
    SELECT source_table, row_count FROM ctl_extract_manifest
     WHERE dw_batch_id = %s
""", (batch.batch_id,)):
    expected = row["row_count"]
    actual = scalar(wh, f"SELECT count(*) FROM bronze.{bronze_object} WHERE dw_batch_id = %s",
                    (batch.batch_id,))
    verdict = "PASS" if expected == actual else "FAIL"
```

**Why:** If a write was lost or truncated, Bronze is corrupted and the run cannot be trusted.

**Consequence:** FAIL = batch is PUBLISH_BLOCKED.

**Recovery:** Re-run the batch; Bronze is idempotent per batch (B-2).

#### RC-2: Bronze → Silver Accounting

**Check:** All Bronze rows must be accounted for: loaded + quarantined + rejected ≥ Bronze.

```python
for row in query(wh, "SELECT source_table, rows_read, rows_written, rows_quarantined, rows_rejected FROM ctl_step_log WHERE dw_batch_id = %s AND step_name = 'silver_load'", (batch.batch_id,)):
    bronze = row["rows_read"] or 0
    accounted = (row["rows_written"] or 0) + (row["rows_quarantined"] or 0) + (row["rows_rejected"] or 0)
    verdict = "PASS" if accounted >= bronze else "FAIL"
```

**Why:** No row can disappear silently; quarantine and rejection are the only legitimate missing-row cases.

**Consequence:** FAIL = code defect; inspect `silver_load()` SQL for missing rows.

#### RC-3: Silver → Gold Grain Equality

**Check:** Silver rows at declared grain match fact row counts (dedup rules are documented).

```python
pairs = [
    ("slv_order", "fact_order", ""),
    ("slv_payment", "fact_payment", "after S-24 retry-collapse"),
    ("slv_delivery", "fact_delivery", "after S-25 dedup"),
]
for silver_tbl, gold_tbl, note in pairs:
    silver_rows = scalar(wh, f"SELECT count(*) FROM silver.{silver_tbl} WHERE NOT dw_is_deleted")
    gold_rows = scalar(wh, f"SELECT count(*) FROM gold.{gold_tbl}")
    verdict = "PASS" if silver_rows == gold_rows else "FAIL"
```

**Why:** Gold facts are the authoritative grain; if counts diverge, the load SQL or merge key is wrong.

**Consequence:** FAIL = code defect; check the fact load SQL and MERGE logic.

**Known Dedup:**
- **S-24:** Payment retry collapse — multiple payment attempts per order → one collected payment
- **S-25:** Delivery deduplication — multiple delivery rows → one latest terminal status

#### RC-4 & RC-5: Source → Gold Closed Period Reconciliation

**Check:** For a closed period (e.g., a day in the past), source row count must equal Gold row count.

```python
# Only check closed periods (closed_date < run_cutoff)
for closed_period in closed_periods:
    source = scalar(src, f"SELECT count(*) FROM orders WHERE order_date = %s", (closed_period,))
    gold = scalar(wh, f"SELECT count(*) FROM fact_order WHERE order_date = %s", (closed_period,))
    verdict = "PASS" if source == gold else "FAIL"
```

**Why:** A closed period should never change; any difference is data loss or corruption.

**Consequence:** FAIL = very serious; escalate before re-running. Indicates the merge key is wrong or facts are being double-counted.

#### RC-6: Referential Integrity (Foreign Keys Resolved)

**Check:** No more than configured threshold of foreign key SKs can be -1 (unknown).

```python
for fact_tbl, sk_cols in [
    ("fact_order", ("customer_sk", "address_sk", "restaurant_sk")),
    ("fact_payment", ("customer_sk", "restaurant_sk")),
]:
    total = scalar(wh, f"SELECT count(*) FROM gold.{fact_tbl}")
    unresolved = scalar(wh, f"SELECT count(*) FROM gold.{fact_tbl} WHERE {' OR '.join(f'{c}=-1' for c in sk_cols)}")
    share = Decimal(unresolved) / Decimal(total)
    verdict = "PASS" if share <= threshold else "FAIL"
```

**Why:** Unresolved dimensions indicate a parent table failed to load or a join broke.

**Consequence:** FAIL = check dimension load logs; likely a dimension load failed (check `ctl_step_log` for failed dimension steps).

#### RC-7: No Duplicates at Fact Grain

**Check:** For each fact table, the merge/grain key is unique (no duplicates).

```python
for fact_tbl, grain_keys in [
    ("fact_order", ("order_id",)),
    ("fact_order_item", ("order_id", "line_item_id")),
    ("fact_payment", ("order_id",)),  # after S-24 dedup
]:
    dups = scalar(wh, f"SELECT count(*) FROM (SELECT {', '.join(grain_keys)} FROM gold.{fact_tbl} GROUP BY {', '.join(grain_keys)} HAVING count(*) > 1) d")
    verdict = "PASS" if dups == 0 else "FAIL"
```

**Why:** The fact table's declared grain is its key uniqueness promise; duplicates violate the grain contract.

**Consequence:** FAIL = code defect; the merge key in the fact SQL is wrong.

#### RC-8: SCD2 Dimension Integrity

**Check:** All dimension versions (SCD2) are non-overlapping; no gaps or overlaps.

```python
for dim_tbl in ["dim_customer", "dim_address", "dim_restaurant"]:
    gaps = scalar(wh, f"""
        SELECT count(*) FROM (
            SELECT dw_version, valid_from, valid_to,
                   LEAD(valid_from) OVER (ORDER BY valid_from) as next_valid_from
              FROM gold.{dim_tbl}
             WHERE dw_is_current = false
        ) v
         WHERE valid_to < next_valid_from OR valid_from > valid_to
    """)
    verdict = "PASS" if gaps == 0 else "FAIL"
```

**Why:** SCD2 intervals must be continuous and non-overlapping for as-at queries to work correctly.

**Consequence:** FAIL = do NOT hand-edit (EH-10). Re-run with `--replay` from a known good Bronze version.

#### RC-9: Mart Agreement

**Check:** Mart row counts agree with underlying fact aggregations.

```python
# mart_daily_business_summary should equal COUNT(DISTINCT order_id) per day
mart_count = scalar(wh, "SELECT count(*) FROM gold.mart_daily_business_summary")
fact_count = scalar(wh, "SELECT count(DISTINCT order_id) FROM gold.fact_order")
verdict = "PASS" if mart_count == fact_count else "FAIL"
```

**Why:** Marts are aggregates of facts; disagreement means the mart SQL diverged from the fact SQL.

**Consequence:** FAIL = re-run; marts rebuild in full every run. If it persists, compare mart and fact SQL for differences.

#### RC-10: Gold Freshness (No Regression)

**Check:** Gold cutoff timestamp must be ≥ prior run's cutoff (no regress).

```python
prior_cutoff = scalar(wh, f"SELECT max(run_cutoff_ts_utc) FROM ctl_batch WHERE published AND dw_batch_id < %s", (batch.batch_id,))
current_cutoff = batch.run_cutoff
verdict = "PASS" if current_cutoff >= prior_cutoff else "FAIL"
```

**Why:** Data should always advance; a regressed cutoff indicates the extract silently returned nothing (watermark bug).

**Consequence:** FAIL = check `ctl_watermark` for the affected tables; likely a watermark stall.

---

### 3. **Quarantine Mechanism (S-1, P-2)**

**What:** Invalid rows are never dropped; they are diverted to quarantine with a reason code and full payload, enabling replay without re-extraction.

#### Quarantine Table Structure

For each Silver entity, a quarantine sibling is created:

```sql
CREATE TABLE silver.slv_order_quarantine (
    dw_batch_id bigint,
    dw_ingest_ts_utc timestamptz,
    dw_quarantine_reason varchar(200),    -- e.g., "cast: order_total is not decimal"
    dw_raw_payload jsonb,                 -- full row from Bronze as JSON
    source_system varchar(30),
    source_table varchar(100),
    ...all Silver columns as text or NULL...
);
```

#### Quarantine Routing (Silver Load)

```python
# In Silver load SQL:
INSERT INTO silver.slv_order (dw_batch_id, order_id, order_total, ...)
SELECT dw_batch_id, 
       TRY_CAST(order_id AS bigint),
       TRY_CAST(order_total AS decimal),
       ...
  FROM bronze.br_order
 WHERE dw_batch_id = :batch_id AND NOT dw_is_deleted;

-- Rows that fail any cast or conformance check are inserted into quarantine:
INSERT INTO silver.slv_order_quarantine (dw_batch_id, dw_quarantine_reason, dw_raw_payload, ...)
SELECT dw_batch_id,
       CONCAT('cast: order_total is not decimal (value=', order_total, ')'),
       row_to_json(br_order),
       ...
  FROM bronze.br_order
 WHERE dw_batch_id = :batch_id
    AND (TRY_CAST(order_total AS decimal) IS NULL OR ...)
```

#### Quarantine Counting

```python
# In dq.py, track quarantined rows per entity per batch
quarantined = scalar(wh,
    f"SELECT count(*) FROM silver.{entity}_quarantine WHERE dw_batch_id = %s",
    (batch.batch_id,))
```

#### Quarantine Replay

When the root cause is fixed (e.g., reference data corrected), quarantine rows can be replayed:

```python
# Case 1: Reference data fix (e.g., add missing status to ref_payment_method_map)
# UPDATE silver.ref_payment_method_map SET conformed_value = 'DEBIT_CARD' WHERE source_value = 'Online';
# Then the existing Silver rows automatically incorporate the fix (re-select with new mapping).

# Case 2: Cast rule change (e.g., order_total now accepts NULL)
# Update the cast logic in the Silver load SQL.
# Then re-run with --replay; quarantined rows are automatically re-attempted.
```

**Key Property:** Quarantine rows are never hand-edited; they are always replayed by fixing the underlying rule and re-running.

---

### 4. **Publish Gate Logic (P-3)**

**What:** Prevent unsafe data from reaching consumers; block publish if any quality or integrity check fails.

#### Gate Implementation

```python
# pipeline.py:run()
try:
    # ... execute all 12 steps ...
    
    # Collect failures
    blocking_dq = [r for r in report.dq if r.verdict == "FAIL" and r.severity == "BLOCK"]
    blocking_recon = [c for c in report.recon if c.verdict == "FAIL"]
    
    if blocking_dq or blocking_recon:
        report.status = "PUBLISH_BLOCKED"
        report.publish_blocked_reasons = [
            f"DQ {r.rule_id}: {r.detail}" for r in blocking_dq
        ] + [
            f"RC {c.check_id}: {c.detail}" for c in blocking_recon
        ]
        close_batch(batch, "PUBLISH_BLOCKED", notes="; ".join(report.publish_blocked_reasons))
        mark_published(batch, False)
    else:
        report.status = "SUCCEEDED"
        close_batch(batch, "SUCCEEDED")
        mark_published(batch, True)
        report.published = True

except Exception as exc:
    report.status = "FAILED"
    close_batch(batch, "FAILED", notes=str(exc))
    raise
```

#### Consequence

- **SUCCEEDED + published=true:** Semantic layer (views) now serve this batch
- **PUBLISH_BLOCKED:** Semantic layer continues serving the prior good batch (P-3); current batch is visible in `ctl_batch` but not active
- **FAILED:** Batch aborted; batch state visible in `ctl_batch`; semantic layer unchanged

**Operational Impact:**
- ✓ Consumers see consistent, validated data
- ✓ No silent data quality degradation
- ✓ On-call engineer must investigate and fix, then re-run
- ✓ Prior good version remains available (not overwritten)

---

### 5. **Scorecards & KPI Publication (BRD-B §12.2)**

**What:** Publish a comprehensive data quality scorecard every run, showing business metrics and pipeline health.

#### KPI Definitions

| KPI | Measure | Source | Expected | Severity |
|-----|---------|--------|----------|----------|
| **KPI-33** | Pipeline SLA | `ctl_step_log` duration sum | < 1800s (30 min) | WARN |
| **KPI-34** | Order-Line Coverage | `count(order_item) / (count(order) * avg_lines_per_order)` | 10–15% (Cohort A only) | INFO |
| **KPI-35** | Status Consistency | `count(*) where order_status = conformed_status / count(*)` | > 89% (BR-R3 expected) | INFO |
| **KPI-36** | Amount Reconciliation | `count(*) where order_total = sum(line_items) / count(*)` | > 88% (S-27) | INFO |
| **KPI-37** | Payment Retry Rate | `count(distinct order_id with retry) / count(distinct order_id)` | ~6.1% (BR-R5) | INFO |
| **KPI-38** | Delivery Timeline | `count(*) where delivery_date >= pickup_date / count(*)` | > 92% (BR-R6) | INFO |
| **KPI-39** | Customer Activity | `count(distinct active_customer_id)` | Trend metric | INFO |
| **KPI-40** | Quarantine Rate | `count(quarantine) / count(bronze)` | < 0.5% (0.005) | WARN |
| **KPI-41** | Restaurant Concentration | `max(order_share_pct) for top restaurant` | < 90% (Herfindahl) | INFO |
| **KPI-42** | Cohort Mix | `count(COHORT_A) / count(*)` | ~12.9% (stable) | INFO |

#### Scorecard View

```sql
-- gold.sem_dq_scorecard
SELECT
    kpi_id,
    kpi_name,
    metric_value,
    threshold,
    verdict,
    dw_batch_id
FROM (
    SELECT 'KPI-33' AS kpi_id, 'Pipeline SLA' AS kpi_name,
           (SELECT sum(duration_seconds) FROM ctl_step_log WHERE dw_batch_id = :batch_id) AS metric_value,
           1800 AS threshold,
           CASE WHEN metric_value < 1800 THEN 'PASS' ELSE 'WARN' END AS verdict
    UNION ALL
    SELECT 'KPI-34', 'Order-Line Coverage',
           (SELECT count(*) FROM fact_order_item) * 1.0 / 
           (SELECT count(*) FROM fact_order) / 3,  -- avg ~3 lines per order
           ...
) scores
WHERE dw_batch_id = :batch_id;
```

#### CLI Scorecard Output

```powershell
python -m zwiggy_dwh.cli scorecard
```

**Output:**
```
DATA QUALITY SCORECARD
  batch_id  | 43
  run_type  | INCREMENTAL
  status    | SUCCEEDED
  published | true

KPI-33 Pipeline SLA              465 seconds (target 1800)          PASS
KPI-34 Order-Line Coverage       0.129 (12.9%, expected ~13%)       PASS
KPI-35 Status Consistency        0.890 (89.0%, expected >89%)       PASS
KPI-36 Amount Reconciliation     0.883 (88.3%, expected >88%)       PASS
KPI-37 Payment Retry Rate        0.061 (6.1%, expected ~6%)        PASS
KPI-38 Delivery Timeline         0.924 (92.4%, expected >92%)      PASS
KPI-39 Active Customers          125,432                            INFO
KPI-40 Quarantine Rate           0.0001 (0.01%, threshold 0.5%)    PASS
KPI-41 Restaurant Concentration 0.871 (87.1% top restaurant)       INFO
KPI-42 Cohort Mix                A: 12.9% / B: 87.1%              INFO
```

---

### 6. **Blocking Rules & Severity Levels**

**What:** Classify DQ rules by consequence to enable intelligent enforcement.

#### Severity Levels

| Severity | Meaning | Consequence | Example Rule |
|----------|---------|-----------|--------------|
| **BLOCK** | Data cannot be published | Publish gate closes; Gold unchanged; batch is PUBLISH_BLOCKED | DQ-R01 (cast failures), DQ-R03 (NULL business key), DQ-R09 (duplicate payment) |
| **QUARANTINE** | Row-level flag; loaded with caveat | Row loaded with `dw_is_quarantined = true` and `dw_quarantine_reason`; counted in KPI-40 | DQ-R04 (unknown status), DQ-R05 (invalid email) |
| **WARN** | Informational; never fails | Row loaded as-is; counted on scorecard; never blocks publish | DQ-R34, DQ-R35, DQ-R36 (expected source defects per BRD-B §12.1) |

#### Blocking Rule Threshold

A BLOCK rule with a threshold of 0.05 (5%) means:
- Failure rate ≤ 5% → verdict='PASS' (publish approved)
- Failure rate > 5% → verdict='FAIL' (publish blocked)

Example:
```python
# DQ-R03: Business keys not null
# severity=BLOCK, threshold=0
# If even 1 customer_id is NULL, verdict='FAIL' and publish is blocked
```

---

## Handoff Points

### ✅ Receives from Pipeline Orchestration Skill:

1. **Open Batch** — Batch ID and cutoff timestamp
2. **Bronze Data** — All 18 tables fully loaded and reconciled
3. **Silver Data** — All 17 entities typed, conformed, deduplicated
4. **Gold Data** — All dimensions, facts, marts loaded
5. **Step Log Records** — Rows read/written per step for row-count lineage

### ✅ Provides to Pipeline Orchestration Skill:

1. **DQ Results** — All 27 rules evaluated with verdict (PASS/FAIL)
2. **Reconciliation Results** — All 10 checks with verdict (PASS/FAIL)
3. **Publish Gate Decision** — True if all BLOCK rules and recon checks passed, false otherwise
4. **Run Report Summaries** — DQ and recon sections for CLI output

### ✅ Provides to CLI Layer:

1. **Scorecard Data** — KPI-33 through KPI-42 for display
2. **Status Query Results** — DQ failures, recon failures, blocking reasons

---

## Implementation Files

### Core Python Modules
- **`dwh/src/zwiggy_dwh/dq.py`** — DQ rule engine, batch rules, rule recording, scorecard
- **`dwh/src/zwiggy_dwh/reconcile.py`** — 10 reconciliation checks, verdict logic, result recording

### SQL Files
- **`dwh/sql/silver/012_seed_dq_rules.sql`** — Seed the 27 DQ rules into `silver.dq_rule`
- **`dwh/sql/silver/020_entity_ddl.sql`** — Create `*_quarantine` tables for each entity
- **`dwh/sql/gold/020_semantic_layer.sql`** — Create `sem_dq_scorecard` view

### CLI Entry Point
- **`dwh/src/zwiggy_dwh/cli.py`** — `cmd_scorecard()`, scorecard display logic

---

## Usage & Commands

### View DQ Scorecard
```powershell
cd dwh
$env:PYTHONPATH = "$PWD\src"
python -m zwiggy_dwh.cli scorecard
```

**Output:** 10 KPIs with metric, threshold, verdict.

### Query Reconciliation Results
```sql
SELECT check_id, target_object, expected_value, actual_value, variance, verdict, detail
  FROM ctl.ctl_reconciliation
 WHERE dw_batch_id = (SELECT max(dw_batch_id) FROM ctl.ctl_batch)
   AND verdict = 'FAIL';
```

### Query DQ Results
```sql
SELECT dq_rule_id, target_object, rows_evaluated, rows_failed, verdict, detail
  FROM ctl.ctl_dq_result
 WHERE dw_batch_id = (SELECT max(dw_batch_id) FROM ctl.ctl_batch)
   AND verdict = 'FAIL' AND severity = 'BLOCK';
```

### Query Quarantine
```sql
-- Which entities have quarantined rows this batch?
SELECT entity, count(*) as quarantined_rows
  FROM silver.slv_customer_quarantine
 WHERE dw_batch_id = (SELECT max(dw_batch_id) FROM ctl.ctl_batch)
 GROUP BY entity;

-- What's the reason?
SELECT dw_quarantine_reason, count(*) as count
  FROM silver.slv_customer_quarantine
 WHERE dw_batch_id = (SELECT max(dw_batch_id) FROM ctl.ctl_batch)
 GROUP BY dw_quarantine_reason;

-- Replay quarantine rows after reference data fix
INSERT INTO silver.slv_customer (...)
SELECT dw_batch_id, ..., TRY_CAST(customer_id AS bigint), ...
  FROM silver.slv_customer_quarantine
 WHERE dw_quarantine_reason LIKE 'cast:%';
```

---

## Test Coverage

### Unit Tests (`tests/test_unit.py`)
- ✓ Configuration loading and validation
- ✓ (Pending: Rule evaluation logic)

### Integration Tests (Pending)
- All 27 DQ rules evaluate correctly
- Reconciliation checks pass with valid data
- Publish blocked when DQ or recon fails
- Quarantine rows are captured and counted
- Scorecards are generated and accurate
- Threshold enforcement works (e.g., 5% failure rate)

---

## Error Handling & Recovery

| Failure | Detection | Recovery |
|---------|-----------|----------|
| DQ rule fails (BLOCK severity) | verdict='FAIL' in dq_result | Fix the source data or rule; re-run with `--replay` |
| Reconciliation check fails | verdict='FAIL' in ctl_reconciliation | Fix the load SQL or merge logic; re-run with `--replay` |
| Quarantine rate exceeds threshold (KPI-40) | verdict='FAIL' for KPI-40 | Investigate quarantine reason; fix and replay |
| Dimension resolution fails (RC-6) | High share of SK=-1 | Check dimension load logs; fix and re-run |
| SCD2 overlap (RC-8) | Gaps or overlaps in valid_from/valid_to | Do NOT hand-edit; re-run with `--replay` from known good Bronze |
| Duplicate rows at fact grain (RC-7) | Duplicates found by GROUP BY | Code defect; fix merge key in fact SQL; re-run with `--replay` |

---

## Traceability to BRD-B

| BRD-B §Section | Requirement | Implementation |
|---|---|---|
| §9 | DQ rules and engine | `dq.py:run_rules()`, 27 rules in `silver.dq_rule` |
| §9.1 | Data-driven rule catalogue | `silver.dq_rule` table (rows, not code) |
| §9.3 | Quarantine mechanism | `*_quarantine` tables, `dw_quarantine_reason`, `dw_raw_payload` |
| §9.4 | Reconciliation checks RC-1 … RC-10 | `reconcile.py:run_all()` |
| §12.1 | Expected source defects | Scorecard KPI-35 through KPI-42 (WARN rules) |
| §12.2 | DQ scorecard (KPI-33 … KPI-42) | `gold.sem_dq_scorecard` view, `cli scorecard` command |
| P-2 | No silent row loss | RC-2 check: loaded + quarantined + rejected ≥ bronze |
| P-3 | Publish gate | `pipeline.py:run()` blocks if any BLOCK rule or recon check fails |
| S-1 | Quarantine for non-conformant rows | Silver load SQL routes failures to `*_quarantine` |
| BR-R3 | Order status conformance | DQ-R04, mapped via `ref_payment_method_map` |
| BR-R5 | Payment retry collapse | S-24 enforced; DQ-R09 checks uniqueness after merge |
| BR-R6 | Delivery dedup | S-25 enforced; DQ-R19 validates delivery timeline |

---

## Success Criteria

✓ All 27 DQ rules execute without error  
✓ All 10 reconciliation checks complete  
✓ Blocking rules prevent publish when thresholds violated  
✓ Quarantine rows captured with reason and payload  
✓ Scorecard (KPI-33 … KPI-42) generated and accurate  
✓ Publish gate decision correct (block iff any FAIL)  
✓ Publish flag flipped only after all checks pass  
✓ No silent data quality degradation  
✓ Prior good version remains served while publish is blocked  
✓ Quarantine rows replayable without re-extraction  

---

## Related Skills

- **Pipeline Orchestration & Monitoring** — Invokes DQ and reconciliation phases; checks gate before publish
- **Warehouse Foundation & Configuration** — Provides control plane tables (ctl_dq_result, ctl_reconciliation, etc.)

---

## References

- BRD-B: Business Requirements Document, Zwiggy Medallion Warehouse
- README.md: Project overview, key features
- RUNBOOK.md: Operational procedures, investigating DQ failures
- `dwh/src/zwiggy_dwh/`: Core Python modules
- `dwh/sql/`: All DDL, transformation SQL, and seeds

