"""Qtile widget: connected bluetooth devices and their battery levels.

Reads the latest entry from the ``bluetooth`` Redis stream and renders a per-device
battery glyph. ``BackgroundPoll`` based.
"""

import json

import libqtile.widget.base
import libqtile.log_utils
import redis.exceptions


class WidgetBluetooth(libqtile.widget.base.BackgroundPoll):
    def __init__(self, r, icons={}, warning_color="#ff0000", **config):
        libqtile.widget.base.BackgroundPoll.__init__(self, "", **config)
        self.r = r

        self.icons = icons
        self.warning_color = warning_color

        self.capcity_symbols = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

    def _scale(self, value, in_min, in_max, out_min, out_max):
        # Real division: with // the result was already an integer, so the round() below
        # never did anything and the buckets came out skewed — the full block only ever
        # appeared at exactly 100 and everything from 86 up collapsed into one level.
        return (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

    def poll(self):
        if self.r is None:
            return ""
        try:
            data = self.r.xrevrange("bluetooth", count=1)
            eid, payload = data[-1]
            measurement = json.loads(payload[b"measurement"].decode("utf-8"))
            output = ""
            for device in measurement:
                if device in self.icons:
                    output += f"{self.icons[device]} "
                    if measurement[device]["capacity"] != "Unknown":
                        capcity = float(measurement[device]["capacity"])
                        idx = int(round(self._scale(capcity, 0, 100, 0, 7)))
                        if idx < 2:
                            output += f"<span color='{self.warning_color}'>{self.capcity_symbols[idx]}</span>"
                        else:
                            output += f"{self.capcity_symbols[idx]}"

            return f"{output}"
        except (IndexError, KeyError, AttributeError, TypeError, ValueError, json.JSONDecodeError, redis.exceptions.RedisError):
            return ""
