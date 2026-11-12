"""Rule executor orchestrating quality validations over datasets."""

from typing import Callable, List, Optional
import time

from datasentinel.config.schema import RuleConfig
from datasentinel.connectors.base import DataSet
from datasentinel.core.exceptions import RuleExecutionError
from datasentinel.core.types import RuleResult, Severity, ValidationStatus
from datasentinel.rules.base import RuleRegistry


class RuleExecutor:
    """Executes a suite of quality rules over a loaded DataSet."""

    def __init__(self, rules: List[RuleConfig]) -> None:
        self.rules: List[RuleConfig] = rules

    def execute_all(
        self,
        dataset: DataSet,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[RuleResult]:
        """Execute all configured quality rules.

        Args:
            dataset: The loaded DataSet to evaluate.
            progress_callback: Optional callback(current, total, rule_name) for UI progress bars.

        Returns:
            List of RuleResult objects for every rule.
        """
        results: List[RuleResult] = []
        total = len(self.rules)

        for index, rule_config in enumerate(self.rules, start=1):
            if progress_callback:
                progress_callback(index, total, rule_config.name)

            try:
                validator = RuleRegistry.create(rule_config)
                result = validator.evaluate(dataset)
                results.append(result)
            except Exception as exc:
                # Fallback error result
                err_msg = str(exc)
                results.append(
                    RuleResult(
                        rule_name=rule_config.name,
                        rule_type=rule_config.type,
                        column=rule_config.column,
                        passed=False,
                        total_checked=dataset.row_count,
                        violation_count=dataset.row_count,
                        pass_rate=0.0,
                        severity=Severity.CRITICAL,
                        message=f"ERROR during evaluation: {err_msg}",
                        parameters=rule_config.parameters,
                    )
                )

        return results

    @staticmethod
    def calculate_status(results: List[RuleResult]) -> ValidationStatus:
        """Derive overall ValidationStatus from rule execution results."""
        if not results:
            return ValidationStatus.PASSED

        has_critical_or_error = any(
            (not r.passed) and (r.severity in (Severity.ERROR, Severity.CRITICAL))
            for r in results
        )
        if has_critical_or_error:
            return ValidationStatus.FAILED

        has_warning = any((not r.passed) and (r.severity == Severity.WARNING) for r in results)
        if has_warning:
            return ValidationStatus.WARNING

        return ValidationStatus.PASSED
