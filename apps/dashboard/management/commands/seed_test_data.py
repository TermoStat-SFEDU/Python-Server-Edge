import logging
from typing import Any

from django.core.management.base import BaseCommand
from django.conf import settings

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """A Django management command to seed the database with test data."""
    help = "Clears old data and populates the database with initial test data for Grafana."

    def handle(self, *args: Any, **options: Any) -> None:
        """
        Execute the data seeding logic.

        This command should only be run when `TEST_MODE` is enabled. It
        initializes the test data generator and calls its method to create
        a historical dataset.

        Args:
            *args: Variable length argument list.
            **options: Arbitrary keyword arguments.
        """
        if not settings.TEST_MODE:
            self.stdout.write(self.style.WARNING("TEST_MODE is not enabled. Aborting."))
            return

        self.stdout.write(self.style.SUCCESS("--- Starting test data seeding ---"))
        
        from apps.dashboard.test_data_generator import generator

        # Synchronize event types before generating data
        from apps.auditing.apps import AuditingConfig
        AuditingConfig.synchronize_event_types(self)

        generator.generate_initial_data()
        
        self.stdout.write(self.style.SUCCESS("--- Test data seeding finished successfully ---"))
