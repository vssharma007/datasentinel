"""Excel (.xlsx / .xls) data connector."""

from pathlib import Path
from typing import Any, Dict
import pandas as pd

from datasentinel.config.schema import SourceConfig
from datasentinel.connectors.base import BaseConnector, ConnectorRegistry, DataSet
from datasentinel.core.exceptions import ConnectorError


@ConnectorRegistry.register("excel")
class ExcelConnector(BaseConnector):
    """Adapter for reading Excel spreadsheet datasets."""

    def __init__(self, config: SourceConfig) -> None:
        super().__init__(config)
        if not self.config.path:
            raise ConnectorError("Excel connector requires 'path' parameter in configuration.")
        self.file_path = Path(self.config.path)
        self.sheet_name = self.config.sheet_name or 0

    def connect(self) -> None:
        """Verify Excel file exists and is accessible."""
        if not self.file_path.exists():
            raise ConnectorError(
                f"Excel file not found: {self.file_path}",
                details="Verify the path in the source configuration.",
            )
        if not self.file_path.is_file():
            raise ConnectorError(
                f"Excel path is not a file: {self.file_path}",
                details="Ensure target is a regular file.",
            )

    def test_connection(self) -> bool:
        """Check if Excel file structure can be inspected."""
        try:
            excel_file = pd.ExcelFile(self.file_path)
            return len(excel_file.sheet_names) > 0
        except Exception:
            return False

    def load(self) -> DataSet:
        """Load sheet from Excel file into a unified DataSet."""
        try:
            df = pd.read_excel(self.file_path, sheet_name=self.sheet_name)
        except Exception as exc:
            raise ConnectorError(
                f"Failed to read Excel file '{self.file_path}' (sheet: {self.sheet_name})",
                details=str(exc),
            ) from exc

        info: Dict[str, Any] = {
            "source_type": "excel",
            "path": str(self.file_path),
            "sheet_name": str(self.sheet_name),
            "file_size_bytes": self.file_path.stat().st_size,
        }
        return DataSet(name=self.file_path.stem, dataframe=df, source_info=info)
