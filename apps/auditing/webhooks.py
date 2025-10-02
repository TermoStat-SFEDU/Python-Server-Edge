# File: apps/auditing/webhooks.py
import json
import logging
import threading
from datetime import timedelta
from typing import Any, Dict, List, Optional, Union

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from django.core.cache import cache
from django.template import Context, Template
from django.template.exceptions import TemplateSyntaxError
from django.utils import timezone
from django_apscheduler.jobstores import DjangoJobStore

from .models import LogEntry, Webhook

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()
scheduler.add_jobstore(DjangoJobStore(), "default")


def send_webhook_request(webhook: Webhook, context: Dict[str, Any]) -> None:
    """
    Render, parse, and send a single webhook request based on its configuration.

    This function enforces a strict contract: the body_template must render into
    a valid JSON object. It then sends this object using the appropriate method
    (either as a JSON payload for POST/PUT/PATCH or as URL parameters for GET).

    Args:
        webhook: The Webhook instance to be sent.
        context: A dictionary containing the event context for template rendering.
    """
    rendered_template: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    try:
        template_context = Context(context)

        # Step 1: Render the template from the database
        if webhook.body_template:
            template = Template(webhook.body_template)
            rendered_template = template.render(template_context)
        else:
            rendered_template = json.dumps(template_context.flatten())

        # Step 2: Enforce that the rendered template is a valid JSON object
        if not rendered_template:
            logger.warning(f"Webhook '{webhook.name}' (ID: {webhook.id}) rendered an empty template. Aborting.")
            return

        payload = json.loads(rendered_template)
        if not isinstance(payload, dict):
            raise ValueError("Rendered template is not a JSON object.")

        # Step 3: Prepare and send the request
        headers = {'User-Agent': 'Django-Sensor-App/1.0'}
        headers.update(webhook.headers or {})

        request_kwargs: Dict[str, Any] = {
            "method": webhook.http_method,
            "url": webhook.url,
            "headers": headers,
            "timeout": 10,
        }

        if webhook.http_method in ['POST', 'PUT', 'PATCH']:
            request_kwargs['json'] = payload
        else:  # GET, DELETE, etc.
            request_kwargs['params'] = payload

        response = requests.request(**request_kwargs)
        response.raise_for_status()
        logger.info(f"Successfully sent webhook '{webhook.name}' to {webhook.url}. Status: {response.status_code}")

    except (json.JSONDecodeError, ValueError) as e:
        logger.error(
            f"Webhook '{webhook.name}' (ID: {webhook.id}) failed to parse rendered template as a valid JSON object. "
            f"Please ensure the template produces a single-line JSON string. Error: {e}. Result: {rendered_template}"
        )
    except TemplateSyntaxError as e:
        logger.error(
            f"Webhook '{webhook.name}' (ID: {webhook.id}) failed due to a template syntax error: {e}. "
            f"Please correct the Body Template in the admin panel."
        )
    except requests.exceptions.RequestException as e:
        body_for_log: Union[str, Dict, None]
        if webhook.http_method in ['POST', 'PUT', 'PATCH']:
            body_for_log = payload
        else:
            body_for_log = request_kwargs.get('params')

        if e.response is not None:
            logger.error(
                f"Failed to send webhook '{webhook.name}' to {webhook.url}. "
                f"Status: {e.response.status_code}, Response: {e.response.text}, "
                f"Request Body: {body_for_log}"
            )
        else:
            logger.error(f"Failed to send webhook '{webhook.name}' to {webhook.url}. Network Error: {e}")
    except Exception:
        logger.exception(f"An unexpected error occurred while sending webhook '{webhook.name}'")


def _reconstruct_context(log_entry: LogEntry, instance: Optional[Any] = None) -> Dict[str, Any]:
    """
    Build the template context dictionary from a LogEntry instance.

    Args:
        log_entry: The LogEntry object from which to build the context.
        instance: The original model instance that triggered the event, if any.

    Returns:
        A dictionary containing template variables like event, user, device, etc.
    """
    return {
        "event": log_entry.event,
        "user": log_entry.user,
        "device": log_entry.device,
        "details": log_entry.details,
        "instance": instance,
        "timestamp": log_entry.timestamp,
    }


def dispatch_webhook_batch(webhook_id: int) -> None:
    """
    Dispatch a batch of pending webhooks from the cache.

    This function is executed by the scheduler. It retrieves a list of cached
    LogEntry IDs for a specific webhook, fetches the corresponding LogEntry
    objects, and triggers the sending of each webhook in a separate thread.

    Args:
        webhook_id: The primary key of the Webhook to dispatch.
    """
    try:
        webhook = Webhook.objects.get(pk=webhook_id)
        pending_key = f'webhook_{webhook_id}_pending_ids'

        pending_ids: List[int] = cache.get(pending_key, [])
        if not pending_ids:
            return

        cache.delete(pending_key)

        log_entries = LogEntry.objects.filter(id__in=pending_ids).select_related(
            'event', 'user', 'device'
        ).order_by('timestamp')

        # NOTE: Coalescing is not implemented and falls back to queueing.
        for log_entry in log_entries:
            context = _reconstruct_context(log_entry)
            thread = threading.Thread(target=send_webhook_request, args=(webhook, context))
            thread.daemon = True
            thread.start()

    except Webhook.DoesNotExist:
        logger.warning(f"Webhook with id={webhook_id} not found for dispatch.")
    except Exception as e:
        logger.error(f"Error in dispatch_webhook_batch for webhook_id={webhook_id}: {e}")


def trigger_webhooks(log_entry: LogEntry, instance: Optional[Any] = None) -> None:
    """
    Find and trigger webhooks associated with a LogEntry's event.

    This function is the main entry point for processing an event. It finds all
    active webhooks that are triggered by the event from the given LogEntry.
    It handles rate-limiting by either sending the webhook immediately or
    scheduling a batch dispatch for later.

    Args:
        log_entry: The LogEntry instance that was just created.
        instance: The original model instance that triggered the event, if any.
    """
    try:
        event_identifier = log_entry.event.identifier
        webhooks = Webhook.objects.filter(is_active=True, triggers__identifier=event_identifier)
        if not webhooks.exists():
            return

        for webhook in webhooks:
            # No rate limit, send immediately
            if not webhook.rate_limit_seconds or webhook.rate_limit_seconds == 0:
                context = _reconstruct_context(log_entry, instance)
                thread = threading.Thread(target=send_webhook_request, args=(webhook, context))
                thread.daemon = True
                thread.start()
                continue

            # Rate limiting logic: cache the LogEntry ID
            lock_key = f'webhook_{webhook.id}_dispatch_scheduled'
            pending_key = f'webhook_{webhook.id}_pending_ids'

            pending_ids: List[int] = cache.get(pending_key, [])
            pending_ids.append(log_entry.id)
            cache.set(pending_key, pending_ids, timeout=webhook.rate_limit_seconds + 60)

            # If a dispatch is NOT already scheduled, schedule one
            if cache.add(lock_key, 'true', timeout=webhook.rate_limit_seconds):
                run_time = timezone.now() + timedelta(seconds=webhook.rate_limit_seconds)
                scheduler.add_job(
                    dispatch_webhook_batch,
                    trigger='date',
                    run_date=run_time,
                    args=[webhook.id],
                    id=f'dispatch_batch_{webhook.id}_{int(run_time.timestamp())}',
                    replace_existing=False,
                    misfire_grace_time=60
                )
    except Exception as e:
        logger.error(f"Failed to trigger webhooks for event '{log_entry.event.identifier}': {e}")
