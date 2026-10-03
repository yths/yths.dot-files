"""Qtile widget: connected bluetooth devices and their battery levels.

Reads the latest entry from the ``bluetooth`` Redis stream and renders one icon per
connected device, followed by its battery level where the device reports one. A device the
theme maps by MAC (``bluetooth_devices`` in ``config.json``) gets that icon; any other gets
``bluetooth.device``. ``BackgroundPoll`` based.
"""

from typing import Any

import libqtile.widget.base
import redis
import shared.stream
import symbols as vocabulary


class WidgetBluetooth(libqtile.widget.base.BackgroundPoll):

    def __init__(
        self,
        r: redis.Redis | None,
        devices: dict[str, str] | None = None,
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
        #: Upper-case MAC -> icon, as ``symbols.bluetooth_devices`` resolves it.
        self.devices = {address.upper(): icon for address, icon in (devices or {}).items()}

    def _scale(
        self, value: float, in_min: float, in_max: float, out_min: float, out_max: float
    ) -> float:
        # Real division: with // the result was already an integer, so the round() below
        # never did anything and the buckets came out skewed — the full block only ever
        # appeared at exactly 100 and everything from 86 up collapsed into one level.
        return (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

    def _level_index(self, capacity: float) -> int:
        capacity = min(max(capacity, 0), 100)
        return round(self._scale(capacity, 0, 100, 0, len(self.symbols["meter.ramp"]) - 1))

    def poll(self) -> str:
        measurement = shared.stream.read_measurement(self.r, "bluetooth")
        if measurement is None:
            return ""

        # The backend publishes connected devices only, so every entry is drawn, in the
        # order it reports them.
        output = ""
        for device, device_state in measurement.items():
            if not isinstance(device_state, dict):
                continue
            icon = self.devices.get(str(device).upper(), self.symbols["bluetooth.device"])
            output += f"{icon} "
            capacity = device_state.get("capacity")
            if capacity == "Unknown":
                continue
            try:
                index = self._level_index(float(capacity))
            except (TypeError, ValueError):
                continue
            level = self.symbols["meter.ramp"][index]
            if index < 2:
                output += f"<span color='{self.warning_color}'>{level}</span>"
            else:
                output += level
        return output
