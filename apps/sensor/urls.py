# File: apps/sensor/urls.py
from django.urls import path
from .views import SensorConfigAPIView, TemperatureDataAPIView, DeviceReadingsAPIView

urlpatterns = [
    path('config/', SensorConfigAPIView.as_view(), name='sensor-config'),
    path('data/', TemperatureDataAPIView.as_view(), name='sensor-data'),
    path('device/<str:ip_address>/readings/', DeviceReadingsAPIView.as_view(), name='device-readings'),
]
