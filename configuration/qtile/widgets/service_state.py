"""Qtile widget: indicator that toggles when a systemd user unit is active.

Polls ``systemctl --user is-active <service>`` (default service: ``backend.service``).
Renders a blinking dot when the service is up and, in ``warning_color``, a marker when it is
not: a backend that is down is an error state, which is the one thing that colour is for.
The cell is centred by its ink rather than by its line, because a lone dot shows the pixel
or two that a row of digits hides; see ``shared/glyph_centre.py``. ``BackgroundPoll`` based.
"""

import subprocess
from typing import Any

import libqtile.log_utils
import libqtile.widget.base
import shared.glyph_centre
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

    def _configure(self, qtile: Any, bar: Any) -> None:
        libqtile.widget.base.BackgroundPoll._configure(self, qtile, bar)
        # ``_TextBox.draw`` picks the line's top from the font's line box and hands it to
        # the layout. Wrapping that one call replaces the position and leaves the rest of
        # the drawing -- clearing, padding, the copy to the bar -- to qtile.
        draw = self.layout.draw

        def centred(x: float, y: float) -> None:
            draw(x, self._top(y))

        self.layout.draw = centred

    def _top(self, y: float) -> float:
        """Where the line's top goes: its ink centred in the bar, else qtile's own ``y``."""
        top = shared.glyph_centre.top(self.layout.text, self.font, self.fontsize, self.bar.size)
        return y if top is None else top

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
