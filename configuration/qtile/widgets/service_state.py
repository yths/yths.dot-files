import subprocess

import libqtile.log_utils
import libqtile.widget.base


class WidgetServiceState(libqtile.widget.base.BackgroundPoll):
    def __init__(self, service, warning_color="#ff0000", **config):
        libqtile.widget.base.BackgroundPoll.__init__(self, "", **config)
        self.service = service
        self.warning_color = warning_color

        self.tick_visible = False

    def poll(self):
        result = subprocess.run(
            ["systemctl", "--user", "is-active", "--quiet", self.service],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

        if result.returncode == 0:
            output = "·" if self.tick_visible else " "
            self.tick_visible = not self.tick_visible
        else:
            output = f"<span color='{self.warning_color}'>󰒲</span>"

        return output
