"""Install the dot files.

Discovers theme bundles under ``assets/``, picks the one setup.toml names, writes its
``config.json`` (merged with detected monitor geometry, font, and the unpickled palette) to
``~/.config/config.json``, and symlinks each per-app configuration tree from
``configuration/`` into ``~/.config/``. Nothing is copied, so the installed configuration is
this repository. See docs/architecture.md for the full theme-bundle lifecycle.
"""

import argparse
import json
import os
import pickle
import platform
import subprocess
import sys
import time
from typing import Any

try:
    import loguru

    logger = loguru.logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

import helper.apply_icc
import helper.patch_configurations
import helper.screen_configuration
from helper.utils import (
    install_credentials,
    install_file,
    install_folder,
    read_setup,
)

#: The repository this installer is part of, resolved through any symlink. Deliberately not
#: DOTFILES_REPOSITORY_PATH: that variable redirects where configuration is *read from*, and
#: following it here could arm the hooks of a clone other than the one being run.
_REPOSITORY_ROOT = os.path.dirname(os.path.realpath(__file__))


def enable_git_hooks() -> None:
    """Arm the pre-commit gate in the repository this installer came from.

    Git will not let a repository configure its own hooks -- ``core.hooksPath`` is local
    configuration, deliberately outside version control, so that cloning can never run code
    the author chose. Every fresh clone therefore starts with the gate off and nothing says
    so. Installing is the one step everyone takes, so the gate is armed from here.

    Never fatal, and never interactive: installing the desktop does not depend on being able
    to commit to the repository it came from, and an installer that stops for a linting gate
    would be worse than one that ships without it.
    """
    enable_script = os.path.join(_REPOSITORY_ROOT, "helper", "hooks", "enable")
    if not os.path.exists(enable_script):
        return
    try:
        result = subprocess.run(
            [enable_script], capture_output=True, text=True, check=False
        )
    except OSError as error:
        logger.info(f"Could not arm the pre-commit gate: {error}")
        return
    reported = (result.stdout or result.stderr).strip()
    if result.returncode == 0:
        logger.info(reported or "Armed the pre-commit gate.")
    else:
        logger.info(
            f"The pre-commit gate is not armed ({reported}). Run helper/hooks/enable "
            "from a clone of this repository to arm it."
        )


def report_display_calibration() -> None:
    """Say what will happen to display colour on this machine, and how to change it.

    Calibration is optional and needs a colorimeter, so nothing here prompts or fails.
    The point is that the outcome is stated at install time rather than discovered later
    from a display that looks wrong.
    """
    host = platform.node()
    host_map = helper.apply_icc.read_displays().get(host, {})
    displays = helper.apply_icc.detect_displays()

    if not host_map:
        logger.info(
            f"No display profiles are configured for {host!r}. The desktop installs and "
            "runs uncalibrated; to add one, calibrate with displaycal and then run "
            "`python helper/apply_icc.py --import-profile <file>.icc --display <output>`."
        )
        return

    for index, output in displays or []:
        name = host_map.get(output) or host_map.get(index)
        if name and helper.apply_icc.profile_path(name):
            logger.info(f"Display {index} ({output}) will use the {name} profile.")
        elif name:
            logger.info(f"Display {index} ({output}) is mapped to {name}, which is missing.")
        else:
            logger.info(f"Display {index} ({output}) has no profile; it stays uncalibrated.")
    if not displays:
        logger.info(
            f"Profiles are configured for {host!r} but no display could be queried; they "
            "will be applied at the next X session start."
        )
    logger.info("Create ~/.config/icc/disabled to run uncalibrated without changing anything.")


#: Everything installed verbatim out of ``configuration/``, as (path under configuration/,
#: destination, label). A directory is linked whole, a file on its own. Expressed as data
#: because it was 90 lines of near-identical call pairs, in which a missing entry looked
#: exactly like the entries around it.
STATIC_INSTALLS = (
    ("bash/.bashrc", "~/.bashrc", "bash"),
    ("bash/.dircolors", "~/.dircolors", "dircolors"),
    ("xorg/.xinitrc", "~/.xinitrc", "xorg"),
    ("xorg/.Xresources", "~/.Xresources", "xorg"),
    ("hardware/icc", "~/.config/icc", "icc"),
    ("vim/.vimrc", "~/.vimrc", "vim"),
    ("starship/starship.toml", "~/.config/starship.toml", "starship"),
    ("qtile", "~/.config/qtile", "qtile"),
    ("picom", "~/.config/picom", "picom"),
    ("tmux", "~/.config/tmux", "tmux"),
    ("kitty", "~/.config/kitty", "kitty"),
    ("lock", "~/.config/lock", "lock"),
    ("dunst", "~/.config/dunst", "dunst"),
    ("rofi", "~/.config/rofi", "rofi"),
    ("qutebrowser/config.py", "~/.config/qutebrowser/config.py", "qutebrowser"),
    ("mpv", "~/.config/mpv", "mpv"),
    ("vscode/settings.json", "~/.config/Code/User/settings.json", "Visual Studio Code settings"),
)

