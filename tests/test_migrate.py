"""Migrating an installed configuration, as against installing one.

Two machines, two problems. A new one has no configuration, so installing writes one and the
chosen theme is fully applied. One that has been running for months has a configuration that
predates whatever the repository gained since -- and the consumers of a missing field fall
back rather than fail, which is the good behaviour and also the reason nothing announces that
half the desktop is running on defaults.

Telling the second machine to reinstall would fix the file and reset `state` with it: a
pinned theme reverts to automatic switching, an audio mode goes back to default. That is the
property these tests are here to hold, because it is invisible until the next sunset moves
the theme on a machine that was deliberately pinned.
"""

import json
import pathlib
import pickle

import pytest
import symbols

import install

PALETTE = {"light": {"background": "#ffffff"}, "dark": {"background": "#000000"}}


@pytest.fixture
def bundle(tmp_path: pathlib.Path) -> str:
    """A bundle that overrides exactly one symbol, so its effect is identifiable."""
    directory = tmp_path / "abundle"
    directory.mkdir()
    (directory / "config.json").write_text(
        json.dumps({"name": "abundle", "symbols": {"vpn.off": "GONE"}})
    )
    return str(directory)


@pytest.fixture
def installed(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """A configuration as an older install left it: no vocabulary, and a state to protect."""
    monkeypatch.setenv("HOME", str(tmp_path))
    palette = tmp_path / ".config" / "palette.pkl"
    palette.parent.mkdir(parents=True, exist_ok=True)
    palette.write_bytes(pickle.dumps(PALETTE))
    return {
        "name": "abundle",
        "palette": {"dark": {}, "light": {}},
        "font": {"family": "Stale", "size": 1},
        "monitors": {"HDMI-0": {"width": 3840}},
        "wallpapers": {"dark": "~/.config/qtile/wallpaper-dark.png"},
        "state": {"theme": "dark", "condition": "normal",
                  "theme_mode": "manual", "audio_mode": "manual"},
        "colors": {"legacy": "#000000"},
    }


# The failure this whole path exists for: a machine installed before the vocabulary existed
# runs an ASCII desktop, silently, until something refreshes the file.
def test_migrating_adds_a_vocabulary_the_configuration_never_had(
    bundle: str, installed: dict
) -> None:
    migrated, changes = install.migrate_configuration(bundle, installed)
    assert migrated["symbols"]["vpn.off"] == "GONE", "the bundle's override must win"
    assert migrated["symbols"]["vpn.on"] == symbols.SYMBOLS["vpn.on"], "the rest are defaults"
    assert migrated["strings"] == symbols.STRINGS
    assert "added symbols" in changes


# The reason migrating is its own path rather than advice to reinstall.
def test_migrating_keeps_the_state_this_machine_is_in(bundle: str, installed: dict) -> None:
    migrated, changes = install.migrate_configuration(bundle, installed)
    assert migrated["state"] == installed["state"]
    assert migrated["state"]["theme_mode"] == "manual", "a pinned theme must survive"
    assert migrated["monitors"] == installed["monitors"]
    assert migrated["wallpapers"] == installed["wallpapers"]
    assert "kept state" in changes


def test_installing_would_have_reset_that_state() -> None:
    """The contrast, asserted so the two paths cannot quietly converge."""
    assert install.SETUP["state"]["theme_mode"] != "manual", (
        "if setup.toml ever pins the theme this test stops meaning anything"
    )
    assert "state" not in ("name", "palette", "font", "symbols", "strings")
    assert "state" in install.MACHINE_OWNED


def test_migrating_drops_a_field_the_schema_no_longer_has(
    bundle: str, installed: dict
) -> None:
    migrated, changes = install.migrate_configuration(bundle, installed)
    assert "colors" not in migrated
    assert any("dropped colors" in change for change in changes)


# Each of these is a copy taken at install time that goes stale when the repository moves.
def test_migrating_re_derives_what_the_repository_owns(bundle: str, installed: dict) -> None:
    migrated, _ = install.migrate_configuration(bundle, installed)
    assert migrated["palette"] == PALETTE, "the palette is re-read from the installed pickle"
    assert migrated["font"]["family"] == install.SETUP["desktop"]["font_family"]
    assert migrated["font"] != installed["font"]


# An install and a migration that disagreed would make a machine look different before and
# after an update with nothing to say why.
def test_installing_and_migrating_agree_on_the_vocabulary(bundle: str) -> None:
    manifest = json.loads((pathlib.Path(bundle) / "config.json").read_text())
    assert install.theme_vocabulary(manifest)["symbols"]["vpn.off"] == "GONE"
    assert set(install.theme_vocabulary(manifest)["symbols"]) == set(symbols.SYMBOLS)


# ------------------------------------------------------------------------ the entry point


def test_migrating_without_a_configuration_says_to_install_instead(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    assert install.run_migration(str(tmp_path / "assets"), None) == 1


def test_migrating_to_a_theme_that_does_not_ship_is_refused(
    tmp_path: pathlib.Path, installed: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".config" / "config.json").write_text(json.dumps(installed))
    assets = tmp_path / "assets"
    assets.mkdir()
    assert install.run_migration(str(assets), "nonesuch") == 1


def test_the_installed_theme_is_migrated_when_none_is_named(
    tmp_path: pathlib.Path, installed: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On a machine that has been running, the installed theme and setup.toml's may differ."""
    assets = tmp_path / "assets"
    (assets / "abundle").mkdir(parents=True)
    (assets / "abundle" / "config.json").write_text(
        json.dumps({"name": "abundle", "symbols": {"vpn.off": "GONE"}})
    )
    (tmp_path / ".config" / "config.json").write_text(json.dumps(installed))
    monkeypatch.setattr(install, "generate_application_configuration", lambda _c: None)

    assert install.run_migration(str(assets), None) == 0
    written = json.loads((tmp_path / ".config" / "config.json").read_text())
    assert written["name"] == "abundle"
    assert written["symbols"]["vpn.off"] == "GONE"
    assert written["state"]["theme_mode"] == "manual"
