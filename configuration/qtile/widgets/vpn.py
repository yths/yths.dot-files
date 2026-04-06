import json

import libqtile.widget.base


class WidgetVPN(libqtile.widget.base.BackgroundPoll):
    def __init__(self, r, warning_color="#ff0000", **config):
        libqtile.widget.base.InLoopPollText.__init__(self, **config)
        self.r = r

        self.warning_color = warning_color

    def poll(self):
        if self.r is None:
            return ""
        data = self.r.xrevrange("vpn", count=1)
        try:
            eid, payload = data[-1]
        except IndexError:
            return ""
        measurement = json.loads(payload.get(b"measurement").decode("utf-8"))

        output = []
        if measurement["connected"]:
            output.append(f"<span color='{self.warning_color}'>󰛳</span>")
            output.append(measurement["country"])
            output.append(f"({measurement['city']})")
        else:
            output.append("󰲝")
        return f"{' '.join(output)}"
