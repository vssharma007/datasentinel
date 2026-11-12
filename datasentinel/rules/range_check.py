"""Range check rule executor."""

from typing import List, Optional
import pandas as pd

from datasentinel.connectors.base import DataSet
from datasentinel.core.types import RuleResult, RuleType, ViolationSample
from datasentinel.rules.base import BaseRule, RuleRegistry


@RuleRegistry.register(RuleType.RANGE)
class RangeCheckRule(BaseRule):
    """Validates that column values fall within YAML-configured [min, max] bounds."""

    def evaluate(self, dataset: DataSet) -> RuleResult:
        self._validate_column_exists(dataset)
        df = dataset.dataframe
        col = self.column
        total = len(df)

        min_val = self.config.parameters.get("min_value")
        max_val = self.config.parameters.get("max_value")
        inclusive = bool(self.config.parameters.get("inclusive", True))

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
                message="Dataset is empty; range check skipped.",
                parameters=self.config.parameters,
            )

        # Convert to numeric if possible
        series = pd.to_numeric(df[col], errors="coerce")
        valid_numeric_mask = series.notnull()

        violation_mask = pd.Series(False, index=df.index)

        # Any non-null value that could not be parsed as numeric is flagged as a range violation
        non_null_mask = df[col].notnull()
        non_numeric_violations = non_null_mask & (~valid_numeric_mask)
        violation_mask |= non_numeric_violations

        if min_val is not None:
            min_num = float(min_val)
            if inclusive:
                violation_mask |= valid_numeric_mask & (series < min_num)
            else:
                violation_mask |= valid_numeric_mask & (series <= min_num)

        if max_val is not None:
            max_num = float(max_val)
            if inclusive:
                violation_mask |= valid_numeric_mask & (series > max_num)
            else:
                violation_mask |= valid_numeric_mask & (series >= max_num)

        violation_count = int(violation_mask.sum())
        pass_rate = round(((total - violation_count) / total) * 100.0, 2)
        passed = violation_count == 0

        samples: List[ViolationSample] = []
        if not passed:
            violation_rows = df[violation_mask].head(10)
            for idx, val in zip(violation_rows.index, violation_rows[col]):
                bounds_str = f"[{min_val if min_val is not None else '-inf'}, {max_val if max_val is not None else '+inf'}]"
                samples.append(
                    ViolationSample(
                        row_index=int(idx),
                        column=col,
                        value=str(val),
                        reason=f"Value {val} falls outside expected range {bounds_str}",
                    )
                )

        bound_desc = f"range [{min_val}, {max_val}]"
        status_msg = (
            f"PASSED: All {total} rows comply with {bound_desc}."
            if passed
            else f"FAILED: {violation_count}/{total} rows fall outside {bound_desc}."
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
