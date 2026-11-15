"""``shared.stream``: every failure a bar cell has to survive, and the rename fallback."""

import json
from typing import Any

import pytest
import redis.exceptions
from shared import stream


class FakeRedis:
    """Just enough of the client for ``xrevrange``, plus a way to make it misbehave."""

    def __init__(
        self, entries: dict[str, list] | None = None, raises: Exception | None = None
    ) -> None:
        self.entries = entries or {}
        self.raises = raises
        self.asked: list[str] = []

    def xrevrange(self, name: str, count: int = 1) -> list:
        self.asked.append(name)
        if self.raises is not None:
            raise self.raises
        return self.entries.get(name, [])


def entry(payload: Any) -> list:
    return [(b"1-0", {b"measurement": json.dumps(payload).encode()})]


def test_reads_the_newest_measurement() -> None:
    client = FakeRedis({"vpn": entry({"connected": True})})
    assert stream.read_measurement(client, "vpn") == {"connected": True}


def test_no_client_is_not_an_error() -> None:
    # config.py passes None when Redis was unreachable at startup; the bar still renders.
    assert stream.read_measurement(None, "vpn") is None


@pytest.mark.parametrize(
    ("name", "client"),
    [
        ("empty stream", FakeRedis({"vpn": []})),
        ("absent stream", FakeRedis({})),
        ("server unreachable", FakeRedis(raises=redis.exceptions.ConnectionError("down"))),
        ("field missing", FakeRedis({"vpn": [(b"1-0", {})]})),
        ("payload not json", FakeRedis({"vpn": [(b"1-0", {b"measurement": b"{not json"})]})),
        ("payload not utf-8", FakeRedis({"vpn": [(b"1-0", {b"measurement": b"\xff\xfe"})]})),
    ],
)
def test_every_survivable_failure_returns_none(name: str, client: FakeRedis) -> None:
    # None, never an exception: one escaping poll() stops qtile rescheduling that cell for
    # the rest of the session, and says so in a single log line.
    assert stream.read_measurement(client, "vpn") is None, name


@pytest.mark.parametrize("payload", [[], "a string", 3, None])
def test_a_payload_that_is_not_an_object_returns_none(payload: Any) -> None:
    assert stream.read_measurement(FakeRedis({"vpn": entry(payload)}), "vpn") is None


# One cell, one read per poll: a stream that answers nothing is not retried under another name.
def test_a_missing_stream_costs_one_read() -> None:
    client = FakeRedis({})
    assert stream.read_measurement(client, "vpn") is None
    assert client.asked == ["vpn"]
