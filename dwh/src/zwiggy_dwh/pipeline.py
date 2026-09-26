"""Complete 12-step Data Pipeline Orchestrator."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional

from zwiggy_dwh.batch import Batch, close_batch, mark_published, open_batch
from zwiggy_dwh.bronze import run_extract_and_bronze
from zwiggy_dwh.dq import DqResult, run_rules
from zwiggy_dwh.gold import run_gold
from zwiggy_dwh.metadata import verify_contract
from zwiggy_dwh.reconcile import ReconCheck, run_reconciliation
from zwiggy_dwh.silver import run_silver

logger = logging.getLogger(__name__)


@dataclass
class RunReport:
    """Run execution summary report."""
    batch_id: int
    run_type: str
    status: str = "RUNNING"
    published: bool = False
    bronze_counts: Dict[str, int] = field(default_factory=dict)
    silver_counts: Dict[str, dict] = field(default_factory=dict)
    gold_counts: Dict[str, int] = field(default_factory=dict)
    dq_results: List[DqResult] = field(default_factory=list)
    recon_results: List[ReconCheck] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def preflight() -> bool:
    """Execute preflight safety and connectivity checks."""
    logger.info("Executing preflight checks...")
    contract_ok = verify_contract()
    if not contract_ok:
        logger.error("Preflight check failed: Source database contract verification failed.")
        return False
    logger.info("✓ Preflight checks passed.")
    return True


def run(
    run_type: str = "INCREMENTAL",
    cutoff: Optional[datetime] = None,
    force_full: bool = False,
    skip_gold: bool = False
) -> RunReport:
    """Execute full 12-step data pipeline sequence."""

    # 1. Preflight check
    if not preflight():
        raise RuntimeError("Pipeline run aborted due to preflight failure.")

    # 2. Open Batch
    batch = open_batch(run_type, cutoff)
    report = RunReport(batch_id=batch.batch_id, run_type=run_type)

    try:
        # 3. Extract & Bronze load
        logger.info("Step 1/6: Extract & Bronze Ingestion")
        report.bronze_counts = run_extract_and_bronze(batch, force_full=force_full)

        # 4. Silver Load
        logger.info("Step 2/6: Silver Conforming & Transformations")
        report.silver_counts = run_silver(batch)

        # 5. Silver DQ Rules
        logger.info("Step 3/6: Data Quality Rule Evaluation")
        report.dq_results = run_rules(batch)

        # 6. Gold Layer
        if not skip_gold:
            logger.info("Step 4/6: Gold Dimensional Modeling")
            report.gold_counts = run_gold(batch)

        # 7. Reconciliation
        logger.info("Step 5/6: Reconciliation Checks")
        report.recon_results = run_reconciliation(batch)

        # 8. Publish Gate Decision
        dq_blocking_failures = [r for r in report.dq_results if r.verdict == "FAIL" and r.severity == "BLOCK"]
        recon_failures = [r for r in report.recon_results if r.verdict == "FAIL"]

        if dq_blocking_failures or recon_failures:
            report.status = "PUBLISH_BLOCKED"
            report.published = False
            mark_published(batch, False)
            notes = f"Publish blocked: {len(dq_blocking_failures)} DQ blocking failures, {len(recon_failures)} Recon failures."
            close_batch(batch, "PUBLISH_BLOCKED", notes=notes)
            logger.warning("Pipeline completed with PUBLISH_BLOCKED state. %s", notes)
        else:
            report.status = "SUCCEEDED"
            report.published = True
            mark_published(batch, True)
            close_batch(batch, "SUCCEEDED", notes="Run completed and published successfully.")
            logger.info("✓ Pipeline run SUCCEEDED and published.")

    except Exception as e:
        report.status = "FAILED"
        report.errors.append(str(e))
        close_batch(batch, "FAILED", notes=f"Run failed with exception: {e}")
        logger.error("Pipeline run FAILED: %s", e)
        raise

    return report
