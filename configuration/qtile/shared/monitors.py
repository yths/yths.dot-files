"""Detect connected monitors, and keep ``~/.config/config.json`` in step with them.

Every size in this desktop is derived from monitor geometry -- the bar's font, the layout
margins, rofi's width, the X server's DPI -- and that geometry was read once, by
``install.py``, and never again. Plugging a display in therefore changed nothing until qtile
was restarted by hand.

Lives here rather than in ``helper/`` because qtile has to reach it on a hotplug and
``configuration/qtile`` is already on its path. ``helper/screen_configuration.py`` imports it
from the other side, the way ``helper/preview_audio.py`` reaches ``shared.spectrum``.
"""

from typing import Any

import screeninfo
import shared.state

#: The geometry recorded per monitor. Anything reading ``configuration["monitors"]`` expects
#: these keys, so a change here is a change to the schema in docs/config-schema.md.
MILLIMETRES_PER_INCH = 25.4


def _monitor(monitor: screeninfo.Monitor) -> dict[str, Any]:
    """One monitor's geometry, in the shape config.json records."""
    diagonal = (monitor.width**2 + monitor.height**2) ** 0.5
    diagonal_mm = (monitor.width_mm**2 + monitor.height_mm**2) ** 0.5
    diagonal_dpi = round(diagonal / diagonal_mm * MILLIMETRES_PER_INCH)
    return {
        "width": monitor.width,
        "width_mm": monitor.width_mm,
        "width_dpi": round(monitor.width / monitor.width_mm * MILLIMETRES_PER_INCH),
        "height": monitor.height,
        "height_mm": monitor.height_mm,
        "height_dpi": round(monitor.height / monitor.height_mm * MILLIMETRES_PER_INCH),
        "diagonal": diagonal,
        "diagonal_mm": diagonal_mm,
        "diagonal_dpi": diagonal_dpi,
        # Every scaled size in the bar and the layouts is this times a base measurement.
        "scaling_factor": diagonal_dpi / 100,
        "is_primary": bool(getattr(monitor, "is_primary", False)),
    }


def detect() -> dict[str, dict[str, Any]]:
    """Every connected monitor, keyed by output name. Empty if none can be queried."""
    try:
        monitors = screeninfo.get_monitors()
    except (screeninfo.ScreenInfoError, OSError):
        return {}
    return {
        monitor.name: _monitor(monitor)
        for monitor in monitors
        if monitor.width_mm and monitor.height_mm
    }


def refresh(configuration_file_path: str | None = None) -> bool:
    """Record the currently connected monitors. Returns whether anything changed.

    ``False`` for an unchanged layout is what lets the caller skip the reload: a screen-change
    event fires for things that are not a plug or an unplug, and reloading qtile on each one
    would drop the bar for no reason.
    """
    path = configuration_file_path or shared.state.CONFIGURATION_FILE_PATH
    configuration = shared.state.read_state(path)
    if not configuration:
        return False

    detected = detect()
    # An empty result means the query failed, not that every display was unplugged; writing it
    # would leave the desktop with no geometry to scale from and nothing to recover it.
    if not detected or detected == configuration.get("monitors"):
        return False

    configuration["monitors"] = detected
    return shared.state.write_state(configuration, path)
