import json

import libqtile.widget.base


class WidgetPowerSupply(libqtile.widget.base.BackgroundPoll):
    def __init__(self, r, warning_color="#ff0000", **config):
        libqtile.widget.base.InLoopPollText.__init__(self, **config)
        self.r = r

        self.warning_color = warning_color

    def poll(self):
        if self.r is None:
            return ""
        data = self.r.xrevrange("power_supply", count=1)
        try:
            eid, payload = data[-1]
        except IndexError:
            return ""
        measurement = json.loads(payload.get(b"measurement").decode("utf-8"))

        output = []
        if measurement["grid"]:
            output.append("󰚥")
        for battery in measurement["batteries"]:
            if measurement["batteries"][battery]["status"] == "Charging":
                if int(measurement["batteries"][battery]["capacity"]) >= 100:
                    battery = "󰁹"
                elif int(measurement["batteries"][battery]["capacity"]) >= 90:
                    battery = "󰂋"
                elif int(measurement["batteries"][battery]["capacity"]) >= 80:
                    battery = "󰂊"
                elif int(measurement["batteries"][battery]["capacity"]) >= 70:
                    battery = "󰂉"
                elif int(measurement["batteries"][battery]["capacity"]) >= 60:
                    battery = "󰂈"
                elif int(measurement["batteries"][battery]["capacity"]) >= 50:
                    battery = "󰂇"
                elif int(measurement["batteries"][battery]["capacity"]) >= 40:
                    battery = "󰂆"
                elif int(measurement["batteries"][battery]["capacity"]) >= 30:
                    battery = "󰂇"
                elif int(measurement["batteries"][battery]["capacity"]) >= 20:
                    battery = "󰂆"
                elif int(measurement["batteries"][battery]["capacity"]) >= 10:
                    battery = "󰢜"
                else:
                    battery = "󰢜"
            else:
                if int(measurement["batteries"][battery]["capacity"]) >= 100:
                    battery = "󰁹"
                elif int(measurement["batteries"][battery]["capacity"]) >= 90:
                    battery = "󰂂"
                elif int(measurement["batteries"][battery]["capacity"]) >= 80:
                    battery = "󰂁"
                elif int(measurement["batteries"][battery]["capacity"]) >= 70:
                    battery = "󰂀"
                elif int(measurement["batteries"][battery]["capacity"]) >= 60:
                    battery = "󰁿"
                elif int(measurement["batteries"][battery]["capacity"]) >= 50:
                    battery = "󰁾"
                elif int(measurement["batteries"][battery]["capacity"]) >= 40:
                    battery = "󰁽"
                elif int(measurement["batteries"][battery]["capacity"]) >= 30:
                    battery = "󰁼"
                elif int(measurement["batteries"][battery]["capacity"]) >= 20:
                    battery = "󰁼"
                elif int(measurement["batteries"][battery]["capacity"]) >= 10:
                    battery = "<span color='{self.warning_color}'>󰁺</span>"
                else:
                    battery = f"<span color='{self.warning_color}'>󰁺</span>"
            output.append(battery)
        return f"{' '.join(output)}"
