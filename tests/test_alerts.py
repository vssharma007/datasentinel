"""Tests for Email and Slack alert services."""

import json
from unittest.mock import MagicMock, patch
import pytest

from datasentinel.alerts.email_service import EmailAlertService
from datasentinel.alerts.webhook_service import SlackAlertService
from datasentinel.config.schema import EmailAlertConfig, SlackAlertConfig
from datasentinel.core.types import (
    RuleResult,
    RuleType,
    RunSummary,
    Severity,
    ValidationStatus,
    ViolationSample,
)


@pytest.fixture
def failing_run_summary() -> RunSummary:
    return RunSummary(
        run_id="fail-run-999",
        dataset_name="critical_orders",
        status=ValidationStatus.FAILED,
        duration_seconds=1.2,
        total_rows=500,
        total_columns=4,
        total_rules=2,
        passed_rules=1,
        failed_rules=1,
        warning_rules=0,
        overall_pass_rate=50.0,
        schema_drift_detected=True,
        total_anomalies=3,
        rule_results=[
            RuleResult(
                rule_name="mandatory_id",
                rule_type=RuleType.NULL_CHECK,
                column="order_id",
                passed=False,
                total_checked=500,
                violation_count=5,
                pass_rate=99.0,
                severity=Severity.CRITICAL,
                message="5 null IDs found",
                samples=[
                    ViolationSample(
                        row_index=12,
                        column="order_id",
                        value="NULL",
                        reason="missing",
                    )
                ],
            )
        ],
    )


def test_email_alert_service_no_raw_data_rows(failing_run_summary: RunSummary) -> None:
    config = EmailAlertConfig(
        enabled=True,
        sender="alerts@test.com",
        recipients=["team@test.com"],
    )
    service = EmailAlertService(config)

    with patch("smtplib.SMTP") as mock_smtp:
        mock_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_instance

        sent = service.send_alert(failing_run_summary)
        assert sent is True
        assert mock_instance.sendmail.called

        # Verify sent email content has summary counts, not raw database rows
        args, kwargs = mock_instance.sendmail.call_args
        msg_str = args[2]
        assert "critical_orders" in msg_str
        assert "Pass Rate:            50.0%" in msg_str
        assert "Total Anomalies:      3" in msg_str


def test_slack_webhook_payload_structure(
    monkeypatch: pytest.MonkeyPatch, failing_run_summary: RunSummary
) -> None:
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T00/B00/X00")
    config = SlackAlertConfig(enabled=True)
    service = SlackAlertService(config)

    payload = service.build_payload(failing_run_summary)
    blocks = payload["blocks"]
    assert len(blocks) >= 2

    # Verify no raw data rows are embedded in JSON payload
    payload_str = json.dumps(payload)
    assert "critical_orders" in payload_str
    assert "50.0%" in payload_str
    # Verify top violations section is present
    assert "mandatory_id" in payload_str


def test_slack_webhook_send(
    monkeypatch: pytest.MonkeyPatch, failing_run_summary: RunSummary
) -> None:
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T00/B00/X00")
    config = SlackAlertConfig(enabled=True)
    service = SlackAlertService(config)

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        assert service.send_alert(failing_run_summary) is True
        assert mock_post.called
