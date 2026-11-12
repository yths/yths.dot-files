"""Qtile widget: indicator that toggles when a systemd user unit is active.

Polls ``systemctl --user is-active <service>`` (default service: ``backend.service``).
Renders a blinking dot when the service is up, an empty cell otherwise, and applies
``warning_color`` if the service has failed. ``BackgroundPoll`` based.
"""

import subprocess
from typing import Any

import libqtile.log_utils
import libqtile.widget.base
import symbols as vocabulary


class WidgetServiceState(libqtile.widget.base.BackgroundPoll):
    # Trailing space: qtile clips the cell to the text's advance width and this glyph's
    # ink runs 0.418em past it, so a lone icon would be cut off on the right.

    def __init__(
        self,
        service: str,
        warning_color: str = "#ff0000",
        symbols: dict[str, Any] | None = None,
        **config: Any,
    ) -> None:
        libqtile.widget.base.BackgroundPoll.__init__(self, "", **config)
        self.service = service
        self.warning_color = warning_color

        self.tick_visible = False
        #: The active vocabulary, passed down from config.py the same way the colours are.
        #: Defaults to ASCII so a widget built without one still draws something.
        self.symbols = symbols or vocabulary.SYMBOLS

    def poll(self) -> str:
        # A failure to even run systemctl must read as "service down", not freeze the cell
        # on its last value — a health indicator stuck on "up" is worse than no indicator.
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-active", "--quiet", self.service],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except OSError:
            libqtile.log_utils.logger.exception("could not run systemctl")
            return f"<span color='{self.warning_color}'>{self.symbols['service.down']} </span>"

        if result.returncode == 0:
            output = self.symbols["service.tick"] if self.tick_visible else " "
            self.tick_visible = not self.tick_visible
        else:
            output = f"<span color='{self.warning_color}'>{self.symbols['service.down']} </span>"

        return output
