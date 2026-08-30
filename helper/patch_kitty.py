"""Patch kitty: the terminal's base settings and its 16-colour theme file.

Writes ``~/.config/kitty/kitty.conf`` and a per-preset
``~/.config/kitty/themes/<name>.conf`` mapping palette tokens onto the ANSI slots.
"""

import json
import os
from typing import Any

# Resolves whether this runs as ``helper.patch_kitty`` or as a script; see helper/README.md.
try:
    from helper.utils import logger
except ImportError:
    from utils import logger


def patch_kitty(configuration: dict[str, Any]) -> None:
    theme = configuration["state"]["theme"]
    patched_configuration = {
        "allow_remote_control": "yes",
        "enable_audio_bell": "no",
        "font_size": round(configuration["font"]["size"] * 0.714),
        #"include": "current-theme.conf",
    }
    with open(os.path.expanduser("~/.config/kitty/kitty.conf"), "w") as output_handle:
        for key, value in patched_configuration.items():
            output_handle.write(f"{key} {value}\n")

    patched_configuration = {
        "background": configuration["palette"][theme]["background"],
        "selection_background": configuration["palette"][theme]["foreground"],
        "foreground": configuration["palette"][theme]["foreground"],
        "selection_foreground": configuration["palette"][theme]["background"],
        "font_family": configuration["font"]["family"],
        "cursor": configuration["palette"][theme]["foreground_variant"],

        # black = 0/8
        # red = 1/9
        # green = 2/10
        # yellow = 4/12 3/11
        # blue = 3/11 4/12
        # magenta = 5/13
        # cyan = 6/14
        # white = 7/15

        "color0": configuration["palette"][theme]["foreground_variant"],
        "color1": configuration["palette"][theme]["red"],
        "color2": configuration["palette"][theme]["green"],
        "color3": configuration["palette"][theme]["yellow"],
        "color4": configuration["palette"][theme]["blue"],
        "color5": configuration["palette"][theme]["magenta"],
        "color6": configuration["palette"][theme]["cyan"],
        "color7": configuration["palette"][theme]["background"],
        "color8": configuration["palette"][theme]["foreground"],
        "color9": configuration["palette"][theme]["red_variant"],
        "color10": configuration["palette"][theme]["green_variant"],
        "color11": configuration["palette"][theme]["yellow_variant"],
        "color12": configuration["palette"][theme]["blue_variant"],
        "color13": configuration["palette"][theme]["magenta_variant"],
        "color14": configuration["palette"][theme]["cyan_variant"],
        "color15": configuration["palette"][theme]["neutral"],
    }
    with open(
        os.path.expanduser(f"~/.config/kitty/themes/{configuration['name']}.conf"), "w"
    ) as output_handle:
        for key, value in patched_configuration.items():
            output_handle.write(f"{key} {value}\n")

    logger.info("Patched kitty configuration ...")


if __name__ == "__main__":
    with open(os.path.expanduser("~/.config/config.json")) as input_handle:
        patch_kitty(json.load(input_handle))
