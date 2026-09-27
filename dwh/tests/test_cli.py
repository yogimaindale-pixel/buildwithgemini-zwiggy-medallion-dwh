"""Unit tests for Zwiggy Medallion DWH CLI subcommands."""

import unittest
from unittest.mock import patch, MagicMock
from zwiggy_dwh.cli import main as cli_main

class TestCLI(unittest.TestCase):
    @patch("zwiggy_dwh.cli.init_warehouse")
    def test_cli_init_command(self, mock_init):
        test_args = ["zwiggy_cli", "init"]
        with patch("sys.argv", test_args):
            cli_main()
        mock_init.assert_called_once()

    @patch("zwiggy_dwh.cli.run")
    def test_cli_run_command_full(self, mock_run):
        mock_report = MagicMock()
        mock_report.batch_id = "BATCH_001"
        mock_report.status = "SUCCESS"
        mock_report.published = True
        mock_report.bronze_counts = {"orders": 100}
        mock_report.dq_results = []
        mock_report.recon_results = []
        mock_run.return_value = mock_report

        test_args = ["zwiggy_cli", "run", "--full"]
        with patch("sys.argv", test_args):
            cli_main()
        mock_run.assert_called_once_with(
            run_type="FULL",
            cutoff=None,
            force_full=True,
            skip_gold=False
        )

    @patch("zwiggy_dwh.cli.warehouse_connection")
    @patch("zwiggy_dwh.cli.fetch_all")
    def test_cli_status_command(self, mock_fetch_all, mock_conn):
        mock_fetch_all.side_effect = [
            [{"dw_batch_id": 1, "run_type": "FULL", "status": "SUCCESS", "published": True, "start_ts_utc": "2025-01-01"}],
            [{"source_table": "orders", "watermark_value": "2025-01-01", "updated_ts_utc": "2025-01-01"}]
        ]
        test_args = ["zwiggy_cli", "status"]
        with patch("sys.argv", test_args):
            cli_main()
        self.assertEqual(mock_fetch_all.call_count, 2)

    @patch("zwiggy_dwh.cli.warehouse_connection")
    @patch("zwiggy_dwh.cli.fetch_all")
    def test_cli_scorecard_command(self, mock_fetch_all, mock_conn):
        mock_fetch_all.return_value = [
            {"verdict": "PASS", "rule_id": "DQ-001", "target_object": "orders", "rows_failed": 0, "rows_evaluated": 100, "failure_rate": 0.0, "severity": "HIGH"}
        ]
        test_args = ["zwiggy_cli", "scorecard"]
        with patch("sys.argv", test_args):
            cli_main()
        mock_fetch_all.assert_called_once()

if __name__ == "__main__":
    unittest.main()