#: The four wallpaper variants, as (key in the `wallpapers` block, filename in the bundle).
WALLPAPERS = (
    ("dark", "wallpaper-dark.png"),
    ("light", "wallpaper-light.png"),
    ("dark-highlight", "wallpaper-dark-highlight.png"),
    ("light-highlight", "wallpaper-light-highlight.png"),
)

#: Everything a reader would change lives in setup.toml, not here. See helper/utils.py.
SETUP = read_setup()


class InconsistentBundle(ValueError):
    """A bundle whose directory name and manifest name disagree."""


def discover_themes(assets_folder_path: str) -> dict[str, str]:
    """Map every bundled theme's name to its directory, keyed by the directory.

    The directory name is the identity. ``--theme <name>`` names a directory, so a bundle can
    be picked out of a file listing rather than by opening the JSON inside each one, and
    ``.gitignore`` can carry ``!assets/default/`` and mean something.

    The manifest's ``name`` has to agree, and is checked rather than trusted. The two are
    written from one value by ``yths.themes``, but nothing here can enforce that at the far
    end -- and a disagreement is not cosmetic: ``patch_plymouth`` finds a preset's boot splash
    at ``configuration/plymouth/themes/<manifest name>``, so a bundle installed under a
    directory that says something else would quietly ship no splash at all. Refused here,
    before anything is installed, rather than discovered at the next boot.

    Sorted so the numbering the prompt shows is the same on every machine; ``os.listdir``
    order is not.
    """
    theme_paths = {}
    disagreements = []
    for entry in sorted(os.listdir(assets_folder_path)):
        manifest = os.path.join(assets_folder_path, entry, "config.json")
        if not os.path.isfile(manifest):
            continue
        with open(manifest, encoding="utf-8") as handle:
            declared = json.load(handle).get("name")
        if declared != entry:
            disagreements.append(
                f"  assets/{entry}/ has a manifest naming it {declared!r}"
            )
            continue
        theme_paths[entry] = os.path.dirname(manifest)
    if disagreements:
        raise InconsistentBundle(
            "A theme bundle's directory and its manifest disagree about its name:\n"
            + "\n".join(disagreements)
            + "\nRename the directory, or fix the manifest, so the two match."
        )
    return theme_paths


def select_theme(theme_paths: dict[str, str], requested: str | None) -> str:
    """Return the theme to install, prompting only when one was not named.

    Resolved before anything is installed, so an unknown ``--theme`` exits without having
    already replaced half the configuration.
    """
    theme_names = sorted(theme_paths)
    if requested is not None:
        if requested not in theme_paths:
            sys.exit(
                f"Unknown theme {requested!r}. Available: {', '.join(theme_names)}."
            )
        return requested

    for index, name in enumerate(theme_names):
        print(f"[{index}] {name}")
    while True:
        user_input = input(
            f"Select a theme by number or name (default = {theme_names[0]}): "
        ).strip()
        if not user_input:
            return theme_names[0]
        if user_input.isdigit() and int(user_input) < len(theme_names):
            return theme_names[int(user_input)]
        if user_input in theme_paths:
            return user_input
        print(
            f"  Not a valid choice. Enter 0-{len(theme_names) - 1}, "
            f"or one of: {', '.join(theme_names)}."
        )


def install_static_configuration(configuration_folder_path: str) -> None:
    """Link every per-app configuration into place. Nothing here depends on the theme."""
    for relative_path, destination, label in STATIC_INSTALLS:
        source = os.path.join(configuration_folder_path, relative_path)
        install = install_folder if os.path.isdir(source) else install_file
        install(source, os.path.expanduser(destination), label)


