"""Patch rofi: the launcher's theme colours, font, width and vertical offset.

Writes ``~/.config/rofi/theme_config.rasi``, which the checked-in rofi theme
``@import``s. Width and offset are scaled to the average monitor, so a machine with
no detected geometry is left alone rather than given a launcher sized for nothing.
"""

import json
import os
import re
from typing import Any

# Resolves whether this runs as ``helper.patch_rofi`` or as a script; see helper/README.md.
try:
    from helper import symbols
    from helper.utils import logger, monitor_average, template_path
except ImportError:
    import symbols
    from utils import logger, monitor_average, template_path


def patch_rofi_configuration(configuration: dict[str, Any]) -> None:
    """Write ``config.rasi``, whose two mode prompts are the theme's.

    Line-based rather than parsed: ``.rasi`` has no stdlib parser, and the rest of the file
    is hand-written settings this has no opinion about -- the same reason ``patch_tmux``
    rewrites its four lines and copies the others through.
    """
    glyphs, _ = symbols.resolve(configuration)
    prompts = {
        "display-run": f"{glyphs['rofi.run']} ",
        "display-window": f" {glyphs['rofi.window']} ",
        "display-power": f" {glyphs['rofi.power']} ",
    }
    with open(template_path("rofi", "config.rasi.template")) as input_handle:
        lines = input_handle.readlines()

    with open(os.path.expanduser("~/.config/rofi/config.rasi"), "w") as output_handle:
        for line in lines:
            patched = line
            for option, value in prompts.items():
                patched = re.sub(rf'({option}:\s*)"[^"]*"', rf'\g<1>"{value}"', patched)
            output_handle.write(patched)


def patch_rofi(configuration: dict[str, Any]) -> None:
    theme = configuration["state"]["theme"]

    # Written first, and unconditionally: the two mode prompts are symbols, which need no
    # monitor to scale against. config.rasi is generated rather than tracked, and it is what
    # carries `@theme "theme"` -- so a machine that fell through the guard below without
    # writing it would leave rofi with no configuration at all, unthemed rather than
    # unscaled. patch_dunst splits on the same line, for the same reason.
    patch_rofi_configuration(configuration)

    average_width = monitor_average(configuration, "width")
    average_scaling_factor = monitor_average(configuration, "scaling_factor")
    if average_width is None or average_scaling_factor is None:
        logger.info("No monitor geometry available; leaving the rofi theme colours alone.")
        return

    patched_configuration = {
        "FONT": f'"{configuration["font"]["family"]} {round(configuration["font"]["size"] * 1.214)}"',
        "COLOR0": f"{configuration['palette'][theme]['background']}",
        "COLOR1": f"{configuration['palette'][theme]['neutral']}",
        "COLOR2": f"{configuration['palette'][theme]['failure']}",
        "COLOR3": f"{configuration['palette'][theme]['foreground']}",
        "COLOR4": f"{configuration['palette'][theme]['highlight']}",
        # The matched part of an entry. Style and colour travel as one value because rofi
        # will not parse a style followed by a reference (`bold @COLOR3`) in the theme.
        "MATCH": f"bold {configuration['palette'][theme]['foreground']}",
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
