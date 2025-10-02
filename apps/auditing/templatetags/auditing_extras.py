# File: apps/auditing/templatetags/auditing_extras.py
import json
from typing import Any, Dict, Optional, Union

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name="json_dump", is_safe=True)
def json_dump(value: Optional[Dict[str, Any]], indent: Optional[Union[int, str]] = None) -> str:
    """
    Serialize a Python dictionary to a JSON formatted string and mark it as safe.

    This prevents Django's template engine from HTML-escaping the quotes and
    other characters within the JSON string.

    Usage:
        {{ my_dict | json_dump }}
        {{ my_dict | json_dump:2 }}

    Args:
        value: The dictionary or object to serialize.
        indent: The indentation level for pretty-printing the JSON.
            Defaults to None (compact JSON).

    Returns:
        A safe JSON formatted string, or an empty string if the input is None.
    """
    if value is None:
        return ""
    try:
        # Ensure indent is an integer if provided
        indent_int = int(indent) if indent is not None else None
        json_string = json.dumps(value, indent=indent_int, ensure_ascii=False)
        return mark_safe(json_string)
    except (TypeError, ValueError):
        # Fallback for non-serializable objects or invalid indent values
        return "Cannot serialize object to JSON"
