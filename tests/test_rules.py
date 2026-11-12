"""Tests for quality rules and RuleExecutor."""

import pandas as pd
import pytest

from datasentinel.config.schema import RuleConfig
from datasentinel.connectors.base import DataSet
from datasentinel.core.exceptions import RuleExecutionError
from datasentinel.core.types import RuleType, Severity, ValidationStatus
from datasentinel.rules.executor import RuleExecutor
from datasentinel.rules.foreign_key_check import ForeignKeyCheckRule
from datasentinel.rules.null_check import NullCheckRule
from datasentinel.rules.range_check import RangeCheckRule
from datasentinel.rules.regex_check import RegexCheckRule
from datasentinel.rules.unique_check import UniqueCheckRule


def test_null_check_rule_pass(sample_dataset: DataSet) -> None:
    config = RuleConfig(
        name="no_null_ids",
        type=RuleType.NULL_CHECK,
        column="id",
        parameters={"allow_null": False},
    )
    rule = NullCheckRule(config)
    result = rule.evaluate(sample_dataset)
    assert result.passed is True
    assert result.violation_count == 0
    assert result.pass_rate == 100.0


def test_null_check_rule_fail() -> None:
    df = pd.DataFrame({"id": [1, None, 3, None]})
    ds = DataSet("test_nulls", df)
    config = RuleConfig(
        name="strict_no_nulls",
        type=RuleType.NULL_CHECK,
        column="id",
        parameters={"allow_null": False, "max_null_count": 0},
    )
    rule = NullCheckRule(config)
    result = rule.evaluate(ds)
    assert result.passed is False
    assert result.violation_count == 2
    assert len(result.samples) == 2


def test_unique_check_rule_pass(sample_dataset: DataSet) -> None:
    config = RuleConfig(
        name="unique_id",
        type=RuleType.UNIQUE_CHECK,
        column="id",
    )
    rule = UniqueCheckRule(config)
    result = rule.evaluate(sample_dataset)
    assert result.passed is True
    assert result.violation_count == 0


def test_unique_check_rule_fail() -> None:
    df = pd.DataFrame({"code": ["A", "B", "A", "C"]})
    ds = DataSet("test_duplicates", df)
    config = RuleConfig(
        name="unique_codes",
        type=RuleType.UNIQUE_CHECK,
        column="code",
        parameters={"allow_duplicates": False},
    )
    rule = UniqueCheckRule(config)
    result = rule.evaluate(ds)
    assert result.passed is False
    assert result.violation_count == 2
    assert len(result.samples) > 0


def test_range_check_rule_pass_and_fail() -> None:
    df = pd.DataFrame({"score": [50, 75, 120, -5, 90]})
    ds = DataSet("test_range", df)
    config = RuleConfig(
        name="score_between_0_100",
        type=RuleType.RANGE,
        column="score",
        parameters={"min_value": 0, "max_value": 100, "inclusive": True},
    )
    rule = RangeCheckRule(config)
    result = rule.evaluate(ds)
    assert result.passed is False
    # Offending rows: 120 and -5
    assert result.violation_count == 2
    assert result.pass_rate == 60.0


def test_regex_check_rule_email() -> None:
    df = pd.DataFrame(
        {
            "email": [
                "valid@corp.com",
                "invalid-email-at",
                "another.valid@domain.org",
                "bad@",
            ]
        }
    )
    ds = DataSet("test_regex", df)
    config = RuleConfig(
        name="email_format",
        type=RuleType.REGEX,
        column="email",
        parameters={"pattern": r"^[\w\.-]+@[\w\.-]+\.\w+$"},
    )
    rule = RegexCheckRule(config)
    result = rule.evaluate(ds)
    assert result.passed is False
    assert result.violation_count == 2
    assert result.pass_rate == 50.0


def test_foreign_key_check_allowed_values() -> None:
    df = pd.DataFrame({"status": ["OPEN", "CLOSED", "PENDING", "INVALID_STATUS"]})
    ds = DataSet("test_fk", df)
    config = RuleConfig(
        name="status_fk",
        type=RuleType.FOREIGN_KEY,
        column="status",
        parameters={"allowed_values": ["OPEN", "CLOSED", "PENDING"]},
    )
    rule = ForeignKeyCheckRule(config)
    result = rule.evaluate(ds)
    assert result.passed is False
    assert result.violation_count == 1
    assert result.samples[0].value == "INVALID_STATUS"


def test_missing_column_raises_error(sample_dataset: DataSet) -> None:
    config = RuleConfig(
        name="missing_col_rule",
        type=RuleType.NULL_CHECK,
        column="non_existent_column",
    )
    rule = NullCheckRule(config)
    with pytest.raises(RuleExecutionError, match="does not exist in dataset"):
        rule.evaluate(sample_dataset)


def test_rule_executor(sample_dataset: DataSet) -> None:
    rules = [
        RuleConfig(name="r1", type=RuleType.NULL_CHECK, column="id"),
        RuleConfig(name="r2", type=RuleType.RANGE, column="age", parameters={"min_value": 18}),
    ]
    executor = RuleExecutor(rules)
    results = executor.execute_all(sample_dataset)
    assert len(results) == 2
    assert all(r.passed for r in results)
    assert executor.calculate_status(results) == ValidationStatus.PASSED
