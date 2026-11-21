"""Recolouring qutebrowser from its own stock defaults.

The browser themed itself before this existed: `config.py` read the palette at startup and
indexed it for twenty-eight colours chosen by hand, which left seventy-seven of its
hundred-and-five colour settings stock. Naming those seventy-seven by hand is the work the
patcher avoids -- it reads the value qutebrowser itself would use out of the stock dump and
replaces it with the nearest colour the palette has.

What has to hold is that the *parse* is exhaustive and the *classification* is honest. A
setting the regex misses, or a value wrongly judged not-a-colour, is a surface that silently
stays stock -- which is indistinguishable from one the theme chose to leave alone.
"""

import json
import pathlib

import color_match
import patch_qutebrowser
import pytest

PALETTE = {
    "dark": {"background": "#322f2f", "foreground": "#d5d1d1", "neutral": "#afabab",
             "highlight": "#4d91c7", "warning": "#958e28", "failure": "#cd6869",
             "success": "#569c67", "notification": "#c07726"},
}
PALETTE["light"] = PALETTE["dark"]


#: What the theme derives from the palette rather than takes from it: the inactive tabs'
#: blocks, mixed between two tokens, and the selected tab's font, which is not a colour.
DERIVED = {
    *(f"c.colors.tabs.{kind}.bg" for kind in patch_qutebrowser.INACTIVE_TABS),
    "c.fonts.tabs.selected",
}


@pytest.fixture
def configuration() -> dict:
    return {"state": {"theme": "dark"}, "palette": PALETTE}


@pytest.fixture(scope="module")
def source() -> str:
    return patch_qutebrowser.stock_source()


# ------------------------------------------------------------------------- the parse


def test_every_colour_setting_in_the_dump_is_found(source: str) -> None:
    """105 is what qutebrowser ships; a regex that found 104 would look like a theme choice."""
    defaults = patch_qutebrowser.stock_defaults(source)
    assert len(defaults) == 105
    assert all(name.startswith("c.colors.") for name in defaults)


def test_the_parse_recovers_values_not_just_names(source: str) -> None:
    defaults = patch_qutebrowser.stock_defaults(source)
    assert defaults["c.colors.statusbar.normal.bg"] == "black"
    assert defaults["c.colors.completion.item.selected.bg"] == "#e8c000"
    assert defaults["c.colors.completion.fg"] == ["white", "white", "white"]
    assert defaults["c.colors.contextmenu.menu.bg"] is None
    assert defaults["c.colors.webpage.darkmode.threshold.foreground"] == 256


# A name the regex cannot see is a setting that silently stays stock. The character class has
# to allow digits: one qutebrowser setting has one in its name.
def test_the_name_pattern_allows_a_digit() -> None:
    found = patch_qutebrowser.SETTING.findall("# c.colors.x2.y = 'white'\n")
    assert found == [("c.colors.x2.y", "'white'")]


# ------------------------------------------------------------------- the classification


def test_the_settings_left_stock_are_the_ones_that_are_not_colours(source: str) -> None:
    left = patch_qutebrowser.unmapped(source)
    assert len(left) == 23
    for name, value in left.items():
        assert color_match.to_rgb(value) is None or isinstance(value, list), name


@pytest.mark.parametrize(
    "name",
    [
        "c.colors.completion.category.bg",      # qlineargradient(...)
        "c.colors.hints.bg",                    # qlineargradient(...)
        "c.colors.keyhint.bg",                  # rgba(0, 0, 0, 80%)
        "c.colors.prompts.border",              # '1px solid gray', a QSS shorthand
        "c.colors.contextmenu.menu.bg",         # None: let Qt decide
        "c.colors.downloads.system.bg",         # 'rgb', a ColorSystem enum
        "c.colors.webpage.darkmode.enabled",    # a bool
        "c.colors.webpage.darkmode.contrast",   # a float
    ],
)
def test_a_value_that_is_not_a_colour_is_left_alone(source: str, name: str) -> None:
    assert name in patch_qutebrowser.unmapped(source)


# `colors.completion.fg` is one entry per completion column. Replacing the list with a single
# colour would collapse three columns into one.
def test_a_list_of_colours_is_mapped_element_wise(configuration: dict) -> None:
    settings = patch_qutebrowser.theme_settings(configuration, "dark")
    assert isinstance(settings["c.colors.completion.fg"], list)
    assert len(settings["c.colors.completion.fg"]) == 3


