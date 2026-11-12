"""Install the dot files.

Discovers theme bundles under ``assets/theme-*/``, prompts for one, writes the chosen bundle's
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

try:
    import loguru

    logger = loguru.logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

import helper.apply_icc
import helper.screen_configuration
from helper.utils import (
    install_credentials,
    install_file,
    install_files,
    install_folder,
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Install the yths dot files and one of the bundled themes."
    )
    parser.add_argument(
        "--theme",
        type=str,
        default=None,
        help="Install this theme by name, without prompting (e.g. --theme yths).",
    )
    arguments = parser.parse_args()

    enable_git_hooks()

    repository_folder_path = os.environ.get(
        "DOTFILES_REPOSITORY_PATH",
        os.path.join("~", "repositories", "yths.dot-files"),
    )
    repository_folder_path = os.path.expanduser(repository_folder_path)
    configuration_folder_path = os.path.join(repository_folder_path, "configuration")
    assets_folder_path = os.path.join(repository_folder_path, "assets")

    # Resolved before anything is installed, so `--theme <unknown>` fails without
    # having already replaced half the configuration.
    # Discover the theme bundles. Sorted by name so the numbering is the same on every
    # machine -- os.listdir order is not.
    theme_paths = {}
    for entry in sorted(os.listdir(assets_folder_path)):
        theme_path = os.path.join(assets_folder_path, entry)
        if not entry.startswith("theme-") or not os.path.isdir(theme_path):
            continue
        with open(os.path.join(theme_path, "config.json"), encoding="utf-8") as handle:
            theme_paths[json.load(handle)["name"]] = theme_path

    if not theme_paths:
        sys.exit(f"No theme bundles found under {assets_folder_path}.")

    theme_names = sorted(theme_paths)
    if arguments.theme is not None:
        if arguments.theme not in theme_paths:
            sys.exit(
                f"Unknown theme {arguments.theme!r}. "
                f"Available: {', '.join(theme_names)}."
            )
        selected_theme = arguments.theme
    else:
        for index, name in enumerate(theme_names):
            print(f"[{index}] {name}")
        selected_theme = None
        while selected_theme is None:
            user_input = input(
                f"Select a theme by number or name (default = {theme_names[0]}): "
            ).strip()
            if not user_input:
                selected_theme = theme_names[0]
            elif user_input.isdigit() and int(user_input) < len(theme_names):
                selected_theme = theme_names[int(user_input)]
            elif user_input in theme_paths:
                selected_theme = user_input
            else:
                print(
                    f"  Not a valid choice. Enter 0-{len(theme_names) - 1}, "
                    f"or one of: {', '.join(theme_names)}."
                )

    print(f"Selected theme: {selected_theme}")

    assets_folder_path = theme_paths[selected_theme]

    # install bash configuration
    source_file_path = os.path.join(configuration_folder_path, "bash", ".bashrc")
    destination_file_path = os.path.join(os.path.expanduser("~"), ".bashrc")
    install_file(source_file_path, destination_file_path, "bash")
    source_file_path = os.path.join(configuration_folder_path, "bash", ".dircolors")
    destination_file_path = os.path.join(os.path.expanduser("~"), ".dircolors")
    install_file(source_file_path, destination_file_path, "dircolors")

    # install xorg configuration
    files_paths = {
        os.path.join(configuration_folder_path, "xorg", ".xinitrc"): os.path.join(
            os.path.expanduser("~"), ".xinitrc"
        ),
        os.path.join(configuration_folder_path, "xorg", ".Xresources"): os.path.join(
            os.path.expanduser("~"), ".Xresources"
        ),
    }
    install_files(files_paths, "xorg")
    source_folder_path = os.path.join(configuration_folder_path, "hardware", "icc")
    destination_folder_path = os.path.join(os.path.expanduser("~"), ".config", "icc")
    install_folder(source_folder_path, destination_folder_path, "icc")
    report_display_calibration()

    # install vim configuration
    source_file_path = os.path.join(configuration_folder_path, "vim", ".vimrc")
    destination_file_path = os.path.join(os.path.expanduser("~"), ".vimrc")
    install_file(source_file_path, destination_file_path, "vim")

    # install starship configuration
    source_file_path = os.path.join(
        configuration_folder_path, "starship", "starship.toml"
    )
    destination_file_path = os.path.join(
        os.path.expanduser("~"), ".config", "starship.toml"
    )
    install_file(source_file_path, destination_file_path, "starship")

    # install qtile configuration
    source_folder_path = os.path.join(configuration_folder_path, "qtile")
    destination_folder_path = os.path.join(os.path.expanduser("~"), ".config", "qtile")
    install_folder(source_folder_path, destination_folder_path, "qtile")

    # install picom configuration
    source_folder_path = os.path.join(configuration_folder_path, "picom")
    destination_folder_path = os.path.join(os.path.expanduser("~"), ".config", "picom")
    install_folder(source_folder_path, destination_folder_path, "picom")

    # install tmux configuration
    source_folder_path = os.path.join(configuration_folder_path, "tmux")
    destination_folder_path = os.path.join(os.path.expanduser("~"), ".config", "tmux")
    install_folder(source_folder_path, destination_folder_path, "tmux")

    # install kitty configuration
    source_folder_path = os.path.join(configuration_folder_path, "kitty")
    destination_folder_path = os.path.join(os.path.expanduser("~"), ".config", "kitty")
    install_folder(source_folder_path, destination_folder_path, "kitty")

    # install dunst configuration
    source_folder_path = os.path.join(configuration_folder_path, "dunst")
    destination_folder_path = os.path.join(os.path.expanduser("~"), ".config", "dunst")
    install_folder(source_folder_path, destination_folder_path, "dunst")

    # install rofi configuration
    source_folder_path = os.path.join(configuration_folder_path, "rofi")
    destination_folder_path = os.path.join(os.path.expanduser("~"), ".config", "rofi")
    install_folder(source_folder_path, destination_folder_path, "rofi")

    # install qutebrowser configuration
    source_file_path = os.path.join(
        configuration_folder_path, "qutebrowser", "config.py"
    )
    destination_file_path = os.path.join(
        os.path.expanduser("~"), ".config", "qutebrowser", "config.py"
    )
    install_file(source_file_path, destination_file_path, "qutebrowser")

    #install mpv configuration
    source_folder_path = os.path.join(configuration_folder_path, "mpv")
    destination_folder_path = os.path.join(os.path.expanduser("~"), ".config", "mpv")
    install_folder(source_folder_path, destination_folder_path, "mpv")

    # install Visual Studio Code configuration
    source_folder_path = os.path.join(configuration_folder_path, "vscode")
    destination_folder_path = os.path.join(
        os.path.expanduser("~"), ".config", "Code", "User"
    )
    install_file(
        os.path.join(source_folder_path, "settings.json"),
        os.path.join(destination_folder_path, "settings.json"),
        "Visual Studio Code settings",
    )

    # install credentials
    # check if user wants to install credentials
    user_input = input("Do you want to install credentials? (y/n): ")
    if user_input.lower() == "y":
        credentials = ["IPINFO_TOKEN"]
        install_credentials(credentials)

    # configure theme

    # install configuration
    source_file_path = os.path.join(assets_folder_path, "palette.pkl")
    destination_file_path = os.path.join(
        os.path.expanduser("~"), ".config", "palette.pkl"
    )
    install_file(source_file_path, destination_file_path, "palette")

    with open(
        os.path.join(assets_folder_path, "config.json"), encoding="utf-8"
    ) as handle:
        configuration = json.load(handle)
    configuration.pop("colors", None)

    monitors = helper.screen_configuration.get()
    configuration["monitors"] = monitors

    with open(
        os.path.expanduser(os.path.join("~", ".config", "palette.pkl")), "rb"
    ) as handle:
        palette = pickle.load(handle)
    configuration["palette"] = palette

    configuration["wallpapers"] = {}
    configuration["wallpapers"]["dark"] = "~/.config/qtile/wallpaper-dark.png"
    configuration["wallpapers"]["light"] = "~/.config/qtile/wallpaper-light.png"
    configuration["wallpapers"]["dark-highlight"] = (
        "~/.config/qtile/wallpaper-dark-highlight.png"
    )
    configuration["wallpapers"]["light-highlight"] = (
        "~/.config/qtile/wallpaper-light-highlight.png"
    )


    install_file(
        os.path.join(assets_folder_path, "wallpapers", "wallpaper-dark.png"),
        os.path.expanduser("~/.config/qtile/wallpaper-dark.png"),
        "wallpaper dark",
    )

    install_file(
        os.path.join(assets_folder_path, "wallpapers", "wallpaper-light.png"),
        os.path.expanduser("~/.config/qtile/wallpaper-light.png"),
        "wallpaper light",
    )

    install_file(
        os.path.join(assets_folder_path, "wallpapers", "wallpaper-dark-highlight.png"),
        os.path.expanduser("~/.config/qtile/wallpaper-dark-highlight.png"),
        "wallpaper dark highlight",
    )

    install_file(
        os.path.join(assets_folder_path, "wallpapers", "wallpaper-light-highlight.png"),
        os.path.expanduser("~/.config/qtile/wallpaper-light-highlight.png"),
        "wallpaper light highlight",
    )

    configuration["font"] = {}
    configuration["font"]["size"] = 14
    configuration["font"]["family"] = "Iosevka NF"

    configuration["state"] = {}
    configuration["state"]["theme"] = "light"
    configuration["state"]["condition"] = "normal"
    configuration["state"]["theme_mode"] = "automatic"

    # if configuration file already exists, back it up
    global_configuration_path = os.path.expanduser(
        os.path.join("~", ".config", "config.json")
    )
    if os.path.exists(global_configuration_path):
        logger.info(
            f"Global configuration already exists at {global_configuration_path}."
        )
        # Backing up the existing configuration
        timestamp = int(time.time())
        os.rename(
            global_configuration_path,
            f"{global_configuration_path}.{timestamp}.bak",
        )
        logger.info(
            f"Backed up existing global configuration to {global_configuration_path}.{timestamp}.bak."
        )
    with open(global_configuration_path, "w", encoding="utf-8") as handle:
        json.dump(configuration, handle, indent=4)
    logger.info(f"Installed global configuration to {global_configuration_path}.")
