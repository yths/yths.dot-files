"""Patch rofi: the launcher's theme colours, font and mode prompts.

Writes ``~/.config/rofi/theme_config.rasi``, which the checked-in rofi theme ``@import``s,
and ``~/.config/rofi/config.rasi``. Geometry is not written here: the qtile key bindings
pass each launch the focused screen's exact width and offset
(``configuration/qtile/shared/launcher.py``). This used to write an average across
monitors as well, which was right for none of them when they differed, and kept rofi
unthemed on a machine with no monitors recorded.
"""

import json
import os
import re
from typing import Any

# Resolves whether this runs as ``helper.patch_rofi`` or as a script; see helper/README.md.
try:
    from helper import symbols
    from helper.utils import logger, template_path
except ImportError:
    import symbols
    from utils import logger, template_path


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

    # config.rasi is generated rather than tracked, and it is what carries `@theme "theme"`:
    # without it rofi loads no theme at all.
    patch_rofi_configuration(configuration)

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
