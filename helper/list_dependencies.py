"""Map every third-party Python import in this repo to the Arch package providing it.

Which files import what is derivable from the code, so it is derived here rather than
maintained by hand -- that column drifted twice before this existed. What is *not* derivable
is the Arch package name: ``import PIL`` comes from ``python-pillow``, and nothing in the
source says so. That mapping is the one hand-maintained table below.

``generate_markdown`` returns the body ``gendocs.py`` injects into
``docs/dependencies.md``; running the module prints the same body to stdout. An import with
no entry in ``ARCH_PACKAGES``, or an entry nothing imports any more, is reported as an error
rather than rendered, so the two halves cannot drift apart.
"""

import ast
import collections
import pathlib
import subprocess
import sys

import utils

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

#: Not part of what this desktop needs installed. The qutebrowser config is vendor-generated
#: and excluded from linting for the same reason; the tests import pytest, which is
#: development tooling and belongs in CONTRIBUTING.md beside ruff, not in a table of what a
#: machine needs to run the desktop.
EXCLUDED_FILES = ("configuration/qutebrowser/config.py",)
EXCLUDED_DIRECTORIES = ("tests/",)

#: The only thing here that the code cannot tell us: which Arch package provides an import,
#: and anything a reader needs to know before installing it. Everything else is derived.
ARCH_PACKAGES: dict[str, tuple[str, str]] = {
    "PIL": ("python-pillow", "renders the boot background"),
    "cairo": ("python-pycairo", "draws the boot background and the README preview"),
    "colour": (
        "python-colour-science",
        "perceptual nearest-colour matching, sRGB → XYZ → ΔE",
    ),
    "libqtile": ("qtile", "the window manager package provides the library"),
    "loguru": ("python-loguru", "optional; `helper/utils.py` falls back to stdlib `logging`"),
    "numpy": ("python-numpy", "level-meter maths"),
    "redis": ("python-redis", "optional at run time; cells render empty if Redis is unreachable"),
    "screeninfo": ("python-screeninfo", "detects monitor geometry at install time"),
    "sounddevice": ("python-sounddevice", "live audio sampling"),
    "toml": ("python-toml", "reads and rewrites `~/.config/starship.toml`"),
    "websockets": ("python-websockets", "live theme editing and reload broadcast"),
}

#: Packages that live in the AUR rather than the main repositories, so `yay -S` is required
#: rather than merely convenient. Kept as data so the marker lands outside the code span,
#: where it renders as bold rather than as literal asterisks.
AUR_PACKAGES = frozenset({"python-colour-science", "python-sounddevice"})

#: Above this many files, the column names directories instead of every path.
MAX_LISTED_FILES = 3


def tracked_modules() -> list[pathlib.Path]:
    """Every hand-written Python file in the repository."""
    listing = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "*.py"],
        capture_output=True, text=True, check=False,
    ).stdout.split()
    return [
        REPO_ROOT / name
        for name in listing
        if name not in EXCLUDED_FILES and not name.startswith(EXCLUDED_DIRECTORIES)
    ]


def first_party_names() -> set[str]:
    """Module names this repository defines, which are never dependencies."""
    return {path.stem for path in REPO_ROOT.rglob("*.py")} | {"helper", "widgets", "shared"}


def third_party_imports() -> dict[str, list[str]]:
    """Map each third-party import to the repo-rooted paths that import it."""
    local, users = first_party_names(), collections.defaultdict(set)
    for path in tracked_modules():
        try:
            tree = ast.parse(path.read_text())
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            else:
                continue
            for name in names:
                if name not in sys.stdlib_module_names and name not in local:
                    users[name].add(str(path.relative_to(REPO_ROOT)))
    return {module: sorted(paths) for module, paths in sorted(users.items())}


def describe_users(paths: list[str]) -> str:
    """The 'used by' cell: every file when there are few, otherwise the directories."""
    if len(paths) <= MAX_LISTED_FILES:
        return ", ".join(f"`{path}`" for path in paths)
    by_directory = collections.defaultdict(list)
    for path in paths:
        by_directory[str(pathlib.PurePosixPath(path).parent) + "/"].append(path)
    return ", ".join(
        f"`{files[0]}`" if len(files) == 1 else f"`{directory}` ({len(files)} files)"
        for directory, files in sorted(by_directory.items())
    )


def installed_packages() -> set[str]:
    """Every Arch package setup.toml tells the bootstrap script to install."""
    return {
        name
        for group in utils.read_setup()["packages"].values()
        for name in group
    }


def mismatches(imports: dict[str, list[str]]) -> list[str]:
    """Every way the imports, the recorded packages and the install list can disagree.

    Three sources have to stay in step: what the code imports, which Arch package provides
    it, and whether a fresh machine is told to install that package. A dependency added to
    the code without a line in setup.toml installs fine here and fails on someone else's
    machine, which is the failure this catches.
    """
    installed = installed_packages()
    return sorted(
        [f"{name}: imported, but no Arch package recorded" for name in imports
         if name not in ARCH_PACKAGES]
        + [f"{name}: Arch package recorded, but nothing imports it" for name in ARCH_PACKAGES
           if name not in imports]
        + [f"{package}: provides {name}, but setup.toml never installs it"
           for name, (package, _) in ARCH_PACKAGES.items()
           if name in imports and package not in installed]
    )


def generate_markdown() -> str:
    """Return the markdown body for the DEPENDENCIES block in docs/dependencies.md."""
    imports = third_party_imports()
    lines = ["| Import | Arch package | Used by | Notes |", "|---|---|---|---|"]
    for module, paths in imports.items():
        package, note = ARCH_PACKAGES.get(module, ("unrecorded", ""))
        marked = f"`{package}`" + (" **(AUR)**" if package in AUR_PACKAGES else "")
        lines.append(f"| `{module}` | {marked} | {describe_users(paths)} | {note} |")
    return "\n".join(lines)


def main() -> int:
    problems = mismatches(third_party_imports())
    if problems:
        print("Dependency table and imports disagree:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print("Record it in ARCH_PACKAGES and list it under [packages] in setup.toml.", file=sys.stderr)
        return 1
    print(generate_markdown())
    return 0


if __name__ == "__main__":
    sys.exit(main())
