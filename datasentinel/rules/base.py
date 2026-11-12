"""Base quality rule abstraction and registry."""

from abc import ABC, abstractmethod
from typing import Callable, Dict, List, Type
import pandas as pd

from datasentinel.config.schema import RuleConfig
from datasentinel.connectors.base import DataSet
from datasentinel.core.exceptions import RuleExecutionError
from datasentinel.core.types import RuleResult, RuleType, ViolationSample


class BaseRule(ABC):
    """Abstract base class for all data quality validation rules."""

    def __init__(self, config: RuleConfig) -> None:
        self.config: RuleConfig = config

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def column(self) -> str:
        return self.config.column

    def _validate_column_exists(self, dataset: DataSet) -> None:
        """Verify target column is present in the dataset."""
        if self.column not in dataset.column_names:
            raise RuleExecutionError(
                f"Rule '{self.name}' failed: Column '{self.column}' does not exist in dataset '{dataset.name}'.",
                details=f"Available columns: {', '.join(dataset.column_names)}",
            )

    @abstractmethod
    def evaluate(self, dataset: DataSet) -> RuleResult:
        """Execute validation against dataset and return RuleResult."""


class RuleRegistry:
    """Registry for pluggable quality rules."""

    _registry: Dict[RuleType, Type[BaseRule]] = {}

    @classmethod
    def register(cls, rule_type: RuleType) -> Callable[[Type[BaseRule]], Type[BaseRule]]:
        """Register a rule executor for a specific RuleType."""

        def decorator(subclass: Type[BaseRule]) -> Type[BaseRule]:
            cls._registry[rule_type] = subclass
            return subclass

        return decorator

    @classmethod
    def create(cls, config: RuleConfig) -> BaseRule:
        """Instantiate appropriate rule validator from configuration."""
        rule_cls = cls._registry.get(config.type)
        if not rule_cls:
            raise RuleExecutionError(
                f"No rule executor registered for type '{config.type}'",
                details=f"Supported types: {[t.value for t in cls._registry.keys()]}",
            )
        return rule_cls(config)
