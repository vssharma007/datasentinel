"""APScheduler recurring validation runner with coalesce=True overlap protection."""

import logging
from typing import Callable, Optional
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from datasentinel.config.schema import SentinelConfig
from datasentinel.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class ValidationScheduler:
    """Schedules periodic DataSentinel validation runs using cron expressions."""

    def __init__(
        self,
        config: SentinelConfig,
        task_callback: Callable[[], None],
    ) -> None:
        self.config: SentinelConfig = config
        self.task_callback: Callable[[], None] = task_callback
        self.scheduler: BlockingScheduler = BlockingScheduler()

        if not self.config.scheduler or not self.config.scheduler.cron:
            raise ConfigurationError(
                "Scheduler configuration missing 'cron' expression in YAML.",
                details="Add a 'scheduler' block with a 5-field cron expression.",
            )

    def start(self) -> None:
        """Start blocking scheduler loop."""
        if not self.config.scheduler:
            return

        cron_expr = self.config.scheduler.cron
        coalesce = self.config.scheduler.coalesce
        max_instances = self.config.scheduler.max_instances

        trigger = CronTrigger.from_crontab(cron_expr)

        self.scheduler.add_job(
            func=self.task_callback,
            trigger=trigger,
            id=f"datasentinel_{self.config.dataset_name}",
            name=f"DataSentinel validation for {self.config.dataset_name}",
            coalesce=coalesce,  # Prevents overlapping missed runs
            max_instances=max_instances,
            replace_existing=True,
        )

        logger.info(
            f"Starting scheduler for '{self.config.dataset_name}' with cron: '{cron_expr}' (coalesce={coalesce})"
        )
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self.scheduler.shutdown(wait=False)

    def stop(self) -> None:
        """Shutdown scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
