"""The power menu: rofi script mode, with a confirmation in front of anything that ends the
session. Run for real, against stand-ins for the programs it calls, which record their argv."""

import os
import pathlib
import subprocess

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "configuration/rofi/power-menu.sh"


@pytest.fixture
def menu(tmp_path: pathlib.Path) -> tuple[callable, pathlib.Path]:
    bin_directory, log = tmp_path / "bin", tmp_path / "calls.log"
    bin_directory.mkdir()
    for name in ("loginctl", "systemctl", "qtile"):
        stand_in = bin_directory / name
        stand_in.write_text(f'#!/bin/sh\necho "{name} $*" >> "{log}"\n')
        stand_in.chmod(0o755)
    environment = {**os.environ, "PATH": f"{bin_directory}:{os.environ['PATH']}"}

    def run(*arguments: str) -> list[str]:
        result = subprocess.run(
            [str(SCRIPT), *arguments], env=environment, capture_output=True, text=True,
            check=True,
        )
        return result.stdout.splitlines()

    return run, log


def _calls(log: pathlib.Path) -> list[str]:
    return log.read_text().splitlines() if log.exists() else []


def test_the_menu_lists_the_harmless_entries_first(menu: tuple) -> None:
    run, _ = menu
    assert run() == ["lock", "suspend", "log out", "reboot", "shut down"]


@pytest.mark.parametrize("entry", ["log out", "reboot", "shut down"])
def test_ending_the_session_asks_first_and_does_nothing_yet(menu: tuple, entry: str) -> None:
    run, log = menu
    assert run(entry) == [f"yes, {entry}", "no"]
    assert _calls(log) == []


@pytest.mark.parametrize(("entry", "call"), [
    ("lock", "loginctl lock-session"),
    ("suspend", "systemctl suspend"),
    ("yes, log out", "qtile cmd-obj -o cmd -f shutdown"),
    ("yes, reboot", "systemctl reboot"),
    ("yes, shut down", "systemctl poweroff"),
])
def test_each_entry_does_what_it_says(menu: tuple, entry: str, call: str) -> None:
    run, log = menu
    assert run(entry) == [], "printing nothing closes rofi"
    assert _calls(log) == [call]


def test_no_does_nothing(menu: tuple) -> None:
    run, log = menu
    assert run("no") == []
    assert _calls(log) == []
