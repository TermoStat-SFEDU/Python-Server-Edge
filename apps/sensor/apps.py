from django.apps import AppConfig


class SensorConfig(AppConfig):
    """Configuration for the Sensor application."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.sensor"
    verbose_name = "Датчики"
