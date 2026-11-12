"""Patch kitty: the terminal's settings and its sixteen ANSI colours, in one file.

Writes ``~/.config/kitty/kitty.conf`` -- base settings and the palette together, with no
``include`` and no second file. kitty watches that path itself and re-reads it a fraction of
a second after it changes, so the theme reaches every open window without anything being
signalled or restarted; see ``AUTO_RELOAD_SECONDS``.
"""

import json
import os
from typing import Any

# Resolves whether this runs as ``helper.patch_kitty`` or as a script; see helper/README.md.
try:
    from helper.utils import logger
except ImportError:
    from utils import logger

#: kitty re-reads kitty.conf this many seconds after it changes, and that is the whole reload
#: mechanism: writing the file below is what applies the theme. Written explicitly rather than
#: left to kitty's default because the value is read once at startup and ignored on reload, so
#: it has to already be in the file kitty starts with -- and because it is load-bearing here,
#: not a preference. A negative value would mean no theme change until every window is closed.
AUTO_RELOAD_SECONDS = "0.1"

#: Settings that are not derived from the palette. A keybinding or a scrollback limit goes
#: here, not into kitty.conf, which is rewritten from this dict on every theme switch.
BASE_SETTINGS: dict[str, str] = {
    "allow_remote_control": "yes",
    "enable_audio_bell": "no",
    "auto_reload_config": AUTO_RELOAD_SECONDS,
}

#: kitty's sixteen ANSI slots, in pairs: slot *i* takes the first token, slot *i + 8* the
#: second. Black and white are the palette's own foreground and background rather than true
#: black and white, so a program that prints in "black" stays legible on this background.
ANSI_SLOTS: tuple[tuple[str, str, str], ...] = (
    ("black", "foreground_variant", "foreground"),
    ("red", "red", "red_variant"),
    ("green", "green", "green_variant"),
    ("yellow", "yellow", "yellow_variant"),
    ("blue", "blue", "blue_variant"),
    ("magenta", "magenta", "magenta_variant"),
    ("cyan", "cyan", "cyan_variant"),
    ("white", "background", "neutral"),
)

#: kitty's font size is given in points against the configured size, which is in pixels.
FONT_SIZE_RATIO = 0.714


def kitty_configuration(configuration: dict[str, Any]) -> dict[str, str]:
    """Return every setting ``kitty.conf`` holds, in the order it is written."""
    palette = configuration["palette"][configuration["state"]["theme"]]
    settings = dict(BASE_SETTINGS)
    settings["font_family"] = configuration["font"]["family"]
    settings["font_size"] = str(round(configuration["font"]["size"] * FONT_SIZE_RATIO))
    settings["background"] = palette["background"]
    settings["foreground"] = palette["foreground"]
    settings["selection_background"] = palette["foreground"]
    settings["selection_foreground"] = palette["background"]
    settings["cursor"] = palette["foreground_variant"]
    for slot, (_, normal, bright) in enumerate(ANSI_SLOTS):
        settings[f"color{slot}"] = palette[normal]
        settings[f"color{slot + 8}"] = palette[bright]
    return settings


def patch_kitty(configuration: dict[str, Any]) -> None:
    path = os.path.expanduser("~/.config/kitty/kitty.conf")
    with open(path, "w") as output_handle:
        for key, value in kitty_configuration(configuration).items():
            output_handle.write(f"{key} {value}\n")

    logger.info("Patched kitty configuration ...")


if __name__ == "__main__":
    with open(os.path.expanduser("~/.config/config.json")) as input_handle:
        patch_kitty(json.load(input_handle))
