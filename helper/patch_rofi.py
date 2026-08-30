"""Patch rofi: the launcher's theme colours, font, width and vertical offset.

Writes ``~/.config/rofi/theme_config.rasi``, which the checked-in rofi theme
``@import``s. Width and offset are scaled to the average monitor, so a machine with
no detected geometry is left alone rather than given a launcher sized for nothing.
"""

import json
import os
from typing import Any

# Resolves whether this runs as ``helper.patch_rofi`` or as a script; see helper/README.md.
try:
    from helper.utils import logger, monitor_average
except ImportError:
    from utils import logger, monitor_average


def patch_rofi(configuration: dict[str, Any]) -> None:
    theme = configuration["state"]["theme"]

    average_width = monitor_average(configuration, "width")
    average_scaling_factor = monitor_average(configuration, "scaling_factor")
    if average_width is None or average_scaling_factor is None:
        logger.info("No monitor geometry available; leaving the rofi theme alone.")
        return

    patched_configuration = {
        "FONT": f'"{configuration["font"]["family"]} {round(configuration["font"]["size"] * 1.214)}"',
        "COLOR0": f"{configuration['palette'][theme]['background']}",
        "COLOR1": f"{configuration['palette'][theme]['neutral']}",
        "COLOR2": f"{configuration['palette'][theme]['failure']}",
        "COLOR3": f"{configuration['palette'][theme]['foreground']}",
        "COLOR4": f"{configuration['palette'][theme]['highlight']}",
        "WIDTH": f"{round(average_width)}px",
        "YOFFSET": f"{round(configuration['font']['size'] * average_scaling_factor * 2.75)}px",
    }
    with open(
        os.path.expanduser("~/.config/rofi/theme_config.rasi"), "w"
    ) as output_handle:
        output_handle.write("* {\n")
        for key, value in patched_configuration.items():
            output_handle.write(f"    {key}: {value};\n")
        output_handle.write("}\n")
    logger.info("Patched rofi configuration ...")


if __name__ == "__main__":
    with open(os.path.expanduser("~/.config/config.json")) as input_handle:
        patch_rofi(json.load(input_handle))
