import json

import libqtile.widget.base


class WidgetVPN(libqtile.widget.base.BackgroundPoll):
    def __init__(self, r, warning_color="#ff0000", **config):
        libqtile.widget.base.BackgroundPoll.__init__(self, "", **config)
        self.r = r

        self.warning_color = warning_color

    def poll(self):
        if self.r is None:
            return ""
        try:
            data = self.r.xrevrange("vpn", count=1)
            eid, payload = data[-1]
            measurement = json.loads(payload[b"measurement"].decode("utf-8"))

            output = []
            if measurement["connected"]:
                output.append(f"<span color='{self.warning_color}'>󰛳</span>")
                output.append(measurement["country"])
                output.append(f"({measurement['city']})")
            else:
                output.append("󰲝")
            return f"{' '.join(output)}"
        except (IndexError, KeyError, AttributeError, TypeError, json.JSONDecodeError):
            return ""
