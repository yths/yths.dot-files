"""Qtile widget: IP-derived geolocation with current sunrise/sunset.

Reads the latest entry from the ``location`` Redis stream (latitude, longitude, timezone,
sunrise, sunset) and surfaces the day/night transition that drives the automatic theme
switch. ``InLoopPollText`` based, so ``poll()`` must never raise: ``timer_setup``
reschedules only after ``tick()`` returns, and one escaped exception freezes the cell — and
with it the automatic theme switch — for the rest of the session.
"""

import datetime
import os
import subprocess
import zoneinfo
from typing import Any

import libqtile.widget.base
import redis
import widgets._state
import widgets._stream

#: Repository root, resolved through the ~/.config/qtile symlink qtile loads this file
#: through. Reaching helper/ directly is what lets the patcher symlinks in this directory
#: -- which existed only to be reachable from here -- be removed.
REPOSITORY_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
)


class WidgetLocation(libqtile.widget.base.InLoopPollText):
    # Nerd Font Private Use Area glyphs. They render as blank in most editors and
    # diffs, so they are named here rather than inlined into the format strings below.
    SUNRISE_ICON = ""  # U+E34D
    SUNSET_ICON = ""  # U+E34C
    MANUAL_ICON = ""  # U+F456, shown when the theme switch is pinned

    def __init__(
        self,
        r: redis.Redis | None,
        notification_color: str = "#ff0000",
        configuration_file_path: str | None = None,
        **config: Any,
    ) -> None:
        libqtile.widget.base.InLoopPollText.__init__(self, **config)
        self.r = r
        self.configuration_file_path = (
            configuration_file_path
            if configuration_file_path is not None
            else widgets._state.CONFIGURATION_FILE_PATH
        )

        self.notification_color = notification_color

        self.add_callbacks(
            {"Button2": self.toggle_mode, "Button3": self.toggle_theme_manually}
        )

    def toggle_mode(self) -> None:
        state = widgets._state.read_state(self.configuration_file_path).get("state", {})
        mode = "manual" if state.get("mode") == "automatic" else "automatic"
        widgets._state.update_state(self.configuration_file_path, mode=mode)

    def toggle_theme_manually(self) -> None:
        state = widgets._state.read_state(self.configuration_file_path).get("state", {})
        theme = "light" if state.get("theme") == "dark" else "dark"
        widgets._state.update_state(self.configuration_file_path, mode="manual")
        self.apply_theme(theme)

    def apply_theme(self, theme: str) -> None:
        """Set the theme to ``theme`` and re-patch every application.

        Takes the target rather than flipping whatever is on disk, so repeated calls
        converge instead of cancelling each other out.
        """
        widgets._state.update_state(self.configuration_file_path, theme=theme)
        subprocess.Popen(
            args=[
                "python",
                os.path.join(REPOSITORY_ROOT, "helper", "patch_configurations.py"),
            ]
        )

    def _now(self, timezone: str | None) -> datetime.time:
        """Local time in the *geolocated* zone, which is what sunrise/sunset are given in."""
        if timezone:
            try:
                return datetime.datetime.now(zoneinfo.ZoneInfo(timezone)).time()
            except (zoneinfo.ZoneInfoNotFoundError, ValueError):
                pass
        return datetime.datetime.now().astimezone().time()

    def poll(self) -> str:
        measurement = widgets._stream.read_measurement(self.r, "location")
        if measurement is None:
            return ""

        sunrise = measurement.get("sunrise")
        sunset = measurement.get("sunset")
        if not isinstance(sunrise, str) or not isinstance(sunset, str):
            return ""
        try:
            sunrise_ts = datetime.time.fromisoformat(sunrise)
            sunset_ts = datetime.time.fromisoformat(sunset)
        except ValueError:
            return ""

        # The backend queries sunrisesunset.io with the IP-derived timezone, so these are
        # wall-clock times *there* — compare against that zone, not the machine's.
        now = self._now(measurement.get("timezone"))
        is_night = now < sunrise_ts or now > sunset_ts
        theme = "dark" if is_night else "light"

        state = widgets._state.read_state(self.configuration_file_path).get("state", {})
        if theme != state.get("theme") and state.get("mode") == "automatic":
            self.apply_theme(theme)

        mode_icon = f" {self.MANUAL_ICON}" if state.get("mode") == "manual" else ""

        if is_night:
            return (
                f"<span color='{self.notification_color}'>"
                f"{self.SUNRISE_ICON} {sunrise}</span> "
                f"{self.SUNSET_ICON} {sunset}{mode_icon}"
            )
        return (
            f"{self.SUNRISE_ICON} {sunrise} "
            f"<span color='{self.notification_color}'>"
            f"{self.SUNSET_ICON} {sunset}</span>{mode_icon} "
        )
