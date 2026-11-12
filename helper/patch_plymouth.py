"""Patch plymouth: the boot splash's palette, fonts and rendered assets.

Unlike every other patcher, plymouth's target is not under ``~``: themes live in
``/usr/share/plymouth/themes/``, which is root-owned. That is why this runs in two stages.
**Render** copies the theme source out of this repository into a staging directory and
rewrites it for the active palette — no privileges, nothing in the repository touched.
**Install** copies the staged theme into the system path, which needs root.

This does not run on a theme switch, and is not in ``patch_all``'s registry. The boot splash
is a property of the machine rather than of whoever is logged into it: it is drawn before
login, needs root to install and an ``mkinitcpio`` run to take effect, and is always rendered
dark. Re-rendering it twice a day would prompt for a password, rebuild the initramfs, and
change something nobody is looking at.

Run it when the palette itself changes::

    python helper/patch_plymouth.py --install --rebuild

The rebuild is separate because it re-runs ``mkinitcpio`` for every preset: the boot splash
reads its theme from the initramfs, so copying files into place is necessary but not
sufficient.
"""

import argparse
import configparser
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Any

import cairo
import PIL.Image

# Resolves whether this runs as ``helper.patch_plymouth`` or as a script; see helper/README.md.
try:
    from helper import symbols
    from helper.utils import logger, root_prefix
except ImportError:
    import symbols
    from utils import logger, root_prefix

#: Where plymouth looks for themes. Root-owned, which is the whole reason for the two stages.
SYSTEM_THEME_ROOT = "/usr/share/plymouth/themes"

#: The boot splash is always rendered dark, whatever the desktop's current theme. It is drawn
#: before anyone logs in, so there is no user whose preference could apply; ``state.theme``
#: describes a session that does not exist yet. Dark also matches ``background-tile.png``,
#: which links to the dark wallpaper, and suits a screen coming up in a dark room.
PALETTE_VARIANT = "dark"

#: This file's repository, resolved through any symlink used to invoke it.
_REPOSITORY_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

#: The one boot splash this repository ships. Not one per preset, which is what it used to be:
#: nothing in the directory is bundle-specific. The patcher rewrites the INI's colours and fonts
#: and re-renders all eight images from the palette, and ``background-tile.png`` is a symlink to
#: whichever wallpaper the installed bundle put in place -- so a second copy differed from the
#: first only by the name of its directory.
#:
#: That name was the problem rather than a detail. The splash was found by looking for a
#: directory named after the active preset, so exporting a bundle under any other name silently
#: got no splash at all: "a preset need not ship one" made a missing directory indistinguishable
#: from a deliberate omission.
THEME_SOURCE = os.path.join(_REPOSITORY_ROOT, "configuration", "plymouth", "theme")

#: What it installs as, and what ``/etc/plymouth/plymouthd.conf`` has to name. A constant, so the
#: two cannot drift: while this was the preset's name, renaming a preset left plymouthd.conf
#: pointing at a theme nothing wrote any more, and the splash stayed frozen at whatever had been
#: installed under the old name.
THEME_NAME = "yths"


def theme_source(_configuration: dict[str, Any] | None = None) -> str | None:
    """The boot splash's source directory, or ``None`` if the tree has none.

    Takes a configuration it no longer reads, because every caller has one to hand and the
    signature is what the tests and ``main`` reach for. The splash is the same for every bundle;
    only its colours come from the palette.
    """
    return THEME_SOURCE if os.path.isdir(THEME_SOURCE) else None


def stage_theme(source: str) -> str:
    """Copy the theme source into a fresh temporary directory and return its path.

    Rendering happens on the copy, never on the source. The eight PNGs and the ``.plymouth``
    INI are all rewritten on every run, so rendering in place would rewrite tracked files
    twice a day — which is exactly the churn the wallpapers and the web-greeter stylesheets
    are gitignored to avoid.
    """
    dangling = [
        entry.name
        for entry in os.scandir(source)
        if entry.is_symlink() and not os.path.exists(entry.path)
    ]
    if dangling:
        raise FileNotFoundError(
            f"{', '.join(dangling)} in {source} points at a file that does not exist. "
            "Run install.py first: it creates the wallpaper links the theme dereferences."
        )
    staged = tempfile.mkdtemp(prefix="plymouth-theme-")
    # symlinks=False dereferences background-tile.png, which points at the active wallpaper:
    # the system copy has to hold the image, not a link into a home directory root cannot read.
    shutil.copytree(source, staged, symlinks=False, dirs_exist_ok=True)
    return staged


