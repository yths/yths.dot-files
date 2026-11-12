"""Qtile widget: VPN connection state with country/city.

Reads the latest entry from the ``vpn`` Redis stream (``connected``, ``country``, ``city``)
and surfaces an indicator plus a short location label when a tunnel is up.
``BackgroundPoll`` based.
"""

from typing import Any

import libqtile.widget.base
import redis
import widgets._stream


class WidgetVPN(libqtile.widget.base.BackgroundPoll):
    def __init__(
        self,
        r: redis.Redis | None,
        warning_color: str = "#ff0000",
        **config: Any,
    ) -> None:
        libqtile.widget.base.BackgroundPoll.__init__(self, "", **config)
        self.r = r

        self.warning_color = warning_color

    def poll(self) -> str:
        measurement = widgets._stream.read_measurement(self.r, "vpn")
        if measurement is None:
            return ""

        if not measurement.get("connected"):
            return "󰲝"
        output = [f"<span color='{self.warning_color}'>󰛳</span>"]
        country = measurement.get("country")
        city = measurement.get("city")
        if country:
            output.append(str(country))
        if city:
            output.append(f"({city})")
        return " ".join(output)
