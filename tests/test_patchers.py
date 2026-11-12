"""The five patchers that turn the palette into one application's configuration.

They read the real templates from this repository and write into a redirected HOME, so what
is exercised is the contract each app actually gets -- not a paraphrase of it.

Two behaviours here are not symmetric and are easy to break by making them so. `patch_rofi`
and `patch_xorg` need monitor geometry for a size they cannot invent, so with none they write
nothing at all; `patch_dunst` needs it only for its offset, so with none it still themes the
notifications. And `patch_xorg` resolves its DPI *before* opening `~/.Xresources`, because
opening first truncated the file and a failure while computing then left it empty -- and the
raise aborted `patch_all`, leaving every later app on the previous palette.
"""

import configparser
import os
import pathlib

import patch_dunst
import patch_rofi
import patch_starship
import patch_tmux
import patch_xorg
import pytest
import toml

PALETTE = {
    "background": "#322f2f", "foreground": "#d5d1d1", "foreground_variant": "#fffbfb",
    "neutral": "#afabab", "highlight": "#4d91c7", "notification": "#b66cac",
    "warning": "#c07726", "success": "#569c67", "failure": "#cd6869",
    "red": "#ffa3a4", "green": "#91dca0", "yellow": "#ffb565", "blue": "#95ceff",
    "magenta": "#f9a8ee", "cyan": "#71dbe0", "red_variant": "#cd6869",
    "green_variant": "#569c67", "yellow_variant": "#c07726", "blue_variant": "#4d91c7",
    "magenta_variant": "#b66cac", "cyan_variant": "#229ca0",
}

#: Two monitors with different DPI, so an average is distinguishable from either one.
MONITORS = {
    "HDMI-0": {"diagonal_dpi": 160.0, "width": 3840, "scaling_factor": 1.6},
    "HDMI-1": {"diagonal_dpi": 140.0, "width": 2560, "scaling_factor": 1.4},
}


@pytest.fixture
def configuration() -> dict:
    return {
        "name": "default",
        "state": {"theme": "dark"},
        "palette": {"dark": PALETTE},
        "font": {"family": "Iosevka NF", "size": 14},
        "monitors": {name: dict(values) for name, values in MONITORS.items()},
    }


