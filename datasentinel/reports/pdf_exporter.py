"""Executive PDF report generator using ReportLab."""

from pathlib import Path
from typing import List, Union
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from datasentinel.core.exceptions import DataSentinelError
from datasentinel.core.types import RunSummary


class PDFReportExporter:
    """Exports structured executive validation summary into high-resolution PDF."""

    @staticmethod
    def export(summary: RunSummary, output_path: Union[str, Path]) -> Path:
        """Render RunSummary into formatted executive PDF."""
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            doc = SimpleDocTemplate(
                str(out_file),
                pagesize=letter,
                rightMargin=36,
                leftMargin=36,
                topMargin=36,
                bottomMargin=36,
            )
            styles = getSampleStyleSheet()

            # Custom typography styles
            title_style = ParagraphStyle(
                "DocTitle",
                parent=styles["Heading1"],
                fontName="Helvetica-Bold",
                fontSize=20,
                leading=24,
                textColor=colors.HexColor("#0f172a"),
            )
            h2_style = ParagraphStyle(
                "SectionH2",
                parent=styles["Heading2"],
                fontName="Helvetica-Bold",
                fontSize=13,
                leading=16,
                textColor=colors.HexColor("#1e293b"),
                spaceBefore=14,
                spaceAfter=6,
            )
            meta_style = ParagraphStyle(
                "MetaText",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=9,
                leading=12,
                textColor=colors.HexColor("#475569"),
            )
            cell_style = ParagraphStyle(
                "TableCell",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=8,
                leading=10,
                textColor=colors.HexColor("#1e293b"),
            )
            badge_pass = ParagraphStyle(
                "PassBadge",
                parent=cell_style,
                fontName="Helvetica-Bold",
                textColor=colors.HexColor("#065f46"),
            )
            badge_fail = ParagraphStyle(
                "FailBadge",
                parent=cell_style,
                fontName="Helvetica-Bold",
                textColor=colors.HexColor("#991b1b"),
            )

            story = []

            # Document Title & Subtitle
            story.append(Paragraph("🛡️ DataSentinel Executive Quality Report", title_style))
            story.append(
                Paragraph(
                    "Automated Pipeline Quality, Schema Drift & Statistical Anomaly Monitoring",
                    meta_style,
                )
            )
            story.append(Spacer(1, 10))
            story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563eb")))
            story.append(Spacer(1, 10))

            # Run Metadata Grid
            status_color = "#10b981" if summary.status.value == "passed" else "#ef4444"
            meta_data = [
                [
                    Paragraph(f"<b>Dataset:</b> {summary.dataset_name}", meta_style),
                    Paragraph(f"<b>Run ID:</b> {summary.run_id[:16]}...", meta_style),
                ],
                [
                    Paragraph(
                        f"<b>Timestamp:</b> {summary.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
                        meta_style,
                    ),
                    Paragraph(
                        f"<b>Status:</b> <font color='{status_color}'><b>{summary.status.value.upper()}</b></font>",
                        meta_style,
                    ),
                ],
            ]
            meta_table = Table(meta_data, colWidths=[270, 270])
            meta_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                        ("PADDING", (0, 0), (-1, -1), 6),
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ]
                )
            )
            story.append(meta_table)
            story.append(Spacer(1, 14))

            # Executive Summary Metrics Table
            story.append(Paragraph("Executive Summary Metrics", h2_style))
            metrics_data = [
                ["Pass Rate", "Total Rules", "Passed", "Failed", "Warnings", "Drift", "Anomalies"],
                [
                    f"{summary.overall_pass_rate}%",
                    str(summary.total_rules),
                    str(summary.passed_rules),
                    str(summary.failed_rules),
                    str(summary.warning_rules),
                    "DETECTED" if summary.schema_drift_detected else "MATCH",
                    str(summary.total_anomalies),
                ],
            ]
            kpi_table = Table(metrics_data, colWidths=[80, 75, 75, 75, 75, 80, 80])
            kpi_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 8),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 1), (-1, 1), 10),
                        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f1f5f9")),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                        ("PADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.append(kpi_table)
            story.append(Spacer(1, 14))

            # Quality Rules Breakdown Table
            story.append(Paragraph("Quality Rules Verification", h2_style))
            rules_header = ["Status", "Rule Name", "Type", "Column", "Pass Rate", "Violations"]
            rules_rows = [rules_header]

            for r in summary.rule_results:
                badge = Paragraph("PASS", badge_pass) if r.passed else Paragraph("FAIL", badge_fail)
                rules_rows.append(
                    [
                        badge,
                        Paragraph(f"<b>{r.rule_name}</b>", cell_style),
                        Paragraph(r.rule_type.value, cell_style),
                        Paragraph(r.column, cell_style),
                        Paragraph(f"{r.pass_rate}%", cell_style),
                        Paragraph(str(r.violation_count), cell_style),
                    ]
                )

            rules_table = Table(rules_rows, colWidths=[50, 150, 100, 110, 65, 65])
            rules_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 8),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                        ("PADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            story.append(rules_table)
            story.append(Spacer(1, 14))

            # Schema Drift Table (if drift detected)
            if summary.schema_report and summary.schema_report.drifts:
                story.append(Paragraph("Schema Drift Discrepancies", h2_style))
                drift_header = ["Drift Type", "Column", "Baseline", "Current", "Details"]
                drift_rows = [drift_header]
                for d in summary.schema_report.drifts:
                    drift_rows.append(
                        [
                            Paragraph(d.drift_type.value, cell_style),
                            Paragraph(d.column_name, cell_style),
                            Paragraph(d.baseline_value or "-", cell_style),
                            Paragraph(d.current_value or "-", cell_style),
                            Paragraph(d.details, cell_style),
                        ]
                    )
                drift_table = Table(drift_rows, colWidths=[100, 90, 80, 80, 190])
                drift_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fee2e2")),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, 0), 8),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                            ("PADDING", (0, 0), (-1, -1), 5),
                        ]
                    )
                )
                story.append(drift_table)
                story.append(Spacer(1, 14))

            # Statistical Anomalies Summary (if any)
            if summary.anomaly_report and summary.anomaly_report.column_summaries:
                story.append(Paragraph("Statistical Anomaly Insights", h2_style))
                anom_header = ["Column", "Method", "Threshold", "Evaluated", "Flagged", "Rate"]
                anom_rows = [anom_header]
                for c in summary.anomaly_report.column_summaries:
                    anom_rows.append(
                        [
                            Paragraph(c.column, cell_style),
                            Paragraph(c.method.upper(), cell_style),
                            Paragraph(str(c.threshold), cell_style),
                            Paragraph(str(c.total_evaluated), cell_style),
                            Paragraph(str(c.anomalous_count), cell_style),
                            Paragraph(f"{c.anomaly_rate}%", cell_style),
                        ]
                    )
                anom_table = Table(anom_rows, colWidths=[110, 80, 70, 90, 90, 100])
                anom_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fef3c7")),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, 0), 8),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                            ("PADDING", (0, 0), (-1, -1), 5),
                        ]
                    )
                )
                story.append(anom_table)

            doc.build(story)
            return out_file
        except Exception as exc:
            raise DataSentinelError("Failed to render PDF report", details=str(exc)) from exc
