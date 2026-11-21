"""Which icon the bar draws for a connected bluetooth device.

The widget used to draw only two devices, named by MAC in `config.py`: anything else that
connected was invisible, and changing an icon meant editing the bar. Now every device is
drawn -- as `bluetooth.device` unless the theme's `bluetooth_devices` block names it -- and
the mapping lives in the bundle next to the glyphs it refers to.
"""

import json
import pathlib

import bluetooth_icon
import pytest
import shared.stream
import symbols
from widgets.bluetooth import WidgetBluetooth

import install

HEADPHONES = "00:11:22:33:44:55"
UNKNOWN = "11:22:33:44:55:66"


def _poll(monkeypatch: pytest.MonkeyPatch, widget: WidgetBluetooth, measurement: dict) -> str:
    monkeypatch.setattr(shared.stream, "read_measurement", lambda _r, _stream: measurement)
    return widget.poll()


def test_a_device_the_theme_does_not_name_gets_the_generic_icon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vocabulary, _ = symbols.resolve({})
    widget = WidgetBluetooth(r=None, symbols=vocabulary)
    output = _poll(monkeypatch, widget, {UNKNOWN: {"capacity": "Unknown"}})
    assert output == f"{vocabulary['bluetooth.device']} "


def test_a_device_the_theme_names_gets_its_icon(monkeypatch: pytest.MonkeyPatch) -> None:
    configuration = {"bluetooth_devices": {HEADPHONES: "bluetooth.headphones"}}
    vocabulary, _ = symbols.resolve(configuration)
    widget = WidgetBluetooth(
        r=None, symbols=vocabulary,
        devices=symbols.bluetooth_devices(configuration, vocabulary),
    )
    output = _poll(monkeypatch, widget, {
        HEADPHONES: {"capacity": "Unknown"}, UNKNOWN: {"capacity": "Unknown"},
    })
    assert output == f"{vocabulary['bluetooth.headphones']} {vocabulary['bluetooth.device']} "


# A symbol key resolves through the vocabulary, so it keeps the ASCII fallback and follows
# the bundle's override of that key. Anything else is the theme's own glyph, drawn as written.
def test_a_mapping_value_is_a_symbol_key_or_a_literal_glyph() -> None:
    configuration = {
        "symbols": {"bluetooth.headphones": "H"},
        "bluetooth_devices": {HEADPHONES: "bluetooth.headphones", UNKNOWN: "\U000f037d"},
    }
    vocabulary, _ = symbols.resolve(configuration)
    assert symbols.bluetooth_devices(configuration, vocabulary) == {
        HEADPHONES: "H", UNKNOWN: "\U000f037d",
    }


# BlueZ reports upper case; a MAC typed into a theme by hand need not be.
def test_a_lower_case_mac_in_the_theme_still_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    configuration = {"bluetooth_devices": {HEADPHONES.lower(): "X"}}
    vocabulary, _ = symbols.resolve(configuration)
    widget = WidgetBluetooth(
        r=None, symbols=vocabulary,
        devices=symbols.bluetooth_devices(configuration, vocabulary),
    )
    assert _poll(monkeypatch, widget, {HEADPHONES: {"capacity": "Unknown"}}) == "X "


def test_a_configuration_without_the_block_maps_nothing() -> None:
    vocabulary, _ = symbols.resolve({})
    assert symbols.bluetooth_devices({}, vocabulary) == {}
    assert symbols.bluetooth_devices({"bluetooth_devices": None}, vocabulary) == {}


# The block is the theme's, so switching bundles has to carry it -- or a migration would keep
# the previous theme's icons, or none.
def test_migrating_takes_the_mapping_from_the_bundle(tmp_path: pathlib.Path) -> None:
    directory = tmp_path / "abundle"
    directory.mkdir()
    (directory / "config.json").write_text(json.dumps({
        "name": "abundle", "bluetooth_devices": {HEADPHONES: "bluetooth.headphones"},
    }))
    (directory / "palette.json").write_text(json.dumps({"light": {}, "dark": {}}))

    migrated, changes = install.migrate_configuration(
        str(directory), {"bluetooth_devices": {UNKNOWN: "stale"}},
    )
    assert migrated["bluetooth_devices"] == {HEADPHONES: "bluetooth.headphones"}
    assert "refreshed bluetooth_devices" in changes


# helper/bluetooth_icon.py: the command that writes the mapping, so nobody has to look up a
# MAC and a codepoint by hand.
def test_bluetoothctl_output_parses_to_upper_case_addresses() -> None:
    output = "Device dd:f8:a4:c5:fe:5a MX Master 3\nnoise\nDevice 00:11:22:33:44:55 \n"
    assert bluetooth_icon.parse_devices(output) == {
        "DD:F8:A4:C5:FE:5A": "MX Master 3", HEADPHONES: HEADPHONES,
    }


def test_setting_a_mapping_replaces_the_same_address_in_any_case() -> None:
    configuration = {"bluetooth_devices": {HEADPHONES.lower(): "x", UNKNOWN: "y"}}
    bluetooth_icon.set_mapping(configuration, HEADPHONES, "z")
    assert configuration["bluetooth_devices"] == {UNKNOWN: "y", HEADPHONES: "z"}
    bluetooth_icon.set_mapping(configuration, HEADPHONES, None)
    assert configuration["bluetooth_devices"] == {UNKNOWN: "y"}


def test_a_choice_is_a_number_a_name_or_the_glyph_itself() -> None:
    names = [bluetooth_icon.DEFAULT, *bluetooth_icon.COMMON]
    assert bluetooth_icon.resolve_choice("0") is None
    assert bluetooth_icon.resolve_choice("default") is None
    assert bluetooth_icon.resolve_choice(str(names.index("mouse"))) == "\U000f037d"
    assert bluetooth_icon.resolve_choice("headphones") == "bluetooth.headphones"
    assert bluetooth_icon.resolve_choice("\U000f0297") == "\U000f0297"
    with pytest.raises(ValueError, match="no entry"):
        bluetooth_icon.resolve_choice(str(len(names)))


# Every listed icon is either a key the vocabulary declares or a glyph, and no two entries
# draw the same thing -- a duplicate would be a choice that makes no difference.
def test_the_common_icons_resolve_and_are_distinct() -> None:
    vocabulary, _ = symbols.resolve({})
    for value in bluetooth_icon.COMMON.values():
        assert value in vocabulary or not value.isascii()
    assert len(set(bluetooth_icon.COMMON.values())) == len(bluetooth_icon.COMMON)
    assert set(bluetooth_icon.SUGGESTIONS.values()) <= set(bluetooth_icon.COMMON)


def test_writing_updates_the_bundle_and_the_installed_configuration(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = tmp_path / "assets" / "theme" / "config.json"
    bundle.parent.mkdir(parents=True)
    bundle.write_text(json.dumps({"name": "theme"}, indent=4) + "\n", encoding="utf-8")
    installed = tmp_path / "config.json"
    installed.write_text(json.dumps({"name": "theme"}, indent=4), encoding="utf-8")
    monkeypatch.setenv("DOTFILES_REPOSITORY_PATH", str(tmp_path))
    monkeypatch.setattr(bluetooth_icon, "installed_path", lambda: str(installed))

    bluetooth_icon.write({"name": "theme"}, UNKNOWN, "\U000f037d")

    for path in (bundle, installed):
        assert json.loads(path.read_text(encoding="utf-8"))["bluetooth_devices"] == {
            UNKNOWN: "\U000f037d",
        }
    assert bundle.read_text(encoding="utf-8").endswith("}\n")