def install_wallpapers(bundle_path: str) -> dict[str, str]:
    """Link the bundle's wallpapers into place and return the `wallpapers` block for them."""
    wallpapers = {}
    for key, filename in WALLPAPERS:
        destination = f"~/.config/qtile/{filename}"
        install_file(
            os.path.join(bundle_path, "wallpapers", filename),
            os.path.expanduser(destination),
            f"wallpaper {key}",
        )
        wallpapers[key] = destination
    return wallpapers


def assemble_configuration(bundle_path: str, wallpapers: dict[str, str]) -> dict[str, Any]:
    """Build ``~/.config/config.json`` from the bundle plus what this machine reports.

    Only ``name`` survives from the bundle's own manifest. Monitors come from the detected
    hardware, the palette from the installed ``palette.pkl``, and the wallpaper paths from
    wherever the installer just put them -- which is why a bundle's copy of any of these
    can rot without anything failing. See docs/architecture.md for the contract.
    """
    with open(os.path.join(bundle_path, "config.json"), encoding="utf-8") as handle:
        configuration = json.load(handle)
    configuration.pop("colors", None)

    configuration["monitors"] = helper.screen_configuration.get()
    with open(
        os.path.expanduser(os.path.join("~", ".config", "palette.pkl")), "rb"
    ) as handle:
        configuration["palette"] = pickle.load(handle)

    configuration["wallpapers"] = wallpapers
    configuration["font"] = {
        "family": SETUP["desktop"]["font_family"],
        "size": SETUP["desktop"]["font_size"],
    }
    configuration["state"] = dict(SETUP["state"])
    return configuration


def write_configuration(configuration: dict[str, Any]) -> None:
    """Write ``~/.config/config.json``, backing up whatever was there first."""
    path = os.path.expanduser(os.path.join("~", ".config", "config.json"))
    if os.path.exists(path):
        logger.info(f"Global configuration already exists at {path}.")
        timestamp = int(time.time())
        os.rename(path, f"{path}.{timestamp}.bak")
        logger.info(f"Backed up existing global configuration to {path}.{timestamp}.bak.")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(configuration, handle, indent=4)
    logger.info(f"Installed global configuration to {path}.")


def generate_application_configuration(configuration: dict[str, Any]) -> None:
    """Write the palette-derived half of every app's configuration.

    Installing symlinks the static files; this produces the ones computed from the palette,
    which are gitignored and therefore absent from a fresh clone. Without it rofi would start
    with no colour variables to import and kitty with no configuration at all, until the
    first theme switch happened to generate them.
    """
    failed = helper.patch_configurations.patch_all(configuration)
    if failed:
        logger.warning(
            f"These applications were not configured: {', '.join(failed)}. "
            "Run `python helper/patch_configurations.py` once the cause is fixed."
        )


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install these dot files and one of the bundled themes."
    )
    parser.add_argument(
        "--theme",
        type=str,
        default=None,
        help="Install this theme by name, overriding setup.toml's [desktop] theme.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    enable_git_hooks()

    repository_folder_path = os.path.expanduser(
        os.environ.get(
            "DOTFILES_REPOSITORY_PATH",
            os.path.join("~", "repositories", "yths.dot-files"),
        )
    )
    configuration_folder_path = os.path.join(repository_folder_path, "configuration")
    assets_folder_path = os.path.join(repository_folder_path, "assets")

    try:
        theme_paths = discover_themes(assets_folder_path)
    except InconsistentBundle as error:
        sys.exit(str(error))
    if not theme_paths:
        sys.exit(f"No theme bundles found under {assets_folder_path}.")
    selected_theme = select_theme(
        theme_paths, arguments.theme or SETUP["desktop"]["theme"] or None
    )
    print(f"Selected theme: {selected_theme}")
    bundle_path = theme_paths[selected_theme]

    install_static_configuration(configuration_folder_path)
    report_display_calibration()

    wanted = SETUP["credentials"]["prompt"]
    if wanted and input(f"Collect credentials ({', '.join(wanted)})? (y/n): ").lower() == "y":
        install_credentials(wanted)

    install_file(
        os.path.join(bundle_path, "palette.pkl"),
        os.path.expanduser(os.path.join("~", ".config", "palette.pkl")),
        "palette",
    )
    wallpapers = install_wallpapers(bundle_path)
    configuration = assemble_configuration(bundle_path, wallpapers)
    write_configuration(configuration)
    generate_application_configuration(configuration)
    return 0


if __name__ == "__main__":
    sys.exit(main())
