"""Hypothesis property-based tests for statistical anomaly detection algorithms."""

from hypothesis import given, settings, strategies as st
import numpy as np
import pandas as pd

from datasentinel.config.schema import AnomalyConfig
from datasentinel.connectors.base import DataSet
from datasentinel.anomaly.detector import AnomalyDetector


@settings(max_examples=15, deadline=None)
@given(
    data=st.lists(
        st.floats(min_value=-1e4, max_value=1e4, allow_nan=False, allow_infinity=False),
        min_size=10,
        max_size=40,
    ),
    threshold=st.floats(min_value=2.0, max_value=4.0),
)
def test_hypothesis_zscore_confidence_bounds(data: list[float], threshold: float) -> None:
    """Property: Confidence scores must always remain within [0.0, 1.0]."""
    df = pd.DataFrame({"val": data})
    ds = DataSet("hyp_zscore", df)
    config = AnomalyConfig(enabled=True, methods=["zscore"], z_threshold=threshold)
    detector = AnomalyDetector(config)

    summary = detector.detect_zscore(ds, "val", threshold)
    for anomaly in summary.top_anomalies:
        assert 0.0 <= anomaly.confidence_score <= 1.0
        assert anomaly.z_score is not None
        assert anomaly.z_score >= round(threshold, 2) - 0.1


@settings(max_examples=15, deadline=None)
@given(
    data=st.lists(
        st.floats(min_value=-1e4, max_value=1e4, allow_nan=False, allow_infinity=False),
        min_size=10,
        max_size=40,
    ),
    multiplier=st.floats(min_value=1.0, max_value=2.5),
)
def test_hypothesis_iqr_confidence_bounds(data: list[float], multiplier: float) -> None:
    """Property: IQR confidence scores must always remain strictly bounded in [0.0, 1.0]."""
    df = pd.DataFrame({"val": data})
    ds = DataSet("hyp_iqr", df)
    config = AnomalyConfig(enabled=True, methods=["iqr"], iqr_multiplier=multiplier)
    detector = AnomalyDetector(config)

    summary = detector.detect_iqr(ds, "val", multiplier)
    for anomaly in summary.top_anomalies:
        assert 0.0 <= anomaly.confidence_score <= 1.0
        assert anomaly.iqr_distance is not None
        assert anomaly.iqr_distance >= 0.0


@settings(max_examples=10, deadline=None)
@given(val=st.floats(min_value=-1e4, max_value=1e4, allow_nan=False, allow_infinity=False))
def test_hypothesis_constant_series_zero_anomalies(val: float) -> None:
    """Property: A strictly constant series has zero variance and zero anomalies."""
    df = pd.DataFrame({"val": [val] * 20})
    ds = DataSet("hyp_const", df)
    config = AnomalyConfig(enabled=True, methods=["zscore", "iqr"])
    detector = AnomalyDetector(config)

    report = detector.analyze(ds)
    assert report.total_anomalies == 0
