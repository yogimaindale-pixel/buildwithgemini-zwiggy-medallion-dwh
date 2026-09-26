---
title: "Antigravity Skills for Zwiggy Medallion DWH"
description: "Three modular skills enabling Antigravity to build, test, and validate the Zwiggy Medallion Data Warehouse end-to-end"
version: "1.0.0"
created: "2025-01-01"
---

# Antigravity Skills — Zwiggy Medallion Data Warehouse

Welcome to the **Antigravity Skills Package** for the Zwiggy Medallion Data Warehouse project. This directory contains three carefully designed, modular skills that enable Antigravity (or any sophisticated automated agent) to build, test, validate, and operate the complete data warehouse end-to-end.

## 📁 Directory Structure

```
.agents/
└── skills/
    ├── warehouse-foundation/
    │   └── SKILL.md              # Skill 1: Infrastructure setup, configuration, initialization
    ├── pipeline-orchestration/
    │   └── SKILL.md              # Skill 2: Daily run execution, extraction, monitoring
    ├── data-quality-reconciliation/
    │   └── SKILL.md              # Skill 3: Validation, DQ rules, reconciliation, publish gate
    ├── SKILLS_SUMMARY.md         # High-level overview and integration guide
    ├── VALIDATION_REPORT.md      # Comprehensive validation and checklist
    └── README.md                 # This file
```

---

## 🎯 The Three Skills at a Glance

### Skill 1: Warehouse Foundation & Configuration
**When to Use:** Before any data pipeline runs, during initial setup and configuration management.

**What It Does:**
- Loads and validates configuration from `.env` file
- Establishes secure, guarded connections to source and warehouse
- Initializes four medallion schemas (ctl, bronze, silver, gold)
- Generates and applies DDL from source schema
- Seeds reference data (27 DQ rules, 18 table configs, mappings)
- Sets up batch lifecycle framework and logging

**Key Deliverables:**
- Validated configuration object
- Open, guarded database connections (source read-only, warehouse read/write)
- Initialized warehouse with 50+ tables
- Batch lifecycle framework for subsequent runs

**Files:** `config.py`, `db.py`, `batch.py`, `init_db.py`, `sql/ctl/`, `sql/silver/010-015/`, `sql/gold/001/`

---

### Skill 2: Pipeline Orchestration & Monitoring
**When to Use:** During daily pipeline execution, extraction, transformation, and monitoring.

**What It Does:**
- Orchestrates the complete 12-step pipeline sequence
- Implements 5 extraction patterns (E1–E5): incremental and snapshot modes
- Manages batch lifecycle and watermark state for idempotency
- Loads and transforms Bronze → Silver → Gold layers
- Coordinates layer dependencies and parallel execution where possible
- Provides operational monitoring, status reporting, and scorecards

**Key Deliverables:**
- Extracted and landed data in Bronze layer
- Typed, conformed, and deduplicated Silver data
- Dimensional model (SCD2) and facts in Gold
- Watermark advances for incremental efficiency
- Run summary with counts, execution time, and status

**Files:** `pipeline.py`, `bronze.py`, `silver.py`, `gold.py`, `metadata.py`, `sql/silver/load/`, `sql/gold/load/`

---

### Skill 3: Data Quality & Reconciliation
**When to Use:** After all data is extracted and transformed; before approving publish to serving layer.

**What It Does:**
- Executes 27 data quality rules with row-level and batch-level evaluation
- Runs 10 reconciliation checks (RC-1 through RC-10) for end-to-end integrity
- Routes invalid rows to quarantine (never dropped, always replayable)
- Enforces publish gate: blocks unsafe data from reaching consumers
- Generates and publishes scorecards (KPI-33 through KPI-42)
- Provides audit trail for all validation decisions

**Key Deliverables:**
- DQ rule evaluation results (27 rules × verdicts)
- Reconciliation check results (10 checks × verdicts)
- Publish gate decision (SUCCEEDED, PUBLISH_BLOCKED, or FAILED)
- Quarantine summary with reasons
- Scorecards for operational dashboards

**Files:** `dq.py`, `reconcile.py`, `sql/silver/012_seed_dq_rules.sql`, `sql/gold/020_semantic_layer.sql`

---

