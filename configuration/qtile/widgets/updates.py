"""Qtile widget: outstanding pacman updates count.

Reads the latest entry from the ``updates`` Redis stream (``outstanding_updates`` int) and
renders it next to a package glyph. The count refreshes hourly under the backend service
and immediately after every pacman transaction (via the post-transaction hook).
``BackgroundPoll`` based.
"""

import json

import libqtile.log_utils
import libqtile.widget.base
import redis.exceptions


class WidgetUpdates(libqtile.widget.base.BackgroundPoll):
    def __init__(
        self,
        r,
        notification_color="#00ff00",
        warning_color="#ff0000",
        threshold=32,
        **config,
    ):
        libqtile.widget.base.BackgroundPoll.__init__(self, "", **config)
        self.r = r

        self.warning_color = warning_color
        self.notification_color = notification_color
        self.threshold = threshold

    def poll(self):
        if self.r is None:
            return ""
        try:
            data = self.r.xrevrange("updates", count=1)
            eid, payload = data[-1]
            measurement = json.loads(payload[b"measurement"].decode("utf-8"))
        except (IndexError, KeyError, AttributeError, TypeError, json.JSONDecodeError, redis.exceptions.RedisError):
            return ""
        outstanding_updates = measurement.get("outstanding_updates", 0)

        if outstanding_updates > self.threshold:
            output = (
                f"<span color='{self.warning_color}'>󰚰 {outstanding_updates}</span>"
            )
        elif outstanding_updates > 0:
            output = f"<span color='{self.notification_color}'>󰚰 {outstanding_updates}</span>"
        else:
            output = "󰚰 0"

        return f"{output}"
