"""Complete 12-step Data Pipeline Orchestrator for Zwiggy Medallion Data Warehouse.

This module orchestrates the end-to-end data lifecycle across three Medallion architecture layers:
  1. Bronze Layer: Raw ingestion from operational source tables (E1-E5 extraction patterns).
  2. Silver Layer: Typed, conformed, deduplicated, and cleansed relational tables with quarantine routing.
  3. Gold Layer: Dimensional model with SCD Type 2 tracking, facts, and aggregated business marts.
  4. Data Quality & Reconciliation Gate: Enforces 27 DQ rules and 10 reconciliation checks before publishing data to downstream consumers.
"""

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
    """Execution summary report capturing metrics, counts, and validation results for a pipeline run.
    
    Attributes:
        batch_id (int): Unique identifier assigned to the current execution batch.
        run_type (str): Type of run ('FULL', 'INCREMENTAL', or 'REPLAY').
        status (str): Current execution state ('RUNNING', 'SUCCEEDED', 'PUBLISH_BLOCKED', or 'FAILED').
        published (bool): True if data passed all publish gate checks and was served to Gold consumers.
        bronze_counts (Dict[str, int]): Map of table names to raw extracted row counts landed in Bronze.
        silver_counts (Dict[str, dict]): Summary of rows processed, clean, and quarantined in Silver.
        gold_counts (Dict[str, int]): Record counts inserted/updated in Gold dimensions and facts.
        dq_results (List[DqResult]): Detailed verdicts for all 27 Data Quality rules evaluated.
        recon_results (List[ReconCheck]): Detailed verdicts for all 10 reconciliation checks executed.
        errors (List[str]): List of error messages or exception tracebacks captured during execution.
    """
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
    """Execute preflight safety, connectivity, and source schema contract verification.
    
    Returns:
        bool: True if source schema matches expected contract and connection is healthy.
    """
    logger.info("Executing preflight safety checks...")
    contract_ok = verify_contract()
    if not contract_ok:
        logger.error("Preflight check failed: Source database contract verification failed.")
        return False
    logger.info("✓ Preflight checks passed successfully.")
    return True


def run(
    run_type: str = "INCREMENTAL",
    cutoff: Optional[datetime] = None,
    force_full: bool = False,
    skip_gold: bool = False
) -> RunReport:
    """Execute the full 12-step data pipeline sequence with publish gate validation.

    Args:
        run_type (str): Execution mode ('INCREMENTAL', 'FULL', or 'REPLAY'). Default 'INCREMENTAL'.
        cutoff (Optional[datetime]): Optional ISO cutoff timestamp override for historical windowing.
        force_full (bool): If True, ignores stored watermarks and forces full source extraction.
        skip_gold (bool): If True, stops pipeline execution after Silver layer and DQ validation.

    Returns:
        RunReport: Comprehensive execution report containing row counts, DQ verdicts, and publish state.
    """

    # --- Step 1: Preflight Verification ---
    # Validates database connectivity, source table existence, and column structural integrity.
    if not preflight():
        raise RuntimeError("Pipeline run aborted due to preflight failure.")

    # --- Step 2: Open Batch Control Tracking ---
    # Registers a new batch record in `ctl.ctl_batch` to maintain watermark state and run audit logs.
    batch = open_batch(run_type, cutoff)
    report = RunReport(batch_id=batch.batch_id, run_type=run_type)

    try:
        # --- Step 3: Extract & Bronze Layer Ingestion ---
        # Extracts raw data from 18 source tables using patterns E1 (Append), E2 (Key Incremental),
        # E3 (Timestamp Incremental), E4 (CDC), and E5 (Full Snapshot). Landed in JSONB/Raw Bronze.
        logger.info("Step 1/6: Extract & Bronze Ingestion")
        report.bronze_counts = run_extract_and_bronze(batch, force_full=force_full)

        # --- Step 4: Silver Layer Conforming & Cleansing ---
        # Transforms raw Bronze payload into typed relational Silver schema. Appliess deduplication,
        # data type casting, surrogate key preparation, and quarantine routing for malformed records.
        logger.info("Step 2/6: Silver Conforming & Transformations")
        report.silver_counts = run_silver(batch)

        # --- Step 5: Data Quality Rule Evaluation ---
        # Evaluates 27 DQ rules (null checks, range constraints, enum validations, referential checks).
        logger.info("Step 3/6: Data Quality Rule Evaluation")
        report.dq_results = run_rules(batch)

        # --- Step 6: Gold Layer Dimensional Modeling ---
        # Builds Gold star-schema tables: SCD Type 2 dimensions (`dim_customer`, `dim_restaurant`),
        # transaction facts (`fact_order`, `fact_order_item`), and monthly aggregate marts.
        if not skip_gold:
            logger.info("Step 4/6: Gold Dimensional Modeling")
            report.gold_counts = run_gold(batch)

        # --- Step 7: Reconciliation Checks ---
        # Runs 10 reconciliation checks (RC-1 through RC-10) validating row count integrity,
        # revenue metric equality between Bronze/Silver/Gold, and surrogate key coverage.
        logger.info("Step 5/6: Reconciliation Checks")
        report.recon_results = run_reconciliation(batch)

        # --- Step 8: Publish Gate Decision & Batch Closure ---
        # Evaluates severe DQ failures and reconciliation breaches before permitting data release.
        dq_blocking_failures = [r for r in report.dq_results if r.verdict == "FAIL" and r.severity == "BLOCK"]
        recon_failures = [r for r in report.recon_results if r.verdict == "FAIL"]

        if dq_blocking_failures or recon_failures:
            # If critical errors exist, block publish to prevent corrupted data from reaching serving layer.
            report.status = "PUBLISH_BLOCKED"
            report.published = False
            mark_published(batch, False)
            notes = f"Publish blocked: {len(dq_blocking_failures)} DQ blocking failures, {len(recon_failures)} Recon failures."
            close_batch(batch, "PUBLISH_BLOCKED", notes=notes)
            logger.warning("Pipeline completed with PUBLISH_BLOCKED state. %s", notes)
        else:
            # All validation gates passed cleanly. Advance watermarks and publish data to consumers.
            report.status = "SUCCEEDED"
            report.published = True
            mark_published(batch, True)
            close_batch(batch, "SUCCEEDED", notes="Run completed and published successfully.")
            logger.info("✓ Pipeline run SUCCEEDED and published.")

    except Exception as e:
        # Catch unexpected pipeline runtime exceptions, log error, and mark batch FAILED.
        report.status = "FAILED"
        report.errors.append(str(e))
        close_batch(batch, "FAILED", notes=f"Run failed with exception: {e}")
        logger.error("Pipeline run FAILED: %s", e)
        raise

    return report
