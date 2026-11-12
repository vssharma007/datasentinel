"""SMTP email alert service (summary only, no raw data rows)."""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from datasentinel.config.schema import EmailAlertConfig
from datasentinel.core.exceptions import AlertError
from datasentinel.core.types import RunSummary


class EmailAlertService:
    """Dispatches quality alert summaries via SMTP."""

    def __init__(self, config: EmailAlertConfig) -> None:
        self.config: EmailAlertConfig = config

    def send_alert(self, summary: RunSummary) -> bool:
        """Send email alert with validation summary metrics."""
        if not self.config.enabled:
            return False

        subject = (
            f"{self.config.subject_prefix} [{summary.status.value.upper()}] "
            f"Dataset: {summary.dataset_name} (Pass Rate: {summary.overall_pass_rate}%)"
        )

        # Build clean summary text (Strict adherence: NO raw data rows)
        text_lines = [
            f"DataSentinel Quality Run Summary",
            f"==================================",
            f"Dataset:              {summary.dataset_name}",
            f"Run ID:               {summary.run_id}",
            f"Timestamp (UTC):      {summary.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Overall Status:       {summary.status.value.upper()}",
            f"Pass Rate:            {summary.overall_pass_rate}%",
            f"Total Rules Checked:  {summary.total_rules}",
            f"Passed:               {summary.passed_rules}",
            f"Failed:               {summary.failed_rules}",
            f"Warnings:             {summary.warning_rules}",
            f"Schema Drift:         {'YES' if summary.schema_drift_detected else 'NO'}",
            f"Total Anomalies:      {summary.total_anomalies}",
            "",
            "Top Rule Violations:",
            "--------------------",
        ]

        failed_rules = [r for r in summary.rule_results if not r.passed]
        if failed_rules:
            for r in failed_rules[:5]:
                text_lines.append(
                    f" - [{r.severity.value.upper()}] {r.rule_name} (column: {r.column}): "
                    f"{r.violation_count} violations ({100.0 - r.pass_rate:.1f}% fail rate)"
                )
        else:
            text_lines.append(" No rule violations detected.")

        body_text = "\n".join(text_lines)

        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
            <h2 style="color: {'#e11d48' if summary.status.value == 'failed' else '#10b981'};">
                DataSentinel Quality Report: {summary.status.value.upper()}
            </h2>
            <table style="border-collapse: collapse; width: 100%; max-width: 600px;">
                <tr><td style="padding: 6px; font-weight: bold;">Dataset</td><td>{summary.dataset_name}</td></tr>
                <tr style="background: #f8fafc;"><td style="padding: 6px; font-weight: bold;">Pass Rate</td><td>{summary.overall_pass_rate}%</td></tr>
                <tr><td style="padding: 6px; font-weight: bold;">Rules (Pass / Fail / Warn)</td><td>{summary.passed_rules} / {summary.failed_rules} / {summary.warning_rules}</td></tr>
                <tr style="background: #f8fafc;"><td style="padding: 6px; font-weight: bold;">Schema Drift</td><td>{'Detected' if summary.schema_drift_detected else 'None'}</td></tr>
                <tr><td style="padding: 6px; font-weight: bold;">Anomalies Flagged</td><td>{summary.total_anomalies}</td></tr>
            </table>
            <h3>Top Violations</h3>
            <ul>
        """
        for r in failed_rules[:5]:
            html_body += f"<li><strong>{r.rule_name}</strong> ({r.column}): {r.violation_count} issues</li>"
        if not failed_rules:
            html_body += "<li>All configured rules passed successfully.</li>"
        html_body += "</ul></body></html>"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.config.sender
        msg["To"] = ", ".join(self.config.recipients)

        msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        password = os.environ.get(self.config.password_env, "")
        username = os.environ.get(self.config.username_env, "")

        try:
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=10) as server:
                if self.config.use_tls:
                    server.starttls()
                if username and password:
                    server.login(username, password)
                server.sendmail(self.config.sender, self.config.recipients, msg.as_string())
            return True
        except Exception as exc:
            raise AlertError(
                f"Failed to deliver SMTP alert to {self.config.recipients}",
                details=str(exc),
            ) from exc
