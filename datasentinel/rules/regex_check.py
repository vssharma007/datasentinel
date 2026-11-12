"""Regex pattern matching rule executor."""

import re
from typing import List
import pandas as pd

from datasentinel.connectors.base import DataSet
from datasentinel.core.exceptions import RuleExecutionError
from datasentinel.core.types import RuleResult, RuleType, ViolationSample
from datasentinel.rules.base import BaseRule, RuleRegistry


@RuleRegistry.register(RuleType.REGEX)
class RegexCheckRule(BaseRule):
    """Validates that string values match a configured regex pattern."""

    def evaluate(self, dataset: DataSet) -> RuleResult:
        self._validate_column_exists(dataset)
        df = dataset.dataframe
        col = self.column
        total = len(df)

        pattern = self.config.parameters.get("pattern")
        if not pattern:
            raise RuleExecutionError(
                f"Rule '{self.name}' requires 'pattern' parameter in YAML configuration.",
                details="Specify regex pattern under rule parameters.",
            )

        invert_match = bool(self.config.parameters.get("invert_match", False))
        case_sensitive = bool(self.config.parameters.get("case_sensitive", True))
        allow_null = bool(self.config.parameters.get("allow_null", False))

        if total == 0:
            return RuleResult(
                rule_name=self.name,
                rule_type=self.config.type,
                column=col,
                passed=True,
                total_checked=0,
                violation_count=0,
                pass_rate=100.0,
                severity=self.config.severity,
                message="Dataset is empty; regex check skipped.",
                parameters=self.config.parameters,
            )

        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            compiled_regex = re.compile(pattern, flags=flags)
        except re.error as exc:
            raise RuleExecutionError(
                f"Invalid regex pattern '{pattern}' in rule '{self.name}'",
                details=str(exc),
            ) from exc

        series = df[col].astype(str)
        is_null = df[col].isnull()

        def matches_pattern(val: str) -> bool:
            return bool(compiled_regex.match(val))

        matches = series.map(matches_pattern)

        if invert_match:
            # Violation if it DOES match
            violation_mask = matches
        else:
            # Violation if it DOES NOT match
            violation_mask = ~matches

        if allow_null:
            violation_mask = violation_mask & (~is_null)

        violation_count = int(violation_mask.sum())
        pass_rate = round(((total - violation_count) / total) * 100.0, 2)
        passed = violation_count == 0

        samples: List[ViolationSample] = []
        if not passed:
            violation_rows = df[violation_mask].head(10)
            for idx, val in zip(violation_rows.index, violation_rows[col]):
                samples.append(
                    ViolationSample(
                        row_index=int(idx),
                        column=col,
                        value=str(val),
                        reason=f"Value '{val}' fails regex pattern '{pattern}' (invert={invert_match})",
                    )
                )

        status_msg = (
            f"PASSED: All values match pattern '{pattern}'."
            if passed
            else f"FAILED: {violation_count}/{total} values do not conform to pattern '{pattern}'."
        )

        return RuleResult(
            rule_name=self.name,
            rule_type=self.config.type,
            column=col,
            passed=passed,
            total_checked=total,
            violation_count=violation_count,
            pass_rate=pass_rate,
            severity=self.config.severity,
            message=status_msg,
            samples=samples,
            parameters=self.config.parameters,
        )
