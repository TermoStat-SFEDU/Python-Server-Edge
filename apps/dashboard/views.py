# File: apps/dashboard/views.py
from datetime import timedelta
from typing import Any, Dict, List, TypedDict, cast

from django.db.models import Avg, QuerySet, OuterRef, Subquery, F
from django.db.models.functions import TruncHour
from django.utils import timezone
from django.views.generic import TemplateView
from drf_spectacular.utils import OpenApiExample, extend_schema, OpenApiResponse
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auditing.models import LogEntry
from apps.sensor.models import Device, TemperatureReading

from .serializers import DashboardAPISerializer


class DashboardView(TemplateView):
    """
    Renders the main dashboard page.

    This view serves the HTML template which contains the structure and
    JavaScript logic for the dashboard. The dashboard itself fetches its data
    asynchronously from the DashboardAPIView.
    """
    template_name = "dashboard/index.html"


class DeviceStatus(TypedDict):
    """A type definition for a device's status dictionary."""
    ip_address: str
    last_seen: timezone.datetime
    status: str


@extend_schema(
    tags=["dashboard"],
    summary="Получить сводные данные для дашборда",
    description="Предоставляет все необходимые агрегированные данные для построения панели мониторинга в едином ответе.",
    responses={
        200: OpenApiResponse(
            response=DashboardAPISerializer,
            description="Сводные данные успешно получены.",
            examples=[
                OpenApiExample(
                    name="Пример успешного ответа",
                    value={
                        "statistics": {
                            "total_devices": 5,
                            "active_devices": 4,
                            "readings_last_24h": 17280,
                            "recent_dos_ip": "192.168.1.105"
                        },
                        "system_average_temperature_chart": {
                            "labels": ["2023-10-27T09:00:00Z", "2023-10-27T10:00:00Z"],
                            "data": [36.15, 36.32]
                        },
                        "devices": [
                            {
                                "ip_address": "192.168.1.101",
                                "last_seen": "2023-10-27T10:05:00Z",
                                "status": "active",
                                "latest_reading": {
                                    "timestamp": "2023-10-27T10:05:00Z",
                                    "contact_temp": 36.5,
                                    "non_contact_temp": 35.8
                                }
                            }
                        ]
                    }
                )
            ]
        ),
    },
)
class DashboardAPIView(APIView):
    """
    Предоставляет все агрегированные данные для панели мониторинга.

    Этот эндпоинт собирает и структурирует данные из различных моделей,
    предоставляя легковесный ответ, идеальный для рендеринга дашборда
    и использования внешними интеграциями.
    """
    permission_classes: List[Any] = []

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Собирает и возвращает сводную информацию о состоянии системы.

        Args:
            request: Объект запроса от DRF.
            *args: Позиционные аргументы.
            **kwargs: Именованные аргументы.

        Returns:
            DRF Response с сериализованными данными для дашборда.
        """
        now = timezone.now()
        twenty_four_hours_ago = now - timedelta(hours=24)

        # 1. KPI Stats
        total_devices = Device.objects.count()
        readings_last_24h = TemperatureReading.objects.filter(
            timestamp__gte=twenty_four_hours_ago
        ).count()
        recent_dos_log = LogEntry.objects.filter(
            event__identifier='DOS_DETECTED'
        ).order_by('-timestamp').first()
        recent_dos_ip = cast(Dict[str, Any], recent_dos_log.details).get(
            'ip_address') if recent_dos_log else None
        
        # 2. Per-Device Status and last readings
        all_devices = Device.objects.all().order_by('ip_address')
        
        # Subquery to get the latest reading for each device
        latest_reading_sq = TemperatureReading.objects.filter(
            device=OuterRef('pk')
        ).order_by('-timestamp')

        devices_with_latest_reading = all_devices.annotate(
            latest_reading_timestamp=Subquery(latest_reading_sq.values('timestamp')[:1]),
            latest_contact_temp=Subquery(latest_reading_sq.values('contact_temp')[:1]),
            latest_non_contact_temp=Subquery(latest_reading_sq.values('non_contact_temp')[:1]),
        )

        devices_data: List[Dict[str, Any]] = []
        active_devices_count = 0

        for device in devices_with_latest_reading:
            if device.last_seen >= now - timedelta(minutes=10):
                status = 'active'
                active_devices_count += 1
            elif device.last_seen >= now - timedelta(hours=1):
                status = 'warning'
            else:
                status = 'inactive'

            device_info = {
                'ip_address': device.ip_address,
                'last_seen': device.last_seen,
                'status': status,
                'latest_reading': None
            }
            if device.latest_reading_timestamp:
                device_info['latest_reading'] = {
                    'timestamp': device.latest_reading_timestamp,
                    'contact_temp': device.latest_contact_temp,
                    'non_contact_temp': device.latest_non_contact_temp
                }
            
            devices_data.append(device_info)
        
        stats_data: Dict[str, Any] = {
            'total_devices': total_devices,
            'active_devices': active_devices_count,
            'readings_last_24h': readings_last_24h,
            'recent_dos_ip': recent_dos_ip,
        }

        # 3. System-Wide Average Temperature Chart
        avg_temp_data = TemperatureReading.objects.filter(timestamp__gte=twenty_four_hours_ago)\
            .annotate(hour=TruncHour('timestamp'))\
            .values('hour')\
            .annotate(avg_temp=Avg('contact_temp'))\
            .order_by('hour')

        system_average_temperatures_chart: Dict[str, List[Any]] = {
            'labels': [item['hour'] for item in avg_temp_data],
            'data': [round(item['avg_temp'], 2) if item['avg_temp'] else None for item in avg_temp_data]
        }
        
        # Assemble final payload
        payload: Dict[str, Any] = {
            "statistics": stats_data,
            "system_average_temperature_chart": system_average_temperatures_chart,
            "devices": devices_data,
        }

        serializer = DashboardAPISerializer(instance=payload)
        return Response(serializer.data)
