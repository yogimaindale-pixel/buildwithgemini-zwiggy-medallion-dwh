from zwiggy_dwh.reconcile import ReconCheck


def test_recon_check_dataclass():
    check = ReconCheck(
        check_id="RC-1",
        check_name="Extract to Bronze Row Count Reconciliation",
        expected_value=100.0,
        actual_value=100.0,
        variance=0.0,
        verdict="PASS",
        details="Extracted 100 vs Bronze 100"
    )
    assert check.check_id == "RC-1"
    assert check.verdict == "PASS"
    assert check.variance == 0.0
