"""Patch the user's Visual Studio Code ``settings.json``.

Maps the active palette's semantic tokens to VSCode editor colors and token colors using
perceptual nearest-color matching (``colour`` library, sRGB → XYZ → ΔE). Handles both
light and dark variants from the active theme bundle.
"""

import argparse
import json
import os
import pickle
import sys

try:
    from helper import color_match
    from helper.utils import logger
except ImportError:
    # Reached when this file runs as a script: sys.path[0] is then helper/, not the
    # repository root, so the package-qualified form cannot resolve. Both branches land on
    # the same loguru-or-stdlib fallback defined once in helper/utils.py.
    import color_match
    from utils import logger

def dict_replace_value(d: dict, colors: list, lookup_colors: list | None = None) -> dict:
    if lookup_colors is None:
        lookup_colors = colors
    replaced = {}
    for key, value in d.items():
        if isinstance(value, dict):
            entry = dict_replace_value(value, colors, lookup_colors)
        elif isinstance(value, list):
            entry = list_replace_value(value, colors, lookup_colors, parent_key=key)
        elif isinstance(value, str) and value.startswith("#"):
            entry = color_match.replace(
                value,
                color_match.filter_candidates(key, colors),
                None if lookup_colors is None
                else color_match.filter_candidates(key, lookup_colors),
            )
        else:
            entry = value
        replaced[key] = entry
    return replaced


def list_replace_value(
    values: list, colors: list, lookup_colors: list | None = None,
    parent_key: str | None = None,
) -> list:
    if lookup_colors is None:
        lookup_colors = colors
    replaced = []
    for value in values:
        if isinstance(value, list):
            entry = list_replace_value(value, colors, lookup_colors, parent_key=parent_key)
        elif isinstance(value, dict):
            entry = dict_replace_value(value, colors, lookup_colors)
        elif isinstance(value, str) and value.startswith("#"):
            entry = color_match.replace(
                value,
                color_match.filter_candidates(parent_key, colors),
                None if lookup_colors is None
                else color_match.filter_candidates(parent_key, lookup_colors),
            )
        else:
            entry = value
        replaced.append(entry)
    return replaced


#: The two variants a bundle carries, and the order they are built in.
MODES = ("dark", "light")

#: Where VSCode keeps the settings this patcher writes into.
USER_SETTINGS_PATH = os.path.join("~", ".config", "Code", "User", "settings.json")


def build_palette_map(palette: dict) -> dict[str, list]:
    """The palette's CAM16-UCS coordinates. Kept as a name here because
    ``helper/list_palette.py`` and the tests reach for it through this module."""
    return color_match.build_palette_map(palette)


def load_default_themes(input_path: str | None) -> dict[str, dict]:
    """Read the stock VSCode themes this patcher recolours, one per mode."""
    directory = input_path if input_path is not None else os.getcwd()
    themes = {}
    for mode in MODES:
        with open(os.path.join(directory, f"vsc_default_{mode}.json")) as handle:
            themes[mode] = json.load(handle)
    return themes


def build_themes(
    defaults: dict[str, dict], palette_map: dict[str, list], method: str,
    name: str = "dot files",
) -> dict[str, dict]:
    """Recolour both default themes with the active palette.

    ``nearest_neighbor``, the default, maps each mode against its own palette. ``reference``
    differs only for the light theme: colours are still matched against the light palette,
    but the value written is the *dark* palette's entry for whichever token matched.
    """
    themes = {}
    for mode in MODES:
        theme = defaults[mode].copy()
        theme["name"] = f"{name} ({mode})"
        lookup = palette_map["dark"] if method == "reference" and mode == "light" else None
        themes[mode] = dict_replace_value(theme, palette_map[mode], lookup)
    return themes


def apply_to_user_settings(theme: dict) -> bool:
    """Write the recoloured theme into VSCode's settings. Returns whether it was written.

    VSCode may simply not be installed, which is not a failure: the patcher runs on every
    theme switch and must not complain on a machine that has no VSCode.
    """
    settings_path = os.path.expanduser(USER_SETTINGS_PATH)
    if not os.path.exists(settings_path):
        return False
    logger.info("Patching Visual Studio Code settings...")
    with open(settings_path) as handle:
        user_settings = json.load(handle)
    user_settings["editor.tokenColorCustomizations"] = {
        "textMateRules": theme.get("tokenColors", [])
    }
    user_settings["workbench.colorCustomizations"] = theme.get("colors", {})
    with open(settings_path, "w") as handle:
        json.dump(user_settings, handle, indent=4)
    logger.info("Patched Visual Studio Code settings.")
    return True


def write_themes(themes: dict[str, dict], output_path: str) -> None:
    """Save both recoloured themes as standalone files, for inspection or reuse."""
    directory = os.path.expanduser(output_path)
    logger.info(f"Saving patched Visual Studio Code settings to {directory}...")
    for mode in MODES:
        with open(os.path.join(directory, f"vsc_patched_{mode}.json"), "w") as handle:
            json.dump(themes[mode], handle, indent=4)


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--theme-pickle-path",
        type=str,
        default=os.path.join("~", ".config", "palette.pkl"),
        help="Path to the theme pickle file.",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=list(MODES),
        default="dark",
        help="Color mode to patch.",
    )
    parser.add_argument(
        "--method",
        type=str,
        choices=["nearest_neighbor", "reference"],
        default="nearest_neighbor",
        help=(
            "Method by which the colors of the theme are mapped to the "
            "Visual Studio Code configuration."
        ),
    )
    parser.add_argument(
        "--output-path",
        type=str,
        default=None,
        help=(
            "Path to save the patched Visual Studio Code settings. "
            "If not provided, will not output."
        ),
    )
    parser.add_argument(
        "--name",
        type=str,
        default="dot files",
        help="Name recorded inside the generated themes (default: 'dot files').",
    )
    parser.add_argument(
        "--input-path",
        type=str,
        default=None,
        help=(
            "Path to load the Visual Studio Code settings from. "
            "If not provided, will use the current working directory."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(argv)

    with open(os.path.expanduser(arguments.theme_pickle_path), "rb") as handle:
        palette = pickle.load(handle)

    palette_map = build_palette_map(palette)
    themes = build_themes(
        load_default_themes(arguments.input_path), palette_map, arguments.method,
        arguments.name,
    )

    logger.info(f"Patching Visual Studio Code settings to {arguments.mode} theme...")
    apply_to_user_settings(themes[arguments.mode])

    if arguments.output_path is not None:
        write_themes(themes, arguments.output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
