# File: apps/sensor/models.py
from django.db import models
from django.utils import timezone
from solo.models import SingletonModel


class SensorConfig(SingletonModel):
    """
    A singleton model to store global configuration for sensors and the server.

    This model uses django-solo to ensure that only one instance of this
    configuration object can be created in the database.
    """

    # Sensor Settings
    period = models.PositiveIntegerField(
        verbose_name="Период отправки данных",
        default=30,
        help_text="Период в секундах, с которым датчик должен отправлять данные. Если 0, датчик отправляет данные сразу после получения.",
    )
    server_timeout = models.PositiveIntegerField(
        verbose_name="Таймаут на стороне сервера",
        default=5,
        help_text="Запретить отправку данных чаще, чем раз в указанное количество секунд с одного IP. Например, значение 5 разрешит 1 запрос каждые 5 секунд. 0 - отключить ограничение.",
    )

    # Data Rotation Settings
    log_rotation_days = models.PositiveIntegerField(
        verbose_name="Хранить логи (дней)",
        null=True,
        blank=True,
        default=90,
        help_text="Удалять записи журнала старше указанного количества дней. Оставьте пустым, чтобы отключить.",
    )
    log_rotation_max_count = models.PositiveIntegerField(
        verbose_name="Хранить логов (макс. кол-во)",
        null=True,
        blank=True,
        default=100000,
        help_text="Хранить только N самых последних записей в журнале. Оставьте пустым, чтобы отключить.",
    )
    device_pruning_days = models.PositiveIntegerField(
        verbose_name="Удалять неактивные устройства (дней)",
        null=True,
        blank=True,
        default=180,
        help_text="Удалять устройства, которые не проявляли активность указанное количество дней. Оставьте пустым, чтобы отключить.",
    )
    device_pruning_delete_logs = models.BooleanField(
        verbose_name="Удалять связанные логи при удалении устройства",
        default=True,
        help_text="Если флажок снят, при удалении неактивного устройства его записи в журнале аудита будут сохранены (отвязаны от устройства).",
    )

    def __str__(self) -> str:
        """Return a string representation of the singleton model.

        Returns:
            A fixed string "Глобальная конфигурация датчиков".
        """
        return "Глобальная конфигурация датчиков"

    class Meta:
        verbose_name = "Глобальная конфигурация датчиков"


class Device(models.Model):
    """
    Represents a unique sensor device, identified by its IP address.
    """

    ip_address = models.GenericIPAddressField("IP-адрес", unique=True)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    last_seen = models.DateTimeField("Последняя активность", auto_now=True)

    def __str__(self) -> str:
        """Return a string representation of the device.

        Returns:
            A string identifying the device by its IP address.
        """
        return f"Устройство с IP {self.ip_address}"

    class Meta:
        verbose_name = "Устройство"
        verbose_name_plural = "Устройства"


class TemperatureReading(models.Model):
    """
    Stores a single temperature reading from a device.
    """

    device = models.ForeignKey(
        Device,
        verbose_name="Устройство",
        related_name="readings",
        on_delete=models.CASCADE,
    )
    contact_temp = models.FloatField(
        "Контактная температура",
        null=True,
        blank=True,
        help_text="Температура, измеренная контактным способом.",
    )
    non_contact_temp = models.FloatField(
        "Бесконтактная температура",
        null=True,
        blank=True,
        help_text="Температура, измеренная бесконтактным способом (например, инфракрасным).",
    )
    timestamp = models.DateTimeField("Метка времени", default=timezone.now, db_index=True)

    def __str__(self) -> str:
        """Return a string representation of the temperature reading.

        Returns:
            A string describing the reading, its source device, and timestamp.
        """
        return f"Показание от {self.device.ip_address} в {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

    class Meta:
        verbose_name = "Показание температуры"
        verbose_name_plural = "Показания температуры"
        ordering = ["-timestamp"]
