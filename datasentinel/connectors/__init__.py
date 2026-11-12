"""Connectors module exposing BaseConnector, DataSet, and ConnectorRegistry."""

from datasentinel.connectors.api_connector import RestAPIConnector
from datasentinel.connectors.base import BaseConnector, ConnectorRegistry, DataSet
from datasentinel.connectors.csv_connector import CSVConnector
from datasentinel.connectors.excel_connector import ExcelConnector
from datasentinel.connectors.json_connector import JSONConnector
from datasentinel.connectors.sql_connector import (
    BaseSQLConnector,
    PostgreSQLConnector,
    SQLiteConnector,
)

__all__ = [
    "BaseConnector",
    "DataSet",
    "ConnectorRegistry",
    "CSVConnector",
    "ExcelConnector",
    "JSONConnector",
    "BaseSQLConnector",
    "SQLiteConnector",
    "PostgreSQLConnector",
    "RestAPIConnector",
]
