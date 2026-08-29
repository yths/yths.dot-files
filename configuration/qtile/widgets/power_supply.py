"""Qtile widget: AC/battery state.

Reads the latest entry from the ``power_supply`` Redis stream and renders the grid/battery
icon plus per-battery capacity and charging status. ``BackgroundPoll`` based.
"""

from typing import Any

import libqtile.widget.base
import redis
import shared.stream


class WidgetPowerSupply(libqtile.widget.base.BackgroundPoll):
    GRID_SYMBOL = "󰚥"
    #: Indexed by ``capacity // 10``, so entry *n* covers n0–n9 % and the last covers 100 %.
    #: These are the Material Design Icons battery ramps in full; the previous if/elif
    #: ladders repeated several glyphs and skipped others, losing granularity.
    DISCHARGING_SYMBOLS = ("󰁺", "󰁺", "󰁻", "󰁼", "󰁽", "󰁾", "󰁿", "󰂀", "󰂁", "󰂂", "󰁹")
    CHARGING_SYMBOLS = ("󰢜", "󰢜", "󰂆", "󰂇", "󰂈", "󰂉", "󰂊", "󰂋", "󰂌", "󰂍", "󰁹")
    #: Below this the discharging glyph is tinted with ``warning_color``.
    WARNING_CAPACITY = 20

    def __init__(
        self,
        r: redis.Redis | None,
        warning_color: str = "#ff0000",
        **config: Any,
    ) -> None:
        libqtile.widget.base.BackgroundPoll.__init__(self, "", **config)
        self.r = r

        self.warning_color = warning_color

    def _symbol(self, capacity: float, charging: bool) -> str:
        capacity = min(max(capacity, 0), 100)
        symbols = self.CHARGING_SYMBOLS if charging else self.DISCHARGING_SYMBOLS
        symbol = symbols[int(capacity) // 10]
        if not charging and capacity < self.WARNING_CAPACITY:
            return f"<span color='{self.warning_color}'>{symbol}</span>"
        return symbol

    def poll(self) -> str:
        measurement = shared.stream.read_measurement(self.r, "power_supply")
        if measurement is None:
            return ""

        output = []
        if measurement.get("grid"):
            output.append(self.GRID_SYMBOL)

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
