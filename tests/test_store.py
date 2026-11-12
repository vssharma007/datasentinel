"""Tests for SQLite-backed validation result store and trend analysis."""

from pathlib import Path
import pytest

from datasentinel.core.types import RunSummary, ValidationStatus
from datasentinel.store.result_store import ResultStore


def test_result_store_record_and_query(tmp_path: Path) -> None:
    db_file = tmp_path / "test_history.db"
    store = ResultStore(db_path=db_file)

    summary1 = RunSummary(
        run_id="run-001",
        dataset_name="sales_data",
        status=ValidationStatus.PASSED,
        duration_seconds=0.25,
        total_rows=100,
        total_columns=4,
        total_rules=5,
        passed_rules=5,
        failed_rules=0,
        warning_rules=0,
        overall_pass_rate=100.0,
        schema_drift_detected=False,
        total_anomalies=0,
    )

    summary2 = RunSummary(
        run_id="run-002",
        dataset_name="sales_data",
        status=ValidationStatus.FAILED,
        duration_seconds=0.30,
        total_rows=120,
        total_columns=4,
        total_rules=5,
        passed_rules=3,
        failed_rules=2,
        warning_rules=0,
        overall_pass_rate=60.0,
        schema_drift_detected=True,
        total_anomalies=4,
    )

    store.record_run(summary1)
    store.record_run(summary2)

    history = store.get_history(dataset_name="sales_data")
    assert len(history) == 2
    assert history[0].run_id == "run-002"  # Descending order

    trend = store.get_trend("sales_data")
    assert trend["pass_rates"] == [100.0, 60.0]
    assert trend["anomalies"] == [0, 4]
