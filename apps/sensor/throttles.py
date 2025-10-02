# File: apps/sensor/throttles.py
import re
from typing import Optional, Tuple

from rest_framework.request import Request
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from .models import SensorConfig


class DynamicSensorDataRateThrottle(SimpleRateThrottle):
    """
    A custom throttle that dynamically sets its rate from the SensorConfig.

    This throttle overrides the `get_rate` method to fetch the `server_timeout`
    value from the singleton `SensorConfig` model. It then constructs the
    rate limit string dynamically, allowing the rate limit to be changed
    globally from the Django admin without restarting the server.
    """

    scope = "sensor_data"

    def get_rate(self) -> Optional[str]:
        """
        Determine the throttle rate by fetching it from the database.

        Retrieves the `server_timeout` from the global SensorConfig. If the
        timeout is 0, throttling is disabled for this request by returning None.
        Otherwise, it returns a rate string formatted for our custom throttle
        parser (e.g., "1/5s").

        Returns:
            A string representing the throttle rate (e.g., "1/5s") if throttling
            is enabled, or None if it is disabled.
        """
        try:
            config = SensorConfig.get_solo()
            timeout = config.server_timeout

            if timeout == 0:
                return None  # Returning None disables throttling for this request

            # Format is "number_of_requests/period"
            # e.g., "1/5s" means 1 request per 5 seconds.
            return f"1/{timeout}s"
        except SensorConfig.DoesNotExist:
            # Fallback if config doesn't exist yet, effectively disabling throttling.
            return None

    def parse_rate(self, rate: Optional[str]) -> Optional[Tuple[int, int]]:
        """
        Parse a rate string like "1/5s" into a numeric tuple.

        Overrides the default `SimpleRateThrottle.parse_rate` to support
        rate strings with a numeric value in the duration part, which is
        necessary for our dynamic timeout feature.

        Args:
            rate: The rate string to parse (e.g., "1/5s").

        Returns:
            A tuple of (number_of_requests, duration_in_seconds), or None
            if the rate is invalid or None.
        """
        if rate is None:
            return None
        
        try:
            num, period_str = rate.split('/')
            num_requests = int(num)
            
            # Use regex to extract the numeric duration and the time unit
            match = re.match(r"(\d+)([smhd])", period_str)
            if not match:
                raise ValueError("Invalid rate period format")

            duration_val_str, duration_unit = match.groups()
            duration_val = int(duration_val_str)
            
            multipliers = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
            duration = duration_val * multipliers[duration_unit]
            
            return (num_requests, duration)
        except (ValueError, KeyError):
            # If parsing fails for any reason, treat it as an invalid rate.
            return None

    def get_cache_key(self, request: Request, view: APIView) -> Optional[str]:
        """
        Generate a unique cache key for the request.

        Uses the client's IP address as the unique identifier for throttling.

        Args:
            request: The current request object.
            view: The view being accessed.

        Returns:
            A string to be used as the cache key, or None to bypass throttling.
        """
        return self.get_ident(request)
