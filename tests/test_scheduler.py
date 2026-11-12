"""Tests for APScheduler recurring runner and coalesce overlap protection."""

from unittest.mock import MagicMock
import pytest

from datasentinel.config.schema import SchedulerConfig, SentinelConfig, SourceConfig
from datasentinel.scheduler.runner import ValidationScheduler


def test_validation_scheduler_configuration() -> None:
    config = SentinelConfig(
        dataset_name="scheduled_pipeline",
        source=SourceConfig(type="csv", path="dummy.csv"),
        scheduler=SchedulerConfig(cron="0 * * * *", coalesce=True),
    )

    mock_callback = MagicMock()
    runner = ValidationScheduler(config, task_callback=mock_callback)

    assert runner.config.scheduler is not None
    assert runner.config.scheduler.coalesce is True
    assert runner.config.scheduler.cron == "0 * * * *"
