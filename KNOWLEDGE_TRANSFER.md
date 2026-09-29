# Zwiggy Medallion Data Warehouse - Knowledge Transfer (KT) Guide

Welcome to the **Knowledge Transfer (KT) Guide** for the Zwiggy Medallion Data Warehouse. This guide is tailored for junior developers, data engineers, and analysts onboarding to the project.

---

## 1. Core Concepts Explained Simply

### 🏆 What is the Medallion Architecture?
The Medallion Architecture is a design pattern used to structure data in a lakehouse or data warehouse into three distinct layers based on data quality:
1. **Bronze (Raw)**: Acts as the landing zone. Source data is landed as-is without modification. If source data has bad formatting, it still lands successfully without breaking the pipeline.
2. **Silver (Cleansed & Conformed)**: Raw data is cleaned, validated, filtered, and transformed into structured relational tables. Malformed records missing primary keys are routed to quarantine tables.
3. **Gold (Curated Business Layer)**: Data is modeled into star-schema dimension and fact tables optimized for business reporting, BI dashboards, and analytics.

### ⏱️ What is Slowly Changing Dimension Type 2 (SCD2)?
In business analytics, entity attributes change over time (e.g., a customer updates their address or email). SCD Type 2 preserves historical changes by inserting a new row instead of overwriting the existing row:
- `dw_is_current = TRUE` indicates the currently active record version.
- `valid_from` and `valid_to` define the historical time window during which that record version was active.

### 🔐 What is PII Masking?
Personally Identifiable Information (PII) like email addresses and phone numbers must be protected for privacy compliance. In Silver layer transformations, `silver.mask_pii()` redacts sensitive strings before data reaches Gold tables.

---

## 2. Codebase Sitemap & File Responsibilities

All Python source code resides in `dwh/src/zwiggy_dwh/`:

```
dwh/src/zwiggy_dwh/
├── config.py       --> Environment settings, DbTarget connection containers, paths.
├── db.py           --> PostgreSQL connections, retry wrapper with backoff, context managers.
├── init_db.py      --> SQL script execution sequence & static dim_date/dim_time seeding.
├── batch.py        --> Batch control lifecycle (open_batch, close_batch, watermarking).
├── bronze.py       --> Raw extraction engine (patterns E1-E5) and Bronze table loading.
├── silver.py       --> Conforming, PII masking, data sanitization & quarantine routing.
├── gold.py         --> SCD2 dimension tracking, fact table loading & daily summary marts.
├── dq.py           --> Data Quality rule evaluation engine & scorecard logging.
├── reconcile.py    --> 10 reconciliation check functions (RC-1 through RC-10).
├── metadata.py     --> Source schema contract verification & drift detection.
├── pipeline.py     --> Master 12-step pipeline orchestrator & publish gate decision logic.
└── cli.py          --> Command Line Interface commands (init, run, status, scorecard).
```

---

## 3. Step-by-Step Hands-On Tutorial

### Exercise 1: Run Unit Tests
1. Open your terminal and navigate to the project directory:
   ```bash
   cd /config/Desktop/buildwithgemini-zwiggy-medallion-dwh/dwh
   ```
2. Run pytest:
   ```bash
   PYTHONPATH=src ./venv/bin/pytest -v
   ```
3. Observe all 12 test assertions passing.

### Exercise 2: Inspect a Source File
1. Open `dwh/src/zwiggy_dwh/bronze.py` in your editor.
2. Read the line-by-line comments above `build_extraction_plan()`.
3. Understand how `E1` (timestamp incremental) vs `E5` (full snapshot) patterns construct different SQL WHERE clauses.

### Exercise 3: Run the CLI Status Command
1. In your terminal, run:
   ```bash
   PYTHONPATH=src ./venv/bin/python3 -m zwiggy_dwh.cli status
   ```
2. View recent pipeline batch runs and table watermarks.
