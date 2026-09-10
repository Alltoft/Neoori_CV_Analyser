"""Reading a JSON request body without trusting its shape.

Flask's get_json(silent=True) returns whatever the body parsed to. A JSON
array, string or number is valid JSON and truthy, so `or {}` lets it through
and the caller's .get() raises AttributeError -- an unhandled 500 where the
route meant to answer 400. Same for a field that is present but not a string:
.strip() raises. Both were live defects.
"""
from flask import request


def json_object() -> dict:
    """The request body as a dict; {} for anything else, including no body."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def text_field(data: dict, key: str, default: str = "") -> str:
    """A trimmed string field. A non-string value yields the default, so the
    route's own validation rejects it with the route's own French message
    instead of crashing on .strip()."""
    value = data.get(key, default)
    return value.strip() if isinstance(value, str) else default


def raw_text_field(data: dict, key: str, default: str = "") -> str:
    """A string field taken verbatim, without trimming. For values where
    surrounding whitespace is significant -- a password, notably."""
    value = data.get(key, default)
    return value if isinstance(value, str) else default


def dict_field(data: dict, key: str) -> dict:
    """A dict-valued field, copied. `dict(data.get(key, {}))` looks
    equivalent but isn't: handed a JSON array or a scalar, `dict()` either
    misreads it as key/value pairs or raises TypeError. A non-dict value here
    yields {} instead, so the route's own validation rejects the payload with
    its own French message instead of crashing."""
    value = data.get(key, {})
    return dict(value) if isinstance(value, dict) else {}
