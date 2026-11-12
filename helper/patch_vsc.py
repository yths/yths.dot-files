"""Patch the user's Visual Studio Code ``settings.json``.

Maps the active palette's semantic tokens to VSCode editor colors and token colors using
perceptual nearest-color matching (``colour`` library, sRGB → XYZ → ΔE). Handles both
light and dark variants from the active theme bundle.
"""

import argparse
import json
import os
import pickle
import re
import sys

try:
    from helper import color_match
    from helper.utils import logger, template_path
except ImportError:
    # Reached when this file runs as a script: sys.path[0] is then helper/, not the
    # repository root, so the package-qualified form cannot resolve. Both branches land on
    # the same loguru-or-stdlib fallback defined once in helper/utils.py.
    import color_match
    from utils import logger, template_path

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

#: Where VSCode reads the settings from. ``install.py`` symlinks the patcher's output here,
#: so this is a fact about the install rather than a path anything below opens.
USER_SETTINGS_PATH = os.path.join("~", ".config", "Code", "User", "settings.json")


#: The built-in theme each template was exported from, by its file in VSCode's
#: ``theme-defaults`` extension. Pinned in the settings rather than left to VSCode's default:
#: every colour the template does not name falls through to whatever theme is active, and
#: VSCode 1.140 changed the default from Dark Modern to Dark 2026 -- whose grey workbench
#: borders appeared around a palette that never asked for them.
BASE_THEME_FILES = {"dark": "dark_modern.json", "light": "light_modern.json"}

#: Where the packaged VSCode builds keep ``theme-defaults``. The first that exists wins.
THEME_DEFAULTS_DIRECTORIES = (
    "/usr/share/code/resources/app/extensions/theme-defaults",
    "/opt/visual-studio-code/resources/app/extensions/theme-defaults",
    "/usr/lib/code/extensions/theme-defaults",
)


def _read_jsonc(path: str) -> dict:
    """A VSCode theme file: JSON with ``//`` comments and trailing commas allowed."""
    with open(path) as handle:
        raw = handle.read()
    raw = re.sub(r"^\s*//.*$", "", raw, flags=re.M)
    return json.loads(re.sub(r",(\s*[}\]])", r"\1", raw))


def base_theme(
    mode: str, directories: tuple[str, ...] = THEME_DEFAULTS_DIRECTORIES
) -> tuple[str, dict[str, str]] | None:
    """The installed base theme for ``mode``: its id, and every colour it sets.

    Colours come with the theme's ``include`` chain resolved, the way VSCode resolves it, so
    the result is what VSCode would fill an unnamed key with. ``None`` when no VSCode
    installation is found, or it no longer ships the file.
    """
    for directory in directories:
        manifest = os.path.join(directory, "package.json")
        if not os.path.exists(manifest):
            continue
        with open(manifest) as handle:
            declared = json.load(handle)["contributes"]["themes"]
        for entry in declared:
            if os.path.basename(entry["path"]) != BASE_THEME_FILES[mode]:
                continue
            # Theme first, then what it includes, then what that includes; applied in
            # reverse, so the innermost is the base and the outermost overrides it.
            themes = []
            path = os.path.join(directory, "themes", BASE_THEME_FILES[mode])
            while path is not None:
                themes.append(_read_jsonc(path))
                include = themes[-1].get("include")
                path = os.path.join(os.path.dirname(path), include) if include else None
            colors: dict[str, str] = {}
            for theme in reversed(themes):
                colors.update(theme.get("colors", {}))
            return entry["id"], colors
    return None


def with_base_colors(defaults: dict[str, dict], bases: dict[str, dict | None]) -> dict[str, dict]:
    """Each template with its base theme's colours underneath, the template winning.

    A key the template does not name is one VSCode fills from the active theme, unmapped --
    so it is mapped here instead, from the theme that would have filled it.
    """
    layered = {}
    for mode, theme in defaults.items():
        base = bases.get(mode)
        layered[mode] = {
            **theme, "colors": {**(base or {}), **theme.get("colors", {})}
        }
    return layered


def build_palette_map(palette: dict) -> dict[str, list]:
    """The palette's CAM16-UCS coordinates. Kept as a name here because
    ``helper/list_palette.py`` and the tests reach for it through this module."""
    return color_match.build_palette_map(palette)


def load_default_themes(input_path: str | None) -> dict[str, dict]:
    """Read the stock VSCode themes this patcher recolours, one per mode.

    These are what *Developer: Generate Color Theme From Current Settings* writes, so
    refreshing them is a VSCode command rather than an edit here -- which is the point of
    reading a theme file rather than a hand-maintained list of keys.
    """
    directory = input_path if input_path is not None else os.getcwd()
    themes = {}
    for mode in MODES:
        with open(os.path.join(directory, f"template-{mode}-color-theme.json")) as handle:
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


def apply_to_user_settings(theme: dict, base_theme_id: str | None = None) -> bool:
    """Write the recoloured theme into VSCode's settings. Returns whether it was written.

    Reads ``settings.json.template`` and writes the result beside it, the way every other
    patcher that has hand-written settings alongside palette-derived ones works. It used to
    read and rewrite its own output, which made one file both the source of six scalars and
    the home of 487 generated colours -- on a tracked path, so every theme switch dirtied
    76 KB of it, and a colour fixed by hand there was a fix the generator never learned.

    ``install.py`` symlinks the output to ``~/.config/Code/User/settings.json``, so writing
    here is what VSCode reads. A machine without VSCode simply has a file nothing opens.
    """
    template = template_path("vscode", "settings.json.template")
    if not os.path.exists(template):
        logger.info("No settings.json.template; leaving Visual Studio Code alone.")
        return False

    logger.info("Patching Visual Studio Code settings...")
    with open(template) as handle:
        user_settings = json.load(handle)
    user_settings["editor.tokenColorCustomizations"] = {
        "textMateRules": theme.get("tokenColors", [])
    }
    user_settings["workbench.colorCustomizations"] = theme.get("colors", {})
    if base_theme_id is not None:
        user_settings["workbench.colorTheme"] = base_theme_id
    with open(template_path("vscode", "settings.json"), "w") as handle:
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
    bases = {mode: base_theme(mode) for mode in MODES}
    if bases[arguments.mode] is None:
        logger.warning(
            "No VSCode theme-defaults found; colours the template does not name will come "
            "from whatever theme VSCode has active."
        )
    themes = build_themes(
        with_base_colors(
            load_default_themes(arguments.input_path),
            {mode: base[1] if base else None for mode, base in bases.items()},
        ),
        palette_map, arguments.method, arguments.name,
    )

    logger.info(f"Patching Visual Studio Code settings to {arguments.mode} theme...")
    base = bases[arguments.mode]
    apply_to_user_settings(themes[arguments.mode], base[0] if base else None)

    if arguments.output_path is not None:
        write_themes(themes, arguments.output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
