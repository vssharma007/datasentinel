"""Referential integrity cross-column check rule executor."""

from typing import Any, List, Set
import pandas as pd

from datasentinel.connectors.base import DataSet
from datasentinel.core.exceptions import RuleExecutionError
from datasentinel.core.types import RuleResult, RuleType, ViolationSample
from datasentinel.rules.base import BaseRule, RuleRegistry


@RuleRegistry.register(RuleType.FOREIGN_KEY)
class ForeignKeyCheckRule(BaseRule):
    """Validates referential integrity: values in target column must exist in reference values/column."""

    def evaluate(self, dataset: DataSet) -> RuleResult:
        self._validate_column_exists(dataset)
        df = dataset.dataframe
        col = self.column
        total = len(df)

        ref_col = self.config.parameters.get("reference_column")
        allowed_values_param = self.config.parameters.get("allowed_values")
        allow_null = bool(self.config.parameters.get("allow_null", True))

        if not ref_col and allowed_values_param is None:
            raise RuleExecutionError(
                f"Rule '{self.name}' requires either 'reference_column' or 'allowed_values' parameter in YAML.",
                details="Specify parent reference key in rule parameters.",
            )

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
                message="Dataset is empty; foreign key check skipped.",
                parameters=self.config.parameters,
            )

        valid_references: Set[Any] = set()

        if ref_col:
            if ref_col not in df.columns:
                raise RuleExecutionError(
                    f"Reference column '{ref_col}' does not exist in dataset '{dataset.name}'."
                )
            valid_references.update(df[ref_col].dropna().unique())

        if allowed_values_param and isinstance(allowed_values_param, list):
            valid_references.update(allowed_values_param)

        series = df[col]
        is_null = series.isnull()

        # Check membership
        is_valid_ref = series.isin(valid_references)

        if allow_null:
            violation_mask = (~is_valid_ref) & (~is_null)
        else:
            violation_mask = ~is_valid_ref

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
                        reason=f"Orphan key '{val}' not found in reference values for '{ref_col or 'allowed_values'}'",
                    )
                )

        ref_target = ref_col if ref_col else f"{len(valid_references)} allowed values"
        status_msg = (
            f"PASSED: All references in '{col}' resolve against '{ref_target}'."
            if passed
            else f"FAILED: Found {violation_count}/{total} orphan foreign key references not present in '{ref_target}'."
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
