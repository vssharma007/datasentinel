"""Tests for Typer CLI commands and help texts."""

from pathlib import Path
from typer.testing import CliRunner
import pytest

from datasentinel.cli import app

runner = CliRunner()


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "validate" in result.stdout
    assert "compare-schemas" in result.stdout
    assert "register-schema" in result.stdout
    assert "list-rules" in result.stdout
    assert "history" in result.stdout
    assert "schedule" in result.stdout


def test_cli_list_rules_general() -> None:
    result = runner.invoke(app, ["list-rules"])
    assert result.exit_code == 0
    assert "null_check" in result.stdout
    assert "unique_check" in result.stdout
    assert "range" in result.stdout


def test_cli_validate_command(temp_yaml_config: Path) -> None:
    result = runner.invoke(app, ["validate", str(temp_yaml_config), "--no-alerts"])
    # Should run validation and exit with code 0 (all pass)
    assert result.exit_code == 0
    assert "Quality Rules Execution Summary" in result.stdout
    assert "Validation Status: PASSED" in result.stdout


def test_cli_register_and_compare_schema(temp_yaml_config: Path) -> None:
    reg_result = runner.invoke(app, ["register-schema", str(temp_yaml_config)])
    assert reg_result.exit_code == 0
    assert "Registered Schema Baseline Fingerprint" in reg_result.stdout

    cmp_result = runner.invoke(app, ["compare-schemas", str(temp_yaml_config)])
    assert cmp_result.exit_code == 0
    assert "matches baseline" in cmp_result.stdout


def test_cli_report_generation(tmp_path: Path, temp_yaml_config: Path) -> None:
    out_dir = tmp_path / "cli_reports"
    result = runner.invoke(app, ["report", str(temp_yaml_config), "-o", str(out_dir)])
    assert result.exit_code == 0
    assert out_dir.exists()
    assert len(list(out_dir.glob("*.html"))) == 1
    assert len(list(out_dir.glob("*.pdf"))) == 1


def test_cli_history() -> None:
    result = runner.invoke(app, ["history", "--limit", "5"])
    assert result.exit_code == 0
