"""Qtile widget: AC/battery state.

Reads the latest entry from the ``power_supply`` Redis stream and renders the grid/battery
icon plus per-battery capacity and charging status. ``BackgroundPoll`` based.
"""

from typing import Any

import libqtile.widget.base
import redis
import shared.stream
import symbols as vocabulary


class WidgetPowerSupply(libqtile.widget.base.BackgroundPoll):
    #: Below this the discharging symbol is tinted with ``warning_color``.
    WARNING_CAPACITY = 20

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
        #: The active vocabulary, from ~/.config/config.json via config.py -- the same route
        #: the colours take. Falls back to the ASCII defaults so a widget built without one
        #: still draws something.
        self.symbols = symbols or vocabulary.SYMBOLS

    def _symbol(self, capacity: float, charging: bool) -> str:
        """The rung of the battery ladder this capacity sits on.

        Indexed by ``capacity // 10``, so entry *n* covers n0-n9 % and the last covers 100 %.
        The ladders are in the vocabulary rather than here: a theme swaps them, and a machine
        without the font gets ASCII instead of eleven empty boxes.
        """
        capacity = min(max(capacity, 0), 100)
        key = "battery.charging" if charging else "battery.discharging"
        symbol = self.symbols[key][int(capacity) // 10]
        if not charging and capacity < self.WARNING_CAPACITY:
            return f"<span color='{self.warning_color}'>{symbol}</span>"
        return symbol

    def poll(self) -> str:
        measurement = shared.stream.read_measurement(self.r, "power_supply")
        if measurement is None:
            return ""

        output = []
        if measurement.get("grid"):
            output.append(self.symbols["battery.grid"])

        batteries = measurement.get("batteries")
        if isinstance(batteries, dict):
            for state in batteries.values():
                if not isinstance(state, dict):
                    continue
                try:
                    capacity = float(state.get("capacity"))
                except (TypeError, ValueError):
                    continue
                output.append(self._symbol(capacity, state.get("status") == "Charging"))

        return " ".join(output)
