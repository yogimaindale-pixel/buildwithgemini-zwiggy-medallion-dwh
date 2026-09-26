-- Create Control Plane Tables

-- 1. ctl_batch: Pipeline batch executions
CREATE TABLE IF NOT EXISTS ctl.ctl_batch (
    dw_batch_id BIGSERIAL PRIMARY KEY,
    run_type VARCHAR(20) NOT NULL DEFAULT 'INCREMENTAL',
    cutoff_ts_utc TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'RUNNING',
    published BOOLEAN NOT NULL DEFAULT FALSE,
    start_ts_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    end_ts_utc TIMESTAMPTZ,
    code_version VARCHAR(20),
    notes TEXT
);

-- 2. ctl_step_log: Execution steps per batch
CREATE TABLE IF NOT EXISTS ctl.ctl_step_log (
    step_id BIGSERIAL PRIMARY KEY,
    dw_batch_id BIGINT NOT NULL REFERENCES ctl.ctl_batch(dw_batch_id),
    step_name VARCHAR(100) NOT NULL,
    target_object VARCHAR(100),
    rows_read INT DEFAULT 0,
    rows_written INT DEFAULT 0,
    rows_quarantined INT DEFAULT 0,
    rows_rejected INT DEFAULT 0,
    duration_ms INT DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'SUCCEEDED',
    error_text TEXT,
    created_ts_utc TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. ctl_watermark: Watermarks per source table
CREATE TABLE IF NOT EXISTS ctl.ctl_watermark (
    watermark_id BIGSERIAL PRIMARY KEY,
    dw_batch_id BIGINT NOT NULL REFERENCES ctl.ctl_batch(dw_batch_id),
    source_table VARCHAR(100) NOT NULL,
    watermark_value VARCHAR(100) NOT NULL,
    updated_ts_utc TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. ctl_extract_manifest: Manifest of extracted row counts
CREATE TABLE IF NOT EXISTS ctl.ctl_extract_manifest (
    manifest_id BIGSERIAL PRIMARY KEY,
    dw_batch_id BIGINT NOT NULL REFERENCES ctl.ctl_batch(dw_batch_id),
    source_table VARCHAR(100) NOT NULL,
    pattern VARCHAR(10) NOT NULL,
    extracted_rows INT NOT NULL DEFAULT 0,
    watermark_value VARCHAR(100),
    extracted_ts_utc TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. ctl_reconciliation: Reconciliation check results
CREATE TABLE IF NOT EXISTS ctl.ctl_reconciliation (
    recon_id BIGSERIAL PRIMARY KEY,
    dw_batch_id BIGINT NOT NULL REFERENCES ctl.ctl_batch(dw_batch_id),
    check_id VARCHAR(20) NOT NULL,
    check_name VARCHAR(100) NOT NULL,
    expected_value NUMERIC,
    actual_value NUMERIC,
    variance NUMERIC,
    verdict VARCHAR(20) NOT NULL, -- PASS, FAIL, SKIP
    details TEXT,
    created_ts_utc TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. ctl_dq_result: Data quality rule evaluation results
CREATE TABLE IF NOT EXISTS ctl.ctl_dq_result (
    dq_result_id BIGSERIAL PRIMARY KEY,
    dw_batch_id BIGINT NOT NULL REFERENCES ctl.ctl_batch(dw_batch_id),
    rule_id VARCHAR(20) NOT NULL,
    target_object VARCHAR(100) NOT NULL,
    rows_evaluated INT NOT NULL DEFAULT 0,
    rows_failed INT NOT NULL DEFAULT 0,
    failure_rate NUMERIC(7,4) DEFAULT 0,
    threshold NUMERIC(7,4),
    severity VARCHAR(20) NOT NULL, -- BLOCK, QUARANTINE, WARN
    verdict VARCHAR(20) NOT NULL, -- PASS, FAIL
    details TEXT,
    created_ts_utc TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 7. ctl_table_config: Source table configuration metadata
CREATE TABLE IF NOT EXISTS ctl.ctl_table_config (
    source_table VARCHAR(100) PRIMARY KEY,
    extraction_pattern VARCHAR(10) NOT NULL, -- E1, E2, E3, E4, E5
    watermark_column VARCHAR(100),
    lookback_days INT DEFAULT 0,
    primary_key VARCHAR(100),
    expected_rows INT DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);
