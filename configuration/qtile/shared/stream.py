"""Shared Redis stream access for the qtile bar cells.

Every cell in the bar reads the newest entry of one Redis stream, whose single
``measurement`` field holds a UTF-8 JSON object. This module owns that read so the cells do
not each carry their own transcription of it.
"""

import json
from typing import Any

import redis.exceptions

#: Streams renamed here before yths.backend-service could follow. ``read_measurement``
#: falls back to the old name, so a cell keeps working against a backend that still
#: publishes it: this repository and the backend are separate deployments and cannot change
#: in the same commit. Delete an entry once no machine runs a backend old enough to need it.
LEGACY_STREAM_NAMES = {"broadcast": "stream"}

#: Everything a malformed entry, an absent stream or an unreachable server can raise.
#: ``json.JSONDecodeError`` subclasses ``ValueError`` and is listed for the reader's benefit.
STREAM_ERRORS = (
    IndexError,
    KeyError,
    AttributeError,
    TypeError,
    ValueError,
    UnicodeDecodeError,
    json.JSONDecodeError,
    redis.exceptions.RedisError,
)


def _read_one(r: redis.Redis, stream: str) -> dict[str, Any] | None:
    """The newest ``measurement`` object from exactly ``stream``, or ``None``."""
    try:
        entries = r.xrevrange(stream, count=1)
        _entry_id, fields = entries[-1]
        measurement = json.loads(fields[b"measurement"].decode("utf-8"))
    except STREAM_ERRORS:
        return None
    return measurement if isinstance(measurement, dict) else None


def read_measurement(r: redis.Redis | None, stream: str) -> dict[str, Any] | None:
    """Return the newest ``measurement`` object from ``stream``, or ``None``.

    ``None`` covers every failure a cell should survive: no client, an unreachable server,
    an empty stream, a missing field, or a payload that is not a JSON object. Callers render
    an empty string rather than raising — an exception escaping ``poll()`` stops qtile
    rescheduling that cell for the rest of the session.

    A stream listed in ``LEGACY_STREAM_NAMES`` is retried under its old name when the new
    one yields nothing, which costs one extra ``xrevrange`` against a local Redis only while
    the backend has not caught up.
    """
    if r is None:
        return None
    measurement = _read_one(r, stream)
    if measurement is None and stream in LEGACY_STREAM_NAMES:
        return _read_one(r, LEGACY_STREAM_NAMES[stream])
    return measurement
