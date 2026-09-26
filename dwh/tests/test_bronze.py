from datetime import datetime, timezone
from zwiggy_dwh.batch import Batch
from zwiggy_dwh.bronze import build_extraction_plan


def test_build_extraction_plan_full():
    now = datetime.now(timezone.utc)
    batch = Batch(batch_id=1, run_type="FULL", cutoff=now)
    table_cfg = {
        "source_table": "customer",
        "extraction_pattern": "E1",
        "watermark_column": "updated_at",
        "lookback_days": 7
    }
    plan = build_extraction_plan(table_cfg, force_full=True, batch=batch)
    assert plan.predicate == "1=1"
    assert plan.pattern == "E1"


def test_build_extraction_plan_snapshot_pattern():
    now = datetime.now(timezone.utc)
    batch = Batch(batch_id=1, run_type="INCREMENTAL", cutoff=now)
    table_cfg = {
        "source_table": "menu_category",
        "extraction_pattern": "E3",
        "watermark_column": None,
        "lookback_days": 0
    }
    plan = build_extraction_plan(table_cfg, force_full=False, batch=batch)
    assert plan.predicate == "1=1"
    assert plan.pattern == "E3"
