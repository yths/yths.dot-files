"""Patch tmux: the four palette colours its status line reads.

Rewrites the ``color*`` lines at the top of ``~/.config/tmux/tmux.conf`` and leaves
the rest of the file untouched, so hand-written bindings survive a theme switch.
"""

import json
import os
from typing import Any

# Resolves whether this runs as ``helper.patch_tmux`` or as a script; see helper/README.md.
try:
    from helper.utils import logger
except ImportError:
    from utils import logger


def patch_tmux(configuration: dict[str, Any]) -> None:
    configuration_path = os.path.expanduser("~/.config/tmux/tmux.conf")

    theme = configuration["state"]["theme"]
    output = []
    with open(configuration_path) as input_handle:
        for line in input_handle:
            if line.startswith("color"):
                continue
            output.append(line)

    patched_configuration = {
        "color0": configuration["palette"][theme]["background"],
        "color1": configuration["palette"][theme]["neutral"],
        "color2": configuration["palette"][theme]["highlight"],
        "color3": configuration["palette"][theme]["foreground"],
    }

    with open(configuration_path, "w") as output_handle:
        for key, value in patched_configuration.items():
            output_handle.write(f"{key}={value}\n")
        for line in output:
            output_handle.write(line)
    logger.info("Patched tmux configuration ...")


if __name__ == "__main__":
    with open(os.path.expanduser("~/.config/config.json")) as input_handle:
        patch_tmux(json.load(input_handle))
