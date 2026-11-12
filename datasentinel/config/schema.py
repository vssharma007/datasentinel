"""Pydantic v2 schemas for DataSentinel YAML configuration files."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from datasentinel.core.types import RuleType, Severity


class SourceConfig(BaseModel):
    """Configuration for a data source connection."""

    type: str = Field(description="Connector type: csv, excel, json, sqlite, postgresql, rest_api")
    path: Optional[str] = Field(default=None, description="Local file path for file-based connectors")
    connection_string: Optional[str] = Field(
        default=None, description="Database connection URI or DSN"
    )
    env_conn_var: Optional[str] = Field(
        default=None, description="Environment variable holding connection string or credentials"
    )
    table_name: Optional[str] = Field(default=None, description="Database table name")
    query: Optional[str] = Field(default=None, description="SQL query to execute")
    sheet_name: Optional[str] = Field(default=None, description="Excel sheet name or index")
    nested_path: Optional[str] = Field(
        default=None, description="JSON path or dot notation for nested JSON records"
    )
    api_url: Optional[str] = Field(default=None, description="REST API endpoint URL")
    headers: Dict[str, str] = Field(default_factory=dict, description="Custom HTTP headers")
    page_param: str = Field(default="page", description="Query parameter for pagination")
    size_param: str = Field(default="limit", description="Query parameter for page size")
    max_pages: int = Field(default=5, description="Maximum pages to fetch")


class RuleConfig(BaseModel):
    """Configuration for a specific quality rule."""

    name: str = Field(description="Descriptive human-readable rule name")
    type: RuleType = Field(description="Rule validator type")
    column: str = Field(description="Target column name")
    severity: Severity = Field(default=Severity.ERROR, description="Alert severity level")
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Rule parameters (all thresholds defined in YAML)",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Rule name cannot be empty")
        return v.strip()


class AnomalyConfig(BaseModel):
    """Configuration for statistical anomaly detection."""

    enabled: bool = Field(default=True)
    methods: List[str] = Field(default=["zscore", "iqr"])
    z_threshold: float = Field(default=3.0, description="Z-score threshold (|z| > threshold)")
    iqr_multiplier: float = Field(default=1.5, description="IQR fence multiplier (Q3 + mult*IQR)")
    columns: Optional[List[str]] = Field(
        default=None, description="Columns to analyze, or None for all numeric"
    )
    chunk_size: int = Field(
        default=50000, description="Streaming chunk size for memory-bounded execution"
    )


class SchemaDriftConfig(BaseModel):
    """Configuration for baseline schema tracking and drift detection."""

    enabled: bool = Field(default=True)
    baseline_store_path: Optional[str] = Field(
        default=None, description="Optional path to persistent schema baseline store"
    )
    fail_on_drift: bool = Field(
        default=False, description="Whether drift causes overall validation failure"
    )


class EmailAlertConfig(BaseModel):
    """SMTP email alerting configuration."""

    enabled: bool = Field(default=True)
    smtp_host: str = Field(default="localhost")
    smtp_port: int = Field(default=587)
    use_tls: bool = Field(default=True)
    username_env: str = Field(default="SMTP_USERNAME")
    password_env: str = Field(default="SMTP_PASSWORD")
    sender: str
    recipients: List[str]
    subject_prefix: str = Field(default="[DataSentinel Alert]")


class SlackAlertConfig(BaseModel):
    """Slack webhook alerting configuration."""

    enabled: bool = Field(default=True)
    webhook_url_env: str = Field(
        default="SLACK_WEBHOOK_URL",
        description="Environment variable containing incoming webhook URL",
    )
    channel: Optional[str] = Field(default=None)


class AlertConfig(BaseModel):
    """Aggregated alerting configuration."""

    email: Optional[EmailAlertConfig] = None
    slack: Optional[SlackAlertConfig] = None


class SchedulerConfig(BaseModel):
    """APScheduler recurring job configuration."""

    cron: str = Field(description="Standard 5-part cron expression (e.g. '0 * * * *')")
    coalesce: bool = Field(
        default=True, description="Coalesce missed jobs to avoid overlapping runs"
    )
    max_instances: int = Field(default=1, description="Concurrency limit")


class SentinelConfig(BaseModel):
    """Root configuration for DataSentinel."""

    dataset_name: str = Field(description="Unique identifier for the monitored dataset")
    source: SourceConfig
    rules: List[RuleConfig] = Field(default_factory=list)
    anomaly_detection: AnomalyConfig = Field(default_factory=AnomalyConfig)
    schema_drift: SchemaDriftConfig = Field(default_factory=SchemaDriftConfig)
    alerts: Optional[AlertConfig] = None
    scheduler: Optional[SchedulerConfig] = None
