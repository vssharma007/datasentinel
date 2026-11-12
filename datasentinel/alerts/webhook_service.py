"""Slack webhook alert service using httpx."""

import os
from typing import Any, Dict, List
import httpx

from datasentinel.config.schema import SlackAlertConfig
from datasentinel.core.exceptions import AlertError
from datasentinel.core.types import RunSummary, ValidationStatus


class SlackAlertService:
    """Sends structured notification messages to Slack incoming webhook endpoints."""

    def __init__(self, config: SlackAlertConfig) -> None:
        self.config: SlackAlertConfig = config

    def _resolve_webhook_url(self) -> str:
        url = os.environ.get(self.config.webhook_url_env, "")
        if not url:
            raise AlertError(
                f"Slack webhook URL not found in environment variable '{self.config.webhook_url_env}'.",
                details="Set environment variable before triggering webhook alert.",
            )
        return url

    def build_payload(self, summary: RunSummary) -> Dict[str, Any]:
        """Construct Slack Block Kit payload without raw data rows."""
        status_emoji = {
            ValidationStatus.PASSED: "🟢",
            ValidationStatus.WARNING: "🟡",
            ValidationStatus.FAILED: "🔴",
            ValidationStatus.ERROR: "💥",
        }.get(summary.status, "ℹ️")

        title = f"{status_emoji} *DataSentinel Alert: {summary.dataset_name}* ({summary.status.value.upper()})"

        fields = [
            {"type": "mrkdwn", "text": f"*Pass Rate:*\n{summary.overall_pass_rate}%"},
            {"type": "mrkdwn", "text": f"*Rules Passed/Failed:*\n{summary.passed_rules} / {summary.failed_rules}"},
            {"type": "mrkdwn", "text": f"*Schema Drift:*\n{'⚠️ Detected' if summary.schema_drift_detected else 'None'}"},
            {"type": "mrkdwn", "text": f"*Anomalies:*\n{summary.total_anomalies} flagged"},
            {"type": "mrkdwn", "text": f"*Duration:*\n{summary.duration_seconds:.2f}s"},
            {"type": "mrkdwn", "text": f"*Total Rows:*\n{summary.total_rows:,}"},
        ]

        blocks: List[Dict[str, Any]] = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": title},
            },
            {
                "type": "section",
                "fields": fields,
            },
        ]

        failed = [r for r in summary.rule_results if not r.passed]
        if failed:
            top_issues_text = "*Top Rule Violations:*\n"
            for r in failed[:5]:
                top_issues_text += (
                    f"• *{r.rule_name}* (`{r.column}`): {r.violation_count} issues ({100.0 - r.pass_rate:.1f}% failed)\n"
                )
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": top_issues_text},
                }
            )

        payload: Dict[str, Any] = {"blocks": blocks}
        if self.config.channel:
            payload["channel"] = self.config.channel

        return payload

    def send_alert(self, summary: RunSummary) -> bool:
        """Send Slack alert message."""
        if not self.config.enabled:
            return False

        url = self._resolve_webhook_url()
        payload = self.build_payload(summary)

        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(url, json=payload)
                if res.status_code >= 400:
                    raise AlertError(
                        f"Slack webhook returned HTTP {res.status_code}",
                        details=res.text[:200],
                    )
            return True
        except httpx.RequestError as exc:
            raise AlertError("Network failure sending Slack alert", details=str(exc)) from exc
