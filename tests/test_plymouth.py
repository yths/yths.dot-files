"""The boot splash: rendered dark whatever the desktop does, and named for where it installs.

Two things here are easy to get wrong and invisible when they are. The splash is drawn before
anyone logs in, so it has no user whose light/dark preference could apply -- it is always
rendered from the dark palette, and `state.theme` describes a session that does not exist yet.

And `ImageDir` is an absolute path into the system theme directory, so it has to name the
directory `install_theme` is about to create. It did not: after the bundle was renamed from
`yths` to `default` the theme installed to `.../themes/default` while its INI still pointed at
`.../themes/yths`, which plymouth answers by drawing no images at all. Both the name and the
path are derived from the source directory now, so they cannot drift from it again.
"""

import configparser
import os
import pathlib
import re
import shutil

import patch_plymouth
import pytest
import symbols

PALETTE = {"background": "#322f2f", "foreground": "#d5d1d1", "neutral": "#afabab",
           "highlight": "#4d91c7"}
LIGHT = {"background": "#fffbfb", "foreground": "#4f4c4c", "neutral": "#8d8989",
         "highlight": "#4d91c7"}


@pytest.fixture
def configuration() -> dict:
    return {
        "name": "default",
        "state": {"theme": "light"},          # deliberately light: the splash must ignore it
        "palette": {"dark": PALETTE, "light": LIGHT},
        "font": {"family": "Iosevka NF", "size": 16},
    }


@pytest.fixture
def staged(tmp_path: pathlib.Path) -> pathlib.Path:
    """A staging directory holding a copy of the shipped theme's INI."""
    source = pathlib.Path("configuration/plymouth/themes/default/default.plymouth")
    destination = tmp_path / "default.plymouth"
    shutil.copyfile(source, destination)
    return tmp_path


