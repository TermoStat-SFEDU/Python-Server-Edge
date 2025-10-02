# File: apps/auditing/apps.py
import logging
import os
import sys
from typing import Any

from django.apps import AppConfig
from django.conf import settings

logger = logging.getLogger(__name__)


class AuditingConfig(AppConfig):
    """Configuration for the Auditing application."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.auditing"
    verbose_name = "Аудит и Вебхуки"

    def ready(self) -> None:
        """
        Execute startup logic when the app is ready.

        This method imports signals to connect them, synchronizes event types
        from definitions into the database, and starts the background scheduler
        for periodic tasks like data pruning. Custom template tags are now
        registered globally via the TEMPLATES setting.
        """
        # Implicitly connect signal handlers decorated with @receiver.
        from . import signals

        is_running_management_command = any(
            command in sys.argv
            for command in ["makemigrations", "migrate", "collectstatic"]
        )
        if is_running_management_command:
            return

        # Do not run startup logic if in test mode, as dashboard app handles it.
        if settings.TEST_MODE:
            logger.info("TEST_MODE is active. Skipping AuditingConfig startup logic.")
            return

        # Dynamically create/update Event types from a central definition.
        self.synchronize_event_types()
        # Start the scheduler for periodic tasks.
        self.start_scheduler()

    def synchronize_event_types(self) -> None:
        """
        Ensure Event objects in the database match definitions in events.py.

        This method iterates through the `EVENT_DEFINITIONS` list and uses
        `update_or_create` to ensure that an `Event` object exists in the
        database for each definition, creating or updating it as necessary.
        """
        from .events import EVENT_DEFINITIONS
        from .models import Event

        for event_def in EVENT_DEFINITIONS:
            Event.objects.update_or_create(
                identifier=event_def["identifier"], defaults={"name": event_def["name"]}
            )
        logger.info("Event types synchronized.")

    def start_scheduler(self) -> None:
        """
        Start the APScheduler and add the daily data pruning job.

        This function initializes the background scheduler, adds the
        'prune_data' management command as a daily cron job, and starts the
        scheduler if it's not already running. It includes a check to ensure
        the scheduler is only started by the main Django process.
        """
        from django.core.management import call_command

        # The scheduler should only be started once by the main process
        if "runserver" in sys.argv and not os.environ.get("RUN_MAIN"):
            return

        def prune_data_job() -> None:
            """Wrapper function to call the management command."""
            try:
                call_command("prune_data")
            except Exception as e:
                logger.error(f"Error running prune_data job: {e}")

        try:
            from .webhooks import scheduler

            if not scheduler.get_job("prune_data_daily"):
                scheduler.add_job(
                    prune_data_job,
                    trigger="cron",
                    hour="3",
                    minute="00",
                    id="prune_data_daily",
                    jobstore="default",
                    replace_existing=True,
                )
                logger.info("Added daily job: 'prune_data_daily'.")

            if not scheduler.running:
                scheduler.start()
                logger.info("Scheduler started.")

        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
