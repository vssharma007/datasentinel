"""CSV data connector."""

from pathlib import Path
from typing import Any, Dict
import pandas as pd

from datasentinel.config.schema import SourceConfig
from datasentinel.connectors.base import BaseConnector, ConnectorRegistry, DataSet
from datasentinel.core.exceptions import ConnectorError


@ConnectorRegistry.register("csv")
class CSVConnector(BaseConnector):
    """Adapter for reading CSV datasets."""

    def __init__(self, config: SourceConfig) -> None:
        super().__init__(config)
        if not self.config.path:
            raise ConnectorError("CSV connector requires 'path' parameter in configuration.")
        self.file_path = Path(self.config.path)

    def connect(self) -> None:
        """Verify CSV file exists and is accessible."""
        if not self.file_path.exists():
            raise ConnectorError(
                f"CSV file not found: {self.file_path}",
                details="Verify the path in the source configuration.",
            )
        if not self.file_path.is_file():
            raise ConnectorError(
                f"CSV path is not a valid file: {self.file_path}",
                details="Ensure target is a regular file.",
            )

    def test_connection(self) -> bool:
        """Check if file can be opened and has headers."""
        try:
            pd.read_csv(self.file_path, nrows=1)
            return True
        except Exception:
            return False

    def load(self) -> DataSet:
        """Load entire CSV file into a unified DataSet."""
        try:
            df = pd.read_csv(self.file_path)
        except pd.errors.EmptyDataError as exc:
            raise ConnectorError(
                f"CSV file is empty: {self.file_path}",
                details=str(exc),
            ) from exc
        except Exception as exc:
            raise ConnectorError(
                f"Failed to read CSV file: {self.file_path}",
                details=str(exc),
            ) from exc

        info: Dict[str, Any] = {
            "source_type": "csv",
            "path": str(self.file_path),
            "file_size_bytes": self.file_path.stat().st_size,
        }
        return DataSet(name=self.file_path.stem, dataframe=df, source_info=info)
