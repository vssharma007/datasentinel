"""Tests for data connector adapters and registry (Open/Closed Principle)."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from datasentinel.config.schema import SourceConfig
from datasentinel.connectors.base import BaseConnector, ConnectorRegistry, DataSet
from datasentinel.connectors.csv_connector import CSVConnector
from datasentinel.connectors.excel_connector import ExcelConnector
from datasentinel.connectors.json_connector import JSONConnector
from datasentinel.connectors.sql_connector import SQLiteConnector, _mask_connection_string
from datasentinel.connectors.api_connector import RestAPIConnector
from datasentinel.core.exceptions import ConnectorError


def test_csv_connector_success(temp_csv_file: Path) -> None:
    config = SourceConfig(type="csv", path=str(temp_csv_file))
    connector = CSVConnector(config)
    connector.connect()
    assert connector.test_connection() is True
    dataset = connector.load()
    assert dataset.row_count == 5
    assert "email" in dataset.column_names
    assert dataset.get_column_types()["id"] is not None


def test_csv_connector_file_not_found(tmp_path: Path) -> None:
    non_existent = tmp_path / "missing.csv"
    config = SourceConfig(type="csv", path=str(non_existent))
    with pytest.raises(ConnectorError, match="CSV file not found"):
        connector = CSVConnector(config)
        connector.connect()


def test_excel_connector_success(tmp_path: Path, sample_dataframe: pd.DataFrame) -> None:
    xlsx_path = tmp_path / "test.xlsx"
    sample_dataframe.to_excel(xlsx_path, index=False)

    config = SourceConfig(type="excel", path=str(xlsx_path))
    connector = ExcelConnector(config)
    connector.connect()
    assert connector.test_connection() is True
    dataset = connector.load()
    assert dataset.row_count == 5
    assert "age" in dataset.column_names


def test_json_connector_nested_path(temp_json_file: Path) -> None:
    config = SourceConfig(
        type="json",
        path=str(temp_json_file),
        nested_path="result.records",
    )
    connector = JSONConnector(config)
    connector.connect()
    assert connector.test_connection() is True
    dataset = connector.load()
    assert dataset.row_count == 3
    assert "item" in dataset.column_names


def test_json_connector_invalid_path(temp_json_file: Path) -> None:
    config = SourceConfig(
        type="json",
        path=str(temp_json_file),
        nested_path="non_existent.path",
    )
    connector = JSONConnector(config)
    connector.connect()
    with pytest.raises(ConnectorError, match="Failed to extract nested path"):
        connector.load()


def test_sqlite_connector_in_memory() -> None:
    config = SourceConfig(
        type="sqlite",
        connection_string="sqlite:///:memory:",
        query="SELECT 1 as num, 'test' as name",
    )
    connector = SQLiteConnector(config)
    connector.connect()
    assert connector.test_connection() is True
    dataset = connector.load()
    assert dataset.row_count == 1
    assert dataset.column_names == ["num", "name"]


def test_mask_connection_string() -> None:
    uri = "postgresql://myuser:supersecretpassword@db.prod.internal:5432/analytics"
    masked = _mask_connection_string(uri)
    assert "supersecretpassword" not in masked
    assert "myuser:****@" in masked


def test_rest_api_connector_mocked() -> None:
    config = SourceConfig(
        type="rest_api",
        api_url="https://api.example.com/v1/users",
        max_pages=2,
    )
    connector = RestAPIConnector(config)

    mock_resp1 = MagicMock()
    mock_resp1.status_code = 200
    mock_resp1.json.return_value = [{"id": 1, "name": "User 1"}, {"id": 2, "name": "User 2"}]

    mock_resp2 = MagicMock()
    mock_resp2.status_code = 200
    mock_resp2.json.return_value = [{"id": 3, "name": "User 3"}]

    with patch("httpx.Client.get", side_effect=[mock_resp1, mock_resp2]):
        dataset = connector.load()
        assert dataset.row_count == 3
        assert "name" in dataset.column_names


def test_connector_registry_open_closed_principle() -> None:
    """Verify OCP: adding custom source plugin without editing existing connectors."""

    @ConnectorRegistry.register("custom_dummy")
    class DummyConnector(BaseConnector):
        def connect(self) -> None:
            pass

        def test_connection(self) -> bool:
            return True

        def load(self) -> DataSet:
            return DataSet("dummy", pd.DataFrame({"dummy_col": [1, 2]}))

    config = SourceConfig(type="custom_dummy")
    connector = ConnectorRegistry.create(config)
    assert isinstance(connector, DummyConnector)
    dataset = connector.load()
    assert dataset.row_count == 2
