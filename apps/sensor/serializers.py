# File: apps/sensor/serializers.py
from typing import Any, Dict

from rest_framework import serializers

from .models import SensorConfig, TemperatureReading


class SensorConfigSerializer(serializers.ModelSerializer):
    """Serializer for the SensorConfig model, exposing only the 'period' field."""
    class Meta:
        model = SensorConfig
        fields = ['period']


class TemperatureReadingSerializer(serializers.ModelSerializer):
    """Serializer for creating TemperatureReading instances from incoming data."""
    class Meta:
        model = TemperatureReading
        fields = ['contact_temp', 'non_contact_temp']

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate that at least one temperature reading is provided.

        Args:
            data: The dictionary of incoming data to be validated.

        Returns:
            The validated data dictionary.

        Raises:
            serializers.ValidationError: If neither temp is provided.
        """
        if data.get('contact_temp') is None and data.get('non_contact_temp') is None:
            raise serializers.ValidationError("At least one temperature reading must be provided.")
        return data


class DeviceTemperatureReadingSerializer(serializers.ModelSerializer):
    """
    Serializer for returning a list of historical temperature readings for a device.
    """
    class Meta:
        model = TemperatureReading
        fields = ['timestamp', 'contact_temp', 'non_contact_temp']
