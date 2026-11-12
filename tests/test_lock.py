"""The lock screen: what it is told to show, and what it is told to withhold."""

import pathlib

import patch_lock
import pytest
import utils
from patch_configurations import PATCHERS

PALETTE = {
    "background": "#111111", "foreground": "#eeeeee", "warning": "#ffcc00",
}

#: xsecurelock reads its flags as strings. Named so an assertion about a setting whose name
#: contains "PASSWORD" is not mistaken for a hardcoded credential.
ON, OFF = "1", "0"


@pytest.fixture
def configuration() -> dict:
    return {
        "state": {"theme": "dark"},
        "palette": {"dark": PALETTE},
        "font": {"family": "Iosevka NF", "size": 14},
    }


def test_the_lock_takes_its_colours_from_the_active_palette(configuration: dict) -> None:
    environment = patch_lock.lock_environment(configuration)
    assert environment["XSECURELOCK_BACKGROUND_COLOR"] == PALETTE["background"]
    assert environment["XSECURELOCK_AUTH_FOREGROUND_COLOR"] == PALETTE["foreground"]
    assert environment["XSECURELOCK_AUTH_WARNING_COLOR"] == PALETTE["warning"]


def test_the_font_follows_the_configured_one(configuration: dict) -> None:
    assert patch_lock.lock_environment(configuration)["XSECURELOCK_FONT"].startswith("Iosevka NF:")


def test_switching_theme_switches_the_lock(configuration: dict) -> None:
    configuration["palette"]["light"] = {**PALETTE, "background": "#ffffff"}
    configuration["state"]["theme"] = "light"
    assert patch_lock.lock_environment(configuration)["XSECURELOCK_BACKGROUND_COLOR"] == "#ffffff"


# The reason this feature exists is that a machine you walked away from should tell a
# passer-by nothing. These are the settings that decide that, so they are asserted rather
# than left to whoever next edits the table.
@pytest.mark.parametrize(
    "setting",
    ["XSECURELOCK_SHOW_USERNAME", "XSECURELOCK_SHOW_HOSTNAME", "XSECURELOCK_SHOW_DATETIME"],
)
def test_the_lock_screen_identifies_neither_the_user_nor_the_machine(
    configuration: dict, setting: str
) -> None:
    assert patch_lock.lock_environment(configuration)[setting] == OFF


def test_the_password_field_reveals_nothing(configuration: dict) -> None:
    assert patch_lock.lock_environment(configuration)["XSECURELOCK_PARANOID_PASSWORD"] == ON


def test_a_locked_screen_also_goes_dark(configuration: dict) -> None:
    environment = patch_lock.lock_environment(configuration)
    assert int(environment["XSECURELOCK_BLANK_TIMEOUT"]) > 0
    assert environment["XSECURELOCK_BLANK_DPMS_STATE"] == "off"


# xss-lock tracks the launcher's process to decide whether the screen is still covered.
def test_the_launcher_execs_rather_than_forking() -> None:
    script = (pathlib.Path(utils.REPOSITORY_ROOT) / "configuration" / "lock" / "lock.sh").read_text()
    assert "exec xsecurelock" in script
    assert "lock/environment" in script, "the launcher must source the generated colours"


def test_the_session_starts_the_lock_daemon() -> None:
    xinitrc = (pathlib.Path(utils.REPOSITORY_ROOT) / "configuration" / "xorg" / ".xinitrc").read_text()
    assert "xss-lock" in xinitrc
    # Without this, suspend can win the race and the machine wakes unlocked.
    assert "--transfer-sleep-lock" in xinitrc


def test_both_lockers_are_installed_by_the_bootstrap() -> None:
    packages = {name for group in utils.read_setup()["packages"].values() for name in group}
    assert {"xsecurelock", "xss-lock"} <= packages


def test_the_lock_is_in_the_patcher_registry() -> None:
    assert "lock" in {name for name, _ in PATCHERS}, "a theme switch must reach the lock screen"
