"""Pytest fixtures and test harnesses for DataSentinel."""

import json
from pathlib import Path
from typing import Any, Dict
import numpy as np
import pandas as pd
import pytest

from datasentinel.config.schema import AnomalyConfig, RuleConfig, SentinelConfig, SourceConfig
from datasentinel.connectors.base import DataSet
from datasentinel.core.types import RuleType, Severity


@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    """Fixture providing a deterministic test DataFrame."""
    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "email": [
                "alice@example.com",
                "bob@example.com",
                "charlie@example.com",
                "david@example.com",
                "eve@example.com",
            ],
            "age": [25, 30, 35, 40, 45],
            "score": [88.5, 92.0, 79.5, 85.0, 95.0],
            "department": ["ENG", "ENG", "SALES", "MARKETING", "SALES"],
        }
    )


@pytest.fixture
def sample_dataset(sample_dataframe: pd.DataFrame) -> DataSet:
    """Fixture providing a sample DataSet instance."""
    return DataSet(name="test_users", dataframe=sample_dataframe)


@pytest.fixture
def temp_csv_file(tmp_path: Path, sample_dataframe: pd.DataFrame) -> Path:
    """Fixture creating a temporary CSV file."""
    csv_file = tmp_path / "test_data.csv"
    sample_dataframe.to_csv(csv_file, index=False)
    return csv_file


@pytest.fixture
def temp_json_file(tmp_path: Path) -> Path:
    """Fixture creating a temporary nested JSON file."""
    data: Dict[str, Any] = {
        "status": "success",
        "result": {
            "records": [
                {"id": 101, "item": "Widget A", "price": 19.99},
                {"id": 102, "item": "Widget B", "price": 29.99},
                {"id": 103, "item": "Widget C", "price": 39.99},
            ]
        },
    }
    json_file = tmp_path / "test_nested.json"
    json_file.write_text(json.dumps(data), encoding="utf-8")
    return json_file


@pytest.fixture
def temp_yaml_config(tmp_path: Path, temp_csv_file: Path) -> Path:
    """Fixture creating a temporary valid YAML rule file."""
    schemas_dir = (tmp_path / "schemas").as_posix()
    yaml_content = f"""
dataset_name: test_dataset
source:
  type: csv
  path: {temp_csv_file.as_posix()}
schema_drift:
  enabled: true
  baseline_store_path: {schemas_dir}
rules:
  - name: check_id_not_null
    type: null_check
    column: id
    severity: critical
    parameters:
      allow_null: false
  - name: check_id_unique
    type: unique_check
    column: id
    severity: critical
  - name: check_age_range
    type: range
    column: age
    severity: error
    parameters:
      min_value: 18
      max_value: 65
"""
    yaml_file = tmp_path / "test_rules.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")
    return yaml_file
