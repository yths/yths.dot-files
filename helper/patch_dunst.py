"""Patch dunst: notification colours, font, offset and per-urgency formats.

Rewrites ``~/.config/dunst/dunstrc`` in place via ``configparser``. Only the offset
needs monitor geometry, so a machine without any still gets themed notifications.
"""

import configparser
import json
import os
from typing import Any

# Resolves whether this runs as ``helper.patch_dunst`` or as a script; see helper/README.md.
try:
    from helper.utils import logger, monitor_average
except ImportError:
    from utils import logger, monitor_average


def patch_dunst(configuration: dict[str, Any]) -> None:
    configuration_path = os.path.expanduser("~/.config/dunst/dunstrc")

    theme = configuration["state"]["theme"]
    with open(configuration_path) as input_handle:
        dunst_configuration = configparser.ConfigParser(interpolation=None)
        dunst_configuration.read_file(input_handle)

    dunst_configuration["global"]["foreground"] = f'"{configuration["palette"][theme]["foreground"]}"'
    dunst_configuration["global"]["background"] = f'"{configuration["palette"][theme]["background"]}"'
    dunst_configuration["global"]["separator_color"] = f'"{configuration["palette"][theme]["background"]}"'
    dunst_font_size = round(configuration["font"]["size"] * 0.714)
    dunst_configuration["global"]["font"] = (
        f'"{configuration["font"]["family"]} {dunst_font_size}"'
    )

    # Only the offset needs a monitor to scale against, so a machine with none still gets
    # a themed dunst rather than no dunst patch at all.
    average_scaling_factor = monitor_average(configuration, "scaling_factor")
    if average_scaling_factor is not None:
        offset = round(configuration["font"]["size"] * average_scaling_factor * 3)
        dunst_configuration["global"]["offset"] = f"0x{offset}"

    dunst_configuration["urgency_normal"]["foreground"] = f'"{configuration["palette"][theme]["foreground"]}"'
    dunst_configuration["urgency_normal"]["format"] = (
        f"\" <span foreground='{configuration["palette"][theme]["notification"]}'>%s</span>\\n  %b\""
    )

    dunst_configuration["urgency_critical"]["foreground"] = f'"{configuration["palette"][theme]["foreground"]}"'
    dunst_configuration["urgency_critical"]["format"] = (
        f"\" <span foreground='{configuration["palette"][theme]["warning"]}'>%s</span>\\n  %b\""
    )

    dunst_configuration["urgency_low"]["foreground"] = f'"{configuration["palette"][theme]["foreground"]}"'
    dunst_configuration["urgency_low"]["format"] = (
        f"\" <span foreground='{configuration["palette"][theme]["neutral"]}'>%s</span>\\n  %b\""
    )

    with open(configuration_path, "w") as output_handle:
        dunst_configuration.write(output_handle)
    logger.info("Patched dunst configuration ...")


if __name__ == "__main__":
    with open(os.path.expanduser("~/.config/config.json")) as input_handle:
        patch_dunst(json.load(input_handle))
