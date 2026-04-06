import json
import os

import libqtile.log_utils
import libqtile.widget.base


class WidgetStreamState(libqtile.widget.base.InLoopPollText):
    def __init__(
        self,
        r,
        notification_color="#00ff00",
        warning_color="#ff0000",
        configuration_file_path=os.path.expanduser(
            os.path.join("~", ".config", "nuunamnir.json")
        ),
        **config,
    ):
        libqtile.widget.base.InLoopPollText.__init__(self, **config)
        self.r = r

        self.warning_color = warning_color
        self.notification_color = notification_color

        self.configuration_file_path = configuration_file_path

        with open(self.configuration_file_path, "r") as f:
            configuration = json.load(f)
        self.urgency = configuration["state"].get("urgency", "normal")

    def poll(self):
        if self.r is None:
            return ""
        data = self.r.xrevrange("stream", count=1)
        try:
            eid, payload = data[-1]
        except IndexError:
            return ""
        measurement = json.loads(payload.get(b"measurement").decode("utf-8"))
        streaming = measurement.get("streaming", True)
        obs = measurement.get("obs", False)

        if obs:
            icon = "󱗝"
        else:
            icon = "󰅘"

        if streaming:
            output = f"<span color='{self.warning_color}'>{icon}</span>"
            if self.urgency != "urgent":
                with open(self.configuration_file_path, "r") as f:
                    configuration = json.load(f)

                configuration["state"]["urgency"] = "urgent"
                self.urgency = "urgent"
                with open(self.configuration_file_path, "w") as f:
                    json.dump(configuration, f, indent=4)
                path_to_wallpaper = os.path.expanduser(
                    configuration["wallpapers"][
                        f"{'-'.join([configuration['state']['theme'], 'urgent'])}"
                    ]
                )
                for screen in self.qtile.screens:
                    screen.set_wallpaper(path_to_wallpaper)

        else:
            output = f"{icon}"
            if self.urgency != "normal":
                with open(self.configuration_file_path, "r") as f:
                    configuration = json.load(f)

                configuration["state"]["urgency"] = "normal"
                self.urgency = "normal"
                with open(self.configuration_file_path, "w") as f:
                    json.dump(configuration, f, indent=4)
                path_to_wallpaper = os.path.expanduser(
                    configuration["wallpapers"][configuration["state"]["theme"]]
                )
                for screen in self.qtile.screens:
                    screen.set_wallpaper(path_to_wallpaper)

        return f"{output}"
