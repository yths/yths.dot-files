"""Regenerate marker-delimited blocks in the documentation from the filesystem.

The docs deliberately avoid manually maintained enumerations (widget lists, theme
preset names, helper inventory, web-greeter theme list). Instead they hold
``<!-- BEGIN: <KEY> -->`` / ``<!-- END: <KEY> -->`` markers, and this script
regenerates the content between them by scanning the source of truth on disk.

Usage::

    python helper/gendocs.py            # rewrite blocks in place
    python helper/gendocs.py --check    # exit non-zero if any block would change

The script is idempotent: running it twice in a row produces no diff.
"""

import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path

import list_colors
import list_keybindings

REPO_ROOT = Path(__file__).resolve().parent.parent


def module_summary(path: Path) -> str:
    """Return the first line of the file's module docstring, or '' if absent."""
    try:
        tree = ast.parse(path.read_text())
    except (SyntaxError, OSError):
        return ""
    if not tree.body:
        return ""
    first = tree.body[0]
    if not isinstance(first, ast.Expr) or not isinstance(first.value, ast.Constant):
        return ""
    if not isinstance(first.value.value, str):
        return ""
    return first.value.value.strip().splitlines()[0]


def is_qtile_widget(path: Path) -> bool:
    """A file under widgets/ counts as a widget only if it imports libqtile.widget.base."""
    try:
        text = path.read_text()
    except OSError:
        return False
    return "libqtile.widget.base" in text


def generate_widgets() -> str:
    lines = []
    widgets_dir = REPO_ROOT / "configuration" / "qtile" / "widgets"
    for path in sorted(widgets_dir.glob("*.py")):
        if not is_qtile_widget(path):
            continue
        summary = module_summary(path) or "(no docstring)"
        lines.append(f"- **{path.stem}** — {summary}")
    return "\n".join(lines)


def generate_helpers() -> str:
    lines = []
    helper_dir = REPO_ROOT / "helper"
    for path in sorted(helper_dir.glob("*.py")):
        if path.name == "gendocs.py":
            continue
        summary = module_summary(path) or "(no docstring)"
        lines.append(f"- **{path.stem}** — {summary}")
    return "\n".join(lines)


def generate_presets() -> str:
    lines = []
    assets_dir = REPO_ROOT / "assets"
    for path in sorted(assets_dir.glob("theme-*")):
        if not path.is_dir():
            continue
        config_path = path / "config.json"
        if not config_path.is_file():
            continue
        try:
            name = json.loads(config_path.read_text()).get("name", "(unnamed)")
        except json.JSONDecodeError:
            name = "(invalid config.json)"
        lines.append(f"- **{name}** — `{path.relative_to(REPO_ROOT)}`")
    return "\n".join(lines)


def generate_web_greeter_themes() -> str:
    lines = []
    themes_dir = REPO_ROOT / "configuration" / "web-greeter" / "themes"
    for path in sorted(themes_dir.iterdir()):
        if not path.is_dir() or path.name.startswith("_"):
            continue
        lines.append(f"- **{path.name}**")
    return "\n".join(lines)


GENERATORS = {
    "WIDGETS": (
        "docs/notes.md",
        generate_widgets,
    ),
    "HELPERS": (
        "helper/README.md",
        generate_helpers,
    ),
    "PRESETS": (
        "docs/architecture.md",
        generate_presets,
    ),
    "WEB_GREETER_THEMES": (
        "configuration/web-greeter/THEME-DEVELOPMENT.md",
        generate_web_greeter_themes,
    ),
    "KEYBINDINGS": (
        "docs/keybindings.md",
        list_keybindings.generate_markdown,
    ),
    "COLORS": (
        "docs/colors.md",
        list_colors.generate_markdown,
    ),
}


MARKER_RE = re.compile(
    r"(<!-- BEGIN: (?P<key>[A-Z_]+) -->)(?P<body>.*?)(<!-- END: (?P=key) -->)",
    re.DOTALL,
)


def rewrite(path: Path, key: str, generated: str) -> bool:
    """Replace the block for ``key`` in ``path``; return True if the file changed."""
    if not path.is_file():
        # Target file doesn't exist yet — nothing to rewrite, no error.
        return False
    text = path.read_text()
    new_body = f"\n{generated}\n"

    def _replace(match: re.Match) -> str:
        if match.group("key") != key:
            return match.group(0)
        return f"{match.group(1)}{new_body}{match.group(4)}"

    new_text, count = MARKER_RE.subn(_replace, text)
    if count == 0:
        # Marker not present in target file — silently skip; the doc may not be in place yet.
        return False
    if new_text == text:
        return False
    path.write_text(new_text)
    return True


def check(path: Path, key: str, generated: str) -> bool:
    """Return True if the on-disk block matches the generated content."""
    if not path.is_file():
        return True
    text = path.read_text()
    new_body = f"\n{generated}\n"
    for match in MARKER_RE.finditer(text):
        if match.group("key") != key:
            continue
        return match.group("body") == new_body
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if any block on disk differs from the generated content",
    )
    args = parser.parse_args()

    stale = []
    changed = []
    for key, (relpath, gen) in GENERATORS.items():
        path = REPO_ROOT / relpath
        generated = gen()
        if args.check:
            if not check(path, key, generated):
                stale.append((key, relpath))
        else:
            if rewrite(path, key, generated):
                changed.append((key, relpath))

    if args.check:
        if stale:
            print("Stale blocks:", file=sys.stderr)
            for key, relpath in stale:
                print(f"  {key} in {relpath}", file=sys.stderr)
            return 1
        print("All blocks up to date.")
        return 0

    if changed:
        print("Updated blocks:")
        for key, relpath in changed:
            print(f"  {key} in {relpath}")
    else:
        print("No changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
