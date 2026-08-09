"""Install the dot files.

Discovers theme bundles under ``assets/theme-*/``, prompts for one, writes the chosen bundle's
``config.json`` (merged with detected monitor geometry, font, and the unpickled palette) to
``~/.config/config.json``, and copies each per-app configuration tree from ``configuration/``
into ``~/.config/``. See docs/architecture.md for the full theme-bundle lifecycle.
"""

import json
import os
import pickle
import time

try:
    import loguru

    logger = loguru.logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

import helper.screen_configuration
from helper.utils import (
    install_credentials,
    install_file,
    install_files,
    install_folder,
)

if __name__ == "__main__":
    repository_folder_path = os.environ.get(
        "DOTFILES_REPOSITORY_PATH",
        os.path.join("~", "repositories", "yths.dot-files"),
    )
    repository_folder_path = os.path.expanduser(repository_folder_path)
    configuration_folder_path = os.path.join(repository_folder_path, "configuration")
    assets_folder_path = os.path.join(repository_folder_path, "assets")
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
    source_folder_path = os.path.join(configuration_folder_path, "icc")
    destination_folder_path = os.path.join(os.path.expanduser("~"), ".config", "icc")
    install_folder(source_folder_path, destination_folder_path, "icc")

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
    # list available themes

    theme_list = {}
    theme_id = 0
    for theme in os.listdir(assets_folder_path):
        if theme.startswith("theme-"):
            theme_path = os.path.join(assets_folder_path, theme)
            if os.path.isdir(theme_path):
                with open(
                    os.path.join(theme_path, "config.json"), encoding="utf-8"
                ) as handle:
                    configuration = json.load(handle)
                print(f"[{theme_id}] {configuration['name']}")
                theme_list[theme_id] = theme_path
                theme_id += 1

    selected_theme_id = None
    while selected_theme_id is None:
        user_input = input("Select a theme by entering its number (default = 0): ")
        selected_theme_id = int(user_input) if user_input.isdigit() else 0

    print(f"Selected theme: {theme_list[selected_theme_id]}")

    assets_folder_path = theme_list[selected_theme_id]

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
    configuration["state"]["mode"] = "automatic"

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
