"""JSON flat and nested path data connector."""

import json
from pathlib import Path
from typing import Any, Dict, List
import pandas as pd

from datasentinel.config.schema import SourceConfig
from datasentinel.connectors.base import BaseConnector, ConnectorRegistry, DataSet
from datasentinel.core.exceptions import ConnectorError


def _extract_nested_path(data: Any, path: str) -> Any:
    """Traverse nested dictionary or list using dot notation e.g. 'response.data.users'."""
    keys = path.strip().split(".")
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        elif isinstance(current, list) and key.isdigit():
            idx = int(key)
            if 0 <= idx < len(current):
                current = current[idx]
            else:
                raise KeyError(f"Index {idx} out of range in nested path '{path}'")
        else:
            raise KeyError(f"Key '{key}' not found while resolving path '{path}'")
    return current


@ConnectorRegistry.register("json")
class JSONConnector(BaseConnector):
    """Adapter for reading flat or nested JSON datasets."""

    def __init__(self, config: SourceConfig) -> None:
        super().__init__(config)
        if not self.config.path:
            raise ConnectorError("JSON connector requires 'path' parameter in configuration.")
        self.file_path = Path(self.config.path)
        self.nested_path = self.config.nested_path

    def connect(self) -> None:
        """Verify JSON file exists."""
        if not self.file_path.exists():
            raise ConnectorError(
                f"JSON file not found: {self.file_path}",
                details="Verify the path in the source configuration.",
            )
        if not self.file_path.is_file():
            raise ConnectorError(
                f"JSON path is not a file: {self.file_path}",
                details="Ensure target is a regular file.",
            )

    def test_connection(self) -> bool:
        """Check if JSON file can be parsed."""
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                json.load(f)
            return True
        except Exception:
            return False

    def load(self) -> DataSet:
        """Load JSON data, extract target array if nested, and return DataSet."""
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = json.load(f)
        except Exception as exc:
            raise ConnectorError(
                f"Failed to parse JSON file: {self.file_path}",
                details=str(exc),
            ) from exc

        target_data = content
        if self.nested_path:
            try:
                target_data = _extract_nested_path(content, self.nested_path)
            except Exception as exc:
                raise ConnectorError(
                    f"Failed to extract nested path '{self.nested_path}' in {self.file_path}",
                    details=str(exc),
                ) from exc

        if isinstance(target_data, list):
            df = pd.DataFrame(target_data)
        elif isinstance(target_data, dict):
            # If dictionary of lists or single record
            try:
                df = pd.DataFrame(target_data)
            except Exception:
                df = pd.DataFrame([target_data])
        else:
            raise ConnectorError(
                f"Expected list of records or dictionary at '{self.nested_path or 'root'}', got {type(target_data).__name__}"
            )

        info: Dict[str, Any] = {
            "source_type": "json",
            "path": str(self.file_path),
            "nested_path": self.nested_path,
        }
        return DataSet(name=self.file_path.stem, dataframe=df, source_info=info)
