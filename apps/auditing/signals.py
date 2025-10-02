# File: apps/auditing/signals.py
from typing import Any, Dict, Type

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import Signal, receiver
from django.http import HttpRequest
from django.utils import timezone

from apps.sensor.models import Device

from .models import Event, LogEntry
from .webhooks import trigger_webhooks

User = get_user_model()

# Custom signal for more flexible event logging
event_logged = Signal()


def create_log_and_trigger_webhooks(event_identifier: str, **kwargs: Any) -> None:
    """
    Create a LogEntry and trigger associated webhooks for a given event.

    This is a central handler function that retrieves the event object from the
    database, creates a log entry, and then calls the webhook triggering logic,
    passing the newly created log entry instance.

    Args:
        event_identifier: The unique identifier for the event (e.g., 'ADMIN_LOGIN').
        **kwargs: A dictionary of context for the event, which can include
            'user', 'device', 'details', and 'instance'.
    """
    try:
        event = Event.objects.get(identifier=event_identifier)
        user = kwargs.get("user")
        device = kwargs.get("device")
        details = kwargs.get("details", {})

        # Create the log entry first
        log_entry = LogEntry.objects.create(
            event=event, user=user, device=device, details=details
        )

        # Pass the created log entry to the webhook trigger
        trigger_webhooks(log_entry=log_entry, instance=kwargs.get("instance"))

    except Event.DoesNotExist:
        # Fails silently if the event type is not defined in the DB
        pass
    except Exception:
        # Catch other exceptions to prevent crashing the main application flow
        pass


@receiver(event_logged)
def handle_custom_event(sender: Type[Any], event_identifier: str, **kwargs: Any) -> None:
    """
    Receive the custom 'event_logged' signal and process it.

    Args:
        sender: The sender of the signal.
        event_identifier: The unique identifier for the event.
        **kwargs: Additional context for the event.
    """
    create_log_and_trigger_webhooks(event_identifier, **kwargs)


@receiver(user_logged_in)
def handle_admin_login(sender: Type[Any], request: HttpRequest, user: AbstractBaseUser, **kwargs: Any) -> None:
    """
    Log an event when a user logs into the Django admin.

    Args:
        sender: The sender of the signal.
        request: The HttpRequest object for the login request.
        user: The user who logged in.
        **kwargs: Additional keyword arguments from the signal.
    """
    details: Dict[str, Any] = {
        "ip_address": request.META.get("REMOTE_ADDR"),
        "user_agent": request.META.get("HTTP_USER_AGENT"),
    }
    create_log_and_trigger_webhooks("ADMIN_LOGIN", user=user, details=details)


@receiver(post_save, sender=Device)
def handle_new_device(sender: Type[Device], instance: Device, created: bool, **kwargs: Any) -> None:
    """
    Log an event when a new Device is created.

    This signal receiver is triggered after a Device model is saved. It only
    acts if the device was newly created (`created` is True).

    Args:
        sender: The model class that sent the signal (Device).
        instance: The actual instance of the model being saved.
        created: A boolean indicating if a new record was created.
        **kwargs: Additional keyword arguments from the signal.
    """
    if created:
        details: Dict[str, Any] = {"ip_address": instance.ip_address}
        create_log_and_trigger_webhooks(
            "NEW_DEVICE", device=instance, details=details, instance=instance
        )
