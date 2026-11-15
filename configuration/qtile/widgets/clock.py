"""Qtile widget: the bar clock, in the timezone the machine is geolocated in.

qtile's ``Clock`` with its timezone taken from the newest ``location`` entry -- the IP-derived
zone the sunrise/sunset cell already compares against -- so after travelling the clock and
the sun times agree without changing the system timezone. A location looked up through the
VPN is the exit server's, not the machine's, and is ignored, as is any zone this machine's
tz database does not know; both fall back to the system timezone. Where the shown zone is not
the system's, its abbreviation is appended, so a clock an hour off from every other one on
the machine says why.
"""

import datetime
import zoneinfo
from typing import Any

import libqtile.widget.clock
import redis
import shared.stream


def location_timezone(measurement: dict[str, Any] | None) -> zoneinfo.ZoneInfo | None:
    """The zone ``measurement`` places this machine in, or ``None`` to use the system's."""
    if not isinstance(measurement, dict) or measurement.get("vpn"):
        return None
    name = measurement.get("timezone")
    if not isinstance(name, str) or not name:
        return None
    try:
        return zoneinfo.ZoneInfo(name)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        return None


class WidgetClock(libqtile.widget.clock.Clock):
    def __init__(self, r: redis.Redis | None, **config: Any) -> None:
        libqtile.widget.clock.Clock.__init__(self, **config)
        self.r = r
        #: The format as configured; ``poll`` adds the zone abbreviation to a copy.
        self.base_format = self.format

    def poll(self) -> str:
        zone = location_timezone(shared.stream.read_measurement(self.r, "location"))
        now = datetime.datetime.now(datetime.UTC)
        foreign = zone is not None and now.astimezone(zone).utcoffset() != now.astimezone().utcoffset()
        self.timezone = zone if foreign else None
        self.format = f"{self.base_format} %Z" if foreign else self.base_format
        return libqtile.widget.clock.Clock.poll(self)
