"""SQLAlchemy 2.0 database connector for SQLite and PostgreSQL."""

import os
import re
from typing import Any, Dict
import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from datasentinel.config.schema import SourceConfig
from datasentinel.connectors.base import BaseConnector, ConnectorRegistry, DataSet
from datasentinel.core.exceptions import ConnectorError


def _mask_connection_string(conn_str: str) -> str:
    """Mask password in URI for secure error messages."""
    return re.sub(r":([^:@/]+)@", ":****@", conn_str)


class BaseSQLConnector(BaseConnector):
    """Base SQL adapter using SQLAlchemy 2.0 engine."""

    def __init__(self, config: SourceConfig) -> None:
        super().__init__(config)
        self.engine: Engine | None = None
        self._raw_conn_str: str = self._resolve_connection_string()

    def _resolve_connection_string(self) -> str:
        """Resolve connection URI from config or specified environment variable."""
        if self.config.env_conn_var:
            env_val = os.environ.get(self.config.env_conn_var)
            if env_val:
                return env_val

        if self.config.connection_string:
            return self.config.connection_string

        # Default fallbacks
        if self.config.type.lower() == "sqlite":
            path = self.config.path or ":memory:"
            return f"sqlite:///{path}"

        raise ConnectorError(
            f"No connection string found for '{self.config.type}'. "
            f"Provide 'connection_string' or set environment variable '{self.config.env_conn_var or 'DATABASE_URL'}'.",
            details="Credentials must be supplied via configuration or environment variable.",
        )

    def connect(self) -> None:
        """Create SQLAlchemy engine and test connectivity."""
        try:
            self.engine = create_engine(self._raw_conn_str)
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            masked = _mask_connection_string(self._raw_conn_str)
            raise ConnectorError(
                f"Failed to connect to database using '{masked}'",
                details=str(exc),
            ) from exc

    def test_connection(self) -> bool:
        """Check if database query executes successfully."""
        try:
            if not self.engine:
                self.connect()
            if self.engine:
                with self.engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                return True
            return False
        except Exception:
            return False

    def load(self) -> DataSet:
        """Query table or execute custom SQL query into DataSet."""
        if not self.engine:
            self.connect()

        if not self.engine:
            raise ConnectorError("Engine not initialized")

        try:
            if self.config.query:
                df = pd.read_sql(text(self.config.query), con=self.engine)
                ds_name = f"{self.config.type}_query"
            elif self.config.table_name:
                df = pd.read_sql_table(self.config.table_name, con=self.engine)
                ds_name = self.config.table_name
            else:
                inspector = inspect(self.engine)
                tables = inspector.get_table_names()
                if not tables:
                    raise ConnectorError("No tables found in database and no query specified.")
                table = tables[0]
                df = pd.read_sql_table(table, con=self.engine)
                ds_name = table
        except SQLAlchemyError as exc:
            masked = _mask_connection_string(self._raw_conn_str)
            raise ConnectorError(
                f"SQL query execution failed on '{masked}'",
                details=str(exc),
            ) from exc

        info: Dict[str, Any] = {
            "source_type": self.config.type,
            "connection": _mask_connection_string(self._raw_conn_str),
            "table": self.config.table_name,
            "has_custom_query": bool(self.config.query),
        }
        return DataSet(name=ds_name, dataframe=df, source_info=info)


@ConnectorRegistry.register("sqlite")
class SQLiteConnector(BaseSQLConnector):
    """SQLite database connector."""


@ConnectorRegistry.register("postgresql")
class PostgreSQLConnector(BaseSQLConnector):
    """PostgreSQL database connector."""


@ConnectorRegistry.register("postgres")
class PostgresAliasConnector(BaseSQLConnector):
    """Alias for PostgreSQL database connector."""
