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
import pickle
import re
import sys
from pathlib import Path

import list_configured
import list_dependencies
import list_keybindings
import list_palette
import render_preview
from utils import read_setup

REPO_ROOT = Path(__file__).resolve().parent.parent
WIDGETS_DIR = REPO_ROOT / "configuration" / "qtile" / "widgets"


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
    """A module is a widget only if it builds on one of qtile's widget base classes."""
    try:
        text = path.read_text()
    except OSError:
        return False
    return "libqtile.widget.base" in text


def stray_widget_modules() -> list[Path]:
    """Modules sitting in widgets/ that are not widgets.

    The directory holds bar cells and nothing else: code shared between cells belongs in
    ``configuration/qtile/shared/``, standalone tools in ``helper/``. Reported rather than
    skipped, so the pre-commit hook refuses a stray file instead of quietly excluding it
    from the generated list -- which is the failure mode that lets one accumulate.
    """
    return [path for path in sorted(WIDGETS_DIR.glob("*.py")) if not is_qtile_widget(path)]


#: Paths in this file must be repo-rooted and real: its whole job is telling a reader which
#: entry point pulls in which dependency, and a name that cannot be pasted into a shell
#: fails at that. See its "Naming Convention" section.
DEPENDENCIES_DOC = REPO_ROOT / "docs" / "dependencies.md"

#: A backticked token naming a Python file, or a bare identifier that happens to be one of
#: this repository's module names. Both forms were used in the tables, along with paths
#: rooted at three different directories; none of them resolved.
MODULE_PATH_REFERENCE = re.compile(r"`([\w./-]+\.py)`")
BARE_NAME_REFERENCE = re.compile(r"`([a-z_][a-z0-9_]*)`")


def module_stems() -> set[str]:
    """Every module name in the repository, without directory or extension."""
    return {path.stem for path in REPO_ROOT.rglob("*.py") if ".git" not in path.parts}


def unresolvable_module_references() -> list[str]:
    """Names in docs/dependencies.md that do not say, resolvably, which module they mean.

    Two ways to fail. A path that does not exist from the repository root -- ``config.py``
    and ``widgets/audio.py`` both named something real without saying where. And a bare
    module name like ``patch_vsc``, which reads as prose but is a module: it has to be given
    as a path or an import scanner cannot resolve it, which is why that open ticket could
    not be written while this column looked the way it did.
    """
    if not DEPENDENCIES_DOC.is_file():
        return []
    text = DEPENDENCIES_DOC.read_text()
    stems = module_stems()
    unresolved = {
        reference
        for reference in MODULE_PATH_REFERENCE.findall(text)
        if not (REPO_ROOT / reference).is_file()
    }
    unresolved |= {
        f"{name} (a module; give its path)"
        for name in BARE_NAME_REFERENCE.findall(text)
        if name in stems
    }
    return sorted(unresolved)


#: A markdown inline link, capturing its target: ``[text](target)``. Also matches the image
#: form, whose leading ``!`` is outside the capture and does not change what has to resolve.
MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)")

#: A ``](target)`` with no bracket still open before it on the line. That is not a broken
#: link but damaged text, and no link checker reports it, because it is not a link -- there
#: is nothing to resolve. One reached the tree exactly this way, from a bulk replacement that
#: took the opening bracket with the words it replaced.
DANGLING_LINK = re.compile(r"\]\(")

#: Directories whose markdown is not this repository's to maintain.
UNMAINTAINED = {".git", "backup", "node_modules", ".pytest_cache"}


def documentation_files() -> list[Path]:
    """Every markdown file this repository maintains."""
    return sorted(
        path
        for path in REPO_ROOT.rglob("*.md")
        if not UNMAINTAINED & set(path.parts)
    )


def broken_documentation_links() -> list[str]:
    """Relative links that do not resolve, and link syntax that was damaged rather than moved.

    This documentation is held together by cross-references -- ``docs/style.md`` requires
    them, and the generated blocks emit them -- so a rename that misses one leaves a reader
    at a dead end with nothing to say so. External links are not fetched: reachability is
    somebody else's uptime, not a property of this commit.

    Anchors are checked as far as the file: ``notes.md#palette-design`` has to name a file
    that exists, not a heading that does.
    """
    problems = []
    for path in documentation_files():
        relative = path.relative_to(REPO_ROOT)
        text = path.read_text()
        for number, line in enumerate(text.splitlines(), 1):
            for match in DANGLING_LINK.finditer(line):
                before = line[: match.start()]
                if before.count("[") <= before.count("]"):
                    problems.append(f"{relative}:{number} — a link lost its opening bracket")
        for target in MARKDOWN_LINK.findall(text):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            destination = target.partition("#")[0]
            if destination and not (path.parent / destination).exists():
                problems.append(f"{relative} — {target}")
    return sorted(problems)


