"""Qtile widget: outstanding pacman updates count.

Reads the latest entry from the ``updates`` Redis stream (``outstanding_updates`` int) and
renders it next to a package glyph. The count refreshes hourly under the backend service
and immediately after every pacman transaction (via the post-transaction hook).
``BackgroundPoll`` based.
"""

from typing import Any

import libqtile.widget.base
import redis
import widgets._stream


class WidgetUpdates(libqtile.widget.base.BackgroundPoll):
    def __init__(
        self,
        r: redis.Redis | None,
        notification_color: str = "#00ff00",
        warning_color: str = "#ff0000",
        threshold: int = 32,
        **config: Any,
    ) -> None:
        libqtile.widget.base.BackgroundPoll.__init__(self, "", **config)
        self.r = r

        self.warning_color = warning_color
        self.notification_color = notification_color
        self.threshold = threshold

    def poll(self) -> str:
        measurement = widgets._stream.read_measurement(self.r, "updates")
        if measurement is None:
            return ""
        outstanding_updates = measurement.get("outstanding_updates", 0)
        if not isinstance(outstanding_updates, int):
            return ""

        if outstanding_updates > self.threshold:
            return f"<span color='{self.warning_color}'>󰚰 {outstanding_updates}</span>"
        if outstanding_updates > 0:
            return f"<span color='{self.notification_color}'>󰚰 {outstanding_updates}</span>"
        return "󰚰 0"
