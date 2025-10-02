# File: core/exceptions.py
from typing import Any, Dict, Optional

from django.core.cache import cache
from rest_framework.exceptions import Throttled
from rest_framework.response import Response
from rest_framework.views import exception_handler

from apps.auditing.signals import event_logged
from apps.sensor.views import get_client_ip


def custom_exception_handler(exc: Exception, context: Dict[str, Any]) -> Optional[Response]:
    """Handle exceptions for DRF views, logging throttling as a DoS attempt.

    This handler calls the default DRF exception handler first to get the
    standard error response. It then checks if the exception is a `Throttled`
    exception. If so, it logs a 'DOS_DETECTED' event with details about the
    request.

    To prevent spamming notifications, this handler uses the Django cache to
    ensure that a 'DOS_DETECTED' event is logged for a specific IP address
    only once every 5 minutes.

    Args:
        exc: The exception instance that was raised.
        context: A dictionary containing context data, such as the view
            and the request.

    Returns:
        A DRF Response object if the exception is handled, or None otherwise.
    """
    # Call REST framework's default exception handler first,
    # to get the standard error response.
    response = exception_handler(exc, context)

    # Now, check if the exception was a Throttled exception
    if isinstance(exc, Throttled):
        request = context['request']
        ip_address = get_client_ip(request)
        
        # Coalesce DoS notifications to avoid spam
        cache_key = f"dos_notification_sent_{ip_address}"
        if cache.get(cache_key):
            # A notification for this IP has been sent recently.
            # Silently ignore this throttled request to prevent spam.
            return response
        
        # We can create a "pseudo-device" for logging purposes if it doesn't exist
        from apps.sensor.models import Device
        device, _ = Device.objects.get_or_create(ip_address=ip_address)

        # Fire the custom signal for DoS detection
        event_logged.send(
            sender='DRFThrottling',
            event_identifier='DOS_DETECTED',
            device=device,
            details={
                "ip_address": ip_address,
                "user_agent": request.META.get('HTTP_USER_AGENT'),
                "path": request.path,
                "wait_seconds": exc.wait,
            }
        )
        
        # Set a lock in the cache to prevent sending another notification
        # for this IP for the next 5 minutes (300 seconds).
        cache.set(cache_key, True, timeout=300)

    return response
