from zwiggy_dwh.dq import DqResult


def test_dq_result_dataclass():
    res = DqResult(
        rule_id="DQ-R01",
        target_object="slv_customer",
        rows_evaluated=100,
        rows_failed=0,
        failure_rate=0.0,
        threshold=0.0,
        severity="BLOCK",
        verdict="PASS",
        details="Evaluated 100 rows"
    )
    assert res.rule_id == "DQ-R01"
    assert res.verdict == "PASS"
    assert res.failure_rate == 0.0
