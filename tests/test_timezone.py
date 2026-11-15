"""The system timezone follows the geolocated one; VPN readings are not a location."""

import json
import os
import pathlib
import subprocess
from collections.abc import Iterator
from typing import Any

import patch_timezone
import pytest
import shared.stream
import shared.timezone
from shared.timezone import TimezoneFollower


@pytest.fixture(autouse=True)
def _no_tzset(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[None]]:
    """``time.tzset`` is process-wide; record calls instead of changing local time."""
    calls: list[None] = []
    monkeypatch.setattr(shared.timezone.time, "tzset", lambda: calls.append(None))
    yield calls


class FakeProcess:
    def __init__(self, returncode: int | None) -> None:
        self.returncode = returncode

    def poll(self) -> int | None:
        return self.returncode


def follower(system: list[str], returncode: int | None = 0) -> tuple[TimezoneFollower, list]:
    spawned: list[list[str]] = []

    def spawn(argv: list[str], **_kwargs: Any) -> FakeProcess:
        spawned.append(argv)
        return FakeProcess(returncode)

    return TimezoneFollower(spawn=spawn, current=lambda: system[0]), spawned


def test_a_new_zone_is_set_without_a_password_prompt() -> None:
    zone, spawned = follower(["Europe/Berlin"])
    zone.follow("Atlantic/Canary")
    assert spawned == [["timedatectl", "--no-ask-password", "set-timezone", "Atlantic/Canary"]]


def test_the_current_zone_is_left_alone() -> None:
    zone, spawned = follower(["Atlantic/Canary"])
    zone.follow("Atlantic/Canary")
    assert spawned == []


@pytest.mark.parametrize("bad", ["", None, "Not/AZone", "../../etc/passwd", "/etc/passwd"])
def test_nothing_but_a_known_zone_reaches_timedatectl(bad: str | None) -> None:
    zone, spawned = follower(["Europe/Berlin"])
    zone.follow(bad)
    assert spawned == []


def test_one_attempt_at_a_time() -> None:
    zone, spawned = follower(["Europe/Berlin"], returncode=None)
    zone.follow("Atlantic/Canary")
    zone.follow("Atlantic/Canary")
    assert len(spawned) == 1


def test_a_refusal_is_not_retried_every_second() -> None:
    zone, spawned = follower(["Europe/Berlin"], returncode=1)
    for _ in range(3):
        zone.follow("Atlantic/Canary")
    assert len(spawned) == 1
    assert "Atlantic/Canary" in zone.refused


def test_qtile_rereads_the_zone_once_it_changes(_no_tzset: list[None]) -> None:
    system = ["Europe/Berlin"]
    zone, _ = follower(system)
    zone.follow("Atlantic/Canary")
    system[0] = "Atlantic/Canary"
    zone.follow("Atlantic/Canary")
    zone.follow("Atlantic/Canary")
    assert len(_no_tzset) == 1


def test_the_system_zone_is_read_from_the_localtime_link(tmp_path: pathlib.Path) -> None:
    zoneinfo = tmp_path / "usr/share/zoneinfo/Atlantic"
    zoneinfo.mkdir(parents=True)
    (zoneinfo / "Canary").write_bytes(b"TZif")
    link = tmp_path / "localtime"
    link.symlink_to(os.path.relpath(zoneinfo / "Canary", tmp_path))
    assert shared.timezone.system_zone(str(link)) == "Atlantic/Canary"


# ------------------------------------------------------------------ skipping VPN readings


class FakeRedis:
    def __init__(self, newest_first: list[dict[str, Any] | bytes]) -> None:
        self.entries = [
            (b"0-0", {b"measurement": entry if isinstance(entry, bytes) else json.dumps(entry).encode()})
            for entry in newest_first
        ]

    def xrevrange(self, _stream: str, count: int) -> list:
        return self.entries[:count]


def test_the_newest_reading_without_the_vpn_is_used() -> None:
    r = FakeRedis([
        {"timezone": "Europe/Amsterdam", "vpn": True},
        b"not json",
        {"timezone": "Atlantic/Canary", "vpn": False},
        {"timezone": "Europe/Berlin", "vpn": False},
    ])
    found = shared.stream.read_latest(r, "location", lambda m: not m.get("vpn"))  # type: ignore[arg-type]
    assert found == {"timezone": "Atlantic/Canary", "vpn": False}


def test_only_vpn_readings_is_no_reading() -> None:
    r = FakeRedis([{"timezone": "Europe/Amsterdam", "vpn": True}])
    assert shared.stream.read_latest(r, "location", lambda m: not m.get("vpn")) is None  # type: ignore[arg-type]


def test_no_client_is_no_reading() -> None:
    assert shared.stream.read_latest(None, "location", lambda _m: True) is None


# ------------------------------------------------------------------------- the polkit rule


def test_the_rule_grants_only_setting_the_timezone() -> None:
    rule = pathlib.Path(patch_timezone.RULE_SOURCE).read_text()
    assert rule.count('action.id == "org.freedesktop.timedate1.set-timezone"') == 1
    assert "action.id.indexOf" not in rule and "startsWith" not in rule
    assert 'subject.isInGroup("wheel")' in rule and "subject.active" in rule


def test_the_rule_is_installed_as_root(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(patch_timezone, "root_prefix", lambda **_k: ["sudo", "-n"])
    monkeypatch.setattr(
        patch_timezone.subprocess, "run",
        lambda argv, **_k: calls.append(argv) or subprocess.CompletedProcess(argv, 0, "", ""),
    )
    assert patch_timezone.install_system({}, prompt=True)
    assert calls == [[
        "sudo", "-n", "install", "-D", "-m", "644", patch_timezone.RULE_SOURCE,
        "/etc/polkit-1/rules.d/50-dot-files-timezone.rules",
    ]]


def test_without_root_nothing_is_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(patch_timezone, "root_prefix", lambda **_k: None)
    assert patch_timezone.install_system({}) is False
