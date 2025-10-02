# File: apps/auditing/models.py
from django.contrib.auth import get_user_model
from django.db import models

from apps.sensor.models import Device

User = get_user_model()


class Event(models.Model):
    """Represents a type of auditable event in the system."""
    name = models.CharField("Название события", max_length=255)
    identifier = models.CharField(
        "Идентификатор",
        max_length=50,
        unique=True,
        help_text="Уникальный код для программного использования (e.g., 'NEW_DEVICE')"
    )

    def __str__(self) -> str:
        """Return the human-readable name of the event.

        Returns:
            The event name.
        """
        return self.name

    class Meta:
        verbose_name = "Тип события"
        verbose_name_plural = "Типы событий"


class Webhook(models.Model):
    """Stores the configuration for an outgoing webhook."""
    class HttpMethod(models.TextChoices):
        POST = 'POST', 'POST'
        GET = 'GET', 'GET'
        PUT = 'PUT', 'PUT'
        PATCH = 'PATCH', 'PATCH'
        DELETE = 'DELETE', 'DELETE'

    class RateLimitAction(models.TextChoices):
        QUEUE = 'QUEUE', 'Поставить в очередь и отправить позже'
        COALESCE = 'COALESCE', 'Объединить и отправить позже'

    name = models.CharField("Название", max_length=255)
    is_active = models.BooleanField("Активен", default=True)
    triggers = models.ManyToManyField(
        Event,
        verbose_name="События-триггеры",
        help_text="Выберите события, которые будут вызывать этот вебхук."
    )
    
    # Request Configuration
    url = models.URLField("URL", max_length=500)
    http_method = models.CharField(
        "HTTP метод", max_length=10, choices=HttpMethod.choices, default=HttpMethod.POST
    )
    headers = models.JSONField(
        "Заголовки",
        default=dict,
        blank=True,
        null=True,
        help_text='JSON-объект с HTTP-заголовками. Пример: {"Authorization": "Bearer key123"}'
    )
    body_template = models.TextField(
        "Шаблон тела запроса",
        blank=True,
        help_text="Django-шаблон для тела запроса (для POST/PUT). Доступны переменные из контекста события (e.g., {{ device.ip_address }})."
    )
    
    # Rate Limiting
    rate_limit_seconds = models.PositiveIntegerField(
        "Период ограничения (секунд)",
        default=0,
        help_text="Не отправлять чаще, чем раз в указанное количество секунд. 0 - отключено."
    )
    rate_limit_action = models.CharField(
        "Действие при ограничении",
        max_length=10,
        choices=RateLimitAction.choices,
        default=RateLimitAction.QUEUE
    )
    coalesce_text_limit = models.PositiveIntegerField(
        "Лимит текста для объединения",
        default=8000,
        help_text="Максимальный размер (в символах) объединенного тела запроса. Если превышен, старые события могут быть отброшены."
    )
    
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата обновления", auto_now=True)
    
    def __str__(self) -> str:
        """Return the human-readable name of the webhook.

        Returns:
            The webhook name.
        """
        return self.name

    class Meta:
        verbose_name = "Вебхук"
        verbose_name_plural = "Вебхуки"


class LogEntry(models.Model):
    """Represents a single entry in the audit log."""
    event = models.ForeignKey(Event, verbose_name="Событие", on_delete=models.PROTECT)
    user = models.ForeignKey(
        User,
        verbose_name="Пользователь",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    device = models.ForeignKey(
        Device, verbose_name="Устройство", on_delete=models.SET_NULL, null=True, blank=True
    )
    timestamp = models.DateTimeField("Метка времени", auto_now_add=True, db_index=True)
    details = models.JSONField("Детали", default=dict, blank=True)

    def __str__(self) -> str:
        """Return a string representation of the log entry.

        Returns:
            A formatted string describing the log entry.
        """
        actor = self.user or self.device or "Система"
        return f"{self.event.name} от {actor} в {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

    class Meta:
        verbose_name = "Запись в журнале аудита"
        verbose_name_plural = "Журнал аудита"
        ordering = ['-timestamp']