def test_named_colours_are_mapped_not_skipped(configuration: dict) -> None:
    """62 of the stock defaults are CSS names; skipping them leaves most of the browser stock."""
    settings = patch_qutebrowser.theme_settings(configuration, "dark")
    assert settings["c.colors.statusbar.normal.bg"].startswith("#")
    assert settings["c.colors.statusbar.caret.bg"].startswith("#")


def test_every_emitted_value_is_a_palette_colour(configuration: dict) -> None:
    palette = set(PALETTE["dark"].values())
    settings = patch_qutebrowser.theme_settings(configuration, "dark")
    assert settings.pop("c.hints.border").split()[-1] in palette
    for name, value in settings.items():
        if name in DERIVED:
            continue
        for entry in value if isinstance(value, list) else [value]:
            assert entry in palette, f"{name} = {entry!r} is not in the palette"


# ------------------------------------------------------------------------- legibility
#
# Each colour is matched on its own, so a text colour and the surface under it can land on
# one token. This palette reproduces the defect as reported: the even tabs' stock `white`
# (fg) and `darkgrey` (bg) are both nearest the light background grey, which drew the
# inactive even tabs' titles invisible.

LIGHT_PALETTE = {
    "light": {"background": "#e3e3e3", "foreground": "#0f0f0f", "neutral": "#717171",
              "highlight": "#007c9a", "warning": "#a25e39", "failure": "#9f5972",
              "success": "#567e3f", "notification": "#886f1b",
              "foreground_variant": "#000000"},
}
LIGHT_PALETTE["dark"] = LIGHT_PALETTE["light"]


@pytest.fixture
def light_configuration() -> dict:
    return {"state": {"theme": "light"}, "palette": LIGHT_PALETTE}


def test_the_light_palette_would_collapse_the_even_tabs_without_the_second_look() -> None:
    """The defect this guards against: both halves of the pair map to one token."""
    candidates = color_match.build_palette_map(LIGHT_PALETTE)["light"]
    assert color_match.nearest("white", candidates).hex == "#e3e3e3"
    assert color_match.nearest("darkgrey", candidates).hex == "#e3e3e3"


def test_a_tab_title_reads_on_the_tab_under_it(light_configuration: dict) -> None:
    settings = patch_qutebrowser.theme_settings(light_configuration, "light")
    ratio = color_match.contrast(
        settings["c.colors.tabs.even.fg"], settings["c.colors.tabs.even.bg"]
    )
    assert ratio >= color_match.MIN_TEXT_CONTRAST


def test_no_fg_lands_on_its_own_bg(light_configuration: dict) -> None:
    settings = patch_qutebrowser.theme_settings(light_configuration, "light")
    for name, value in settings.items():
        if not name.endswith(".fg") or not isinstance(value, str):
            continue
        surface = settings.get(name[: -len(".fg")] + ".bg")
        if isinstance(surface, str):
            assert value != surface, f"{name} vanished into its surface {value!r}"


#: Both modes of one palette: what the hints, the tabs and the reference match are tried on.
TWO_MODE_PALETTE = {
    "dark": {"background": "#0f0f0f", "foreground": "#e3e3e3", "neutral": "#717171",
             "highlight": "#007c9a", "warning": "#a25e39", "failure": "#9f5972",
             "success": "#567e3f", "notification": "#886f1b",
             "foreground_variant": "#ffffff"},
    "light": {"background": "#e3e3e3", "foreground": "#0f0f0f", "neutral": "#717171",
              "highlight": "#007c9a", "warning": "#a25e39", "failure": "#9f5972",
              "success": "#567e3f", "notification": "#886f1b",
              "foreground_variant": "#000000"},
}


# --------------------------------------------------------------------------- the hints
#
# hints.bg is a gradient, so it used to stay qutebrowser's yellow while hints.fg followed the
# palette: stock `black` is the *background* token, which in light mode is a light grey, on
# yellow. The three hint colours are now declared together.


def hint_contrast(settings: dict, name: str = "c.colors.hints.fg") -> float:
    return color_match.contrast(settings[name], settings["c.colors.hints.bg"])


