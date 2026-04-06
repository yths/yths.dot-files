import json

import libqtile.widget.base
import libqtile.log_utils


class WidgetBluetooth(libqtile.widget.base.InLoopPollText):
    def __init__(self, r, icons={}, warning_color="#ff0000", **config):
        libqtile.widget.base.InLoopPollText.__init__(self, **config)
        self.r = r

        self.icons = icons
        self.warning_color = warning_color

        self.capcity_symbols = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

    def _scale(self, value, in_min, in_max, out_min, out_max):
        return (value - in_min) * (out_max - out_min) // (in_max - in_min) + out_min

    def poll(self):
        if self.r is None:
            return ""
        data = self.r.xrevrange("bluetooth", count=1)
        try:
            eid, payload = data[-1]
        except IndexError:
            return ""
        measurement = json.loads(payload.get(b"measurement").decode("utf-8"))
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
