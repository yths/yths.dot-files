"""Shared Redis stream access for the qtile bar cells.

Every cell in the bar reads the newest entry of one Redis stream, whose single
``measurement`` field holds a UTF-8 JSON object. This module owns that read so the cells do
not each carry their own transcription of it.
"""

import json
from collections.abc import Callable
from typing import Any

import redis.exceptions

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
    """
    if r is None:
        return None
    return _read_one(r, stream)


def read_latest(
    r: redis.Redis | None,
    stream: str,
    accept: Callable[[dict[str, Any]], bool],
    scan: int = 48,
) -> dict[str, Any] | None:
    """The newest ``measurement`` in ``stream`` that ``accept`` takes, or ``None``.

    For a stream where the newest entry may be one to skip -- a location looked up through
    the VPN is the exit server's -- and an older one is still the right answer. Looks at the
    newest ``scan`` entries, newest first; the location stream, at one entry an hour, keeps
    two days of VPN use within that. Fails like ``read_measurement``: ``None``, never raises.
    """
    if r is None:
        return None
    try:
        entries = r.xrevrange(stream, count=scan)
    except redis.exceptions.RedisError:
        return None
    for _entry_id, fields in entries:
        try:
            measurement = json.loads(fields[b"measurement"].decode("utf-8"))
        except STREAM_ERRORS:
            continue
        if isinstance(measurement, dict) and accept(measurement):
            return measurement
    return None
