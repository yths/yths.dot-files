"""Qtile widget: OBS streaming and recording state.

Reads the latest entry from the ``stream`` Redis stream (``streaming``, ``obs`` booleans)
and renders a recording dot when OBS is live, switching every screen to the highlight
wallpaper while streaming. ``InLoopPollText`` based, so ``poll()`` must never raise.
"""

import os
from typing import Any

import libqtile.widget.base
import redis
import shared.state
import shared.stream


class WidgetStreamState(libqtile.widget.base.InLoopPollText):
    def __init__(
        self,
        r: redis.Redis | None,
        notification_color: str = "#00ff00",
        warning_color: str = "#ff0000",
        configuration_file_path: str | None = None,
        **config: Any,
    ) -> None:
        libqtile.widget.base.InLoopPollText.__init__(self, **config)
        self.r = r

        self.warning_color = warning_color
        self.notification_color = notification_color

        self.configuration_file_path = (
            configuration_file_path
            if configuration_file_path is not None
            else shared.state.CONFIGURATION_FILE_PATH
        )

        state = shared.state.read_state(self.configuration_file_path).get("state", {})
        self.condition = state.get("condition", "normal")

    def _apply_condition(self, condition: str) -> None:
        """Persist the wallpaper condition and repaint every screen.

        The key is ``state.condition`` and the wallpaper suffix is ``-highlight``, matching
        what ``config.py`` reads at startup and what ``install.py`` writes. This widget
        previously used ``state.urgency`` and a ``-urgent`` suffix — neither of which exists
        in the installed configuration, so the urgent state never persisted and going live
        raised ``KeyError`` out of ``poll()``, permanently freezing the cell.
        """
        configuration = shared.state.update_state(
            self.configuration_file_path, condition=condition
        )
        self.condition = condition

        theme = configuration.get("state", {}).get("theme")
        wallpapers = configuration.get("wallpapers", {})
        key = theme if condition == "normal" else f"{theme}-highlight"
        path_to_wallpaper = wallpapers.get(key)
        if not path_to_wallpaper:
            return
        path_to_wallpaper = os.path.expanduser(path_to_wallpaper)
        for screen in self.qtile.screens:
            screen.set_wallpaper(path_to_wallpaper)

    def poll(self) -> str:
        measurement = shared.stream.read_measurement(self.r, "stream")
        if measurement is None:
            return ""
        # Default to not-streaming: a payload missing the key must not flip the desktop
        # into the urgent wallpaper.
        streaming = measurement.get("streaming", False)
        obs = measurement.get("obs", False)

        icon = "󱗝" if obs else "󰅘"

        if streaming:
            if self.condition != "urgent":
                self._apply_condition("urgent")
            return f"<span color='{self.warning_color}'>{icon}</span>"

        if self.condition != "normal":
            self._apply_condition("normal")
        return icon
