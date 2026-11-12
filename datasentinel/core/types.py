"""Core type definitions and schemas for DataSentinel."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Rule violation severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class RuleType(str, Enum):
    """Supported rule types in DataSentinel."""

    NULL_CHECK = "null_check"
    UNIQUE_CHECK = "unique_check"
    RANGE = "range"
    REGEX = "regex"
    FOREIGN_KEY = "foreign_key"
    ANOMALY_ZSCORE = "anomaly_zscore"
    ANOMALY_IQR = "anomaly_iqr"


class DriftType(str, Enum):
    """Types of schema drift detected against baseline."""

    COLUMN_ADDED = "column_added"
    COLUMN_REMOVED = "column_removed"
    TYPE_CHANGED = "type_changed"
    NULLABILITY_CHANGED = "nullability_changed"


class ValidationStatus(str, Enum):
    """Overall status of a validation run."""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    ERROR = "error"


class ColumnSchema(BaseModel):
    """Fingerprint representation of a single column."""

    name: str
    data_type: str
    nullable: bool
    ordinal_position: int = 0


class SchemaFingerprint(BaseModel):
    """Complete schema fingerprint of a dataset at a point in time."""

    dataset_name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    columns: Dict[str, ColumnSchema]
    row_count: int
    column_count: int
    hash_fingerprint: str


class DriftItem(BaseModel):
    """Specific schema drift detected for a column."""

    drift_type: DriftType
    column_name: str
    baseline_value: Optional[str] = None
    current_value: Optional[str] = None
    details: str


class SchemaDriftReport(BaseModel):
    """Summary of schema drift between baseline and current dataset."""

    dataset_name: str
    has_drift: bool
    baseline_timestamp: Optional[datetime] = None
    current_timestamp: datetime = Field(default_factory=datetime.utcnow)
    drifts: List[DriftItem] = Field(default_factory=list)


class ViolationSample(BaseModel):
    """Individual violation evidence sample for a rule."""

    row_index: int
    column: str
    value: Any
    reason: str


class RuleResult(BaseModel):
    """Execution result for a single quality rule."""

    rule_name: str
    rule_type: RuleType
    column: str
    passed: bool
    total_checked: int
    violation_count: int
    pass_rate: float
    severity: Severity = Severity.ERROR
    message: str
    samples: List[ViolationSample] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class AnomalyPoint(BaseModel):
    """Flagged anomalous data point with confidence score."""

    row_index: int
    column: str
    value: float
    method: str
    z_score: Optional[float] = None
    iqr_distance: Optional[float] = None
    confidence_score: float = Field(ge=0.0, le=1.0)
    details: str


class AnomalyColumnSummary(BaseModel):
    """Summary of anomalies detected for a single column."""

    column: str
    method: str
    threshold: float
    total_evaluated: int
    anomalous_count: int
    anomaly_rate: float
    top_anomalies: List[AnomalyPoint] = Field(default_factory=list)


class AnomalyReport(BaseModel):
    """Full anomaly report across all numeric columns."""

    dataset_name: str
    total_anomalies: int
    columns_evaluated: int
    column_summaries: List[AnomalyColumnSummary] = Field(default_factory=list)


class RunSummary(BaseModel):
    """Executive run summary record."""

    run_id: str
    dataset_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: ValidationStatus
    duration_seconds: float
    total_rows: int
    total_columns: int
    total_rules: int
    passed_rules: int
    failed_rules: int
    warning_rules: int
    overall_pass_rate: float
    schema_drift_detected: bool
    total_anomalies: int
    rule_results: List[RuleResult] = Field(default_factory=list)
    schema_report: Optional[SchemaDriftReport] = None
    anomaly_report: Optional[AnomalyReport] = None
