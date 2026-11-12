"""Statistical anomaly detection using Z-score and IQR fence methods."""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from datasentinel.config.schema import AnomalyConfig
from datasentinel.connectors.base import DataSet
from datasentinel.core.exceptions import AnomalyDetectionError
from datasentinel.core.types import (
    AnomalyColumnSummary,
    AnomalyPoint,
    AnomalyReport,
)
from datasentinel.anomaly.streaming import StreamingColumnStats


class AnomalyDetector:
    """Detects statistical outliers in numeric columns using Z-score and IQR methods."""

    def __init__(self, config: AnomalyConfig) -> None:
        self.config: AnomalyConfig = config

    def _select_numeric_columns(self, dataset: DataSet) -> List[str]:
        """Determine target numeric columns for anomaly detection."""
        df = dataset.dataframe
        if self.config.columns:
            return [col for col in self.config.columns if col in df.columns]

        numeric_cols: List[str] = []
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                numeric_cols.append(str(col))
        return numeric_cols

    def detect_zscore(
        self,
        dataset: DataSet,
        column: str,
        threshold: float,
    ) -> AnomalyColumnSummary:
        """Flag rows where absolute Z-score |z| exceeds threshold."""
        df = dataset.dataframe
        series = pd.to_numeric(df[column], errors="coerce")
        valid_series = series.dropna()

        total_evaluated = len(valid_series)
        if total_evaluated <= 2:
            return AnomalyColumnSummary(
                column=column,
                method="zscore",
                threshold=threshold,
                total_evaluated=total_evaluated,
                anomalous_count=0,
                anomaly_rate=0.0,
                top_anomalies=[],
            )

        mean = float(valid_series.mean())
        std = float(valid_series.std())

        if std == 0.0 or np.isnan(std):
            return AnomalyColumnSummary(
                column=column,
                method="zscore",
                threshold=threshold,
                total_evaluated=total_evaluated,
                anomalous_count=0,
                anomaly_rate=0.0,
                top_anomalies=[],
            )

        z_scores = (valid_series - mean).abs() / std
        anom_mask = z_scores > threshold

        anom_indices = valid_series[anom_mask].index
        anomalies: List[AnomalyPoint] = []

        for idx in anom_indices:
            val = float(valid_series.loc[idx])
            z_val = float(z_scores.loc[idx])
            confidence = min(1.0, max(0.5, round(z_val / (threshold * 1.5), 3)))
            anomalies.append(
                AnomalyPoint(
                    row_index=int(idx),
                    column=column,
                    value=val,
                    method="zscore",
                    z_score=round(z_val, 2),
                    confidence_score=confidence,
                    details=f"Z-score {z_val:.2f} > threshold {threshold:.2f} (mean={mean:.2f}, std={std:.2f})",
                )
            )

        # Sort anomalies by confidence descending
        anomalies.sort(key=lambda a: a.confidence_score, reverse=True)
        anom_count = len(anomalies)
        anom_rate = round((anom_count / total_evaluated) * 100.0, 2) if total_evaluated > 0 else 0.0

        return AnomalyColumnSummary(
            column=column,
            method="zscore",
            threshold=threshold,
            total_evaluated=total_evaluated,
            anomalous_count=anom_count,
            anomaly_rate=anom_rate,
            top_anomalies=anomalies[:10],
        )

    def detect_iqr(
        self,
        dataset: DataSet,
        column: str,
        multiplier: float,
    ) -> AnomalyColumnSummary:
        """Flag rows outside IQR fence: [Q1 - mult*IQR, Q3 + mult*IQR]."""
        df = dataset.dataframe
        series = pd.to_numeric(df[column], errors="coerce")
        valid_series = series.dropna()

        total_evaluated = len(valid_series)
        if total_evaluated <= 3:
            return AnomalyColumnSummary(
                column=column,
                method="iqr",
                threshold=multiplier,
                total_evaluated=total_evaluated,
                anomalous_count=0,
                anomaly_rate=0.0,
                top_anomalies=[],
            )

        q1 = float(valid_series.quantile(0.25))
        q3 = float(valid_series.quantile(0.75))
        iqr = q3 - q1

        if iqr == 0.0:
            return AnomalyColumnSummary(
                column=column,
                method="iqr",
                threshold=multiplier,
                total_evaluated=total_evaluated,
                anomalous_count=0,
                anomaly_rate=0.0,
                top_anomalies=[],
            )

        lower_fence = q1 - (multiplier * iqr)
        upper_fence = q3 + (multiplier * iqr)

        anom_mask = (valid_series < lower_fence) | (valid_series > upper_fence)
        anom_indices = valid_series[anom_mask].index

        anomalies: List[AnomalyPoint] = []
        for idx in anom_indices:
            val = float(valid_series.loc[idx])
            dist = max(lower_fence - val, val - upper_fence)
            confidence = min(1.0, max(0.5, round(0.5 + 0.5 * (dist / max(iqr, 1e-6)), 3)))
            anomalies.append(
                AnomalyPoint(
                    row_index=int(idx),
                    column=column,
                    value=val,
                    method="iqr",
                    iqr_distance=round(dist, 2),
                    confidence_score=confidence,
                    details=f"Value {val:.2f} outside fence [{lower_fence:.2f}, {upper_fence:.2f}] (IQR={iqr:.2f})",
                )
            )

        anomalies.sort(key=lambda a: a.confidence_score, reverse=True)
        anom_count = len(anomalies)
        anom_rate = round((anom_count / total_evaluated) * 100.0, 2) if total_evaluated > 0 else 0.0

        return AnomalyColumnSummary(
            column=column,
            method="iqr",
            threshold=multiplier,
            total_evaluated=total_evaluated,
            anomalous_count=anom_count,
            anomaly_rate=anom_rate,
            top_anomalies=anomalies[:10],
        )

    def detect_streaming_anomalies(
        self,
        dataset: DataSet,
        column: str,
    ) -> List[AnomalyColumnSummary]:
        """Execute two-pass streaming anomaly detection for memory-bounded execution on large datasets."""
        chunk_size = self.config.chunk_size
        stats = StreamingColumnStats(column)

        # Pass 1: Accumulate mean, variance, reservoir quantiles
        for chunk in dataset.iter_chunks(chunk_size=chunk_size):
            if column in chunk.columns:
                stats.update(chunk[column])

        results: List[AnomalyColumnSummary] = []

        if "zscore" in self.config.methods:
            z_threshold = self.config.z_threshold
            mean = stats.mean
            std = stats.std
            z_anomalies: List[AnomalyPoint] = []
            z_count = 0

            # Pass 2: Evaluate chunks
            for chunk in dataset.iter_chunks(chunk_size=chunk_size):
                if column not in chunk.columns or std == 0.0:
                    continue
                s = pd.to_numeric(chunk[column], errors="coerce")
                valid = s.dropna()
                z = (valid - mean).abs() / std
                mask = z > z_threshold
                for idx in valid[mask].index:
                    z_count += 1
                    if len(z_anomalies) < 10:
                        zv = float(z.loc[idx])
                        val = float(valid.loc[idx])
                        conf = min(1.0, max(0.5, round(zv / (z_threshold * 1.5), 3)))
                        z_anomalies.append(
                            AnomalyPoint(
                                row_index=int(idx),
                                column=column,
                                value=val,
                                method="zscore",
                                z_score=round(zv, 2),
                                confidence_score=conf,
                                details=f"Z-score {zv:.2f} > {z_threshold:.2f} (streaming)",
                            )
                        )

            rate = round((z_count / stats.count) * 100.0, 2) if stats.count > 0 else 0.0
            results.append(
                AnomalyColumnSummary(
                    column=column,
                    method="zscore",
                    threshold=z_threshold,
                    total_evaluated=stats.count,
                    anomalous_count=z_count,
                    anomaly_rate=rate,
                    top_anomalies=z_anomalies,
                )
            )

        if "iqr" in self.config.methods:
            iqr_mult = self.config.iqr_multiplier
            q1, q3 = stats.get_quantiles(0.25, 0.75)
            iqr = q3 - q1
            lower_fence = q1 - (iqr_mult * iqr)
            upper_fence = q3 + (iqr_mult * iqr)
            iqr_anomalies: List[AnomalyPoint] = []
            iqr_count = 0

            if iqr > 0.0:
                for chunk in dataset.iter_chunks(chunk_size=chunk_size):
                    if column not in chunk.columns:
                        continue
                    s = pd.to_numeric(chunk[column], errors="coerce")
                    valid = s.dropna()
                    mask = (valid < lower_fence) | (valid > upper_fence)
                    for idx in valid[mask].index:
                        iqr_count += 1
                        if len(iqr_anomalies) < 10:
                            val = float(valid.loc[idx])
                            dist = max(lower_fence - val, val - upper_fence)
                            conf = min(
                                1.0, max(0.5, round(0.5 + 0.5 * (dist / max(iqr, 1e-6)), 3))
                            )
                            iqr_anomalies.append(
                                AnomalyPoint(
                                    row_index=int(idx),
                                    column=column,
                                    value=val,
                                    method="iqr",
                                    iqr_distance=round(dist, 2),
                                    confidence_score=conf,
                                    details=f"Value {val:.2f} outside streaming fence [{lower_fence:.2f}, {upper_fence:.2f}]",
                                )
                            )

            rate = round((iqr_count / stats.count) * 100.0, 2) if stats.count > 0 else 0.0
            results.append(
                AnomalyColumnSummary(
                    column=column,
                    method="iqr",
                    threshold=iqr_mult,
                    total_evaluated=stats.count,
                    anomalous_count=iqr_count,
                    anomaly_rate=rate,
                    top_anomalies=iqr_anomalies,
                )
            )

        return results

    def analyze(self, dataset: DataSet) -> AnomalyReport:
        """Run anomaly detection across all designated numeric columns."""
        if not self.config.enabled:
            return AnomalyReport(
                dataset_name=dataset.name,
                total_anomalies=0,
                columns_evaluated=0,
                column_summaries=[],
            )

        target_columns = self._select_numeric_columns(dataset)
        summaries: List[AnomalyColumnSummary] = []
        total_anomalies = 0

        # If dataset row count is high (e.g. > chunk_size), use streaming mode
        is_large = dataset.row_count > self.config.chunk_size

        for col in target_columns:
            if is_large:
                col_results = self.detect_streaming_anomalies(dataset, col)
                for res in col_results:
                    summaries.append(res)
                    total_anomalies += res.anomalous_count
            else:
                if "zscore" in self.config.methods:
                    z_res = self.detect_zscore(dataset, col, self.config.z_threshold)
                    summaries.append(z_res)
                    total_anomalies += z_res.anomalous_count

                if "iqr" in self.config.methods:
                    iqr_res = self.detect_iqr(dataset, col, self.config.iqr_multiplier)
                    summaries.append(iqr_res)
                    total_anomalies += iqr_res.anomalous_count

        return AnomalyReport(
            dataset_name=dataset.name,
            total_anomalies=total_anomalies,
            columns_evaluated=len(target_columns),
            column_summaries=summaries,
        )
