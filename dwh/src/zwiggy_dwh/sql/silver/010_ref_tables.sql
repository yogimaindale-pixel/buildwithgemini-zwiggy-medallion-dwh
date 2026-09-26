-- Silver Layer Reference Tables

-- 1. ref_cohort_rule: Cohort boundary rule (Cohort A / B split)
CREATE TABLE IF NOT EXISTS silver.ref_cohort_rule (
    cohort_id VARCHAR(10) PRIMARY KEY,
    min_order_id BIGINT,
    max_order_id BIGINT,
    description TEXT
);

-- 2. ref_payment_method_map: Status and payment method conformance mapping
CREATE TABLE IF NOT EXISTS silver.ref_payment_method_map (
    raw_payment_method VARCHAR(50) PRIMARY KEY,
    conformed_payment_method VARCHAR(50) NOT NULL,
    conformed_category VARCHAR(50) NOT NULL
);

-- 3. dq_rule: Data Quality Rule Catalogue (27 rules)
CREATE TABLE IF NOT EXISTS silver.dq_rule (
    rule_id VARCHAR(20) PRIMARY KEY,
    layer VARCHAR(20) NOT NULL, -- bronze, silver, gold
    target_object VARCHAR(100) NOT NULL,
    expression TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL, -- BLOCK, QUARANTINE, WARN
    threshold NUMERIC(7,4), -- max failure rate allowed (e.g. 0.05)
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    linked_finding VARCHAR(50),
    description TEXT
);