## 🔗 Skill Integration Flow

```
Setup Phase
┌─────────────────────────────────────────┐
│ Skill 1: Warehouse Foundation           │
│ • Load .env & validate                  │
│ • Connect to source & warehouse         │
│ • Initialize schemas & DDL              │
│ • Seed reference data                   │
└────────────────┬────────────────────────┘
                 │ (Provides: config, connections, schemas)
                 ↓
Execution Phase
┌─────────────────────────────────────────┐
│ Skill 2: Pipeline Orchestration         │
│ • Preflight checks                      │
│ • Extract 18 tables (E1–E5 patterns)    │
│ • Load Bronze → Silver → Gold layers    │
│ • Log steps, advance watermarks         │
└────────────────┬────────────────────────┘
                 │ (Provides: extracted data, row counts, batch state)
                 ↓
Validation Phase
┌─────────────────────────────────────────┐
│ Skill 3: Data Quality & Reconciliation  │
│ • Evaluate 27 DQ rules                  │
│ • Execute 10 reconciliation checks      │
│ • Decide publish gate (BLOCK or OK)     │
│ • Generate scorecards                   │
└─────────────────────────────────────────┘
                 │ (Provides: validation results, gate decision)
                 ↓
         Publish Decision
       (Serve data to consumers
        or continue blocking)
```

---

## 🚀 Quick Start for Antigravity

### 1. Read the Skills in Order
```
1. warehouse-foundation/SKILL.md     (5–10 minutes)
2. pipeline-orchestration/SKILL.md   (10–15 minutes)
3. data-quality-reconciliation/SKILL.md (10–15 minutes)
4. SKILLS_SUMMARY.md                 (5 minutes)
```

### 2. Understand the Data Flow
Read the "Handoff Points & Data Contracts" section in SKILLS_SUMMARY.md to understand:
- What each skill receives as input
- What each skill produces as output
- How data flows from one skill to the next

### 3. Start with Initialization
```powershell
# Activates Skill 1: Warehouse Foundation
cd dwh
$env:PYTHONPATH = "$PWD\src"
python -m zwiggy_dwh.cli init
```

### 4. Run the Pipeline
```powershell
# Activates Skill 2: Pipeline Orchestration
python -m zwiggy_dwh.cli run
```

### 5. Validate Results
```powershell
# Activates Skill 3: Data Quality & Reconciliation (automatic)
# View status and scorecard
python -m zwiggy_dwh.cli status
python -m zwiggy_dwh.cli scorecard
```

---

## 📋 Key Principles

### Modularity
- **Clear Boundaries:** Each skill owns one domain; no overlapping responsibilities
- **Explicit Handoffs:** All data contracts and activation conditions documented
- **Independent Execution:** Each skill can be understood and executed independently

### Data-Driven Design
- **Externalised Configuration:** All parameters in `.env`, not code
- **Reference Data:** Cohort boundary, mappings, DQ rules stored in database
- **Metadata:** Schema shape, extraction patterns, watermarks all managed via tables

### Safety & Observability
- **Publish Gate:** Blocks unsafe data automatically; prior good version remains served
- **Quarantine:** Invalid rows never dropped; always replayable
- **Idempotency:** Re-running same batch produces identical state
- **Audit Trail:** Every step, every decision, every rule evaluation logged

### Resilience
- **Retry Logic:** Transient failures retried with exponential backoff
- **Per-Table Isolation:** One table's failure doesn't stop others
- **Concurrent Prevention:** Only one run allowed at a time; explicit recovery

---

## 📚 Documentation Organization

| Document | Purpose | Audience |
|----------|---------|----------|
| **warehouse-foundation/SKILL.md** | Detailed setup instructions | Antigravity, DevOps, Infrastructure Engineers |
| **pipeline-orchestration/SKILL.md** | Daily run orchestration | Antigravity, Data Engineers, Orchestration Platforms |
| **data-quality-reconciliation/SKILL.md** | Validation and quality governance | Antigravity, Data Stewards, Quality Engineers |
| **SKILLS_SUMMARY.md** | Integration and workflows | Antigravity, Architects, Project Leads |
| **VALIDATION_REPORT.md** | Completeness and traceability | Architects, QA, Compliance |
| **README.md** (this file) | Getting started | Everyone |

