"""Schema fingerprint generation and baseline persistence."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import pandas as pd

from datasentinel.connectors.base import DataSet
from datasentinel.core.exceptions import SchemaDriftError
from datasentinel.core.types import ColumnSchema, SchemaFingerprint

DEFAULT_SCHEMA_DIR = Path(".datasentinel") / "schemas"


class SchemaRegistry:
    """Manages generation, storage, and retrieval of schema fingerprints."""

    def __init__(self, storage_dir: Optional[Path] = None) -> None:
        self.storage_dir: Path = storage_dir or DEFAULT_SCHEMA_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def extract_fingerprint(
        dataset: DataSet, dataset_name: Optional[str] = None
    ) -> SchemaFingerprint:
        """Extract schema fingerprint from DataSet."""
        target_name = dataset_name or dataset.name
        columns: Dict[str, ColumnSchema] = {}
        type_parts = []

        df = dataset.dataframe
        for pos, col in enumerate(df.columns):
            dtype_str = str(df[col].dtype)
            is_nullable = bool(df[col].isnull().any())
            col_schema = ColumnSchema(
                name=str(col),
                data_type=dtype_str,
                nullable=is_nullable,
                ordinal_position=pos,
            )
            columns[str(col)] = col_schema
            type_parts.append(f"{col}:{dtype_str}:{is_nullable}")

        raw_str = "|".join(type_parts)
        hash_val = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

        return SchemaFingerprint(
            dataset_name=target_name,
            created_at=datetime.utcnow(),
            columns=columns,
            row_count=dataset.row_count,
            column_count=len(columns),
            hash_fingerprint=hash_val,
        )

    def _get_baseline_path(self, dataset_name: str) -> Path:
        sanitized = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in dataset_name)
        return self.storage_dir / f"{sanitized}_baseline.json"

    def register_baseline(self, fingerprint: SchemaFingerprint) -> Path:
        """Persist a schema fingerprint as baseline for future drift comparisons."""
        target_path = self._get_baseline_path(fingerprint.dataset_name)
        try:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(fingerprint.model_dump_json(indent=2))
            return target_path
        except Exception as exc:
            raise SchemaDriftError(
                f"Failed to persist baseline schema for '{fingerprint.dataset_name}'",
                details=str(exc),
            ) from exc

    def get_baseline(self, dataset_name: str) -> Optional[SchemaFingerprint]:
        """Load stored baseline fingerprint for dataset if available."""
        target_path = self._get_baseline_path(dataset_name)
        if not target_path.exists():
            return None

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                raw_json = json.load(f)
            return SchemaFingerprint.model_validate(raw_json)
        except Exception as exc:
            raise SchemaDriftError(
                f"Failed to load baseline schema from {target_path}",
                details=str(exc),
            ) from exc
