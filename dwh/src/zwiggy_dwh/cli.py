# Module docstring explaining Command Line Interface for Zwiggy Medallion Data Warehouse
"""Command Line Interface for Zwiggy Medallion Data Warehouse."""

# Import argparse module for parsing command line arguments and flags
import argparse
# Import datetime module for parsing ISO format timestamp overrides
from datetime import datetime
# Import logging for operational log formatting
import logging
# Import sys module for stdout log stream handler
import sys

# Import batch close helper and database query connection utilities
from zwiggy_dwh.batch import close_batch
from zwiggy_dwh.db import fetch_all, warehouse_connection
from zwiggy_dwh.init_db import init_warehouse
from zwiggy_dwh.pipeline import run

# Configure root logger format and output destination
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
# Obtain CLI logger instance
logger = logging.getLogger("zwiggy_dwh.cli")

# Subcommand handler function for warehouse initialization ('init')
def cmd_init(args):
    """Run warehouse initialization."""
    logger.info("Initializing Zwiggy Medallion Data Warehouse...")
    init_warehouse()

# Subcommand handler function for executing pipeline pipeline run ('run')
def cmd_run(args):
    """Run pipeline execution."""
    cutoff = datetime.fromisoformat(args.cutoff) if args.cutoff else None
    run_type = "FULL" if args.full else ("REPLAY" if args.replay else "INCREMENTAL")

    logger.info("Starting pipeline run (type=%s)...", run_type)
    report = run(
        run_type=run_type,
        cutoff=cutoff,
        force_full=args.full,
        skip_gold=args.skip_gold
    )

    # Print clean formatted text summary of pipeline run metrics
    print("\n" + "=" * 60)
    print(f"PIPELINE RUN SUMMARY (Batch ID: {report.batch_id})")
    print("=" * 60)
    print(f"Status:    {report.status}")
    print(f"Published: {report.published}")
    print(f"Bronze:    {sum(report.bronze_counts.values())} rows extracted")
    print(f"DQ Rules:  {len(report.dq_results)} evaluated")
    print(f"Recon:     {len(report.recon_results)} checks executed")
    print("=" * 60 + "\n")

# Subcommand handler displaying recent pipeline batches and watermarks ('status')
def cmd_status(args):
    """Display latest pipeline run status and watermarks."""
    with warehouse_connection() as conn:
        batches = fetch_all(conn, "SELECT dw_batch_id, run_type, status, published, start_ts_utc, end_ts_utc FROM ctl.ctl_batch ORDER BY dw_batch_id DESC LIMIT 10")
        watermarks = fetch_all(conn, "SELECT source_table, watermark_value, updated_ts_utc FROM ctl.ctl_watermark ORDER BY source_table")

    print("\n--- RECENT BATCH RUNS ---")
    for b in batches:
        print(f"Batch {b['dw_batch_id']:<4} | Type: {b['run_type']:<11} | Status: {b['status']:<15} | Published: {str(b['published']):<5} | Start: {b['start_ts_utc']}")

    print("\n--- CURRENT WATERMARKS ---")
    for w in watermarks:
        print(f"Table: {w['source_table']:<25} | Watermark: {w['watermark_value']:<30} | Updated: {w['updated_ts_utc']}")
    print("")

# Subcommand handler displaying Data Quality scorecard records ('scorecard')
def cmd_scorecard(args):
    """Display latest Data Quality Scorecard."""
    with warehouse_connection() as conn:
        scorecard = fetch_all(conn, "SELECT * FROM gold.sem_dq_scorecard ORDER BY created_ts_utc DESC LIMIT 30")

    print("\n--- DATA QUALITY SCORECARD ---")
    for r in scorecard:
        print(f"[{r['verdict']:<4}] Rule: {r['rule_id']:<8} | Target: {r['target_object']:<20} | Failed: {r['rows_failed']}/{r['rows_evaluated']} ({r['failure_rate']:.2%}) | Severity: {r['severity']}")
    print("")

# Main entrypoint configuring argparse subparsers and invoking command handlers
def main():
    parser = argparse.ArgumentParser(description="Zwiggy Medallion Data Warehouse CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subparser for 'init' command
    parser_init = subparsers.add_parser("init", help="Initialize warehouse schemas and reference data")
    parser_init.set_defaults(func=cmd_init)

    # Subparser for 'run' command
    parser_run = subparsers.add_parser("run", help="Execute pipeline run")
    parser_run.add_argument("--full", action="store_true", help="Force full reload mode")
    parser_run.add_argument("--replay", action="store_true", help="Replay transformation mode")
    parser_run.add_argument("--cutoff", type=str, help="ISO cutoff timestamp override")
    parser_run.add_argument("--skip-gold", action="store_true", help="Skip Gold layer processing")
    parser_run.set_defaults(func=cmd_run)

    # Subparser for 'status' command
    parser_status = subparsers.add_parser("status", help="Show recent run status and watermarks")
    parser_status.set_defaults(func=cmd_status)

    # Subparser for 'scorecard' command
    parser_scorecard = subparsers.add_parser("scorecard", help="Show DQ scorecard")
    parser_scorecard.set_defaults(func=cmd_scorecard)

    # Parse command line arguments and execute assigned function
    args = parser.parse_args()
    args.func(args)

# Execute main() if script is run directly from command line
if __name__ == "__main__":
    main()

