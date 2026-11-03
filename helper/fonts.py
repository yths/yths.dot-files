"""The theme's font: which Arch package provides it, and whether this machine has it.

A bundle names the family the whole desktop derives from in its ``config.json#font``. It does
not say which package installs that family, because bundles are written by ``yths.themes``,
which knows fonts and not Arch -- so that mapping lives here, in ``FONT_PACKAGES``, the way
``list_dependencies.ARCH_PACKAGES`` maps Python imports. A bundle that does know may carry
``font.package`` and is believed over the table.

``resolve`` is what ``install.py`` writes into ``~/.config/config.json``: the bundle's font
when fontconfig can see the family, otherwise ``setup.toml``'s fallback at the bundle's size.
Falling back rather than failing, because a theme whose font did not install is still a theme
-- the palette, the wallpapers and the vocabulary are all there -- and the fallback is a Nerd
Font too, so the bar's glyphs survive the substitution.

A bundle that names the plain family -- ``Atkinson Hyperlegible Mono`` rather than
``AtkynsonMono NF`` -- gets the Nerd Font build where one exists (``NERD_FONT_BUILDS``).
The bar needs the private-use glyphs, and the Nerd Font build is the same face with them
added, so it is what the bundle meant; ``yths.themes`` has written both spellings.

Run as a script by ``bootstrap.sh``::

    python helper/fonts.py --package     # the configured theme's font package, if known

It prints nothing when ``setup.toml`` leaves the theme to the prompt, or when the family is
one this table has not heard of; either way the fallback is already installed.
"""

import argparse
import json
import os
import subprocess
import sys
from typing import Any

try:
    from helper.utils import REPOSITORY_ROOT, logger, read_setup
except ImportError:
    from utils import REPOSITORY_ROOT, logger, read_setup

#: The Nerd Font build of a plain family, under the short name fontconfig reports for it.
#: A bundle naming the left-hand side is installed with the right-hand side.
NERD_FONT_BUILDS = {
    "Iosevka": "Iosevka NF",
    "Iosevka Nerd Font": "Iosevka NF",
    "Atkinson Hyperlegible Mono": "AtkynsonMono NF",
    "AtkynsonMono Nerd Font": "AtkynsonMono NF",
}

#: Which Arch package provides a family a bundle may name, after ``NERD_FONT_BUILDS`` has
#: had its say. Extend this when a theme arrives in a font not listed; until then
#: ``bootstrap.sh`` installs only the fallback for it.
FONT_PACKAGES = {
    "Iosevka NF": "ttf-iosevka-nerd",
    "AtkynsonMono NF": "otf-atkinsonhyperlegiblemono-nerd",
}

#: What a bundle that names no size gets. Bundles always carry one; this is for the fallback
#: taking over from a bundle with no ``font`` at all.
DEFAULT_SIZE = 14


def preferred_family(family: str) -> str:
    """The family to install for the one a bundle names: its Nerd Font build, if there is one."""
    return NERD_FONT_BUILDS.get(family, family)


def package_for(font: dict[str, Any] | None) -> str | None:
    """The Arch package providing ``font``'s family: its own claim first, then the table."""
    if not font:
        return None
    return font.get("package") or FONT_PACKAGES.get(preferred_family(font.get("family", "")))


def installed_families() -> set[str] | None:
    """Every family name fontconfig reports, or ``None`` when it cannot be asked.

    ``fc-list : family`` prints one line per face, each a comma-separated list of the names
    the face answers to -- ``Iosevka Nerd Font,Iosevka NF`` -- so both are collected.
    """
    try:
        result = subprocess.run(
            ["fc-list", ":", "family"], capture_output=True, text=True, check=False
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return {
        name.strip()
        for line in result.stdout.splitlines()
        for name in line.split(",")
        if name.strip()
    }


def resolve(
    bundle_font: dict[str, Any] | None,
    setup: dict[str, Any],
    families: set[str] | None = None,
) -> dict[str, Any]:
    """The font to install for a bundle: its own if this machine has it, else the fallback.

    ``families`` is what fontconfig reports; ``None`` asks it. A machine with no ``fc-list``
    cannot be checked and gets the bundle's font as declared -- fontconfig itself substitutes
    at render time, which is the same outcome one step later and without a warning.
    """
    bundle_font = bundle_font or {}
    size = bundle_font.get("size", DEFAULT_SIZE)
    family = preferred_family(bundle_font.get("family", ""))
    fallback = setup["desktop"]["fallback_font_family"]

    if family:
        if families is None:
            families = installed_families()
        if families is None or family in families:
            return {"family": family, "size": size}
        package = package_for(bundle_font)
        hint = f" (`yay -S {package}`)" if package else ""
        logger.warning(
            f"The theme's font {family!r} is not installed{hint}; using {fallback!r} instead. "
            "Install it and run `python install.py --migrate` to switch."
        )
    return {"family": fallback, "size": size}


def configured_theme_font() -> dict[str, Any] | None:
    """The ``font`` of the bundle ``setup.toml`` selects, or ``None`` if it selects none."""
    theme = read_setup()["desktop"]["theme"]
    if not theme:
        return None
    root = os.path.expanduser(os.environ.get("DOTFILES_REPOSITORY_PATH", REPOSITORY_ROOT))
    manifest = os.path.join(root, "assets", theme, "config.json")
    if not os.path.isfile(manifest):
        return None
    with open(manifest, encoding="utf-8") as handle:
        return json.load(handle).get("font")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--package", action="store_true",
        help="print the Arch package providing the configured theme's font, if known",
    )
    arguments = parser.parse_args()
    if arguments.package:
        package = package_for(configured_theme_font())
        if package:
            print(package)
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
