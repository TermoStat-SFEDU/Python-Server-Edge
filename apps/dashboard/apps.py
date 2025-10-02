import logging
import os
import sys

from django.apps import AppConfig
from django.conf import settings

logger = logging.getLogger(__name__)


class DashboardConfig(AppConfig):
    """Configuration for the Dashboard application."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.dashboard"
    verbose_name = "Панель мониторинга"

    def ready(self) -> None:
        """
        Execute startup logic when the Dashboard app is ready.

        If `TEST_MODE` is enabled, this method starts a scheduler to
        periodically update the simulated data. The initial data seeding
        is now handled by a separate management command.
        """
        if not settings.TEST_MODE:
            return

        is_running_management_command = any(
            command in sys.argv
            for command in ["makemigrations", "migrate", "collectstatic", "seed_test_data"]
        )
        if is_running_management_command or (
            "runserver" in sys.argv and not os.environ.get("RUN_MAIN")
        ):
            return

        logger.info("TEST_MODE is active. Starting scheduler for periodic data generation.")
        from .test_data_generator import generator
        from apps.auditing.webhooks import scheduler

        if not scheduler.get_job("test_data_tick"):
            scheduler.add_job(
                generator.tick,
                "interval",
                seconds=5,
                id="test_data_tick",
                replace_existing=True,
            )
            logger.info("Added periodic job for test data simulation.")

        if not scheduler.running:
            try:
                scheduler.start()
                logger.info("Scheduler started for test data generation.")
            except Exception as e:
                logger.error(f"Failed to start scheduler for test data: {e}")
