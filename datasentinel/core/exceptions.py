"""Core exception hierarchy for DataSentinel."""

from typing import Optional


class DataSentinelError(Exception):
    """Base exception for all DataSentinel errors."""

    def __init__(self, message: str, details: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (Details: {self.details})"
        return self.message


class ConfigurationError(DataSentinelError):
    """Raised when configuration parsing or validation fails."""


class ConnectorError(DataSentinelError):
    """Raised when data connector fails to connect or read data."""


class RuleExecutionError(DataSentinelError):
    """Raised when quality rule execution encounters an unhandled error."""


class SchemaDriftError(DataSentinelError):
    """Raised when schema validation or drift detection fails."""


class AnomalyDetectionError(DataSentinelError):
    """Raised when statistical anomaly detection fails."""


class AlertError(DataSentinelError):
    """Raised when sending an alert (email/webhook) fails."""


class StorageError(DataSentinelError):
    """Raised when persisting or querying the SQLite result store fails."""
