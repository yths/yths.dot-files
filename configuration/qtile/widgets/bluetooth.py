"""Qtile widget: connected bluetooth devices and their battery levels.

Reads the latest entry from the ``bluetooth`` Redis stream and renders a per-device
battery glyph. ``BackgroundPoll`` based.
"""

from typing import Any

import libqtile.widget.base
import redis
import shared.stream


class WidgetBluetooth(libqtile.widget.base.BackgroundPoll):
    CAPACITY_SYMBOLS = ("▁", "▂", "▃", "▄", "▅", "▆", "▇", "█")

    def __init__(
        self,
        r: redis.Redis | None,
        icons: dict[str, str] | None = None,
        warning_color: str = "#ff0000",
        **config: Any,
    ) -> None:
        libqtile.widget.base.BackgroundPoll.__init__(self, "", **config)
        self.r = r

        self.icons = icons if icons is not None else {}
        self.warning_color = warning_color

    def _scale(
        self, value: float, in_min: float, in_max: float, out_min: float, out_max: float
    ) -> float:
        # Real division: with // the result was already an integer, so the round() below
        # never did anything and the buckets came out skewed — the full block only ever
        # appeared at exactly 100 and everything from 86 up collapsed into one level.
        return (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

    def _level_index(self, capacity: float) -> int:
        capacity = min(max(capacity, 0), 100)
        return round(self._scale(capacity, 0, 100, 0, len(self.CAPACITY_SYMBOLS) - 1))

    def poll(self) -> str:
        measurement = shared.stream.read_measurement(self.r, "bluetooth")
        if measurement is None:
            return ""

        # Iterate the measurement, not self.icons, so devices keep the order the backend
        # reports them in.
        output = ""
        for device, device_state in measurement.items():
            if device not in self.icons or not isinstance(device_state, dict):
                continue
            output += f"{self.icons[device]} "
            capacity = device_state.get("capacity")
            if capacity == "Unknown":
                continue
            try:
                index = self._level_index(float(capacity))
            except (TypeError, ValueError):
                continue
            level = self.CAPACITY_SYMBOLS[index]
            if index < 2:
                output += f"<span color='{self.warning_color}'>{level}</span>"
            else:
                output += level
        return output
