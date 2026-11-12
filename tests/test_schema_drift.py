"""Tests for schema fingerprinting and schema drift detection."""

from pathlib import Path
import pandas as pd
import pytest

from datasentinel.connectors.base import DataSet
from datasentinel.core.types import DriftType
from datasentinel.schema.drift import SchemaDriftDetector
from datasentinel.schema.registry import SchemaRegistry


def test_schema_fingerprint_extraction() -> None:
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    ds = DataSet("sample_ds", df)
    fp = SchemaRegistry.extract_fingerprint(ds)

    assert fp.dataset_name == "sample_ds"
    assert fp.column_count == 2
    assert fp.row_count == 3
    assert "a" in fp.columns
    assert "b" in fp.columns
    assert len(fp.hash_fingerprint) == 64


def test_schema_baseline_registration(tmp_path: Path) -> None:
    registry = SchemaRegistry(storage_dir=tmp_path)
    df = pd.DataFrame({"col1": [10, 20]})
    ds = DataSet("reg_test", df)
    fp = registry.extract_fingerprint(ds)

    saved_path = registry.register_baseline(fp)
    assert saved_path.exists()

    loaded_fp = registry.get_baseline("reg_test")
    assert loaded_fp is not None
    assert loaded_fp.hash_fingerprint == fp.hash_fingerprint


def test_schema_drift_detection_types() -> None:
    # Baseline
    df_base = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "name": ["A", "B", "C"],
            "score": [10.5, 20.0, 30.2],
        }
    )
    ds_base = DataSet("drift_test", df_base)
    fp_base = SchemaRegistry.extract_fingerprint(ds_base)

    # Current has:
    # 1. 'score' removed
    # 2. 'tags' added
    # 3. 'id' type changed to float/object
    # 4. 'name' nullability changed (now has None)
    df_curr = pd.DataFrame(
        {
            "id": ["1", "2", "3"],
            "name": ["A", None, "C"],
            "tags": ["vip", "standard", "guest"],
        }
    )
    ds_curr = DataSet("drift_test", df_curr)
    fp_curr = SchemaRegistry.extract_fingerprint(ds_curr)

    report = SchemaDriftDetector.detect_drift(fp_base, fp_curr)
    assert report.has_drift is True
    drift_types = {d.drift_type for d in report.drifts}

    assert DriftType.COLUMN_REMOVED in drift_types
    assert DriftType.COLUMN_ADDED in drift_types
    assert DriftType.TYPE_CHANGED in drift_types
    assert DriftType.NULLABILITY_CHANGED in drift_types
