from django.contrib import admin
from solo.admin import SingletonModelAdmin
from unfold.admin import ModelAdmin

from .models import Device, SensorConfig, TemperatureReading


@admin.register(SensorConfig)
class SensorConfigAdmin(ModelAdmin, SingletonModelAdmin):
    """Admin interface for the singleton SensorConfig model."""
    list_display = (
        "id",
        "period",
        "server_timeout",
        "log_rotation_days",
        "log_rotation_max_count",
        "device_pruning_days",
    )
    fieldsets = (
        ("Настройки датчиков", {"fields": ("period", "server_timeout")}),
        (
            "Ротация данных",
            {
                "fields": (
                    "log_rotation_days",
                    "log_rotation_max_count",
                    "device_pruning_days",
                    "device_pruning_delete_logs",
                ),
                "description": "Настройки для автоматического удаления старых данных для поддержания производительности.",
            },
        ),
    )


@admin.register(Device)
class DeviceAdmin(ModelAdmin):
    """Admin interface for the Device model."""
    list_display = ("ip_address", "created_at", "last_seen")
    search_fields = ("ip_address",)


@admin.register(TemperatureReading)
class TemperatureReadingAdmin(ModelAdmin):
    """Admin interface for the TemperatureReading model."""
    list_display = ("device", "contact_temp", "non_contact_temp", "timestamp")
    list_filter = ("device", "timestamp")
    search_fields = ("device__ip_address",)
