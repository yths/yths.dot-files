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
import shutil
import subprocess

import patch_web_greeter
import pytest
import symbols
import utils

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


# ------------------------------------------------- the desktop vocabulary under the theme
#
# The login screen had its own symbols and strings before the rest of the desktop did, and
# they stay: its three-layer fallback (inline HTML, a CSS var() default, `|| "..."` in JS)
# works when JavaScript never runs, which nothing else here can claim. What changes is where
# the *base* comes from -- the bundle, so an icon shared with the bar is named once.


def test_the_vocabulary_is_namespaced_for_the_greeter(configuration: dict) -> None:
    vocabulary = patch_web_greeter.theme_vocabulary(configuration)
    assert "shutdown" in vocabulary["symbols"], "greeter.* should arrive without its prefix"
    assert "auth_failed" in vocabulary["strings"]
    # The bar's entries must not leak in: theme.json's keys are unprefixed, so a stray
    # `battery.charging` would sit beside the greeter's own `battery_charging` and confuse
    # whichever of the two a reader found first.
    assert not any("." in key for key in vocabulary["symbols"])
    assert not any("." in key for key in vocabulary["strings"])


def test_the_greeter_theme_still_has_the_last_word() -> None:
    """vocabulary.json is the base; theme.json is merged over it in _shared/logic.js."""
    logic = (
        pathlib.Path(patch_web_greeter.THEME_SOURCE_ROOT) / "_shared" / "logic.js"
    ).read_text()
    merge = logic[logic.index("async function load_theme_config"):]
    merge = merge[: merge.index("\n    }")]
    assert "vocabulary.json" in merge and "theme.json" in merge
    # The spread order is the whole contract: vocabulary first, theme second.
    assert merge.index("(vocabulary || {}).symbols") < merge.index("(theme || {}).symbols")
    assert merge.index("(vocabulary || {}).strings") < merge.index("(theme || {}).strings")


def test_a_theme_that_names_no_symbols_inherits_the_desktops(configuration: dict) -> None:
    vocabulary = patch_web_greeter.theme_vocabulary(configuration)
    assert vocabulary["symbols"]["shutdown"] == symbols.SYMBOLS["greeter.shutdown"]


def test_the_vocabulary_falls_back_to_ascii(configuration: dict) -> None:
    """A bundle carrying no overrides must still give the login screen something to draw."""
    configuration.pop("symbols", None)
    vocabulary = patch_web_greeter.theme_vocabulary(configuration)
    assert vocabulary["symbols"]
    assert all(value.isascii() for value in vocabulary["symbols"].values())
    assert all(value.isascii() for value in vocabulary["strings"].values())


# The login screen installs under the active theme's name, and once LightDM is pointed at it,
# the ones this repository installed for earlier themes go -- but never the package's own.
def test_the_login_screen_installs_under_the_theme_name_and_replaces_earlier_ones(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "themes"
    for name, ours in (("earlier", True), ("simple", False)):
        (root / name).mkdir(parents=True)
        if ours:
            (root / name / utils.INSTALL_MARKER).write_text("")
    copied, activated = [], []

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        if argv[0] == "cp":
            copied.append(argv[-1])
        if argv[0] == "rm":
            shutil.rmtree(argv[-1])
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(patch_web_greeter, "SYSTEM_THEME_ROOT", str(root))
    monkeypatch.setattr(patch_web_greeter, "root_prefix", lambda **_kwargs: [])
    monkeypatch.setattr(patch_web_greeter.subprocess, "run", run)
    monkeypatch.setattr(
        patch_web_greeter, "activate", lambda name, _prefix: activated.append(name) or True
    )

    assert patch_web_greeter.install_theme(
        patch_web_greeter.DEFAULT_THEME, "autumn-default", make_active=True
    )
    assert copied == [str(root / "autumn-default")]
    assert activated == ["autumn-default"]
    assert sorted(path.name for path in root.iterdir()) == ["simple"]


def test_the_installed_name_is_the_theme_name_made_safe() -> None:
    assert utils.installed_theme_name({"name": "Autumn Default"}) == "autumn-default"
    assert utils.installed_theme_name({"name": "../etc"}) == "etc"
    assert utils.installed_theme_name({}) == "dot-files"
