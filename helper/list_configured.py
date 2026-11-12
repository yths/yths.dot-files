"""List the applications this repository configures, and the theme it ships.

Both are derived: the applications from ``install.py``'s install table, the theme from
``setup.toml``. That is what makes the README's summary regenerate exactly when one of them
changes — adding an application or switching the default theme — and never otherwise.

``generate_markdown`` returns the body ``gendocs.py`` injects into ``README.md``; running the
module prints the same body to stdout.
"""

import ast
import pathlib
import sys

try:
    from helper.utils import read_setup
except ImportError:
    from utils import read_setup

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

#: Where each installed path lands, for readers who want to know what is taken over. Keyed by
#: the label install.py uses, so an entry that disappears from the table disappears here.
PURPOSE = {
    "bash": "shell",
    "dircolors": "`ls` colours",
    "xorg": "session startup and DPI",
    "icc": "display colour profiles",
    "vim": "editor",
    "starship": "shell prompt",
    "qtile": "window manager and bar",
    "picom": "compositor",
    "tmux": "terminal multiplexer",
    "kitty": "terminal",
    "dunst": "notifications",
    "rofi": "launcher",
    "qutebrowser": "browser",
    "mpv": "video",
    "Visual Studio Code settings": "editor",
}


def installed_applications() -> list[tuple[str, str]]:
    """Read install.py's table rather than repeating it: (label, destination)."""
    tree = ast.parse((REPO_ROOT / "install.py").read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if getattr(node.targets[0], "id", "") != "STATIC_INSTALLS":
            continue
        entries = [tuple(element.value for element in row.elts) for row in node.value.elts]
        seen, applications = set(), []
        for _source, destination, label in entries:
            if label in seen:
                continue
            seen.add(label)
            applications.append((label, destination))
        return applications
    raise LookupError("install.py has no STATIC_INSTALLS table")


def generate_markdown() -> str:
    """The README's summary of what ships and what it takes over."""
    setup = read_setup()
    theme = setup["desktop"]["theme"]
    font = setup["desktop"]["font_family"]

    lines = [
        f"The bar, the terminal, the launcher and the notifications above are drawn from the "
        f"`{theme}` theme in `{font}` — the same palette every application below receives.",
        "",
        "| Application | Installed to | For |",
        "|---|---|---|",
    ]
    for label, destination in installed_applications():
        lines.append(f"| {label} | `{destination}` | {PURPOSE.get(label, '')} |")
    return "\n".join(lines)


def main() -> int:
    print(generate_markdown())
    return 0


if __name__ == "__main__":
    sys.exit(main())
