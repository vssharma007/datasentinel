"""Streaming statistical accumulators for memory-bounded calculation over large datasets."""

import math
import random
from typing import Dict, Iterator, List, Optional, Tuple
import numpy as np
import pandas as pd


class StreamingColumnStats:
    """Computes mean, standard deviation, and approximate quantiles over chunked streams."""

    def __init__(self, column: str, sample_capacity: int = 10000) -> None:
        self.column: str = column
        self.count: int = 0
        self.sum_val: float = 0.0
        self.sum_sq: float = 0.0
        self.min_val: float = float("inf")
        self.max_val: float = float("-inf")

        # Reservoir sampling for quantile estimation in fixed memory
        self.sample_capacity: int = sample_capacity
        self.reservoir: List[float] = []

    def update(self, values: pd.Series) -> None:
        """Process a chunk series of numeric values."""
        numeric_series = pd.to_numeric(values, errors="coerce").dropna()
        if numeric_series.empty:
            return

        chunk_count = len(numeric_series)
        chunk_sum = float(numeric_series.sum())
        chunk_sum_sq = float((numeric_series**2).sum())
        chunk_min = float(numeric_series.min())
        chunk_max = float(numeric_series.max())

        self.min_val = min(self.min_val, chunk_min)
        self.max_val = max(self.max_val, chunk_max)

        # Reservoir sampling (Algorithm R)
        for val in numeric_series:
            self.count += 1
            if len(self.reservoir) < self.sample_capacity:
                self.reservoir.append(float(val))
            else:
                j = random.randint(0, self.count - 1)
                if j < self.sample_capacity:
                    self.reservoir[j] = float(val)

        self.sum_val += chunk_sum
        self.sum_sq += chunk_sum_sq

    @property
    def mean(self) -> float:
        """Calculated mean."""
        if self.count == 0:
            return 0.0
        return self.sum_val / self.count

    @property
    def std(self) -> float:
        """Sample standard deviation."""
        if self.count <= 1:
            return 0.0
        variance = (self.sum_sq - (self.sum_val**2 / self.count)) / (self.count - 1)
        if variance <= 0.0 or math.isnan(variance):
            return 0.0
        return math.sqrt(variance)

    def get_quantiles(self, q1: float = 0.25, q3: float = 0.75) -> Tuple[float, float]:
        """Estimate Q1 and Q3 from reservoir sample."""
        if not self.reservoir:
            return 0.0, 0.0
        arr = np.array(self.reservoir)
        val_q1 = float(np.percentile(arr, q1 * 100))
        val_q3 = float(np.percentile(arr, q3 * 100))
        return val_q1, val_q3
