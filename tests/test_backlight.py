"""The backlight cell: an icon on target, an offset off it, the plain level without one."""

import json
import pathlib

import pytest
import shared.stream
import symbols
import utils
from widgets.backlight import WidgetBacklight, read_target

ICON = symbols.SYMBOLS["backlight.level"]


def _poll(monkeypatch: pytest.MonkeyPatch, measurement: dict | None, **options: object) -> str:
    monkeypatch.setattr(shared.stream, "read_measurement", lambda _r, _stream: measurement)
    return WidgetBacklight(r=None, notification_color="#222222", **options).poll()


def _level(brightness: int, maximum: int = 1000, name: str = "intel_backlight") -> dict:
    return {"devices": {name: {"brightness": brightness, "max_brightness": maximum}}}


def test_without_a_target_the_level_is_shown(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _poll(monkeypatch, _level(362, 1000)) == f"{ICON} 36"


def test_on_target_is_the_icon_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _poll(monkeypatch, _level(555), target=(None, 549)) == f"{ICON} "


def test_off_target_is_a_signed_offset_in_points(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _poll(monkeypatch, _level(649), target=(None, 549)) == (
        f"<span color='#222222'>{ICON} +10</span>"
    )
    assert "-20" in _poll(monkeypatch, _level(349), target=(None, 549))


def test_the_targets_device_is_preferred(monkeypatch: pytest.MonkeyPatch) -> None:
    measurement = {"devices": {
        "acpi_video0": {"brightness": 0, "max_brightness": 1000},
        "intel_backlight": {"brightness": 549, "max_brightness": 1000},
    }}
    assert _poll(monkeypatch, measurement, target=("intel_backlight", 549)) == f"{ICON} "


@pytest.mark.parametrize("measurement", [
    None, {}, {"devices": {}}, _level(5, 0), {"devices": {"x": {"brightness": "5"}}},
])
def test_nothing_usable_is_nothing_drawn(monkeypatch: pytest.MonkeyPatch, measurement: dict | None) -> None:
    assert _poll(monkeypatch, measurement, target=(None, 549)) == ""


def test_the_target_is_read_for_this_host(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "backlight.json"
    path.write_text(json.dumps({"eridu": {"intel_backlight": 549}, "assur": {"*": 10}}))
    assert read_target(str(path), "eridu") == ("intel_backlight", 549)
    assert read_target(str(path), "assur") == (None, 10)
    assert read_target(str(path), "nippur") is None
    assert read_target(str(tmp_path / "missing.json"), "eridu") is None


def test_the_tracked_file_is_valid_json() -> None:
    path = pathlib.Path(utils.REPOSITORY_ROOT) / "configuration" / "hardware" / "backlight.json"
    assert isinstance(json.loads(path.read_text(encoding="utf-8")), dict)
