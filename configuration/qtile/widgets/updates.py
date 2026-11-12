"""Qtile widget: outstanding pacman updates count.

Reads the latest entry from the ``updates`` Redis stream (``outstanding_updates`` int) and
renders it next to a package glyph. The count refreshes hourly under the backend service
and immediately after every pacman transaction (via the post-transaction hook).
``BackgroundPoll`` based.
"""

from typing import Any

import libqtile.widget.base
import redis
import shared.stream
import symbols as vocabulary


class WidgetUpdates(libqtile.widget.base.BackgroundPoll):
    def __init__(
        self,
        r: redis.Redis | None,
        notification_color: str = "#00ff00",
        warning_color: str = "#ff0000",
        threshold: int = 32,
        symbols: dict[str, Any] | None = None,
        **config: Any,
    ) -> None:
        libqtile.widget.base.BackgroundPoll.__init__(self, "", **config)
        self.r = r

        self.warning_color = warning_color
        self.notification_color = notification_color
        self.threshold = threshold
        #: The active vocabulary, passed down from config.py the same way the colours are.
        #: Defaults to ASCII so a widget built without one still draws something.
        self.symbols = symbols or vocabulary.SYMBOLS

    def poll(self) -> str:
        measurement = shared.stream.read_measurement(self.r, "updates")
        if measurement is None:
            return ""
        outstanding_updates = measurement.get("outstanding_updates", 0)
        if not isinstance(outstanding_updates, int):
            return ""

        icon = self.symbols["updates.available"]
        if outstanding_updates > self.threshold:
            colour = self.warning_color
        elif outstanding_updates > 0:
            colour = self.notification_color
        else:
            return f"{icon} 0"
        return f"<span color='{colour}'>{icon} {outstanding_updates}</span>"