@pytest.fixture
def home(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    """A HOME the patchers can write into, with the directories they expect."""
    root = tmp_path / "home"
    for directory in ("rofi", "tmux", "dunst"):
        (root / ".config" / directory).mkdir(parents=True)
    monkeypatch.setenv("HOME", str(root))
    return root


# ------------------------------------------------------------------------------ xorg

def test_xorg_writes_the_average_dpi(configuration: dict, home: pathlib.Path) -> None:
    patch_xorg.patch_xorg(configuration)
    assert (home / ".Xresources").read_text() == "Xft.dpi: 150\n"


def test_xorg_leaves_the_file_alone_without_geometry(
    configuration: dict, home: pathlib.Path
) -> None:
    """The regression: computing after opening truncated ~/.Xresources on the way to failing."""
    existing = home / ".Xresources"
    existing.write_text("Xft.dpi: 96\n")
    configuration["monitors"] = {}
    patch_xorg.patch_xorg(configuration)
    assert existing.read_text() == "Xft.dpi: 96\n"


# ------------------------------------------------------------------------------ rofi

def test_rofi_writes_the_palette_and_the_scaled_width(
    configuration: dict, home: pathlib.Path
) -> None:
    patch_rofi.patch_rofi(configuration)
    written = (home / ".config" / "rofi" / "theme_config.rasi").read_text()
    assert f"COLOR0: {PALETTE['background']};" in written
    assert f"COLOR4: {PALETTE['highlight']};" in written
    assert "WIDTH: 3200px;" in written          # the mean of 3840 and 2560
    assert '"Iosevka NF 17"' in written         # 14 * 1.214, rounded


def test_rofi_writes_nothing_without_geometry(
    configuration: dict, home: pathlib.Path
) -> None:
    """A launcher sized for nothing is worse than the one already installed."""
    configuration["monitors"] = {}
    patch_rofi.patch_rofi(configuration)
    assert not (home / ".config" / "rofi" / "theme_config.rasi").exists()


# ------------------------------------------------------------------------------ tmux

def test_tmux_writes_the_palette_at_the_top(configuration: dict, home: pathlib.Path) -> None:
    patch_tmux.patch_tmux(configuration)
    lines = (home / ".config" / "tmux" / "tmux.conf").read_text().splitlines()
    assert lines[:4] == [
        f"color0={PALETTE['background']}",
        f"color1={PALETTE['neutral']}",
        f"color2={PALETTE['highlight']}",
        f"color3={PALETTE['foreground']}",
    ]


def test_tmux_keeps_the_hand_written_lines(configuration: dict, home: pathlib.Path) -> None:
    patch_tmux.patch_tmux(configuration)
    written = (home / ".config" / "tmux" / "tmux.conf").read_text()
    template = pathlib.Path("configuration/tmux/tmux.conf.template").read_text()
    kept = [line for line in template.splitlines() if line and not line.startswith("color")]
    assert kept, "the template has nothing but colours; this test would prove nothing"
    for line in kept:
        assert line in written


def test_tmux_does_not_leave_the_templates_own_colours_behind(
    configuration: dict, home: pathlib.Path
) -> None:
    """The template still carries the colours it was cut from; two sets would be ambiguous."""
    patch_tmux.patch_tmux(configuration)
    written = (home / ".config" / "tmux" / "tmux.conf").read_text()
    assert written.count("color0=") == 1


# ------------------------------------------------------------------------------ starship

def test_starship_replaces_the_five_palette_entries(
    configuration: dict, home: pathlib.Path
) -> None:
    patch_starship.patch_starship(configuration)
    written = toml.loads((home / ".config" / "starship.toml").read_text())
    assert written["palettes"]["theme"] == {
        "color0": PALETTE["foreground"],
        "color1": PALETTE["foreground_variant"],
        "color2": PALETTE["success"],
        "color3": PALETTE["failure"],
        "color4": PALETTE["highlight"],
    }


def test_starship_keeps_every_other_prompt_setting(
    configuration: dict, home: pathlib.Path
) -> None:
    patch_starship.patch_starship(configuration)
    template = toml.loads(pathlib.Path("configuration/starship/starship.toml.template").read_text())
    written = toml.loads((home / ".config" / "starship.toml").read_text())
    for key in template:
        if key != "palettes":
            assert written[key] == template[key], f"{key} was not preserved"


# ------------------------------------------------------------------------------ dunst

def _dunstrc(home: pathlib.Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(home / ".config" / "dunst" / "dunstrc")
    return parser


def test_dunst_writes_the_palette_and_font(configuration: dict, home: pathlib.Path) -> None:
    patch_dunst.patch_dunst(configuration)
    written = _dunstrc(home)
    assert written["global"]["foreground"] == f'"{PALETTE["foreground"]}"'
    assert written["global"]["background"] == f'"{PALETTE["background"]}"'
    assert written["global"]["font"] == '"Iosevka NF 10"'      # 14 * 0.714, rounded


def test_dunst_colours_each_urgency_from_its_own_token(
    configuration: dict, home: pathlib.Path
) -> None:
    patch_dunst.patch_dunst(configuration)
    written = _dunstrc(home)
    assert PALETTE["notification"] in written["urgency_normal"]["format"]
    assert PALETTE["warning"] in written["urgency_critical"]["format"]
    assert PALETTE["neutral"] in written["urgency_low"]["format"]


def test_dunst_still_themes_without_geometry(configuration: dict, home: pathlib.Path) -> None:
    """Unlike rofi and xorg: only the offset needs a monitor, so the rest still applies."""
    configuration["monitors"] = {}
    patch_dunst.patch_dunst(configuration)
    written = _dunstrc(home)
    assert written["global"]["foreground"] == f'"{PALETTE["foreground"]}"'
    template = configparser.ConfigParser(interpolation=None)
    template.read("configuration/dunst/dunstrc.template")
    assert written["global"].get("offset") == template["global"].get("offset")


def test_dunst_offset_scales_with_the_monitors(configuration: dict, home: pathlib.Path) -> None:
    patch_dunst.patch_dunst(configuration)
    assert _dunstrc(home)["global"]["offset"] == "0x63"        # 14 * 1.5 * 3, rounded


def test_no_patcher_writes_outside_home(configuration: dict, home: pathlib.Path) -> None:
    """Every one of these targets ~/.config; a stray absolute path would escape the fixture."""
    for patch in (patch_xorg.patch_xorg, patch_rofi.patch_rofi, patch_tmux.patch_tmux,
                  patch_starship.patch_starship, patch_dunst.patch_dunst):
        patch(configuration)
    written = {p for p in home.rglob("*") if p.is_file()}
    assert written, "the fixture caught nothing, so it is proving nothing"
    for path in written:
        assert os.path.commonpath([str(path), str(home)]) == str(home)