def stale_preview() -> list[str]:
    """Whether docs/preview/ was rendered from the palette that ships today.

    The images are tracked, unlike everything else generated here, because GitHub has to
    serve them from the README. That is only defensible while they change when the theme
    does and at no other time -- so the digest they were drawn from is compared, and a
    forgotten re-render fails the commit instead of leaving the README showing an old theme.
    """
    setup = read_setup()
    bundle = REPO_ROOT / "assets" / setup["desktop"]["theme"]
    digest_path = REPO_ROOT / "docs" / "preview" / "rendered-from.txt"
    if not digest_path.is_file():
        return ["docs/preview/ has never been rendered"]
    with (bundle / "palette.pkl").open("rb") as handle:
        palette = pickle.load(handle)
    expected = render_preview.palette_digest(palette, setup["desktop"]["font_family"])
    if digest_path.read_text().strip() != expected:
        return [f"rendered from a different palette than assets/{setup['desktop']['theme']}/"]
    return []


def invariants() -> list[tuple[str, list[str], str]]:
    """Every structural rule this script refuses to generate documentation around.

    Each is (what is wrong, what is wrong with it, what to do). Kept together because they
    are checked and reported the same way; the alternative was near-identical blocks in
    ``main``.
    """
    return [
        (
            "Names in docs/dependencies.md that do not resolve to a module:",
            unresolvable_module_references(),
            "Name modules by their path from the repository root, e.g. helper/patch_vsc.py.",
        ),
        (
            "Imports and the recorded Arch packages disagree:",
            list_dependencies.mismatches(list_dependencies.third_party_imports()),
            "Record the package in ARCH_PACKAGES (helper/list_dependencies.py), and list it\n"
            "under [packages] in setup.toml so a fresh machine installs it.",
        ),
        (
            "The rendered preview no longer matches the palette it shows:",
            stale_preview(),
            "Run `python helper/render_preview.py` and commit the images.",
        ),
        (
            "Documentation links that do not resolve:",
            broken_documentation_links(),
            "Fix the path, or the bracket. A `](target)` whose opening `[` is gone is not a\n"
            "link, so nothing but this check will ever mention it.",
        ),
        (
            "Not widgets, but sitting in configuration/qtile/widgets/:",
            [str(path.relative_to(REPO_ROOT)) for path in stray_widget_modules()],
            "Code shared between widgets belongs in configuration/qtile/shared/; "
            "standalone tools belong in helper/.",
        ),
    ]


def generate_widgets() -> str:
    """Every module under widgets/ is a widget, so every module is listed."""
    lines = []
    for path in sorted(WIDGETS_DIR.glob("*.py")):
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
    for path in sorted(assets_dir.iterdir()):
        config_path = path / "config.json"
        if not path.is_dir() or not config_path.is_file():
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
    "CONFIGURED": (
        "README.md",
        list_configured.generate_markdown,
    ),
    "DEPENDENCIES": (
        "docs/dependencies.md",
        list_dependencies.generate_markdown,
    ),
    "PALETTE": (
        "docs/palette-reference.md",
        list_palette.generate_markdown,
    ),
}


GENERATED_NOTE = (
    "*Generated by `helper/gendocs.py` — edits between the markers are overwritten. "
    "Change the source it reads from instead.*"
)

MARKER_RE = re.compile(
    r"(<!-- BEGIN: (?P<key>[A-Z_]+) -->)(?P<body>.*?)(<!-- END: (?P=key) -->)",
    re.DOTALL,
)


def block_body(generated: str) -> str:
    """The exact text that belongs between a pair of markers.

    Defined once because ``rewrite`` and ``check`` must agree byte for byte: two separate
    constructions of the same string silently disagree the moment one of them changes.
    """
    return f"\n{GENERATED_NOTE}\n\n{generated}\n"


def rewrite(path: Path, key: str, generated: str) -> bool:
    """Replace the block for ``key`` in ``path``; return True if the file changed."""
    if not path.is_file():
        # Target file doesn't exist yet — nothing to rewrite, no error.
        return False
    text = path.read_text()
    new_body = block_body(generated)

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
    new_body = block_body(generated)
    for match in MARKER_RE.finditer(text):
        if match.group("key") != key:
            continue
        return match.group("body") == new_body
    return True


def report_violation() -> bool:
    """Print the first violated invariant. True means the caller should stop."""
    for title, offenders, hint in invariants():
        if not offenders:
            continue
        print(title, file=sys.stderr)
        for offender in offenders:
            print(f"  {offender}", file=sys.stderr)
        print(hint, file=sys.stderr)
        return True
    return False


def stale_blocks() -> list[tuple[str, str]]:
    """Marker blocks whose content on disk differs from what the generators produce."""
    return [
        (key, relpath)
        for key, (relpath, gen) in GENERATORS.items()
        if not check(REPO_ROOT / relpath, key, gen())
    ]


def rewrite_blocks() -> list[tuple[str, str]]:
    """Regenerate every marker block; returns the ones that actually changed."""
    return [
        (key, relpath)
        for key, (relpath, gen) in GENERATORS.items()
        if rewrite(REPO_ROOT / relpath, key, gen())
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if any block on disk differs from the generated content",
    )
    args = parser.parse_args()

    if report_violation():
        return 1

    if args.check:
        stale = stale_blocks()
        if stale:
            print("Stale blocks:", file=sys.stderr)
            for key, relpath in stale:
                print(f"  {key} in {relpath}", file=sys.stderr)
            return 1
        print("All blocks up to date.")
        return 0

    changed = rewrite_blocks()
    if changed:
        print("Updated blocks:")
        for key, relpath in changed:
            print(f"  {key} in {relpath}")
    else:
        print("No changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
