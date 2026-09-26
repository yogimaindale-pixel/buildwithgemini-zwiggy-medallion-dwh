from datetime import datetime, timezone
from zwiggy_dwh.batch import Batch, StepResult


def test_batch_dataclass():
    now = datetime.now(timezone.utc)
    b = Batch(batch_id=101, run_type="INCREMENTAL", cutoff=now)
    assert b.batch_id == 101
    assert b.run_type == "INCREMENTAL"
    assert b.cutoff == now


def test_step_result_dataclass():
    res = StepResult(step_name="bronze_load", target_object="customer")
    assert res.step_name == "bronze_load"
    assert res.target_object == "customer"
    assert res.status == "SUCCEEDED"
    assert res.rows_read == 0
