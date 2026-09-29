# Zwiggy Medallion Data Warehouse - Technical Documentation

This document details the architecture, relational database schemas, data pipeline flow, business rules, Data Quality (DQ) rules engine, and reconciliation checks for the Zwiggy Medallion Data Warehouse.

---

## 1. System Architecture & Medallion Layers

The data warehouse processes food delivery OLTP transactions through three progressive quality layers:

```
+-----------------------------------------------------------------------------------+
|                                 SOURCE OLTP (PostgreSQL)                          |
|  customers | restaurants | order_header | order_payment | delivery_agents | ...    |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼ (E1-E5 Extraction Patterns)
+-----------------------------------------------------------------------------------+
|                                BRONZE LAYER (bronze.br_*)                         |
| Raw landed payloads in TEXT columns with audit metadata (dw_batch_id, dw_ingest_ts)|
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼ (Type Casting, PII Masking, Deduplication)
+-----------------------------------------------------------------------------------+
|                                SILVER LAYER (silver.slv_*)                        |
| Conformed relational tables. Malformed records routed to quarantine tables.       |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼ (27 DQ Rules + 10 Reconciliation Checks)
+-----------------------------------------------------------------------------------+
|                             QUALITY & RECONCILIATION GATE                         |
| Blocks publication if BLOCK-severity DQ rules or reconciliation checks fail.      |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼ (Publish Gate Approved)
+-----------------------------------------------------------------------------------+
|                                  GOLD LAYER (gold.*)                              |
| SCD Type 2 Dimensions (dim_*), Star-Schema Facts (fact_*), & Aggregate Marts      |
+-----------------------------------------------------------------------------------+
```

---

## 2. Table Schemas & Layer Specifications

### 🟤 Bronze Layer (`bronze`)
- **Schema Strategy**: Land raw source columns as `TEXT` to prevent ingestion failures.
- **Audit Metadata**:
  - `dw_batch_id BIGINT`: Pipeline execution batch identifier.
  - `dw_ingest_ts_utc TIMESTAMPTZ`: Ingestion wall-clock timestamp.
  - `dw_source_table VARCHAR`: Source table name.
  - `dw_extract_pattern VARCHAR`: Pattern code (`E1` through `E5`).
  - `dw_row_number BIGSERIAL`: Sequential row number.

### ⚪ Silver Layer (`silver`)
- **Primary Tables**:
  - `silver.slv_customer`: Cleansed customer profiles with PII masked (`mask_pii()` hash function).
  - `silver.slv_restaurant`: Restaurant master data with cuisine and city attributes.
  - `silver.slv_order`: Order headers with normalized status (`PLACED`, `DELIVERED`, `CANCELLED`) and business cohort mapping.
  - `silver.slv_payment`: Payment transactions mapped via `ref_payment_method_map`.
- **Quarantine Tables**:
  - `silver.slv_customer_quarantine`: Stores raw JSON payload for records missing `customer_id`.
  - `silver.slv_order_quarantine`: Stores raw JSON payload for records missing `order_id`.

### 🟢 Gold Layer (`gold`)
- **Dimensions**:
  - `gold.dim_customer` (SCD Type 2): Tracks customer name and contact changes over time with `valid_from`, `valid_to`, `dw_is_current`, and `dw_version`.
  - `gold.dim_restaurant` (SCD Type 2): Tracks restaurant city, cuisine, and activity status.
  - `gold.dim_date`: Static date dimension table (date keys e.g. `20260101`).
  - `gold.dim_time`: Static time dimension table (minute resolution `0` through `1439`).
- **Fact Tables**:
  - `gold.fact_order`: Order transaction facts linked to surrogate keys (`customer_sk`, `restaurant_sk`, `order_date_sk`, `order_time_sk`). Unknown foreign keys fallback to `-1`.
  - `gold.fact_payment`: Payment transactions linked to `order_sk`.
- **Semantic Data Marts**:
  - `gold.mart_daily_business_summary`: Aggregated daily revenue, total orders, discount totals, and unique active customers.

---

## 3. Data Quality Engine (27 Rules)

The pipeline evaluates 27 Data Quality rules registered in `silver.dq_rule`. Key rules include:
- **Null Checks**: Primary keys must not be null (`customer_id IS NOT NULL`).
- **Range Constraints**: Financial amounts must be non-negative (`total_amount >= 0`).
- **Enum Conformance**: Status values must match expected sets (`order_status IN ('PLACED', 'CONFIRMED', 'DELIVERED', 'CANCELLED')`).
- **Severity Levels**:
  - `BLOCK`: Failure blocks batch publication to Gold consumers.
  - `WARN`: Logged to scorecard, pipeline proceeds.

---

## 4. Reconciliation Suite (10 Checks)

1. **RC-1 (Extract to Bronze)**: Validates extracted count equals landed Bronze count.
2. **RC-2 (Bronze to Silver)**: Validates Bronze rows = Silver loaded + quarantined.
3. **RC-3 (Silver to Gold Fact Order)**: Validates Silver order count equals Fact order count.
4. **RC-6 (Foreign Key Resolution Rate)**: Validates unknown surrogate key (`customer_sk=-1`) share is <= 5%.
5. **RC-7 (Fact Uniqueness)**: Validates zero duplicate `order_id` records in `fact_order`.
6. **RC-8 (SCD2 Date Non-Overlap)**: Validates zero overlapping active date ranges in `dim_customer`.
7. **RC-9 (Mart to Fact Row Count)**: Validates daily business summary order total equals fact order total.
8. **RC-10 (Gold Freshness)**: Validates latest Gold fact timestamp freshness.
