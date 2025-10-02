# File: apps/sensor/views.py
from typing import Any

from django.db.models import QuerySet
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics
from rest_framework.request import Request
from rest_framework.response import Response

from apps.auditing.signals import event_logged

from .models import Device, SensorConfig, TemperatureReading
from .serializers import (
    DeviceTemperatureReadingSerializer,
    SensorConfigSerializer,
    TemperatureReadingSerializer,
)
from .throttles import DynamicSensorDataRateThrottle


def get_client_ip(request: HttpRequest) -> str:
    """
    Get the client's real IP address from a request object.

    Args:
        request: The Django HttpRequest object.

    Returns:
        The client's IP address as a string.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_for")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return str(ip)


@extend_schema(
    tags=["sensor"],
    summary="Получить конфигурацию датчика",
    description="Предоставляет данные конфигурации для датчика, такие как требуемая частота отправки данных.",
    responses={
        200: OpenApiResponse(
            response=SensorConfigSerializer,
            description="Конфигурация датчика успешно получена.",
        ),
    },
)
class SensorConfigAPIView(generics.RetrieveAPIView):
    """
    API endpoint that provides the global sensor configuration.
    """
    permission_classes: list[Any] = []
    serializer_class = SensorConfigSerializer

    def get_object(self) -> SensorConfig:
        """
        Retrieve the singleton SensorConfig instance.

        Returns:
            The single SensorConfig object.
        """
        return SensorConfig.get_solo()

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Handle GET requests to fetch the sensor configuration.

        Args:
            request: The DRF request object.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            A DRF Response containing the serialized sensor configuration.
        """
        ip_address = get_client_ip(request)
        device, _ = Device.objects.get_or_create(ip_address=ip_address)

        event_logged.send(
            sender=self.__class__,
            event_identifier="CONFIG_FETCHED",
            device=device,
            details={
                "ip_address": ip_address,
                "user_agent": request.META.get("HTTP_USER_AGENT"),
            },
        )
        return super().get(request, *args, **kwargs)


@extend_schema(
    tags=["sensor"],
    summary="Отправить данные температуры с датчика",
    description="Принимает и сохраняет данные о температуре от датчика. Сервер автоматически идентифицирует датчик по его IP-адресу.",
    request=TemperatureReadingSerializer,
    responses={
        201: OpenApiResponse(description="Данные успешно созданы."),
        400: OpenApiResponse(
            description="Неверный запрос: предоставлены некорректные данные."
        ),
        429: OpenApiResponse(
            description="Слишком много запросов."
        ),
    },
)
class TemperatureDataAPIView(generics.CreateAPIView):
    """
    API endpoint for receiving temperature data submissions from sensors.
    """

    permission_classes: list[Any] = []
    serializer_class = TemperatureReadingSerializer
    throttle_classes = [DynamicSensorDataRateThrottle]

    def perform_create(self, serializer: TemperatureReadingSerializer) -> None:
        """
        Save the new TemperatureReading instance and log the event.

        Args:
            serializer: The validated serializer instance containing the data.
        """
        ip_address = get_client_ip(self.request)
        device, created = Device.objects.get_or_create(ip_address=ip_address)

        instance = serializer.save(device=device)

        event_logged.send(
            sender=self.__class__,
            event_identifier="DATA_RECEIVED",
            device=device,
            instance=instance,
            details={"ip_address": ip_address, "payload": serializer.validated_data},
        )


@extend_schema(
    tags=["sensor"],
    summary="Получить последние показания для устройства",
    description="Возвращает список последних 50 показаний температуры для устройства с указанным IP-адресом.",
    responses={
        200: OpenApiResponse(
            response=DeviceTemperatureReadingSerializer(many=True),
            description="Список показаний успешно получен.",
        ),
        404: OpenApiResponse(description="Устройство с таким IP-адресом не найдено."),
    },
)
class DeviceReadingsAPIView(generics.ListAPIView):
    """
    API endpoint to retrieve the last 50 temperature readings for a specific device.
    """
    permission_classes: list[Any] = []
    serializer_class = DeviceTemperatureReadingSerializer

    def get_queryset(self) -> "QuerySet[TemperatureReading]":
        """
        Get the queryset for temperature readings, filtered by device IP.

        It retrieves the device based on the `ip_address` URL parameter and
        returns the last 50 readings for that device, ordered by timestamp.

        Returns:
            A QuerySet of TemperatureReading objects.

        Raises:
            Http404: If no device with the given IP address is found.
        """
        ip_address: str = self.kwargs['ip_address']
        device = get_object_or_404(Device, ip_address=ip_address)
        return TemperatureReading.objects.filter(device=device).order_by('-timestamp')[:50]
