import json

import libqtile.log_utils
import libqtile.widget.base


class WidgetUpdates(libqtile.widget.base.InLoopPollText):
    def __init__(
        self,
        r,
        notification_color="#00ff00",
        warning_color="#ff0000",
        threshold=32,
        **config,
    ):
        libqtile.widget.base.InLoopPollText.__init__(self, **config)
        self.r = r

        self.warning_color = warning_color
        self.notification_color = notification_color
        self.threshold = threshold

    def poll(self):
        if self.r is None:
            return ""
        data = self.r.xrevrange("updates", count=1)
        try:
            eid, payload = data[-1]
        except IndexError:
            return ""
        measurement = json.loads(payload.get(b"measurement").decode("utf-8"))
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