@pytest.mark.parametrize("mode", ["dark", "light"])
def test_a_hint_reads_on_its_own_plate(mode: str) -> None:
    configuration = {"state": {"theme": mode}, "palette": TWO_MODE_PALETTE}
    settings = patch_qutebrowser.theme_settings(configuration, mode)
    assert settings["c.colors.hints.bg"] in TWO_MODE_PALETTE[mode].values()
    assert hint_contrast(settings) >= color_match.MIN_TEXT_CONTRAST
    assert hint_contrast(settings, "c.colors.hints.match.fg") >= patch_qutebrowser.MIN_BOLD_CONTRAST


@pytest.mark.parametrize("mode", ["dark", "light"])
def test_the_typed_part_of_a_hint_stays_distinct(mode: str) -> None:
    configuration = {"state": {"theme": mode}, "palette": TWO_MODE_PALETTE}
    settings = patch_qutebrowser.theme_settings(configuration, mode)
    matched = settings["c.colors.hints.match.fg"]
    assert matched not in (settings["c.colors.hints.fg"], settings["c.colors.hints.bg"])


def test_the_hint_border_is_drawn_in_the_hint_text_colour() -> None:
    """A white plate on a white page is otherwise only its letters."""
    configuration = {"state": {"theme": "dark"}, "palette": TWO_MODE_PALETTE}
    settings = patch_qutebrowser.theme_settings(configuration, "dark")
    assert settings["c.hints.border"] == f"1px solid {settings['c.colors.hints.fg']}"


# ---------------------------------------------------------------------------- the tabs
#
# The tabs are the qtile task list one level down, so they are drawn by its scheme rather
# than matched from qutebrowser's stock greys and greens: the bar is `background`, the
# selected tab a `highlight` block with `background` text, and every other tab `foreground`
# text on a block between `background` and `neutral`.


def tabs(mode: str, palette: dict = TWO_MODE_PALETTE) -> dict:
    settings = patch_qutebrowser.theme_settings({"state": {"theme": mode}, "palette": palette}, mode)
    return {
        name.removeprefix("c.colors.tabs."): value
        for name, value in settings.items() if name.startswith("c.colors.tabs.")
    }


def _saturation(colour: str) -> int:
    channels = [int(colour[index : index + 2], 16) for index in (1, 3, 5)]
    return max(channels) - min(channels)


@pytest.mark.parametrize("mode", ["dark", "light"])
def test_the_selected_tab_and_the_bar_are_the_task_lists(mode: str) -> None:
    palette, drawn = TWO_MODE_PALETTE[mode], tabs(mode)
    assert drawn["bar.bg"] == palette["background"]
    for kind in patch_qutebrowser.ACTIVE_TABS:
        assert drawn[f"{kind}.bg"] == palette["highlight"]
        assert drawn[f"{kind}.fg"] == palette["background"]


# Neutral means on the line between two greys: with this palette, no hue at all.
@pytest.mark.parametrize("mode", ["dark", "light"])
def test_an_inactive_tab_is_never_a_colour(mode: str) -> None:
    drawn = tabs(mode)
    for kind in patch_qutebrowser.INACTIVE_TABS:
        assert _saturation(drawn[f"{kind}.bg"]) == 0, kind
        assert drawn[f"{kind}.fg"] == TWO_MODE_PALETTE[mode]["foreground"]


# There is no gap between tabs, so the four kinds have to differ -- from each other and from
# the bar -- and each steps further from the bar than the one before it.
@pytest.mark.parametrize("mode", ["dark", "light"])
def test_the_inactive_tabs_step_away_from_the_bar_and_stay_legible(mode: str) -> None:
    palette, drawn = TWO_MODE_PALETTE[mode], tabs(mode)
    surfaces = [drawn[f"{kind}.bg"] for kind in patch_qutebrowser.INACTIVE_TABS]
    from_bar = [color_match.contrast(surface, palette["background"]) for surface in surfaces]
    assert from_bar == sorted(from_bar)
    assert from_bar[0] > 1
    assert len(set(surfaces)) == len(surfaces)
    for surface in surfaces:
        assert color_match.contrast(palette["foreground"], surface) >= color_match.MIN_TEXT_CONTRAST


# The furthest tab sits where the title is about to stop reading; a step past it does not.
@pytest.mark.parametrize("mode", ["dark", "light"])
def test_the_reach_is_the_last_weight_at_which_the_title_reads(mode: str) -> None:
    palette = TWO_MODE_PALETTE[mode]
    reach = patch_qutebrowser.legible_reach(
        palette["background"], palette["neutral"], palette["foreground"]
    )
    assert 0 < reach < 1
    beyond = color_match.mix(palette["background"], palette["neutral"], reach + 0.01)
    assert color_match.contrast(palette["foreground"], beyond) < color_match.MIN_TEXT_CONTRAST


