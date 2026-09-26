-- Semantic Layer Views

-- 1. sem_trust_header: Executive summary view of pipeline and warehouse health
CREATE OR REPLACE VIEW gold.sem_trust_header AS
SELECT
    b.dw_batch_id,
    b.run_type,
    b.status AS batch_status,
    b.published,
    b.start_ts_utc,
    b.end_ts_utc,
    ROUND(EXTRACT(EPOCH FROM (COALESCE(b.end_ts_utc, NOW()) - b.start_ts_utc))::numeric, 2) AS duration_seconds,
    (SELECT COUNT(*) FROM ctl.ctl_dq_result WHERE dw_batch_id = b.dw_batch_id AND verdict = 'FAIL') AS total_dq_failures,
    (SELECT COUNT(*) FROM ctl.ctl_reconciliation WHERE dw_batch_id = b.dw_batch_id AND verdict = 'FAIL') AS total_recon_failures
FROM ctl.ctl_batch b
ORDER BY b.dw_batch_id DESC;

-- 2. sem_dq_scorecard: Detailed DQ rule compliance view
CREATE OR REPLACE VIEW gold.sem_dq_scorecard AS
SELECT
    r.dw_batch_id,
    r.rule_id,
    r.target_object,
    r.rows_evaluated,
    r.rows_failed,
    r.failure_rate,
    r.threshold,
    r.severity,
    r.verdict,
    r.details,
    r.created_ts_utc
FROM ctl.ctl_dq_result r;
