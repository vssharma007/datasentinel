"""Null check rule executor."""

from typing import Any, List
import pandas as pd

from datasentinel.config.schema import RuleConfig
from datasentinel.connectors.base import DataSet
from datasentinel.core.types import RuleResult, RuleType, ViolationSample
from datasentinel.rules.base import BaseRule, RuleRegistry


@RuleRegistry.register(RuleType.NULL_CHECK)
class NullCheckRule(BaseRule):
    """Validates that missing or null values do not exceed YAML-configured limits."""

    def evaluate(self, dataset: DataSet) -> RuleResult:
        self._validate_column_exists(dataset)
        df = dataset.dataframe
        col = self.column
        total = len(df)

        allow_null = bool(self.config.parameters.get("allow_null", False))
        max_null_pct = float(self.config.parameters.get("max_null_percentage", 0.0))
        max_null_count = self.config.parameters.get("max_null_count", None)
        if max_null_count is not None:
            max_null_count = int(max_null_count)

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
                message="Dataset is empty; null check skipped.",
                parameters=self.config.parameters,
            )

        null_mask = df[col].isnull()
        null_count = int(null_mask.sum())
        null_pct = (null_count / total) * 100.0
        pass_rate = round(100.0 - null_pct, 2)

        passed = True
        reason_parts: List[str] = []

        if not allow_null and null_count > 0:
            if max_null_count is not None and null_count > max_null_count:
                passed = False
                reason_parts.append(f"null count ({null_count}) > limit ({max_null_count})")
            elif max_null_count is None and null_pct > max_null_pct:
                passed = False
                reason_parts.append(f"null percentage ({null_pct:.2f}%) > threshold ({max_null_pct:.2f}%)")
            elif max_null_count is None and max_null_pct == 0.0:
                passed = False
                reason_parts.append(f"found {null_count} unexpected null values")

        samples: List[ViolationSample] = []
        if not passed:
            sample_indices = df[null_mask].index[:10]
            for idx in sample_indices:
                samples.append(
                    ViolationSample(
                        row_index=int(idx),
                        column=col,
                        value="NULL",
                        reason="Value is missing or null",
                    )
                )

        status_msg = (
            f"PASSED: Null check passed with {null_count}/{total} nulls ({null_pct:.2f}%)."
            if passed
            else f"FAILED: Null check violated - {', '.join(reason_parts)}."
        )

        return RuleResult(
            rule_name=self.name,
            rule_type=self.config.type,
            column=col,
            passed=passed,
            total_checked=total,
            violation_count=null_count,
            pass_rate=pass_rate,
            severity=self.config.severity,
            message=status_msg,
            samples=samples,
            parameters=self.config.parameters,
        )
