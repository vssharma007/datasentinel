"""SQLite-backed run history and trend store for pipeline monitoring."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import sqlalchemy as sa
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from datasentinel.core.exceptions import StorageError
from datasentinel.core.types import RunSummary, ValidationStatus


class Base(DeclarativeBase):
    """Declarative base class for SQLAlchemy 2.0."""
    pass


class RunHistoryModel(Base):
    """Database model for pipeline validation runs."""

    __tablename__ = "validation_runs"

    run_id = Column(String(64), primary_key=True)
    dataset_name = Column(String(128), index=True, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    status = Column(String(32), nullable=False)
    duration_seconds = Column(Float, nullable=False)
    total_rows = Column(Integer, nullable=False)
    total_columns = Column(Integer, nullable=False)
    total_rules = Column(Integer, nullable=False)
    passed_rules = Column(Integer, nullable=False)
    failed_rules = Column(Integer, nullable=False)
    warning_rules = Column(Integer, nullable=False)
    overall_pass_rate = Column(Float, nullable=False)
    schema_drift_detected = Column(Integer, nullable=False, default=0)
    total_anomalies = Column(Integer, nullable=False, default=0)
    summary_json = Column(Text, nullable=False)


class ResultStore:
    """Manages persistence and retrieval of validation run history in SQLite."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is None:
            default_dir = Path(".datasentinel")
            default_dir.mkdir(parents=True, exist_ok=True)
            db_path = default_dir / "history.db"

        self.db_path = db_path
        self.db_url = f"sqlite:///{self.db_path}"
        self.engine = create_engine(self.db_url)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def record_run(self, summary: RunSummary) -> None:
        """Persist a validation run summary record."""
        session = self.SessionLocal()
        try:
            record = RunHistoryModel(
                run_id=summary.run_id,
                dataset_name=summary.dataset_name,
                timestamp=summary.timestamp,
                status=summary.status.value,
                duration_seconds=summary.duration_seconds,
                total_rows=summary.total_rows,
                total_columns=summary.total_columns,
                total_rules=summary.total_rules,
                passed_rules=summary.passed_rules,
                failed_rules=summary.failed_rules,
                warning_rules=summary.warning_rules,
                overall_pass_rate=summary.overall_pass_rate,
                schema_drift_detected=1 if summary.schema_drift_detected else 0,
                total_anomalies=summary.total_anomalies,
                summary_json=summary.model_dump_json(),
            )
            session.merge(record)
            session.commit()
        except Exception as exc:
            session.rollback()
            raise StorageError(
                f"Failed to record run {summary.run_id} into SQLite store",
                details=str(exc),
            ) from exc
        finally:
            session.close()

    def get_history(
        self, dataset_name: Optional[str] = None, limit: int = 20
    ) -> List[RunSummary]:
        """Query recent historical validation runs."""
        session = self.SessionLocal()
        try:
            query = session.query(RunHistoryModel)
            if dataset_name:
                query = query.filter(RunHistoryModel.dataset_name == dataset_name)
            records = (
                query.order_by(RunHistoryModel.timestamp.desc())
                .limit(limit)
                .all()
            )

            results: List[RunSummary] = []
            for r in records:
                try:
                    raw_json = str(r.summary_json)
                    summary = RunSummary.model_validate_json(raw_json)
                    results.append(summary)
                except Exception:
                    continue
            return results
        except Exception as exc:
            raise StorageError("Failed to query run history", details=str(exc)) from exc
        finally:
            session.close()

    def get_trend(self, dataset_name: str, limit: int = 10) -> Dict[str, Any]:
        """Calculate historical trend metrics for charts."""
        runs = self.get_history(dataset_name=dataset_name, limit=limit)
        runs_chronological = list(reversed(runs))

        labels = [r.timestamp.strftime("%m-%d %H:%M") for r in runs_chronological]
        pass_rates = [r.overall_pass_rate for r in runs_chronological]
        anomalies = [r.total_anomalies for r in runs_chronological]
        failed_counts = [r.failed_rules for r in runs_chronological]

        return {
            "labels": labels,
            "pass_rates": pass_rates,
            "anomalies": anomalies,
            "failed_counts": failed_counts,
        }
