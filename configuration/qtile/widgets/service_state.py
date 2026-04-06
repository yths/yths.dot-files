import subprocess

import libqtile.log_utils
import libqtile.widget.base


class WidgetServiceState(libqtile.widget.base.InLoopPollText):
    def __init__(self, service, warning_color="#ff0000", **config):
        libqtile.widget.base.InLoopPollText.__init__(self, **config)
        self.service = service
        self.warning_color = warning_color

        self.tick_visible = False

    def poll(self):
        p = subprocess.Popen(
            f"systemctl --user is-active --quiet {self.service}",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = p.communicate()

        output = ""
        if p.returncode == 0:
            if self.tick_visible:
                output = "·"
            else:
                output = " "
            self.tick_visible = not self.tick_visible
        else:
            output = f"<span color='{self.warning_color}'>💤</span>"

        return f"{output}"
