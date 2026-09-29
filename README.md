# Zwiggy Medallion Data Warehouse (Simplified & Annotated Edition)

Welcome to the **Zwiggy Medallion Data Warehouse**, built with PostgreSQL, Python, and the Medallion Architecture pattern (Bronze, Silver, Gold). This codebase has been simplified, modularized, and annotated with **line-by-line comments** so that developers of all experience levels—from junior engineers to enterprise architects—can easily understand data pipeline orchestration, data quality gates, and reconciliation frameworks.

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- **Python 3.10+** installed on your local machine.
- **PostgreSQL 14+** running locally or via Docker.
- Basic terminal/bash knowledge.

### 2. Environment Setup

Clone or copy the repository to your local directory:
```bash
cd /config/Desktop/buildwithgemini-zwiggy-medallion-dwh/dwh
```

Initialize virtual environment and install dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pytest
```

Configure environment variables by creating or editing `.env`:
```env
PG_HOST=localhost
PG_PORT=5432
PG_DATABASE=zwiggy_db
PG_USER=postgres
PG_PASSWORD=postgres
```

### 3. Execution Commands

#### Run Unit Test Suite
Verify that all 12 test cases pass cleanly:
```bash
PYTHONPATH=src ./venv/bin/pytest -v
```

#### Run Warehouse CLI Subcommands
Initialize warehouse schemas, lookup tables, and date/time dimensions:
```bash
PYTHONPATH=src ./venv/bin/python3 -m zwiggy_dwh.cli init
```

Execute an incremental data pipeline run:
```bash
PYTHONPATH=src ./venv/bin/python3 -m zwiggy_dwh.cli run
```

Execute a full reload run:
```bash
PYTHONPATH=src ./venv/bin/python3 -m zwiggy_dwh.cli run --full
```

Check pipeline run history and source watermarks:
```bash
PYTHONPATH=src ./venv/bin/python3 -m zwiggy_dwh.cli status
```

Display latest Data Quality Scorecard:
```bash
PYTHONPATH=src ./venv/bin/python3 -m zwiggy_dwh.cli scorecard
```

---

## 🏗️ Architecture Overview

The pipeline follows a **Medallion Data Lakehouse & Warehouse Architecture**:

```
 Source OLTP (18 Tables)
         │
         ▼
 🟤 Bronze Layer (Raw Ingestion / br_*)
         │
         ▼
 ⚪ Silver Layer (Cleansed, Conformed & PII Masked / slv_*) ──► Quarantine Tables
         │
         ▼
 🟢 Data Quality & Reconciliation Gate (27 Rules & 10 Checks)
         │
         ▼ (Publish Gate)
 🟡 Gold Layer (SCD2 Dimensions, Facts & Business Marts)
```

---

## 📚 Documentation Index

- **[DOCUMENTATION.md](./DOCUMENTATION.md)**: Technical specifications, database schemas, business rules, DQ checks, and reconciliation suite matrix.
- **[KNOWLEDGE_TRANSFER.md](./KNOWLEDGE_TRANSFER.md)**: Junior developer guide, concept tutorials, codebase walkthrough, and step-by-step hands-on exercises.

---

## 🧪 Testing & Verification

The test suite validates:
1. Dataclass immutability (`DbTarget`, `Batch`, `StepResult`, `DqResult`, `ReconCheck`).
2. Extraction plan generation for incremental vs full snapshot modes.
3. Command Line Interface subcommands (`init`, `run`, `status`, `scorecard`).

To execute tests anytime:
```bash
PYTHONPATH=src ./venv/bin/pytest -v
```