---

## ✅ Before You Start

### Prerequisites
- PostgreSQL 18 server running
- `zwiggy_db` source database with 18 tables and 336,751+ rows seeded
- Python 3.11+ installed
- `.env` file in project root with:
  ```bash
  PG_HOST=localhost
  PG_PORT=5432
  PG_DATABASE=zwiggy_db
  PG_USER=<your_user>
  PG_PASSWORD=<your_password>
  ```

### Verify Setup
```powershell
cd dwh
$env:PYTHONPATH = "$PWD\src"

# Check Python
python --version              # Should be 3.11+

# Install dependencies
pip install -r requirements.txt

# Validate configuration
python -c "from zwiggy_dwh.config import settings; s = settings(); print('✓ Config OK')"
```

---

## 🎓 Learning Path

### For Antigravity Agents
1. **Read all three SKILL.md files** — Understand the complete project scope
2. **Study SKILLS_SUMMARY.md** — Understand how skills interconnect
3. **Review project files** (README.md, RUNBOOK.md, BRD-B) — Deep domain knowledge
4. **Execute workflows** in order (init → run → validate)
5. **Review VALIDATION_REPORT.md** — Ensure you're meeting all success criteria

### For Human Reviewers
1. **Read VALIDATION_REPORT.md** — Confirm completeness
2. **Skim SKILLS_SUMMARY.md** — Understand integration
3. **Spot-check one skill** — e.g., warehouse-foundation/SKILL.md
4. **Review BRD-B traceability** — Confirm requirements mapped
5. **Approve for deployment**

---

## 📞 Support & Clarification

Each SKILL.md includes:
- **Decision Rules:** How to choose between approaches
- **Error-Handling Rules:** What to do if something fails
- **Validation Requirements:** How to verify your work
- **Final Checklist:** Measurable completion criteria
- **Prohibited Actions:** What NOT to do

**Key files to consult:**
- `.agents/skills/warehouse-foundation/SKILL.md` — For setup questions
- `.agents/skills/pipeline-orchestration/SKILL.md` — For execution questions
- `.agents/skills/data-quality-reconciliation/SKILL.md` — For validation questions
- `dwh/RUNBOOK.md` — For operational procedures and troubleshooting

---

## 🔍 Validation Checklist

After reading the skills, you should be able to answer:

- [ ] What does Skill 1 (Warehouse Foundation) own?
- [ ] When should Skill 2 (Pipeline Orchestration) run?
- [ ] What does Skill 3 (Data Quality & Reconciliation) do before publish?
- [ ] What data flows from Skill 1 to Skill 2?
- [ ] What data flows from Skill 2 to Skill 3?
- [ ] How are the three skills non-overlapping in responsibility?
- [ ] What happens if a DQ rule fails?
- [ ] How are invalid rows handled?
- [ ] What is the publish gate?
- [ ] How do you roll back if something goes wrong?

---

## 📊 Project Scope

**Project:** Zwiggy Medallion Data Warehouse  
**Technology:** Python 3.13, PostgreSQL 18  
**Architecture:** Bronze → Silver → Gold medallion pattern  
**Data Volume:** 18 source tables, 336,751+ rows  
**Transformations:** 5 extraction patterns, 27 DQ rules, 10 reconciliation checks  
**Output:** SCD2 dimensions, dimensional facts, aggregate marts  
**Status:** 90% complete, 35 unit tests passing, integration tests pending  

---

## 📝 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-01-01 | Initial release of three modular skills for Antigravity |

---

## 🔐 Important Security Notes

- **Never commit `.env`** — It contains real credentials (gitignore active)
- **Source is read-only** — Session-level `default_transaction_read_only = on` applied
- **No PII in logs** — Passwords masked in CLI output
- **No hardcoded secrets** — All credentials externalised to `.env`

---

## 📄 License & Attribution

These skills are part of the Zwiggy Medallion Data Warehouse project, developed as a production-ready ETL solution. All BRD-B requirements and transformations are documented and traced.

---

**For questions or clarifications, consult the detailed SKILL.md files and cross-reference with the project documentation (README.md, RUNBOOK.md, BRD-B).**

**Ready to build? Start with the Warehouse Foundation skill!** 🚀

