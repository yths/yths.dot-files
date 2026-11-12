"""Which icon the bar draws for a connected bluetooth device.

The widget used to draw only two devices, named by MAC in `config.py`: anything else that
connected was invisible, and changing an icon meant editing the bar. Now every device is
drawn -- as `bluetooth.device` unless the theme's `bluetooth_devices` block names it -- and
the mapping lives in the bundle next to the glyphs it refers to.
"""

import json
import pathlib
import pickle

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
    with (directory / "palette.pkl").open("wb") as handle:
        pickle.dump({"light": {}, "dark": {}}, handle)

    migrated, changes = install.migrate_configuration(
        str(directory), {"bluetooth_devices": {UNKNOWN: "stale"}},
    )
    assert migrated["bluetooth_devices"] == {HEADPHONES: "bluetooth.headphones"}
    assert "refreshed bluetooth_devices" in changes
