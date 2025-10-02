from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.auditing.models import LogEntry
from apps.sensor.models import Device, SensorConfig


class Command(BaseCommand):
    """A Django management command to prune old data based on SensorConfig."""
    help = "Prunes old logs and inactive devices based on settings in SensorConfig."

    def handle(self, *args: Any, **options: Any) -> None:
        """
        Execute the data pruning logic.

        This method fetches the global `SensorConfig` and performs three main
        pruning tasks based on its settings:
        1. Deletes `Device` records that have been inactive for a specified period.
        2. Deletes `LogEntry` records older than a specified number of days.
        3. Deletes the oldest `LogEntry` records if the total count exceeds a maximum.

        Args:
            *args: Variable length argument list.
            **options: Arbitrary keyword arguments.
        """
        self.stdout.write(self.style.SUCCESS("--- Starting data pruning task ---"))

        try:
            config = SensorConfig.get_solo()
        except SensorConfig.DoesNotExist:
            self.stdout.write(
                self.style.ERROR("SensorConfig not found. Skipping task.")
            )
            return

        # 1. Prune devices by inactivity
        if config.device_pruning_days is not None and config.device_pruning_days > 0:
            self.stdout.write(
                f"Pruning devices inactive for more than {config.device_pruning_days} days..."
            )
            cutoff_date = timezone.now() - timedelta(days=config.device_pruning_days)
            devices_to_prune = Device.objects.filter(last_seen__lt=cutoff_date)

            device_count = devices_to_prune.count()

            if device_count > 0:
                if not config.device_pruning_delete_logs:
                    # Preserve logs by disassociating them from the devices to be deleted.
                    self.stdout.write("Preserving audit logs for pruned devices...")
                    logs_updated_count = LogEntry.objects.filter(
                        device__in=devices_to_prune
                    ).update(device=None)
                    self.stdout.write(
                        f"Disassociated {logs_updated_count} log entries."
                    )

                # Now, delete the devices.
                # TemperatureReadings will be cascade-deleted automatically by the database.
                _, deleted_objects = devices_to_prune.delete()
                deleted_count = deleted_objects.get("sensor.Device", 0)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully pruned {deleted_count} inactive devices."
                    )
                )
            else:
                self.stdout.write("No inactive devices found to prune.")
        else:
            self.stdout.write("Device pruning by inactivity is disabled.")

        # 2. Prune logs by age
        if config.log_rotation_days is not None and config.log_rotation_days > 0:
            self.stdout.write(
                f"Pruning logs older than {config.log_rotation_days} days..."
            )
            cutoff_date = timezone.now() - timedelta(days=config.log_rotation_days)
            logs_to_prune = LogEntry.objects.filter(timestamp__lt=cutoff_date)
            count, _ = logs_to_prune.delete()
            self.stdout.write(
                self.style.SUCCESS(f"Successfully pruned {count} logs by age.")
            )
        else:
            self.stdout.write("Log pruning by age is disabled.")

        # 3. Prune logs by max count
        if (
            config.log_rotation_max_count is not None
            and config.log_rotation_max_count > 0
        ):
            self.stdout.write(
                f"Pruning logs to keep a maximum of {config.log_rotation_max_count} entries..."
            )

            # Find the ID of the Nth most recent log entry
            try:
                latest_logs_qs = LogEntry.objects.order_by("-timestamp")
                threshold_entry = latest_logs_qs[config.log_rotation_max_count]

                # Delete all logs older than this entry
                logs_to_prune = LogEntry.objects.filter(
                    timestamp__lt=threshold_entry.timestamp
                )
                count, _ = logs_to_prune.delete()
                self.stdout.write(
                    self.style.SUCCESS(f"Successfully pruned {count} logs by count.")
                )

            except IndexError:
                # This happens if there are fewer logs than the max count, which is fine.
                self.stdout.write(
                    "Total log count is less than the maximum limit. No pruning needed."
                )
        else:
            self.stdout.write("Log pruning by max count is disabled.")

        self.stdout.write(self.style.SUCCESS("--- Data pruning task finished ---"))
