"""Base connector abstractions and registry (Open/Closed Principle)."""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Iterator, List, Optional, Type
import pandas as pd

from datasentinel.config.schema import SourceConfig
from datasentinel.core.exceptions import ConnectorError


class DataSet:
    """Unified wrapper around loaded data providing consistent inspection and chunking."""

    def __init__(self, name: str, dataframe: pd.DataFrame, source_info: Optional[Dict[str, Any]] = None) -> None:
        self.name: str = name
        self._df: pd.DataFrame = dataframe
        self.source_info: Dict[str, Any] = source_info or {}

    @property
    def dataframe(self) -> pd.DataFrame:
        """Access full underlying pandas DataFrame."""
        return self._df

    @property
    def row_count(self) -> int:
        """Total number of records/rows."""
        return len(self._df)

    @property
    def column_names(self) -> List[str]:
        """List of column names in dataset."""
        return list(self._df.columns)

    def get_column_types(self) -> Dict[str, str]:
        """Dictionary of column names to stringified data type names."""
        return {col: str(self._df[col].dtype) for col in self._df.columns}

    def is_nullable(self, col: str) -> bool:
        """Check if a column contains any null values."""
        if col not in self._df.columns:
            return True
        return bool(self._df[col].isnull().any())

    def iter_chunks(self, chunk_size: int = 50000) -> Iterator[pd.DataFrame]:
        """Stream dataset in memory-bounded chunks up to 500k+ rows."""
        total = len(self._df)
        if total == 0:
            yield self._df
            return

        for start in range(0, total, chunk_size):
            yield self._df.iloc[start : start + chunk_size]


class BaseConnector(ABC):
    """Abstract base class for all data connectors."""

    def __init__(self, config: SourceConfig) -> None:
        self.config: SourceConfig = config

    @abstractmethod
    def connect(self) -> None:
        """Validate connectivity and initialize resources."""

    @abstractmethod
    def load(self) -> DataSet:
        """Fetch and return unified DataSet instance."""

    @abstractmethod
    def test_connection(self) -> bool:
        """Check if source can be reached without loading entire dataset."""


class ConnectorRegistry:
    """Registry maintaining available connectors without modifying existing codebase (OCP)."""

    _registry: Dict[str, Type[BaseConnector]] = {}

    @classmethod
    def register(cls, name: str) -> Callable[[Type[BaseConnector]], Type[BaseConnector]]:
        """Decorator to register a connector adapter class."""

        def decorator(subclass: Type[BaseConnector]) -> Type[BaseConnector]:
            cls._registry[name.lower()] = subclass
            return subclass

        return decorator

    @classmethod
    def create(cls, config: SourceConfig) -> BaseConnector:
        """Factory method to instantiate a connector based on config.type."""
        source_type = config.type.lower()
        connector_cls = cls._registry.get(source_type)
        if not connector_cls:
            available = ", ".join(sorted(cls._registry.keys()))
            raise ConnectorError(
                f"Unsupported source type '{config.type}'. Available: {available}",
                details="Verify the 'type' field in the YAML rule configuration source block.",
            )
        connector = connector_cls(config)
        connector.connect()
        return connector

    @classmethod
    def available_connectors(cls) -> List[str]:
        """List registered connector names."""
        return sorted(list(cls._registry.keys()))