def test_a_selected_title_short_of_body_contrast_is_set_bold() -> None:
    palette = color_match.build_palette_map(TWO_MODE_PALETTE)["dark"]
    assert color_match.contrast("#0f0f0f", "#007c9a") < color_match.MIN_TEXT_CONTRAST
    assert patch_qutebrowser.tab_settings(palette)["c.fonts.tabs.selected"].startswith("bold ")

    strong = {**TWO_MODE_PALETTE["dark"], "highlight": "#86bace"}
    palette = color_match.build_palette_map({"dark": strong, "light": strong})["dark"]
    assert "c.fonts.tabs.selected" not in patch_qutebrowser.tab_settings(palette)


def test_the_load_stripe_ends_in_the_tokens_named_for_it() -> None:
    drawn = tabs("dark")
    assert drawn["indicator.stop"] == TWO_MODE_PALETTE["dark"]["success"]
    assert drawn["indicator.error"] == TWO_MODE_PALETTE["dark"]["failure"]


# A palette without the tokens the scheme is built from keeps the plain match, not a crash.
def test_a_palette_without_the_scheme_tokens_falls_back_to_matching() -> None:
    sparse = {"background": "#0f0f0f", "foreground": "#e3e3e3"}
    palette = color_match.build_palette_map({"dark": sparse, "light": sparse})["dark"]
    assert patch_qutebrowser.tab_settings(palette) == {}
    assert tabs("dark", {"dark": sparse, "light": sparse})["bar.bg"] in sparse.values()


# ----------------------------------------------------------------------- the reference match
#
# qutebrowser's stock chrome is a dark one: black statusbar, dark completion popup. Matching
# it against the light palette preserves that lightness -- stock `black` lands on the light
# *foreground* -- so light mode shipped a dark browser. The defaults are therefore matched
# against the dark palette to decide the token, and written in the active mode's colours.



def test_light_mode_inverts_the_stock_dark_chrome() -> None:
    """Stock `black` is the *background* token, so light mode paints the statusbar light."""
    configuration = {"state": {"theme": "light"}, "palette": TWO_MODE_PALETTE}
    settings = patch_qutebrowser.theme_settings(configuration, "light")
    assert settings["c.colors.statusbar.normal.bg"] == "#e3e3e3"
    assert settings["c.colors.statusbar.normal.fg"] in ("#0f0f0f", "#000000")


def test_dark_mode_keeps_the_dark_chrome() -> None:
    configuration = {"state": {"theme": "dark"}, "palette": TWO_MODE_PALETTE}
    settings = patch_qutebrowser.theme_settings(configuration, "dark")
    assert settings["c.colors.statusbar.normal.bg"] == "#0f0f0f"


def test_every_light_value_comes_from_the_light_palette() -> None:
    """A dark hex in a light theme is the token lookup failing, not a theme choice."""
    configuration = {"state": {"theme": "light"}, "palette": TWO_MODE_PALETTE}
    palette = set(TWO_MODE_PALETTE["light"].values())
    settings = patch_qutebrowser.theme_settings(configuration, "light")
    assert settings.pop("c.hints.border").split()[-1] in palette
    for name, value in settings.items():
        if name in DERIVED:
            continue
        for entry in value if isinstance(value, list) else [value]:
            assert entry in palette, f"{name} = {entry!r} is not in the light palette"


@pytest.mark.parametrize("mode", ["dark", "light"])
def test_a_page_without_a_background_gets_the_light_one(mode: str) -> None:
    """Such a page's text is the browser's black, so the surface under it must be light.

    Matched like the rest, stock `white` came out as the light theme's darkest grey, and a
    page that set no colours was black on near-black.
    """
    configuration = {"state": {"theme": mode}, "palette": TWO_MODE_PALETTE}
    settings = patch_qutebrowser.theme_settings(configuration, mode)
    surface = settings["c.colors.webpage.bg"]
    assert surface == TWO_MODE_PALETTE["light"]["background"]
    assert color_match.contrast("#000000", surface) >= color_match.MIN_TEXT_CONTRAST


