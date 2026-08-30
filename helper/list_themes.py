"""List every theme bundle under ``assets/theme-*/``.

Prints each bundle's path, its ``config.json``, and its unpickled ``palette.pkl`` to stdout.
Useful for inspecting what ``install.py`` would offer at install time. Honours the
``DOTFILES_REPOSITORY_PATH`` environment variable.
"""

import json
import os
import pickle
import sys


def assets_folder() -> str:
    """The bundle directory, honouring ``DOTFILES_REPOSITORY_PATH``."""
    repository_folder_path = os.path.expanduser(
        os.environ.get(
            "DOTFILES_REPOSITORY_PATH",
            os.path.join("~", "repositories", "yths.dot-files"),
        )
    )
    return os.path.join(repository_folder_path, "assets")


def describe_theme(theme_path: str) -> str:
    """One bundle's path, manifest and unpickled palette, as printable text."""
    lines = [theme_path]
    with open(os.path.join(theme_path, "config.json"), encoding="utf-8") as handle:
        lines.append(json.dumps(json.load(handle), indent=4))
    with open(os.path.join(theme_path, "palette.pkl"), "rb") as handle:
        lines.append(json.dumps(pickle.load(handle), indent=4))
    return "\n".join(lines)


def main() -> int:
    root = assets_folder()
    for entry in sorted(os.listdir(root)):
        theme_path = os.path.join(root, entry)
        if entry.startswith("theme-") and os.path.isdir(theme_path):
            print(describe_theme(theme_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
