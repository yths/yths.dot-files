"""List the screenshots the README shows, in the order a boot shows them.

``SHOTS`` is the one table: ``capture_tour.py`` and ``capture_boot.py`` write the files it
names, ``gendocs.py`` injects ``generate_markdown`` into ``README.md``, and the tests hold the
files to the size it allows. ``inputs_digest`` is what a capture is recorded against, so a
palette that has moved on since the screenshots were taken can be noticed.

Running the module prints the same body to stdout.
"""

import hashlib
import json
import pathlib
import sys
from typing import NamedTuple

from utils import read_setup

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

#: Where the screenshots live. Tracked, because GitHub has to serve them.
PREVIEW_DIRECTORY = REPO_ROOT / "docs" / "preview"

#: What the last capture was taken from: the inputs digest, and each file's hash and size.
MANIFEST = PREVIEW_DIRECTORY / "captured-from.json"

#: No image may be larger. A README is fetched whole, and the repository has no LFS.
MAX_IMAGE_BYTES = 400_000


class Shot(NamedTuple):
    """One screenshot: its file under ``docs/preview``, its alt text and its caption.

    ``hero`` marks the one the README places by hand, above everything else; the tour leaves
    it out so it is not shown twice. ``wide`` gives an image a row to itself: two monitors
    side by side are unreadable at half the page's width.
    """

    file: str
    alt: str
    caption: str
    hero: bool = False
    wide: bool = False


SHOTS: tuple[Shot, ...] = (
    Shot(
        "boot-splash.webp",
        "The boot splash: the wallpaper under a status line",
        "**Boot.** Plymouth draws the splash from the dark palette.",
    ),
    Shot(
        "boot-passphrase.webp",
        "The boot splash asking for the disk passphrase, the typed characters masked",
        "**Decrypt.** The LUKS passphrase prompt is the same splash, not a text console.",
    ),
    Shot(
        "login.webp",
        "The LightDM login screen: an account, a password field and the session menu",
        "**Log in.** The LightDM greeter, here with the accounts its preview mode invents.",
    ),
    Shot(
        "desktop-dark.webp",
        "The desktop in the dark palette: the bar, a terminal running tmux, the browser",
        "**The desktop, dark.** The bar, kitty with tmux, qutebrowser.",
        hero=True,
    ),
    Shot(
        "desktop-light.webp",
        "The same desktop in the light palette",
        "**The desktop, light.** The same windows after the switch that sunrise triggers.",
    ),
    Shot(
        "desktop-dual.webp",
        "Two monitors side by side, each with its own bar, the focused one outlined",
        "**Two monitors.** Each gets a bar scaled to its own pixel density; the outline "
        "marks the focused one.",
        wide=True,
    ),
    Shot(
        "terminal.webp",
        "kitty running tmux: two shells side by side, each with the starship prompt",
        "**Terminal.** kitty, tmux and the starship prompt.",
    ),
    Shot(
        "browser.webp",
        "qutebrowser with link hints over a page and two tabs",
        "**Browser.** qutebrowser, every colour matched to the palette, link hints shown.",
    ),
    Shot(
        "editor.webp",
        "Visual Studio Code editing a Python file, its interface in the palette's colours",
        "**Editor.** Visual Studio Code, matched the same way.",
    ),
    Shot(
        "launcher.webp",
        "The rofi launcher, as wide as the screen, under the bar",
        "**Launcher.** rofi opens under the bar on the focused screen.",
    ),
    Shot(
        "notification.webp",
        "Two dunst notifications under the bar, one of them critical",
        "**Notifications.** dunst, a normal and a critical one.",
    ),
    Shot(
        "lock.webp",
        "The lock screen: a password prompt and nothing else",
        "**Lock.** xsecurelock, showing neither the account nor the host.",
    ),
)


def inputs_digest() -> str:
    """A digest of what the screenshots depend on: the shipped theme's palette and manifest.

    Deliberately not the whole configuration tree: a capture needs a display and, for the
    boot frames, root, so it cannot be asked of every commit that moves a margin. The palette
    and the font are what make a stale screenshot wrong at a glance.
    """
    theme = read_setup()["desktop"]["theme"]
    bundle = REPO_ROOT / "assets" / theme
    digest = hashlib.sha256()
    for name in ("palette.json", "config.json"):
        digest.update((bundle / name).read_bytes())
    return digest.hexdigest()


def read_manifest() -> dict:
    """The record of the last capture; empty when there has been none."""
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return manifest if isinstance(manifest, dict) else {}


def record(files: list[str]) -> None:
    """Record ``files`` as captured from the current inputs, keeping the other entries.

    Merged rather than rewritten because the tour is captured by two tools: the boot frames
    need root and are taken separately, and neither run may forget the other's files.
    """
    manifest = read_manifest()
    recorded = dict(manifest.get("files") or {})
    for name in files:
        data = (PREVIEW_DIRECTORY / name).read_bytes()
        recorded[name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    known = {shot.file for shot in SHOTS}
    manifest = {
        "inputs": inputs_digest(),
        "files": {name: recorded[name] for name in sorted(recorded) if name in known},
    }
    MANIFEST.write_text(json.dumps(manifest, indent=4) + "\n", encoding="utf-8")


def generate_markdown() -> str:
    """The README's tour: every screenshot but the hero, in boot order.

    Two to a row, in a table for each run of them, and a wide one on a line of its own
    between tables -- a table cannot give one cell the whole width.
    """
    blocks: list[str] = []
    pending: list[Shot] = []

    def flush() -> None:
        if not pending:
            return
        rows = ["| | |", "|---|---|"]
        for index in range(0, len(pending), 2):
            cells = [image(shot) for shot in pending[index:index + 2]]
            cells += [""] * (2 - len(cells))
            rows.append(f"| {cells[0]} | {cells[1]} |")
        blocks.append("\n".join(rows))
        pending.clear()

    for shot in SHOTS:
        if shot.hero:
            continue
        if shot.wide:
            flush()
            blocks.append(image(shot))
        else:
            pending.append(shot)
    flush()
    return "\n\n".join(blocks)


def image(shot: Shot) -> str:
    """One screenshot as Markdown: the image, then its caption on the line under it."""
    return f"![{shot.alt}](docs/preview/{shot.file})<br>{shot.caption}"


def main() -> int:
    print(generate_markdown())
    return 0


if __name__ == "__main__":
    sys.exit(main())
