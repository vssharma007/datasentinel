"""Report generation orchestrator for HTML and PDF outputs."""

from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union
from jinja2 import Environment, FileSystemLoader, select_autoescape

from datasentinel.core.exceptions import DataSentinelError
from datasentinel.core.types import RunSummary
from datasentinel.reports.pdf_exporter import PDFReportExporter

TEMPLATE_DIR = Path(__file__).parent / "templates"


class ReportGenerator:
    """Orchestrates generation of HTML dashboards and PDF executive summaries."""

    def __init__(self, template_dir: Optional[Path] = None) -> None:
        self.template_dir = template_dir or TEMPLATE_DIR
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def generate_html_report(
        self,
        summary: RunSummary,
        output_path: Union[str, Path],
        trend_data: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Render standalone HTML dashboard with embedded Chart.js visualizations."""
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        if trend_data is None:
            trend_data = {
                "labels": [summary.timestamp.strftime("%m-%d %H:%M")],
                "pass_rates": [summary.overall_pass_rate],
                "anomalies": [summary.total_anomalies],
                "failed_counts": [summary.failed_rules],
            }

        try:
            template = self.jinja_env.get_template("report.html.jinja")
            html_content = template.render(
                summary=summary,
                trend_data=trend_data,
            )
            out_file.write_text(html_content, encoding="utf-8")
            return out_file
        except Exception as exc:
            raise DataSentinelError(
                f"Failed to generate HTML report to {out_file}", details=str(exc)
            ) from exc

    def generate_pdf_report(
        self,
        summary: RunSummary,
        output_path: Union[str, Path],
    ) -> Path:
        """Export high-resolution executive PDF summary."""
        return PDFReportExporter.export(summary, output_path)

    def generate_all(
        self,
        summary: RunSummary,
        output_dir: Union[str, Path],
        trend_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Path, Path]:
        """Generate both HTML and PDF reports inside target directory."""
        dir_path = Path(output_dir)
        dir_path.mkdir(parents=True, exist_ok=True)

        html_path = dir_path / f"{summary.dataset_name}_report_{summary.run_id[:8]}.html"
        pdf_path = dir_path / f"{summary.dataset_name}_report_{summary.run_id[:8]}.pdf"

        html_result = self.generate_html_report(summary, html_path, trend_data=trend_data)
        pdf_result = self.generate_pdf_report(summary, pdf_path)
        return html_result, pdf_result
