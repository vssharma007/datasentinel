"""Tests for statistical anomaly detection (Z-score, IQR, and streaming mode)."""

import numpy as np
import pandas as pd
import pytest

from datasentinel.config.schema import AnomalyConfig
from datasentinel.connectors.base import DataSet
from datasentinel.anomaly.detector import AnomalyDetector
from datasentinel.anomaly.streaming import StreamingColumnStats


def test_zscore_anomaly_detector() -> None:
    np.random.seed(42)
    # 100 normal numbers around 50, std ~ 5
    data = list(np.random.normal(50.0, 5.0, 100))
    # Inject 2 extreme outliers (Z > 5)
    data.append(150.0)
    data.append(-50.0)

    df = pd.DataFrame({"metric": data})
    ds = DataSet("z_test", df)

    config = AnomalyConfig(enabled=True, methods=["zscore"], z_threshold=3.0)
    detector = AnomalyDetector(config)
    report = detector.analyze(ds)

    assert report.total_anomalies >= 2
    col_summary = report.column_summaries[0]
    assert col_summary.column == "metric"
    assert col_summary.method == "zscore"

    flagged_values = [a.value for a in col_summary.top_anomalies]
    assert 150.0 in flagged_values
    assert -50.0 in flagged_values
    assert all(0.5 <= a.confidence_score <= 1.0 for a in col_summary.top_anomalies)


def test_iqr_anomaly_detector() -> None:
    # Spread data from 10 to 60 (Q1 ~ 22, Q3 ~ 48, IQR ~ 26)
    data = [float(x) for x in range(10, 60)]
    # Clear Outliers
    data.append(999.0)
    data.append(-500.0)

    df = pd.DataFrame({"amount": data})
    ds = DataSet("iqr_test", df)

    config = AnomalyConfig(enabled=True, methods=["iqr"], iqr_multiplier=1.5)
    detector = AnomalyDetector(config)
    report = detector.analyze(ds)

    assert report.total_anomalies >= 2
    col_summary = report.column_summaries[0]
    assert col_summary.column == "amount"
    assert col_summary.method == "iqr"
    flagged = [a.value for a in col_summary.top_anomalies]
    assert 999.0 in flagged
    assert -500.0 in flagged


def test_streaming_anomaly_memory_bounded() -> None:
    """Test memory-bounded streaming anomaly accumulator."""
    stats = StreamingColumnStats("test_col", sample_capacity=1000)

    # Feed in 3 chunks
    chunk1 = pd.Series([10.0, 20.0, 30.0])
    chunk2 = pd.Series([40.0, 50.0, 60.0])
    chunk3 = pd.Series([70.0, 80.0, 90.0])

    stats.update(chunk1)
    stats.update(chunk2)
    stats.update(chunk3)

    assert stats.count == 9
    assert stats.mean == 50.0
    assert stats.min_val == 10.0
    assert stats.max_val == 90.0

    q1, q3 = stats.get_quantiles(0.25, 0.75)
    assert q1 < q3