def install_theme(staged: str, name: str, *, prompt: bool = False, rebuild: bool = False) -> bool:
    """Copy the staged theme into the system path as root. Returns whether it landed."""
    destination = os.path.join(SYSTEM_THEME_ROOT, name)
    prefix = root_prefix(prompt=prompt)
    if prefix is None:
        logger.info(
            f"Rendered the plymouth theme, but writing {destination} needs root. Run "
            "`python helper/patch_plymouth.py --install --rebuild` to be prompted for it."
        )
        return False

    # -L dereferences whatever the source still links to; -T makes the destination the
    # directory itself rather than a parent to nest a second copy inside.
    result = subprocess.run(
        [*prefix, "cp", "-RLT", staged, destination],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        logger.warning(f"Installing the plymouth theme failed: {result.stderr.strip()}")
        return False
    logger.info(f"Installed the plymouth theme to {destination}.")

    if not rebuild:
        logger.info(
            f"The boot splash changes at the next initramfs rebuild: "
            f"`sudo plymouth-set-default-theme {name} -R`."
        )
        return True

    result = subprocess.run(
        [*prefix, "plymouth-set-default-theme", name, "-R"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        logger.warning(f"Rebuilding the initramfs failed: {result.stderr.strip()}")
        return False
    logger.info(f"Rebuilt the initramfs; {name} is the default boot splash.")
    return True


#: Flat rectangles plymouth composites behind the password entry and the animation:
#: (filename, size, palette token).
SOLID_ASSETS = (
    ("entry.png", (305, 34), "background"),
    ("animation-001.png", (533, 400), "background"),
)

#: Glyphs drawn on transparency: (filename, surface size, palette token, font size, origin,
#: symbol key). These were six near-identical cairo incantations; only these six values ever
#: differed. The character itself is no longer one of them: it comes from the active
#: vocabulary, so a theme can change what the splash draws -- and a machine whose font has no
#: private use area gets the ASCII stand-in instead. This is the one place a missing glyph is
#: baked into a file rather than merely displayed, so an empty box here survives the reboot.
GLYPH_ASSETS = (
    ("capslock.png", (24, 28), "highlight", 24, (6, 22), "plymouth.capslock"),
    ("bullet.png", (10, 10), "foreground", 16, (1, 11), "plymouth.bullet"),
    ("throbber-01.png", (64, 64), "foreground", 32, (24, 44), "plymouth.throbber"),
    ("throbber-02.png", (64, 64), "neutral", 32, (24, 44), "plymouth.throbber"),
    ("keyboard.png", (36, 36), "neutral", 32, (2, 30), "plymouth.keyboard"),
    ("lock.png", (35, 34), "neutral", 32, (3, 29), "plymouth.lock"),
)


def _rgb(hex_colour: str) -> tuple[float, float, float]:
    """``#rrggbb`` to the 0..1 triple cairo wants."""
    return tuple(int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5))


def render_configuration(
    configuration: dict[str, Any], theme_path: str, theme: str, name: str
) -> None:
    """Rewrite the theme's ``.plymouth`` INI with the active palette, fonts, name and text.

    The messages are the newest of those. Until the vocabulary existed they were the one part
    of the splash a theme could not reach: this function rewrote the fonts and the colours
    around them and left the words in the checked-in INI, so every bundle booted to the same
    seven titles no matter what else it changed.
    """
    # Found rather than derived: theme_path is a staging directory whose name has nothing
    # to do with the theme's, and the previous code hardcoded "yths.plymouth", which would
    # have silently produced an empty config for any other preset.
    inis = glob.glob(os.path.join(theme_path, "*.plymouth"))
    if not inis:
        raise FileNotFoundError(f"no .plymouth file in {theme_path}")
    ini_path = inis[0]

    plymouth_configuration = configparser.ConfigParser(interpolation=None)
    plymouth_configuration.optionxform = str
    plymouth_configuration.read(ini_path)

    two_step = plymouth_configuration["two-step"]
    font_family = configuration["font"]["family"]
    font_size = configuration["font"]["size"]
    palette = configuration["palette"][theme]

    two_step["Font"] = f"{font_family} {round(font_size * 1.25)}"
    two_step["TitleFont"] = f"{font_family} {round(font_size * 1.25)}"
    two_step["MonospaceFont"] = f"{font_family} {round(font_size * 0.85)}"

    # Plymouth writes colours as 0xrrggbb rather than #rrggbb.
    two_step["BackgroundStartColor"] = palette["background"].replace("#", "0x")
    two_step["BackgroundEndColor"] = palette["background"].replace("#", "0x")
    two_step["ProgressBarBackgroundColor"] = palette["neutral"].replace("#", "0x")
    two_step["ConsoleLogTextColor"] = palette["foreground"].replace("#", "0x")
    two_step["ConsoleLogBackgroundColor"] = palette["background"].replace("#", "0x")

    # Derived, not carried over from the source. ImageDir is an absolute path into the
    # system theme directory, so it has to name wherever install_theme is about to put this
    # -- and it silently pointed at a directory belonging to the preset's previous name
    # after the bundle was renamed, which plymouth answers by drawing no images at all.
    two_step["ImageDir"] = os.path.join(SYSTEM_THEME_ROOT, name)
    header = plymouth_configuration["Plymouth Theme"]
    header["Name"] = name
    header["Description"] = f"Boot splash for the {name} preset."

    # One title and one subtitle per mode plymouth can boot, shut down or update in. A
    # section the INI does not carry is skipped rather than created: the section list is
    # plymouth's, and inventing one would put a mode in the file that this theme never
    # declared an animation for.
    _, strings = symbols.resolve(configuration)
    for section, prefix in symbols.PLYMOUTH_SECTIONS.items():
        if section not in plymouth_configuration:
            continue
        # ``SubTitle``, not ``Subtitle``: the spelling is plymouth's, and optionxform is off
        # above, so a wrong capital adds a second key rather than replacing the first.
        for field, ini_key in (("title", "Title"), ("subtitle", "SubTitle")):
            value = strings.get(f"plymouth.{prefix}.{field}")
            if value is not None:
                plymouth_configuration[section][ini_key] = value

    with open(ini_path, "w") as handle:
        plymouth_configuration.write(handle, space_around_delimiters=False)


def render_assets(configuration: dict[str, Any], theme_path: str, theme: str) -> None:
    """Re-render every image the theme draws, in the active palette and symbols."""
    palette = configuration["palette"][theme]
    font_family = configuration["font"]["family"]
    glyphs, _ = symbols.resolve(configuration)

    for filename, size, token in SOLID_ASSETS:
        PIL.Image.new("RGB", size, palette[token]).save(os.path.join(theme_path, filename))

    for filename, size, token, font_size, origin, key in GLYPH_ASSETS:
        glyph = glyphs[key]
        with cairo.ImageSurface(cairo.FORMAT_ARGB32, *size) as surface:
            context = cairo.Context(surface)
            context.set_source_rgb(*_rgb(palette[token]))
            context.select_font_face(
                font_family, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL
            )
            context.set_font_size(font_size)
            context.move_to(*origin)
            context.show_text(glyph)
            surface.write_to_png(os.path.join(theme_path, filename))


def render_theme(
    configuration: dict[str, Any], theme_path: str, theme: str, name: str
) -> None:
    """Rewrite the staged theme's INI and re-render its assets for one palette variant."""
    render_configuration(configuration, theme_path, theme, name)
    render_assets(configuration, theme_path, theme)


def patch_plymouth(configuration: dict[str, Any]) -> None:
    """Render the boot splash from ``configuration``'s palette and install it if root is free.

    The importable entry point, for a caller that already holds a configuration -- an
    installer, or a script regenerating a preset. It is deliberately not in ``patch_all``'s
    registry: see this module's docstring. Never prompts, so an unattended caller cannot
    block on a password.
    """
    source = theme_source()
    if source is None:
        logger.info(f"No plymouth theme under {THEME_SOURCE}; skipping the boot splash.")
        return
    staged = stage_theme(source)
    try:
        render_theme(configuration, staged, PALETTE_VARIANT, THEME_NAME)
        install_theme(staged, THEME_NAME, prompt=False)
    finally:
        shutil.rmtree(staged, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--configuration", default="~/.config/config.json", dest="configuration_file_path",
        help="path to the active configuration (default: ~/.config/config.json)",
    )
    parser.add_argument(
        "--theme", default=None,
        help=f"palette variant to render (default: {PALETTE_VARIANT}; the splash is not "
             "themed per session)",
    )
    parser.add_argument(
        "theme_path", nargs="?", default=None,
        help=f"theme source directory (default: {THEME_SOURCE})",
    )
    parser.add_argument(
        "--install", action="store_true",
        help=f"copy the rendered theme into {SYSTEM_THEME_ROOT}, prompting for root if needed",
    )
    parser.add_argument(
        "--rebuild", action="store_true",
        help="with --install, also rebuild the initramfs so the change shows at the next boot",
    )
    arguments = parser.parse_args()

    with open(os.path.expanduser(arguments.configuration_file_path)) as handle:
        configuration = json.load(handle)

    source = arguments.theme_path or theme_source()
    if source is None or not os.path.isdir(source):
        print(f"No plymouth theme source; looked under {THEME_SOURCE}.", file=sys.stderr)
        return 1
    theme = arguments.theme or PALETTE_VARIANT

    # The constant, not the source directory's name. A theme rendered from a directory given on
    # the command line still has to install where plymouthd.conf looks, or it is rendered into
    # nothing -- which is how the installed splash came to be thirteen months old.
    name = THEME_NAME
    staged = stage_theme(source)
    try:
        logger.info(f"Rendering plymouth theme {source} for the {theme} palette ...")
        render_theme(configuration, staged, theme, name)
        if not arguments.install:
            logger.info("Rendered only; pass --install to copy it into place.")
            return 0
        return 0 if install_theme(
            staged, name, prompt=True, rebuild=arguments.rebuild
        ) else 1
    finally:
        shutil.rmtree(staged, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
