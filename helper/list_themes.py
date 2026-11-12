"""List every theme bundle under ``assets/theme-*/``.

Prints each bundle's path, its ``config.json``, and its unpickled ``palette.pkl`` to stdout.
Useful for inspecting what ``install.py`` would offer at install time. Honours the
``DOTFILES_REPOSITORY_PATH`` environment variable.
"""

import json
import os
import pickle

if __name__ == "__main__":
    repository_folder_path = os.environ.get(
        "DOTFILES_REPOSITORY_PATH",
        os.path.join("~", "repositories", "yths.dot-files"),
    )
    repository_folder_path = os.path.expanduser(repository_folder_path)
    assets_folder_path = os.path.join(repository_folder_path, "assets")

    for theme in os.listdir(assets_folder_path):
        if theme.startswith("theme-"):
            theme_path = os.path.join(assets_folder_path, theme)
            if os.path.isdir(theme_path):
                print(theme_path)
                with open(os.path.join(theme_path, "config.json"), encoding="utf-8") as handle:
                    configuration = json.load(handle)
                print(json.dumps(configuration, indent=4))
                with open(os.path.join(theme_path, "palette.pkl"), "rb") as handle:
                    palette = pickle.load(handle)
                print(json.dumps(palette, indent=4))
