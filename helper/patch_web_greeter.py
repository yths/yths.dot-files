"""Patch and install the web-greeter themes LightDM renders at the login screen.

Two stages, for the same reason plymouth has two: the themes are authored here but read from
``/usr/share/web-greeter/themes/``, which is root-owned.

**Patch** generates each theme's ``theme.css`` from the active palette and copies the shared
assets in, so a deployed theme is self-contained. It runs on every theme switch, needs no
privileges, and writes only inside this repository.

**Install** copies a theme into the system directory and, with ``--activate``, points
LightDM at it. Both need root::

    python helper/patch_web_greeter.py --install --activate

Activation is a separate flag because it changes what you see at the next login, and the
theme already deployed may not be one of these.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

try:
    from helper.utils import logger, root_prefix
except ImportError:
    # Reached when this file runs as a script: sys.path[0] is then helper/, not the
    # repository root, so the package-qualified form cannot resolve. Both branches land on
    # the same loguru-or-stdlib fallback defined once in helper/utils.py.
    from utils import logger, root_prefix

#: Where web-greeter looks for themes. Root-owned, which is why installing is its own stage.
SYSTEM_THEME_ROOT = "/usr/share/web-greeter/themes"

#: LightDM's greeter configuration, which names the theme it renders.
GREETER_CONFIG = "/etc/lightdm/web-greeter.yml"

#: The theme installed when none is named. The repository ships one.
DEFAULT_THEME = "standard"

#: This file's repository, resolved through any symlink used to invoke it.
_REPOSITORY_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

#: Theme sources, one directory per theme; a leading underscore marks shared assets.
THEME_SOURCE_ROOT = os.path.join(_REPOSITORY_ROOT, "configuration", "web-greeter", "themes")


def patch_web_greeter(configuration: dict[str, Any]) -> None:
    theme_state = configuration["state"]["theme"]
    palette = configuration["palette"][theme_state]
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    themes_dir = os.path.join(repo, "configuration", "web-greeter", "themes")
    shared_src = os.path.join(themes_dir, "_shared")

    for theme_name in sorted(os.listdir(themes_dir)):
        if theme_name.startswith("_"):
            continue
        theme_dir = os.path.join(themes_dir, theme_name)
        theme_json_path = os.path.join(theme_dir, "theme.json")
        if not os.path.isfile(theme_json_path):
            continue
        with open(theme_json_path) as fh:
            tj = json.load(fh)

        vars_ = {f"--{role}": palette[key] for role, key in tj["role_map"].items()}
        font = {**configuration["font"], **tj.get("font_overrides", {})}
        vars_["--font-family"] = f'"{font["family"]}"'
        vars_["--font-size"] = f'{font["size"]}px'

        wp_path = os.path.expanduser(configuration["wallpapers"][tj["wallpaper_key"]])
        ext = os.path.splitext(wp_path)[1] or ".png"
        link = os.path.join(theme_dir, f"wallpaper{ext}")
        if os.path.lexists(link):
            os.unlink(link)
        os.symlink(wp_path, link)
        vars_["--wallpaper-url"] = f'url("{os.path.basename(link)}")'

        with open(os.path.join(theme_dir, "theme.css"), "w") as fh:
            fh.write(":root {\n")
            for k, v in vars_.items():
                fh.write(f"    {k}: {v};\n")
            fh.write("}\n")

        shared_dst = os.path.join(theme_dir, "_shared")
        if os.path.lexists(shared_dst):
            if os.path.islink(shared_dst) or os.path.isfile(shared_dst):
                os.unlink(shared_dst)
            else:
                shutil.rmtree(shared_dst)
        shutil.copytree(shared_src, shared_dst)

    logger.info("Patched web-greeter configuration ...")


def available_themes() -> list[str]:
    """Every theme this repository ships, in name order."""
    return sorted(
        entry
        for entry in os.listdir(THEME_SOURCE_ROOT)
        if not entry.startswith("_")
        and os.path.isfile(os.path.join(THEME_SOURCE_ROOT, entry, "theme.json"))
    )


def activate(name: str, prefix: list[str]) -> bool:
    """Point LightDM at ``name``, leaving the rest of its configuration alone.

    The file is edited rather than rewritten: it is LightDM's, not ours, and carries settings
    -- the screensaver timeout, secure mode, the image paths -- that nothing here should have
    an opinion about. Only the value on the ``theme:`` line changes.
    """
    try:
        with open(GREETER_CONFIG) as handle:
            original = handle.read()
    except OSError as error:
        logger.warning(f"Cannot read {GREETER_CONFIG}: {error}")
        return False

    edited, replacements = re.subn(
        r"(?m)^(\s*theme:\s*).*$", lambda match: f"{match.group(1)}{name}", original, count=1
    )
    if replacements == 0:
        logger.warning(f"No `theme:` line in {GREETER_CONFIG}; left it alone.")
        return False
    if edited == original:
        logger.info(f"LightDM already renders {name}.")
        return True

    descriptor, staged = tempfile.mkstemp(suffix=".yml")
    with os.fdopen(descriptor, "w") as handle:
        handle.write(edited)
    try:
        result = subprocess.run(
            [*prefix, "cp", staged, GREETER_CONFIG], capture_output=True, text=True, check=False
        )
    finally:
        os.unlink(staged)
    if result.returncode != 0:
        logger.warning(f"Could not update {GREETER_CONFIG}: {result.stderr.strip()}")
        return False
    logger.info(f"LightDM will render {name} at the next login.")
    return True


def install_theme(name: str, *, prompt: bool = False, make_active: bool = False) -> bool:
    """Copy one patched theme into the system directory. Returns whether it landed."""
    source = os.path.join(THEME_SOURCE_ROOT, name)
    if not os.path.isdir(source):
        logger.warning(f"No theme named {name!r}; this repository ships {available_themes()}.")
        return False

    destination = os.path.join(SYSTEM_THEME_ROOT, name)
    prefix = root_prefix(prompt=prompt)
    if prefix is None:
        logger.info(
            f"Patched {name}, but writing {destination} needs root. Run "
            "`python helper/patch_web_greeter.py --install` to be prompted for it."
        )
        return False

    # -L dereferences the wallpaper symlink the patch stage leaves behind: the greeter runs
    # before login and cannot read an image out of a home directory.
    result = subprocess.run(
        [*prefix, "cp", "-RLT", source, destination], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        logger.warning(f"Installing {name} failed: {result.stderr.strip()}")
        return False
    logger.info(f"Installed the {name} theme to {destination}.")

    if make_active:
        return activate(name, prefix)
    logger.info(f"Pass --activate to have LightDM render it; {GREETER_CONFIG} is unchanged.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--configuration", default="~/.config/config.json", dest="configuration_file_path",
        help="path to the active configuration (default: ~/.config/config.json)",
    )
    parser.add_argument(
        "--theme", default=DEFAULT_THEME,
        help=f"which theme to install (default: {DEFAULT_THEME})",
    )
    parser.add_argument(
        "--install", action="store_true",
        help=f"copy the patched theme into {SYSTEM_THEME_ROOT}, prompting for root if needed",
    )
    parser.add_argument(
        "--activate", action="store_true",
        help="with --install, also point LightDM at it",
    )
    arguments = parser.parse_args()

    with open(os.path.expanduser(arguments.configuration_file_path)) as handle:
        configuration = json.load(handle)
    patch_web_greeter(configuration)

    if not arguments.install:
        logger.info("Patched only; pass --install to copy into place.")
        return 0
    return 0 if install_theme(
        arguments.theme, prompt=True, make_active=arguments.activate
    ) else 1


if __name__ == "__main__":
    sys.exit(main())
