"""The login screen's generated stylesheet.

`patch_web_greeter` writes into `configuration/web-greeter/themes/`, which is the installed
login screen -- so these exercise `theme_variables` and `render_theme_css` rather than calling
the patcher, which would leave the real greeter showing a test's palette.

The role map is the point of the design: a theme names its own roles in `theme.json` and maps
them onto palette tokens, so a second theme can use the same palette differently without this
patcher knowing anything about it.
"""

import json
import pathlib
import pickle

import patch_web_greeter
import pytest

PALETTE = {"background": "#322f2f", "foreground": "#d5d1d1", "highlight": "#4d91c7",
           "neutral": "#afabab", "failure": "#cd6869"}


@pytest.fixture
def configuration() -> dict:
    return {
        "state": {"theme": "dark"},
        "palette": {"dark": PALETTE, "light": {**PALETTE, "background": "#fffbfb"}},
        "font": {"family": "Iosevka NF", "size": 14},
        "wallpapers": {"dark": "~/.config/qtile/wallpaper-dark.png"},
    }


def test_each_role_takes_the_token_the_theme_maps_it_to(configuration: dict) -> None:
    theme_json = {"role_map": {"surface": "background", "text": "foreground"}}
    variables = patch_web_greeter.theme_variables(configuration, theme_json, "wallpaper.png")
    assert variables["--surface"] == PALETTE["background"]
    assert variables["--text"] == PALETTE["foreground"]


def test_two_roles_may_share_one_token(configuration: dict) -> None:
    """Nothing requires the map to be injective, and the standard theme relies on that."""
    theme_json = {"role_map": {"surface": "background", "border": "background"}}
    variables = patch_web_greeter.theme_variables(configuration, theme_json, "w.png")
    assert variables["--surface"] == variables["--border"] == PALETTE["background"]


def test_switching_theme_switches_the_login_screen(configuration: dict) -> None:
    theme_json = {"role_map": {"surface": "background"}}
    dark = patch_web_greeter.theme_variables(configuration, theme_json, "w.png")
    configuration["state"]["theme"] = "light"
    light = patch_web_greeter.theme_variables(configuration, theme_json, "w.png")
    assert dark["--surface"] != light["--surface"]


def test_the_font_comes_from_the_configuration(configuration: dict) -> None:
    variables = patch_web_greeter.theme_variables(configuration, {"role_map": {}}, "w.png")
    assert variables["--font-family"] == '"Iosevka NF"'
    assert variables["--font-size"] == "14px"


def test_a_theme_may_override_the_font(configuration: dict) -> None:
    theme_json = {"role_map": {}, "font_overrides": {"size": 22}}
    variables = patch_web_greeter.theme_variables(configuration, theme_json, "w.png")
    assert variables["--font-size"] == "22px"
    assert variables["--font-family"] == '"Iosevka NF"', "an override must not clear the rest"


def test_the_wallpaper_is_referenced_relatively(configuration: dict) -> None:
    """The theme is copied into a root-owned directory, so an absolute path into a home
    directory would resolve to nothing once installed."""
    variables = patch_web_greeter.theme_variables(configuration, {"role_map": {}}, "wallpaper.png")
    assert variables["--wallpaper-url"] == 'url("wallpaper.png")'
    assert "/" not in variables["--wallpaper-url"].strip('url("')


def test_the_stylesheet_is_a_root_block() -> None:
    css = patch_web_greeter.render_theme_css({"--surface": "#322f2f", "--text": "#d5d1d1"})
    assert css == ':root {\n    --surface: #322f2f;\n    --text: #d5d1d1;\n}\n'


def test_the_shipped_theme_maps_only_tokens_the_palette_has(configuration: dict) -> None:
    """A role mapped to a token no bundle carries is a KeyError at the login screen, where
    there is nothing to read the traceback."""
    with open("assets/default/palette.pkl", "rb") as handle:
        palette = pickle.load(handle)
    for name in patch_web_greeter.available_themes():
        path = pathlib.Path(patch_web_greeter.THEME_SOURCE_ROOT) / name / "theme.json"
        for role, token in json.loads(path.read_text())["role_map"].items():
            assert token in palette["dark"], f"{name}: --{role} maps to a missing {token!r}"


def test_available_themes_skips_the_shared_assets() -> None:
    """`_shared` is copied into each theme, not offered as one."""
    themes = patch_web_greeter.available_themes()
    assert themes, "no themes found at all; the source root has moved"
    assert not any(name.startswith("_") for name in themes)


def test_the_default_theme_is_one_that_exists() -> None:
    assert patch_web_greeter.DEFAULT_THEME in patch_web_greeter.available_themes()
