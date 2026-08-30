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


# The widget was renamed to `broadcast` before yths.backend-service could follow; the two
# are separate deployments and cannot change in one commit.
def test_a_renamed_stream_falls_back_to_the_name_the_backend_still_publishes() -> None:
    client = FakeRedis({"stream": entry({"streaming": False})})
    assert stream.read_measurement(client, "broadcast") == {"streaming": False}
    assert client.asked == ["broadcast", "stream"], "new name first, old name only as fallback"


def test_the_new_name_wins_once_the_backend_publishes_it() -> None:
    client = FakeRedis({"broadcast": entry({"obs": True}), "stream": entry({"obs": False})})
    assert stream.read_measurement(client, "broadcast") == {"obs": True}
    assert client.asked == ["broadcast"], "no second read once the new name answers"


def test_a_stream_with_no_alias_costs_one_read() -> None:
    client = FakeRedis({})
    assert stream.read_measurement(client, "vpn") is None
    assert client.asked == ["vpn"]