def _ini(path: pathlib.Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read(path / "default.plymouth")
    return parser


def test_the_splash_is_rendered_dark(configuration: dict, staged: pathlib.Path) -> None:
    """`state.theme` is "light" in the fixture; the splash must not follow it."""
    patch_plymouth.render_configuration(
        configuration, str(staged), patch_plymouth.PALETTE_VARIANT, "default"
    )
    assert _ini(staged)["two-step"]["BackgroundStartColor"] == "0x322f2f"


def test_the_dark_variant_is_what_the_pipeline_asks_for() -> None:
    assert patch_plymouth.PALETTE_VARIANT == "dark"


def test_colours_are_written_the_way_plymouth_reads_them(
    configuration: dict, staged: pathlib.Path
) -> None:
    """0xrrggbb, not #rrggbb; plymouth silently ignores what it cannot parse."""
    patch_plymouth.render_configuration(configuration, str(staged), "dark", "default")
    two_step = _ini(staged)["two-step"]
    for key in ("BackgroundStartColor", "BackgroundEndColor", "ProgressBarBackgroundColor",
                "ConsoleLogTextColor", "ConsoleLogBackgroundColor"):
        assert two_step[key].startswith("0x"), key
        assert "#" not in two_step[key], key


def test_image_dir_names_where_the_theme_installs(
    configuration: dict, staged: pathlib.Path
) -> None:
    """The regression: a renamed preset left this pointing at the old directory."""
    patch_plymouth.render_configuration(configuration, str(staged), "dark", "somepreset")
    expected = os.path.join(patch_plymouth.SYSTEM_THEME_ROOT, "somepreset")
    assert _ini(staged)["two-step"]["ImageDir"] == expected


def test_the_theme_names_itself_after_its_directory(
    configuration: dict, staged: pathlib.Path
) -> None:
    patch_plymouth.render_configuration(configuration, str(staged), "dark", "somepreset")
    assert _ini(staged)["Plymouth Theme"]["Name"] == "somepreset"


def test_the_fonts_scale_from_the_configured_size(
    configuration: dict, staged: pathlib.Path
) -> None:
    patch_plymouth.render_configuration(configuration, str(staged), "dark", "default")
    two_step = _ini(staged)["two-step"]
    assert two_step["Font"] == "Iosevka NF 20"            # 16 * 1.25
    assert two_step["MonospaceFont"] == "Iosevka NF 14"   # 16 * 0.85


def test_a_missing_ini_is_named_rather_than_guessed(
    configuration: dict, tmp_path: pathlib.Path
) -> None:
    """The INI is found by glob, because the staging directory's name is not the theme's."""
    with pytest.raises(FileNotFoundError, match=re.escape("no .plymouth file")):
        patch_plymouth.render_configuration(configuration, str(tmp_path), "dark", "default")


def test_a_preset_without_a_splash_is_not_an_error(configuration: dict) -> None:
    configuration["name"] = "a-preset-that-ships-none"
    assert patch_plymouth.theme_source(configuration) is None


def test_the_shipped_preset_has_a_splash(configuration: dict) -> None:
    assert patch_plymouth.theme_source(configuration) is not None


def test_staging_refuses_a_dangling_wallpaper_link(tmp_path: pathlib.Path) -> None:
    """background-tile.png links to the active wallpaper, which install.py creates. Copying a
    dangling link produces a theme that boots to nothing, so it is refused with the fix."""
    source = tmp_path / "theme"
    source.mkdir()
    (source / "default.plymouth").write_text("[two-step]\n")
    os.symlink(tmp_path / "no-such-wallpaper.png", source / "background-tile.png")
    with pytest.raises(FileNotFoundError, match=re.escape("install.py")):
        patch_plymouth.stage_theme(str(source))


def test_staging_copies_rather_than_rendering_in_place(tmp_path: pathlib.Path) -> None:
    """Rendering in place would rewrite tracked files on every run."""
    source = tmp_path / "theme"
    source.mkdir()
    (source / "default.plymouth").write_text("[two-step]\nFont=original\n")
    staged = patch_plymouth.stage_theme(str(source))
    try:
        assert staged != str(source)
        (pathlib.Path(staged) / "default.plymouth").write_text("[two-step]\nFont=changed\n")
        assert "original" in (source / "default.plymouth").read_text()
    finally:
        shutil.rmtree(staged, ignore_errors=True)


# --------------------------------------------------------------- the themeable messages
#
# Until the symbol vocabulary existed these were the one part of the splash a theme could not
# reach: the patcher rewrote the fonts and colours around them and left the words in the
# checked-in INI, so every bundle booted to the same seven titles.


def test_every_mode_gets_its_title_and_subtitle_from_the_vocabulary(
    configuration: dict, staged: pathlib.Path
) -> None:
    patch_plymouth.render_configuration(
        configuration, str(staged), patch_plymouth.PALETTE_VARIANT, "default"
    )
    parser = _ini(staged)
    _, strings = symbols.resolve(configuration)
    for section, prefix in symbols.PLYMOUTH_SECTIONS.items():
        assert parser[section]["Title"] == strings[f"plymouth.{prefix}.title"]
        assert parser[section]["SubTitle"] == strings[f"plymouth.{prefix}.subtitle"]


def test_a_theme_can_change_one_message_without_touching_the_rest(
    configuration: dict, staged: pathlib.Path
) -> None:
    configuration["strings"] = {"plymouth.reboot.title": "See you shortly."}
    patch_plymouth.render_configuration(
        configuration, str(staged), patch_plymouth.PALETTE_VARIANT, "default"
    )
    parser = _ini(staged)
    assert parser["reboot"]["Title"] == "See you shortly."
    assert parser["boot-up"]["Title"] == symbols.STRINGS["plymouth.boot.title"]


# optionxform is off, so `Subtitle` and `SubTitle` are two keys rather than one. Writing the
# wrong capital leaves the original in place and adds a second the splash never reads.
def test_the_subtitle_spelling_is_plymouths(
    configuration: dict, staged: pathlib.Path
) -> None:
    patch_plymouth.render_configuration(
        configuration, str(staged), patch_plymouth.PALETTE_VARIANT, "default"
    )
    for section in symbols.PLYMOUTH_SECTIONS:
        keys = [key for key in _ini(staged)[section] if key.lower() == "subtitle"]
        assert keys == ["SubTitle"], f"[{section}] ended up with {keys}"


def test_a_section_the_ini_does_not_carry_is_not_invented(
    configuration: dict, staged: pathlib.Path
) -> None:
    """The section list is plymouth's. Adding one declares a mode with no animation."""
    before = set(_ini(staged).sections())
    patch_plymouth.render_configuration(
        configuration, str(staged), patch_plymouth.PALETTE_VARIANT, "default"
    )
    assert set(_ini(staged).sections()) == before


# The splash is the one surface where a missing glyph is baked into a PNG rather than merely
# displayed, so it survives until the next theme switch.
def test_the_rendered_glyphs_come_from_the_vocabulary() -> None:
    declared = {key for *_rest, key in patch_plymouth.GLYPH_ASSETS}
    assert declared <= set(symbols.SYMBOLS), f"undeclared: {declared - set(symbols.SYMBOLS)}"
    for key in declared:
        assert symbols.SYMBOLS[key].isascii(), f"{key} falls back to a glyph, not ascii"
