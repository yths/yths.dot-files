"""GTK: the colours applications draw with, and the two preferences that are not files.

Which mechanism works where is the substance of this patcher, and it was measured by
rendering a window under each toolkit and sampling the result rather than read off a wiki:

    @define-color only     explicit CSS rule
    GTK 3 Adwaita   #F6F5F4 (unchanged)   #FF00FF (applied)
    GTK 4 built-in  #F6F5F4 (unchanged)   #FF00FF (applied)
    libadwaita      #FF00FF (applied)     --

So a stylesheet that only defines colours changes nothing outside libadwaita, and the rules
below are what actually carry the palette. With the real generated configuration all three
render the palette's background, #322F2F, and a selected row takes the palette's highlight.
"""

import pathlib
import re
import subprocess

import patch_gtk
import pytest
from patch_configurations import PATCHERS

PALETTE = {
    "background": "#322f2f", "foreground": "#d5d1d1", "neutral": "#afabab",
    "highlight": "#4d91c7", "warning": "#c07726", "failure": "#cd6869",
    "success": "#569c67",
}
LIGHT = {**PALETTE, "background": "#fffbfb", "foreground": "#4f4c4c"}


@pytest.fixture
def configuration() -> dict:
    return {
        "state": {"theme": "dark"},
        "palette": {"dark": PALETTE, "light": LIGHT},
        "font": {"family": "Iosevka NF", "size": 14},
    }


# ----------------------------------------------------------------------------- colours

def test_every_role_resolves_to_a_palette_colour(configuration: dict) -> None:
    roles = patch_gtk.gtk_roles(configuration)
    assert roles["surface"] == PALETTE["background"]
    assert roles["accent"] == PALETTE["highlight"]
    assert set(roles) == set(patch_gtk.ROLES)


def test_switching_theme_switches_the_surfaces(configuration: dict) -> None:
    dark = patch_gtk.gtk_roles(configuration)
    configuration["state"]["theme"] = "light"
    assert patch_gtk.gtk_roles(configuration)["surface"] != dark["surface"]


def test_the_stylesheet_carries_the_palette_in_rules_not_only_definitions(
    configuration: dict,
) -> None:
    """The regression the measurement above pins: a stylesheet of nothing but
    @define-color leaves GTK 3 and GTK 4 exactly as they were."""
    css = patch_gtk.gtk_css(configuration, adwaita=False)
    assert "background-color:" in css, "nothing here would change a stock theme"
    assert re.search(r"window[^{]*\{[^}]*background-color", css)


def test_every_colour_the_rules_use_is_defined(configuration: dict) -> None:
    """A role named in a rule but missing from the definitions is a silent no-op in GTK."""
    for adwaita in (False, True):
        css = patch_gtk.gtk_css(configuration, adwaita=adwaita)
        defined = set(re.findall(r"@define-color (\S+)", css))
        used = set(re.findall(r"@([a-z0-9_-]+)\s*[;}]", css))
        assert used <= defined, f"undefined: {sorted(used - defined)}"


def test_only_gtk4_is_given_the_libadwaita_names(configuration: dict) -> None:
    """They are the one place @define-color reaches anything, and mean nothing to GTK 3."""
    assert "window_bg_color" in patch_gtk.gtk_css(configuration, adwaita=True)
    assert "window_bg_color" not in patch_gtk.gtk_css(configuration, adwaita=False)


def test_the_libadwaita_names_point_at_real_roles() -> None:
    assert set(patch_gtk.ADWAITA_COLOURS.values()) <= set(patch_gtk.ROLES)


# ---------------------------------------------------------------------------- settings

def test_dark_is_announced_to_gtk3(configuration: dict) -> None:
    """GTK 3 has no other way to be told: it does not watch the GSettings key."""
    assert patch_gtk.gtk_settings(configuration)["gtk-application-prefer-dark-theme"] == "1"
    configuration["state"]["theme"] = "light"
    assert patch_gtk.gtk_settings(configuration)["gtk-application-prefer-dark-theme"] == "0"


def test_the_font_follows_the_configured_one(configuration: dict) -> None:
    assert patch_gtk.gtk_settings(configuration)["gtk-font-name"] == "Iosevka NF 10"


def test_settings_are_written_as_a_keyfile(configuration: dict) -> None:
    """Without the section header GTK ignores the file entirely."""
    assert patch_gtk.render_settings(patch_gtk.gtk_settings(configuration)).startswith(
        "[Settings]\n"
    )


# ------------------------------------------------------------------------- preferences

