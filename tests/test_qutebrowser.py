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
    for name, value in patch_qutebrowser.theme_settings(configuration, "dark").items():
        for entry in value if isinstance(value, list) else [value]:
            assert entry in palette, f"{name} = {entry!r} is not in the palette"


# ------------------------------------------------------------------------ the output


def test_the_generated_module_is_valid_python(configuration: dict) -> None:
    """qutebrowser executes it; a syntax error there stops the browser starting."""
    compile(patch_qutebrowser.theme_module(configuration, "dark"), "theme.py", "exec")


def test_the_generated_module_sets_what_it_mapped(configuration: dict) -> None:
    module = patch_qutebrowser.theme_module(configuration, "dark")
    expected = len(patch_qutebrowser.theme_settings(configuration, "dark"))
    assert sum(1 for line in module.splitlines() if line.startswith("c.colors.")) == expected
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
    assert "config.bind('td'" in config


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
