"""Qtile widget: screen backlight, as its deviation from this machine's calibrated level.

Reads the latest entry from the ``backlight`` Redis stream (``devices``: raw ``brightness``
and ``max_brightness`` per device) and renders an icon. With a target recorded for this host
in ``configuration/hardware/backlight.json`` -- the raw level that measured 120 cd/m² when
the display was calibrated, see docs/install.md -- the icon alone means "on target", and an
offset in percentage points of the range follows it otherwise, in ``notification_color``:
off-calibration is worth knowing and nothing to act on. Without a target the plain level is
shown. A machine without a backlight shows nothing. ``BackgroundPoll`` based.
"""

import json
import socket
from typing import Any

import libqtile.widget.base
import redis
import shared.stream
import symbols as vocabulary


def read_target(path: str, hostname: str | None = None) -> tuple[str | None, int] | None:
    """``(device, raw target)`` for this host from ``path``, or ``None`` when the file, the
    host or a usable value is missing. The file maps hostname to ``{device: raw level}``;
    a device of ``"*"`` matches whichever backlight the machine has."""
    try:
        with open(path, encoding="utf-8") as handle:
            mapping = json.load(handle)
    except (OSError, ValueError):
        return None
    entry = mapping.get(hostname or socket.gethostname()) if isinstance(mapping, dict) else None
    if not isinstance(entry, dict):
        return None
    for device, target in entry.items():
        if isinstance(target, int) and not isinstance(target, bool) and target >= 0:
            return (None if device == "*" else device), target
    return None


class WidgetBacklight(libqtile.widget.base.BackgroundPoll):
    def __init__(
        self,
        r: redis.Redis | None,
        notification_color: str = "#00ff00",
        target: tuple[str | None, int] | None = None,
        tolerance: int = 1,
        symbols: dict[str, Any] | None = None,
        **config: Any,
    ) -> None:
        libqtile.widget.base.BackgroundPoll.__init__(self, "", **config)
        self.r = r

        self.notification_color = notification_color
        #: ``(device, raw level)`` from ``read_target``; ``None`` shows the plain level.
        self.target = target
        #: Percentage points either side of the target still drawn as "on target", so one
        #: keypress of rounding in the driver does not make the cell flicker.
        self.tolerance = tolerance
        #: The active vocabulary, passed down from config.py the same way the colours are.
        #: Defaults to ASCII so a widget built without one still draws something.
        self.symbols = symbols or vocabulary.SYMBOLS

    def _device(self, devices: dict[str, Any]) -> dict[str, Any] | None:
        """The target's device when it is present, else the first one published."""
        wanted = self.target[0] if self.target else None
        if wanted is not None and isinstance(devices.get(wanted), dict):
            return devices[wanted]
        for state in devices.values():
            if isinstance(state, dict):
                return state
        return None

    def poll(self) -> str:
        measurement = shared.stream.read_measurement(self.r, "backlight")
        if measurement is None or not isinstance(measurement.get("devices"), dict):
            return ""
        state = self._device(measurement["devices"])
        if state is None:
            return ""
        brightness, maximum = state.get("brightness"), state.get("max_brightness")
        if not isinstance(brightness, int) or not isinstance(maximum, int) or maximum <= 0:
            return ""

        icon = self.symbols["backlight.level"]
        if self.target is None:
            return f"{icon} {round(100 * brightness / maximum)}"
        offset = round(100 * (brightness - self.target[1]) / maximum)
        if abs(offset) <= self.tolerance:
            # A lone nerd-font glyph's ink overruns its advance; see vpn.py.
            return f"{icon} "
        return f"<span color='{self.notification_color}'>{icon} {offset:+d}</span>"
