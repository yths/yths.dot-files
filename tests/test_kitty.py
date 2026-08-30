"""kitty's configuration: one generated file that applies itself.

Two defects are pinned here. The patcher used to write a kitty.conf with no theme in it and
no `include` either, leaving kitty unthemed until `kitty +kitten themes` ran and put the
`include` back -- so any path that patched without a full theme switch (a monitor hotplug,
running the patcher on its own) left the terminal on kitty's own defaults. And the kitten,
when it did run, backed kitty.conf up to kitty.conf.bak inside the repository.
"""

import inspect
import pathlib

import patch_configurations
import patch_kitty
import pytest

PALETTE = {
    "background": "#322f2f", "foreground": "#d5d1d1", "foreground_variant": "#fffbfb",
    "neutral": "#afabab",
    "red": "#ffa3a4", "green": "#91dca0", "yellow": "#ffb565", "blue": "#95ceff",
    "magenta": "#f9a8ee", "cyan": "#71dbe0",
    "red_variant": "#cd6869", "green_variant": "#569c67", "yellow_variant": "#c07726",
    "blue_variant": "#4d91c7", "magenta_variant": "#b66cac", "cyan_variant": "#229ca0",
}


@pytest.fixture
def configuration() -> dict:
    return {
        "name": "default",
        "state": {"theme": "dark"},
        "palette": {"dark": PALETTE},
        "font": {"family": "Iosevka NF", "size": 14},
    }


def test_the_palette_is_in_kitty_conf_itself(configuration: dict) -> None:
    """The regression: the colours must not need a second file to be reachable."""
    settings = patch_kitty.kitty_configuration(configuration)
    assert settings["background"] == PALETTE["background"]
    assert all(f"color{slot}" in settings for slot in range(16))
    assert "include" not in settings


def test_kitty_is_told_to_reload_the_file_it_is_given(configuration: dict) -> None:
    """Writing the file is the only reload there is, so this setting must be in it."""
    assert float(patch_kitty.kitty_configuration(configuration)["auto_reload_config"]) > 0


def test_all_sixteen_slots_are_distinct_from_their_bright_pair(configuration: dict) -> None:
    settings = patch_kitty.kitty_configuration(configuration)
    for slot in range(8):
        assert settings[f"color{slot}"] != settings[f"color{slot + 8}"]


def test_black_and_white_stay_legible_on_this_background(configuration: dict) -> None:
    """Slots 0 and 7 are the palette's own extremes, not true black and white."""
    settings = patch_kitty.kitty_configuration(configuration)
    assert settings["color0"] == PALETTE["foreground_variant"]
    assert settings["color7"] == PALETTE["background"]
    assert "#000000" not in settings.values()


def test_switching_theme_switches_every_colour(configuration: dict) -> None:
    dark = patch_kitty.kitty_configuration(configuration)
    configuration["palette"]["light"] = {**PALETTE, "background": "#fffbfb"}
    configuration["state"]["theme"] = "light"
    assert patch_kitty.kitty_configuration(configuration)["background"] != dark["background"]


def test_the_patcher_writes_one_file_and_no_backup(configuration: dict, tmp_path: pathlib.Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    """The other defect: nothing may leave a .bak or a second theme file in the repository."""
    home = tmp_path / "home"
    (home / ".config" / "kitty").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    patch_kitty.patch_kitty(configuration)
    written = sorted(p.name for p in (home / ".config" / "kitty").rglob("*"))
    assert written == ["kitty.conf"]


def test_nothing_calls_the_themes_kitten() -> None:
    """The kitten is what created kitty.conf.bak; the reload must not reach for it again."""
    source = inspect.getsource(patch_configurations)
    called = [line for line in source.splitlines()
              if "kitten" in line and not line.lstrip().startswith("#")]
    assert called == []


def test_kitty_is_still_patched_on_a_theme_switch() -> None:
    """Dropping the reload call must not drop the patcher along with it."""
    assert "kitty" in dict(patch_configurations.PATCHERS)
