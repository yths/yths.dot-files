"""Patch starship: the prompt's named palette entries.

Loads ``~/.config/starship.toml``, replaces the five colours under
``palettes.theme``, and writes it back -- preserving every other prompt setting.
"""

import json
import os
from typing import Any

import toml

# Resolves whether this runs as ``helper.patch_starship`` or as a script; see helper/README.md.
try:
    from helper.utils import logger
except ImportError:
    from utils import logger


def patch_starship(configuration: dict[str, Any]) -> None:
    configuration_path = os.path.expanduser("~/.config/starship.toml")

    theme = configuration["state"]["theme"]
    with open(configuration_path) as input_handle:
        starship_configuration = toml.load(input_handle)

    starship_configuration["palettes"]["theme"]["color0"] = configuration["palette"][theme]["foreground"]
    starship_configuration["palettes"]["theme"]["color1"] = configuration["palette"][theme]["foreground_variant"]
    starship_configuration["palettes"]["theme"]["color2"] = configuration["palette"][theme]["success"]
    starship_configuration["palettes"]["theme"]["color3"] = configuration["palette"][theme]["failure"]
    starship_configuration["palettes"]["theme"]["color4"] = configuration["palette"][theme]["highlight"]

    with open(configuration_path, "w") as output_handle:
        toml.dump(starship_configuration, output_handle)
    logger.info("Patched starship configuration ...")


if __name__ == "__main__":
    with open(os.path.expanduser("~/.config/config.json")) as input_handle:
        patch_starship(json.load(input_handle))
