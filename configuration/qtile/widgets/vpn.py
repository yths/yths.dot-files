"""Qtile widget: VPN connection state with country/city.

Reads the latest entry from the ``vpn`` Redis stream (``connected``, ``country``, ``city``)
and surfaces an indicator plus a short location label when a tunnel is up.
``BackgroundPoll`` based.
"""

from typing import Any

import libqtile.widget.base
import redis
import shared.stream
import symbols as vocabulary


class WidgetVPN(libqtile.widget.base.BackgroundPoll):
    def __init__(
        self,
        r: redis.Redis | None,
        warning_color: str = "#ff0000",
        symbols: dict[str, Any] | None = None,
        **config: Any,
    ) -> None:
        libqtile.widget.base.BackgroundPoll.__init__(self, "", **config)
        self.r = r

        self.warning_color = warning_color
        #: The active vocabulary, passed down from config.py the same way the colours are.
        #: Defaults to ASCII so a widget built without one still draws something.
        self.symbols = symbols or vocabulary.SYMBOLS

    def poll(self) -> str:
        measurement = shared.stream.read_measurement(self.r, "vpn")
        if measurement is None:
            return ""

        if not measurement.get("connected"):
            # qtile clips each cell to the width derived from the text's advance, and the
            # nerd-font glyph's ink runs past its advance, so a lone icon needs a trailing
            # space or its right edge is cut off. Harmless for an ASCII stand-in.
            return f"{self.symbols['vpn.off']} "
        output = [f"<span color='{self.warning_color}'>{self.symbols['vpn.on']}</span>"]
        country = measurement.get("country")
        city = measurement.get("city")
        if country:
            output.append(str(country))
        if city:
            output.append(f"({city})")
        return " ".join(output)
