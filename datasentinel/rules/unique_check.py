"""Uniqueness check rule executor."""

from typing import List
import pandas as pd

from datasentinel.connectors.base import DataSet
from datasentinel.core.types import RuleResult, RuleType, ViolationSample
from datasentinel.rules.base import BaseRule, RuleRegistry


@RuleRegistry.register(RuleType.UNIQUE_CHECK)
class UniqueCheckRule(BaseRule):
    """Validates uniqueness of values in specified column based on YAML configuration."""

    def evaluate(self, dataset: DataSet) -> RuleResult:
        self._validate_column_exists(dataset)
        df = dataset.dataframe
        col = self.column
        total = len(df)

        max_dup_pct = float(self.config.parameters.get("max_duplicate_percentage", 0.0))
        max_dup_count = self.config.parameters.get("max_duplicate_count", None)
        if max_dup_count is not None:
            max_dup_count = int(max_dup_count)
        allow_duplicates = bool(self.config.parameters.get("allow_duplicates", False))

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
                message="Dataset is empty; unique check skipped.",
                parameters=self.config.parameters,
            )

        # Detect duplicated values (excluding nulls if null check handles them separately, or including them)
        dup_mask = df.duplicated(subset=[col], keep=False)
        dup_count = int(dup_mask.sum())
        dup_pct = (dup_count / total) * 100.0
        pass_rate = round(100.0 - dup_pct, 2)

        passed = True
        reason_parts: List[str] = []

        if not allow_duplicates and dup_count > 0:
            if max_dup_count is not None and dup_count > max_dup_count:
                passed = False
                reason_parts.append(f"duplicate count ({dup_count}) > limit ({max_dup_count})")
            elif max_dup_count is None and dup_pct > max_dup_pct:
                passed = False
                reason_parts.append(
                    f"duplicate percentage ({dup_pct:.2f}%) > threshold ({max_dup_pct:.2f}%)"
                )

        samples: List[ViolationSample] = []
        if not passed:
            dup_rows = df[dup_mask].head(10)
            for idx, val in zip(dup_rows.index, dup_rows[col]):
                samples.append(
                    ViolationSample(
                        row_index=int(idx),
                        column=col,
                        value=str(val),
                        reason="Duplicate value found in unique constraint column",
                    )
                )

        status_msg = (
            f"PASSED: Unique check passed with {dup_count}/{total} duplicates ({dup_pct:.2f}%)."
            if passed
            else f"FAILED: Uniqueness violated - {', '.join(reason_parts)}."
        )

        return RuleResult(
            rule_name=self.name,
            rule_type=self.config.type,
            column=col,
            passed=passed,
            total_checked=total,
            violation_count=dup_count,
            pass_rate=pass_rate,
            severity=self.config.severity,
            message=status_msg,
            samples=samples,
            parameters=self.config.parameters,
        )