# ------------------------------------------------------------------------ the output


def test_the_generated_module_is_valid_python(configuration: dict) -> None:
    """qutebrowser executes it; a syntax error there stops the browser starting."""
    compile(patch_qutebrowser.theme_module(configuration, "dark"), "theme.py", "exec")


def test_the_generated_module_sets_what_it_mapped(configuration: dict) -> None:
    module = patch_qutebrowser.theme_module(configuration, "dark")
    expected = len(patch_qutebrowser.theme_settings(configuration, "dark"))
    # `c.` rather than `c.colors.`: the hint border is a colour that lives under `c.hints`.
    assert sum(1 for line in module.splitlines() if line.startswith("c.")) == expected
    assert "Generated by helper/patch_qutebrowser.py" in module


def test_it_writes_nothing_when_qutebrowser_has_no_configuration_directory(
    configuration: dict, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A machine without qutebrowser gets no file, not a traceback mid theme switch."""
    monkeypatch.setenv("HOME", str(tmp_path))
    patch_qutebrowser.patch_qutebrowser(configuration)
    assert not (tmp_path / ".config" / "qutebrowser" / "theme.py").exists()


def test_it_writes_the_theme_where_config_py_sources_it(
    configuration: dict, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".config" / "qutebrowser").mkdir(parents=True)
    patch_qutebrowser.patch_qutebrowser(configuration)
    written = (tmp_path / ".config" / "qutebrowser" / "theme.py")
    assert written.is_file()
    assert "c.colors." in written.read_text()


# ------------------------------------------------------------------- the hand-written half


def test_config_py_sources_the_generated_theme() -> None:
    """The two halves only meet here; without this line the patcher writes into nothing."""
    config = pathlib.Path("configuration/qutebrowser/config.py").read_text()
    assert 'config.source("theme.py")' in config
    assert "theme.py" in config.split("load_autoconfig")[1][:600], "sourced too late to matter"


def test_config_py_no_longer_picks_colours_by_hand() -> None:
    """Twenty-seven hand-chosen lookups were superseded; two sources of colour would drift."""
    config = pathlib.Path("configuration/qutebrowser/config.py").read_text()
    live = [
        line for line in config.splitlines()
        if line.startswith("c.colors.") and "configuration[" in line
    ]
    assert live == []


def test_config_py_keeps_what_is_not_declarative() -> None:
    """The monitor loop and the darkmode switch are logic, not colours; theme.py has neither."""
    config = pathlib.Path("configuration/qutebrowser/config.py").read_text()
    assert "c.tabs.padding" in config
    assert "c.colors.webpage.darkmode.enabled" in config
    assert 'config.bind("td"' in config


def test_the_darkmode_switch_is_not_also_set_by_the_generated_theme(source: str) -> None:
    """Both setting it would make which one wins depend on source order."""
    assert "c.colors.webpage.darkmode.enabled" in patch_qutebrowser.unmapped(source)


# ------------------------------------------------------------------ the two halves together
#
# config.py and theme.py only meet at run time, inside qutebrowser. Each half is valid Python
# on its own, so nothing else here would notice `config.source` naming a file the patcher does
# not write, or the generated module setting something config.py then overrides. This loads
# them the way qutebrowser does.


class _Section:
    """Stands in for qutebrowser's `c`, recording what a config assigns."""

    def __init__(self, applied: dict, path: str = "") -> None:
        object.__setattr__(self, "_applied", applied)
        object.__setattr__(self, "_path", path)

    def __getattr__(self, name: str) -> _Section:
        return _Section(self._applied, f"{self._path}.{name}".lstrip("."))

    def __setattr__(self, name: str, value: object) -> None:
        self._applied[f"{self._path}.{name}".lstrip(".")] = value


class _ConfigAPI:
    """Stands in for qutebrowser's `config`, including `source`."""

    def __init__(self, directory: pathlib.Path, section: _Section, applied: dict) -> None:
        self.directory = directory
        self.sourced: list[str] = []
        self._section = section
        self._applied = applied

    def load_autoconfig(self, *_args: object) -> None:
        pass

    def bind(self, *_args: object, **_kwargs: object) -> None:
        pass

    def set(self, name: str, value: object) -> None:
        self._applied[name] = value

    def source(self, name: str) -> None:
        self.sourced.append(name)
        path = self.directory / name
        exec(  # noqa: S102 - this is what qutebrowser does with the file
            compile(path.read_text(), str(path), "exec"),
            {"c": self._section, "config": self},
        )


@pytest.fixture
def loaded(
    configuration: dict, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict, _ConfigAPI]:
    """config.py executed against a patched theme, as qutebrowser would."""
    monkeypatch.setenv("HOME", str(tmp_path))
    directory = tmp_path / ".config" / "qutebrowser"
    directory.mkdir(parents=True)
    configuration["font"] = {"family": "Iosevka NF", "size": 14}
    configuration["monitors"] = {"HDMI-0": {"scaling_factor": 1.6}}
    (tmp_path / ".config" / "config.json").write_text(json.dumps(configuration))

    patch_qutebrowser.patch_qutebrowser(configuration)

    applied: dict = {}
    section = _Section(applied)
    api = _ConfigAPI(directory, section, applied)
    source = pathlib.Path("configuration/qutebrowser/config.py")
    exec(  # noqa: S102 - ditto
        compile(source.read_text(), str(source), "exec"),
        {"c": section, "config": api, "__name__": "config"},
    )
    return applied, api


def test_config_py_loads_and_sources_the_generated_theme(loaded: tuple) -> None:
    applied, api = loaded
    assert api.sourced == ["theme.py"]
    assert sum(1 for name in applied if name.startswith("colors.")) > 80


def test_the_loaded_colours_are_all_well_formed(loaded: tuple) -> None:
    """`#569c67en` reached a generated theme once, from an alpha slice taken on length."""
    applied, _ = loaded
    for name, value in applied.items():
        if not name.startswith("colors."):
            continue
        for entry in value if isinstance(value, list) else [value]:
            if isinstance(entry, str) and entry.startswith("#"):
                assert len(entry) in (7, 9), f"{name} = {entry!r}"


def test_the_hand_written_half_still_computes_what_only_it_can(loaded: tuple) -> None:
    """A generated theme cannot know the monitors or the active variant."""
    applied, _ = loaded
    assert applied["fonts.default_family"] == ["Iosevka NF"]
    assert applied["tabs.padding"]["top"] > 0
    assert applied["colors.webpage.darkmode.enabled"] is True


# ------------------------------------------------------------------------- config.py itself
#
# qutebrowser runs config.py with two objects in scope: `c`, the settings tree, and `config`,
# the functions. Stand-ins for both let it run here, against a configuration file of choice.

CONFIG_PY = pathlib.Path(__file__).resolve().parent.parent / "configuration/qutebrowser/config.py"


class Settings:
    """`c`: any attribute path can be read and assigned, and assignments are kept."""

    def __init__(self, path: str = "") -> None:
        object.__setattr__(self, "_path", path)
        object.__setattr__(self, "assigned", {})

    def __getattr__(self, name: str) -> Settings:
        child = Settings(f"{self._path}.{name}".lstrip("."))
        object.__setattr__(child, "assigned", self.assigned)
        object.__setattr__(self, name, child)
        return child

    def __setattr__(self, name: str, value: object) -> None:
        self.assigned[f"{self._path}.{name}".lstrip(".")] = value


class Functions:
    """`config`: every call is accepted and ignored."""

    def __getattr__(self, _name: str) -> object:
        return lambda *_args, **_kwargs: None


def _run_config(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, monitors: dict) -> dict:
    (tmp_path / ".config").mkdir()
    (tmp_path / ".config" / "config.json").write_text(json.dumps({
        "font": {"family": "Iosevka NF", "size": 14},
        "monitors": monitors,
        "state": {"theme": "dark"},
    }))
    monkeypatch.setenv("HOME", str(tmp_path))
    settings = Settings()
    exec(compile(CONFIG_PY.read_text(), str(CONFIG_PY), "exec"),  # noqa: S102
         {"c": settings, "config": Functions()})
    return settings.assigned


def test_the_tab_padding_is_a_third_of_the_scaled_font(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assigned = _run_config(tmp_path, monkeypatch, {"A": {"scaling_factor": 1.5}})
    assert assigned["tabs.padding"]["top"] == round(1.5 * 14) // 3


# No monitors recorded divided by zero, and qutebrowser fell back to its defaults entirely.
def test_no_monitors_recorded_still_loads(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assigned = _run_config(tmp_path, monkeypatch, {})
    assert assigned["tabs.padding"]["top"] == 14 // 3
