# File: apps/dashboard/serializers.py
from rest_framework import serializers
from typing import Dict, Any, List, Optional


class DashboardStatisticsSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    Serializes the key performance indicator (KPI) statistics for the dashboard.
    """
    total_devices = serializers.IntegerField(help_text="Total number of registered devices.")
    active_devices = serializers.IntegerField(help_text="Number of devices seen in the last 10 minutes.")
    readings_last_24h = serializers.IntegerField(help_text="Number of temperature readings received in the last 24 hours.")
    recent_dos_ip = serializers.IPAddressField(allow_null=True, required=False, help_text="The last IP address that was throttled.")


class SystemAverageTemperatureChartSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    Serializes data formatted for a time-series chart.
    """
    labels = serializers.ListField(child=serializers.DateTimeField(), help_text="List of timestamps for the X-axis.")
    data = serializers.ListField(child=serializers.FloatField(allow_null=True), help_text="List of data points for the Y-axis.")


class DeviceLatestReadingSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    Serializes the most recent temperature reading from a device.
    """
    timestamp = serializers.DateTimeField()
    contact_temp = serializers.FloatField(allow_null=True)
    non_contact_temp = serializers.FloatField(allow_null=True)


class DashboardDeviceSerializer(serializers.Serializer[Dict[str, Any]]):
    """
    Serializes the status and latest data for a single device.
    """
    ip_address = serializers.IPAddressField()
    last_seen = serializers.DateTimeField()
    status = serializers.ChoiceField(choices=['active', 'warning', 'inactive'])
    latest_reading = DeviceLatestReadingSerializer(allow_null=True, required=False)


class DashboardAPISerializer(serializers.Serializer[Dict[str, Any]]):
    """
    Top-level serializer for all aggregated dashboard data provided by the API.
    """
    statistics = DashboardStatisticsSerializer()
    system_average_temperature_chart = SystemAverageTemperatureChartSerializer()
    devices = DashboardDeviceSerializer(many=True)