def test_both_file_choosers_are_told_to_show_hidden_entries(configuration: dict) -> None:
    """Each toolkit keeps its own copy of this, and neither defaults to showing them."""
    preferences = {
        (schema, key): value
        for schema, key, value in patch_gtk.gsettings_preferences(configuration)
    }
    assert preferences[("org.gtk.Settings.FileChooser", "show-hidden")] == "true"
    assert preferences[("org.gtk.gtk4.Settings.FileChooser", "show-hidden")] == "true"


def test_the_colour_scheme_follows_the_theme(configuration: dict) -> None:
    def scheme(config: dict) -> str:
        return next(
            value for schema, key, value in patch_gtk.gsettings_preferences(config)
            if key == "color-scheme"
        )
    assert scheme(configuration) == "prefer-dark"
    configuration["state"]["theme"] = "light"
    assert scheme(configuration) == "prefer-light"


class FakeGsettings:
    """Stands in for the gsettings binary, recording what would have been written."""

    def __init__(self, current: dict | None = None, missing: set | None = None) -> None:
        self.current = current or {}
        self.missing = missing or set()
        self.written: list[tuple[str, str, str]] = []

    def __call__(self, argv: list[str], **_: object) -> subprocess.CompletedProcess:
        _, action, schema, key, *rest = argv
        if schema in self.missing:
            return subprocess.CompletedProcess(argv, 1, "", "No such schema")
        if action == "get":
            value = self.current.get((schema, key), "")
            return subprocess.CompletedProcess(argv, 0, f"'{value}'\n", "")
        self.written.append((schema, key, rest[0]))
        self.current[(schema, key)] = rest[0]
        return subprocess.CompletedProcess(argv, 0, "", "")


def test_a_preference_already_set_is_not_rewritten(
    configuration: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """This runs on every theme switch; rewriting dconf each time is pointless churn."""
    fake = FakeGsettings(current={
        ("org.gtk.Settings.FileChooser", "show-hidden"): "true",
        ("org.gtk.gtk4.Settings.FileChooser", "show-hidden"): "true",
        ("org.gnome.desktop.interface", "color-scheme"): "prefer-dark",
    })
    monkeypatch.setattr(patch_gtk.subprocess, "run", fake)
    assert patch_gtk.apply_gsettings(patch_gtk.gsettings_preferences(configuration)) == []
    assert fake.written == []


def test_a_preference_that_differs_is_written(
    configuration: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeGsettings(current={
        ("org.gtk.Settings.FileChooser", "show-hidden"): "false",
        ("org.gtk.gtk4.Settings.FileChooser", "show-hidden"): "false",
        ("org.gnome.desktop.interface", "color-scheme"): "prefer-dark",
    })
    monkeypatch.setattr(patch_gtk.subprocess, "run", fake)
    changed = patch_gtk.apply_gsettings(patch_gtk.gsettings_preferences(configuration))
    assert len(changed) == 2
    assert all(value == "true" for _, _, value in fake.written)


def test_a_missing_schema_is_skipped_not_raised(
    configuration: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gtk4 keys ship with gtk4. Absent means that toolkit is not installed, and there
    is nothing the setting could affect."""
    fake = FakeGsettings(missing={"org.gtk.gtk4.Settings.FileChooser"})
    monkeypatch.setattr(patch_gtk.subprocess, "run", fake)
    changed = patch_gtk.apply_gsettings(patch_gtk.gsettings_preferences(configuration))
    assert not any("gtk4" in key for key in changed)


def test_no_gsettings_binary_does_not_break_the_theme_switch(
    configuration: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    def absent(*_: object, **__: object) -> None:
        raise OSError(2, "No such file or directory")
    monkeypatch.setattr(patch_gtk.subprocess, "run", absent)
    assert patch_gtk.apply_gsettings(patch_gtk.gsettings_preferences(configuration)) == []


# ------------------------------------------------------------------------------ wiring

def test_the_patcher_writes_both_toolkits(
    configuration: dict, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(patch_gtk, "apply_gsettings", lambda _: [])
    patch_gtk.patch_gtk(configuration)
    written = sorted(
        str(p.relative_to(tmp_path / ".config")) for p in (tmp_path / ".config").rglob("*")
        if p.is_file()
    )
    assert written == [
        "gtk-3.0/gtk.css", "gtk-3.0/settings.ini",
        "gtk-4.0/gtk.css", "gtk-4.0/settings.ini",
    ]


def test_gtk_is_patched_on_a_theme_switch() -> None:
    assert "gtk" in dict(PATCHERS)


def test_both_toolkit_directories_are_installed() -> None:
    """The patcher writes to ~/.config/gtk-*.0, which has to be the symlink into here or the
    generated files land outside the repository and outside .gitignore."""
    installed = pathlib.Path("install.py").read_text()
    assert '("gtk/gtk-3.0", "~/.config/gtk-3.0"' in installed
    assert '("gtk/gtk-4.0", "~/.config/gtk-4.0"' in installed
