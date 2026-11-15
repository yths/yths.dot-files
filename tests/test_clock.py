"""The bar clock follows the geolocated timezone, but never a VPN exit server's."""

import datetime
import os
import time
import zoneinfo
from collections.abc import Iterator
from typing import Any

import pytest
import widgets.clock
from widgets.clock import WidgetClock, location_timezone

CANARY = {"timezone": "Atlantic/Canary", "sunrise": "07:24:14", "sunset": "18:18:08", "vpn": False}


@pytest.mark.parametrize(
    ("measurement", "expected"),
    [
        (CANARY, "Atlantic/Canary"),
        ({**CANARY, "vpn": True}, None),
        ({k: v for k, v in CANARY.items() if k != "vpn"}, "Atlantic/Canary"),  # older backend
        ({**CANARY, "timezone": "Not/AZone"}, None),
        ({**CANARY, "timezone": ""}, None),
        (None, None),
    ],
)
def test_which_location_sets_the_zone(measurement: dict[str, Any] | None, expected: str | None) -> None:
    zone = location_timezone(measurement)
    assert (None if zone is None else zone.key) == expected


@pytest.fixture(autouse=True)
def _berlin() -> Iterator[None]:
    """The system zone the tests assume, restored -- with ``tzset`` -- afterwards, so the
    process's notion of local time does not leak into the tests that run after these."""
    saved = os.environ.get("TZ")
    os.environ["TZ"] = "Europe/Berlin"
    time.tzset()
    yield
    if saved is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = saved
    time.tzset()


def clock(monkeypatch: pytest.MonkeyPatch, measurement: dict[str, Any] | None) -> WidgetClock:
    monkeypatch.setattr(widgets.clock.shared.stream, "read_measurement", lambda _r, _s: measurement)
    widget = WidgetClock.__new__(WidgetClock)
    widget.r, widget.base_format, widget.format = None, "%H:%M", "%H:%M"
    widget.timezone = None
    return widget


def test_a_foreign_zone_is_shown_and_named(monkeypatch: pytest.MonkeyPatch) -> None:
    widget = clock(monkeypatch, CANARY)
    text = widget.poll()
    expected = (datetime.datetime.now(datetime.UTC) + widget.DELTA).astimezone(
        zoneinfo.ZoneInfo("Atlantic/Canary")
    )
    assert text == expected.strftime("%H:%M %Z")


def test_the_system_zone_is_shown_bare(monkeypatch: pytest.MonkeyPatch) -> None:
    widget = clock(monkeypatch, {**CANARY, "timezone": "Europe/Berlin"})
    assert widget.poll().count(" ") == 0
    assert widget.timezone is None


def test_through_the_vpn_the_clock_keeps_the_system_zone(monkeypatch: pytest.MonkeyPatch) -> None:
    widget = clock(monkeypatch, {**CANARY, "vpn": True})
    widget.poll()
    assert widget.timezone is None
