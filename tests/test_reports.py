"""Tests for HTML and PDF report generation."""

from pathlib import Path
import pytest

from datasentinel.core.types import (
    RuleResult,
    RuleType,
    RunSummary,
    Severity,
    ValidationStatus,
)
from datasentinel.reports.generator import ReportGenerator
from datasentinel.reports.pdf_exporter import PDFReportExporter


@pytest.fixture
def dummy_run_summary() -> RunSummary:
    """Fixture providing a mock RunSummary."""
    return RunSummary(
        run_id="test-run-12345678",
        dataset_name="demo_dataset",
        status=ValidationStatus.PASSED,
        duration_seconds=0.45,
        total_rows=1000,
        total_columns=5,
        total_rules=2,
        passed_rules=2,
        failed_rules=0,
        warning_rules=0,
        overall_pass_rate=100.0,
        schema_drift_detected=False,
        total_anomalies=0,
        rule_results=[
            RuleResult(
                rule_name="id_not_null",
                rule_type=RuleType.NULL_CHECK,
                column="id",
                passed=True,
                total_checked=1000,
                violation_count=0,
                pass_rate=100.0,
                severity=Severity.CRITICAL,
                message="All rows non-null",
            ),
            RuleResult(
                rule_name="id_unique",
                rule_type=RuleType.UNIQUE_CHECK,
                column="id",
                passed=True,
                total_checked=1000,
                violation_count=0,
                pass_rate=100.0,
                severity=Severity.ERROR,
                message="All values unique",
            ),
        ],
    )


def test_html_report_generation(tmp_path: Path, dummy_run_summary: RunSummary) -> None:
    generator = ReportGenerator()
    html_out = tmp_path / "report.html"

    result_path = generator.generate_html_report(dummy_run_summary, html_out)
    assert result_path.exists()
    content = result_path.read_text(encoding="utf-8")

    assert "demo_dataset" in content
    assert "chart.umd.min.js" in content
    assert "id_not_null" in content
    assert "100.0%" in content


def test_pdf_report_generation(tmp_path: Path, dummy_run_summary: RunSummary) -> None:
    generator = ReportGenerator()
    pdf_out = tmp_path / "report.pdf"

    result_path = generator.generate_pdf_report(dummy_run_summary, pdf_out)
    assert result_path.exists()
    assert result_path.stat().st_size > 500  # Valid non-empty PDF binary


def test_generate_all(tmp_path: Path, dummy_run_summary: RunSummary) -> None:
    generator = ReportGenerator()
    html_p, pdf_p = generator.generate_all(dummy_run_summary, tmp_path)
    assert html_p.exists()
    assert pdf_p.exists()
