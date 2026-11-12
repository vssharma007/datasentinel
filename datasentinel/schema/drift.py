"""Schema drift detection comparing baseline to current schema."""

from datetime import datetime
from typing import List, Optional

from datasentinel.core.types import (
    DriftItem,
    DriftType,
    SchemaDriftReport,
    SchemaFingerprint,
)


class SchemaDriftDetector:
    """Compares current dataset schema against registered baseline fingerprint."""

    @staticmethod
    def detect_drift(
        baseline: Optional[SchemaFingerprint],
        current: SchemaFingerprint,
    ) -> SchemaDriftReport:
        """Calculate diff between baseline and current schema fingerprints.

        If baseline is None, returns report with has_drift=False (no baseline established yet).
        """
        if baseline is None:
            return SchemaDriftReport(
                dataset_name=current.dataset_name,
                has_drift=False,
                baseline_timestamp=None,
                current_timestamp=current.created_at,
                drifts=[],
            )

        drifts: List[DriftItem] = []
        base_cols = baseline.columns
        curr_cols = current.columns

        # Check for removed columns
        for col_name, base_schema in base_cols.items():
            if col_name not in curr_cols:
                drifts.append(
                    DriftItem(
                        drift_type=DriftType.COLUMN_REMOVED,
                        column_name=col_name,
                        baseline_value=f"{base_schema.data_type} (nullable={base_schema.nullable})",
                        current_value=None,
                        details=f"Column '{col_name}' was present in baseline but has been removed.",
                    )
                )

        # Check for added columns and changes
        for col_name, curr_schema in curr_cols.items():
            if col_name not in base_cols:
                drifts.append(
                    DriftItem(
                        drift_type=DriftType.COLUMN_ADDED,
                        column_name=col_name,
                        baseline_value=None,
                        current_value=f"{curr_schema.data_type} (nullable={curr_schema.nullable})",
                        details=f"New column '{col_name}' detected which was not in baseline schema.",
                    )
                )
            else:
                base_schema = base_cols[col_name]

                # Check data type change
                if base_schema.data_type != curr_schema.data_type:
                    drifts.append(
                        DriftItem(
                            drift_type=DriftType.TYPE_CHANGED,
                            column_name=col_name,
                            baseline_value=base_schema.data_type,
                            current_value=curr_schema.data_type,
                            details=(
                                f"Type altered for column '{col_name}': "
                                f"expected '{base_schema.data_type}', found '{curr_schema.data_type}'."
                            ),
                        )
                    )

                # Check nullability change
                if (not base_schema.nullable) and curr_schema.nullable:
                    drifts.append(
                        DriftItem(
                            drift_type=DriftType.NULLABILITY_CHANGED,
                            column_name=col_name,
                            baseline_value="not null",
                            current_value="contains nulls",
                            details=(
                                f"Nullability altered for '{col_name}': "
                                "baseline was non-null, but current data contains null values."
                            ),
                        )
                    )

        return SchemaDriftReport(
            dataset_name=current.dataset_name,
            has_drift=len(drifts) > 0,
            baseline_timestamp=baseline.created_at,
            current_timestamp=current.created_at,
            drifts=drifts,
        )
