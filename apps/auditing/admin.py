# File: apps/auditing/admin.py
from typing import Any, Optional

from django.contrib import admin
from django.http import HttpRequest
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin

from .models import Event, LogEntry, Webhook


@admin.register(Event)
class EventAdmin(ModelAdmin):
    """Admin interface for the Event model."""
    list_display = ("name", "identifier")
    search_fields = ("name", "identifier")

    def has_add_permission(self, request: HttpRequest) -> bool:
        """
        Prevent adding new Event objects from the admin interface.

        Events should be defined in code (events.py) and synchronized,
        not created manually.

        Args:
            request: The current HTTP request.

        Returns:
            False to disable the 'Add' functionality.
        """
        return False

    def has_change_permission(self, request: HttpRequest, obj: Optional[Event] = None) -> bool:
        """
        Prevent changing Event objects from the admin interface.

        Args:
            request: The current HTTP request.
            obj: The Event object being considered.

        Returns:
            False to disable the 'Change' functionality.
        """
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Optional[Event] = None) -> bool:
        """
        Prevent deleting Event objects from the admin interface.

        Args:
            request: The current HTTP request.
            obj: The Event object being considered.

        Returns:
            False to disable the 'Delete' functionality.
        """
        return False


@admin.register(Webhook)
class WebhookAdmin(ModelAdmin):
    """Admin interface for the Webhook model."""
    list_display = ("name", "url", "http_method", "is_active", "created_at")
    list_filter = ("is_active", "http_method", "triggers")
    search_fields = ("name", "url")
    filter_horizontal = ("triggers",)

    fieldsets = (
        (None, {"fields": ("name", "is_active", "triggers")}),
        (
            "Конфигурация запроса",
            {
                "fields": ("url", "http_method", "headers", "body_template"),
                "description": mark_safe(
                    """
                <div class="p-4 space-y-4 border rounded-md bg-base-50 border-base-200 dark:bg-base-800 dark:border-base-700 text-font-default-light dark:text-font-default-dark">
                    <h4 class="font-semibold text-lg text-font-important-light dark:text-font-important-dark">Справка по шаблонам</h4>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <h5 class="font-medium text-base">Доступные переменные:</h5>
                            <ul class="list-disc list-inside space-y-1">
                                <li><code>{{ event }}</code> - Объект события (e.g., <code>{{ event.name }}</code>).</li>
                                <li><code>{{ device }}</code> - Объект устройства (e.g., <code>{{ device.ip_address }}</code>).</li>
                                <li><code>{{ user }}</code> - Объект пользователя (e.g., <code>{{ user.username }}</code>).</li>
                                <li><code>{{ instance }}</code> - Конкретный объект, вызвавший событие.</li>
                                <li><code>{{ details }}</code> - JSON-объект с доп. информацией.</li>
                                <li><code>{{ timestamp }}</code> - Метка времени события (объект datetime).</li>
                                <li><code>{{ events }}</code> - <strong>(Для объединенных)</strong> Список событий.</li>
                            </ul>
                        </div>
                        <div>
                            <h5 class="font-medium text-base">Доступные фильтры:</h5>
                            <ul class="list-disc list-inside space-y-1">
                                <li><code>|json_dump</code> - Преобразует объект в компактный JSON.</li>
                                <li><code>|escapejs</code> - Экранирует символы для встраивания в JSON/JS.</li>
                                <li><code>|date:"d.m.Y H:i"</code> - Форматирует дату.</li>
                                <li><code>|default:"N/A"</code> - Значение по умолчанию.</li>
                            </ul>
                        </div>
                    </div>

                    <h5 class="font-medium text-base mt-4">Примеры шаблонов</h5>

                    <details class="p-2 bg-base-100 rounded dark:bg-base-700" open>
                        <summary class="cursor-pointer font-semibold">Пример: Telegram (Рекомендуемый способ)</summary>
                        <div class="mt-2 pt-2 border-t border-base-200 dark:border-base-700">
                            <p class="text-sm"><strong>Важное правило:</strong> Шаблон тела должен всегда формировать <strong>валидный однострочный JSON-объект</strong>. Переносы строк внутри текста сообщения должны быть указаны как <code>\\n</code>.</p>
                            <p class="text-sm"><strong>Метод:</strong> <code>POST</code>. <strong>Режим парсинга:</strong> <code>HTML</code>.</p>
                            <pre style="white-space: pre-wrap; word-break: break-all;"><code class="block text-sm">
{"chat_id": "YOUR_CHAT_ID", "parse_mode": "HTML", "disable_web_page_preview": true, "text": "🚨 &lt;b&gt;Новое событие&lt;/b&gt;\\n\\nТип: &lt;code&gt;{{ event.name }}&lt;/code&gt;\\nУстройство: &lt;code&gt;{{ device.ip_address | default:\"N/A\" }}&lt;/code&gt;\\nПользователь: &lt;code&gt;{{ user.username | default:\"N/A\" }}&lt;/code&gt;\\nВремя: &lt;code&gt;{{ timestamp | date:\"d.m.Y H:i:s\" }}&lt;/code&gt;{% if details %}\\n\\n&lt;b&gt;Доп. инфо:&lt;/b&gt;\\n&lt;code&gt;{{ details | json_dump | escapejs }}&lt;/code&gt;{% endif %}"}
                            </code></pre>
                        </div>
                    </details>
                    
                    <details class="p-2 bg-base-100 rounded dark:bg-base-700 mt-2">
                        <summary class="cursor-pointer font-semibold">Пример: Discord/Slack</summary>
                        <div class="mt-2 pt-2 border-t border-base-200 dark:border-base-700">
                           <p class="text-sm">Шаблон также должен быть валидным однострочным JSON.</p>
                            <pre style="white-space: pre-wrap; word-break: break-all;"><code class="block text-sm">
{"username": "Sensor Monitor", "content": "Событие: **{{ event.name }}**", "embeds": [{"title": "Детали события", "fields": [{"name": "Устройство", "value": "{{ device.ip_address | default:'N/A' }}", "inline": true}, {"name": "Время", "value": "{{ timestamp | date:'d.m.Y H:i:s' }}", "inline": true}]}]}
                            </code></pre>
                        </div>
                    </details>

                    <details class="p-2 bg-base-100 rounded dark:bg-base-700 mt-2">
                        <summary class="cursor-pointer font-semibold">Пример: Репорт на AbuseIPDB (для события DOS_DETECTED)</summary>
                        <div class="mt-2 pt-2 border-t border-base-200 dark:border-base-700">
                            <p><strong>URL:</strong> <code>https://api.abuseipdb.com/api/v2/report</code></p>
                            <p><strong>Метод:</strong> <code>POST</code></p>
                            <p><strong>Заголовки:</strong> <code>{"Key": "ВАШ_API_КЛЮЧ", "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}</code></p>
                            <p class="text-sm"><strong>Примечание:</strong> Этот пример не использует JSON, поэтому новая логика на него не повлияет.</p>
                            <pre style="white-space: pre-wrap; word-break: break-all;"><code class="block text-sm">ip={{ details.ip_address }}&categories=18,21&comment=Automated report: Throttling detected for sensor data endpoint. User-Agent: {{ details.user_agent }}.</code></pre>
                        </div>
                    </details>
                    
                    <div class="mt-4 pt-4 border-t border-base-200 dark:border-base-700">
                        <h5 class="font-medium text-base"><strong>⚠️ Устранение неполадок</strong></h5>
                        <p class="text-sm">Если вебхуки не отправляются, в первую очередь проверьте логи Docker-контейнера. Ошибка <code>failed to parse rendered template</code> означает, что ваш шаблон не является валидным JSON-объектом.</p>
                    </div>
                </div>
            """
                ),
            },
        ),
        (
            "Ограничение частоты отправки",
            {
                "fields": (
                    "rate_limit_seconds",
                    "rate_limit_action",
                    "coalesce_text_limit",
                ),
                "description": "Настройки для предотвращения спама на эндпоинт вебхука.",
            },
        ),
    )


@admin.register(LogEntry)
class LogEntryAdmin(ModelAdmin):
    """Admin interface for the LogEntry model (read-only)."""
    list_display = ("timestamp", "event", "user", "device")
    list_filter = ("event", "timestamp", "user", "device")
    search_fields = ("details", "user__username", "device__ip_address")
    readonly_fields = [f.name for f in LogEntry._meta.fields]

    def has_add_permission(self, request: HttpRequest) -> bool:
        """
        Prevent adding log entries from the admin interface.

        Logs are created programmatically by the system in response to events.

        Args:
            request: The current HTTP request.

        Returns:
            False to disable the 'Add' functionality.
        """
        return False

    def has_change_permission(self, request: HttpRequest, obj: Optional[LogEntry] = None) -> bool:
        """
        Prevent changing log entries from the admin interface.

        Args:
            request: The current HTTP request.
            obj: The LogEntry object being considered.

        Returns:
            False to make the log entries read-only.
        """
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Optional[LogEntry] = None) -> bool:
        """
        Prevent deleting individual log entries from the admin interface.

        Deletion should happen via automated pruning tasks.

        Args:
            request: The current HTTP request.
            obj: The LogEntry object being considered.

        Returns:
            False to disable the 'Delete' functionality.
        """
        return False
