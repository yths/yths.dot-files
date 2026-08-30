"""Patch xorg: the X server's DPI, averaged across the detected monitors.

Writes ``~/.Xresources``. The DPI is resolved before the file is opened, because
opening it first truncates it -- a failure while computing then left it empty.
"""

import json
import os
from typing import Any

# Resolves whether this runs as ``helper.patch_xorg`` or as a script; see helper/README.md.
try:
    from helper.utils import logger, monitor_average
except ImportError:
    from utils import logger, monitor_average


def patch_xorg(configuration: dict[str, Any]) -> None:
    # The DPI is resolved before the file is opened. Opening first truncated ~/.Xresources,
    # so any failure while computing left it empty -- and the exception then aborted
    # patch_all, leaving the remaining apps on the previous palette.
    average_dpi = monitor_average(configuration, "diagonal_dpi")
    if average_dpi is None:
        logger.info("No monitor geometry available; leaving ~/.Xresources alone.")
        return
    with open(os.path.expanduser("~/.Xresources"), "w") as output_handle:
        output_handle.write(f"Xft.dpi: {round(average_dpi)}\n")
    logger.info(f"Patched .Xresources with average DPI: {round(average_dpi)}.")


if __name__ == "__main__":
    with open(os.path.expanduser("~/.config/config.json")) as input_handle:
        patch_xorg(json.load(input_handle))
