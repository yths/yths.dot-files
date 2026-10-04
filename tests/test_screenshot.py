"""The screenshot keys: which part of the screen, where it is saved, and what happens after.

The pipeline is run for real, against stand-ins for maim, xclip and notify-send that record
their arguments, so the shell quoting and the order of the steps are what is tested.
"""

import datetime
import os
import pathlib
import subprocess

import pytest
import shared.screenshot
from shared.screenshot import Geometry

SCREEN = Geometry(3840, 2160, 3840, 0)


def test_a_region_is_selected_by_hand() -> None:
    command = shared.screenshot.capture_command("region", "/p.png", SCREEN)
    assert command[-1] == "--select"


# maim alone takes the whole X screen -- both monitors -- so the focused one is named.
def test_the_screen_capture_is_only_the_focused_screen() -> None:
    command = shared.screenshot.capture_command("screen", "/p.png", SCREEN)
    assert command[-2:] == ["--geometry", "3840x2160+3840+0"]


def test_a_window_capture_names_the_window() -> None:
    command = shared.screenshot.capture_command("window", "/p.png", SCREEN, window=4242)
    assert command[-2:] == ["--window", "4242"]


def test_a_window_capture_with_no_window_takes_the_screen() -> None:
    command = shared.screenshot.capture_command("window", "/p.png", SCREEN, window=None)
    assert "--geometry" in command


def test_the_file_is_named_for_the_moment() -> None:
    moment = datetime.datetime(2026, 10, 4, 9, 5, 7, tzinfo=datetime.UTC)
    assert shared.screenshot.target_path("/pics", moment) == (
        "/pics/Screenshots/2026-10-04_09-05-07.png"
    )


def test_the_pictures_directory_follows_xdg(tmp_path: pathlib.Path) -> None:
    (tmp_path / ".config").mkdir()
    (tmp_path / ".config" / "user-dirs.dirs").write_text('XDG_PICTURES_DIR="$HOME/Bilder"\n')
    assert shared.screenshot.pictures_directory(str(tmp_path)) == str(tmp_path / "Bilder")


def test_without_xdg_it_is_pictures(tmp_path: pathlib.Path) -> None:
    assert shared.screenshot.pictures_directory(str(tmp_path)) == str(tmp_path / "Pictures")


# ------------------------------------------------------------------------- the pipeline


@pytest.fixture
def tools(tmp_path: pathlib.Path) -> tuple[dict, pathlib.Path]:
    """Stand-ins for the three programs, each logging its argv; maim writes the file."""
    bin_directory, log = tmp_path / "bin", tmp_path / "calls.log"
    bin_directory.mkdir()
    for name, body in {
        "maim": 'for last; do :; done; [ -n "$MAIM_FAILS" ] && exit 1; echo png > "$last"',
        "xclip": "",
        "notify-send": "",
    }.items():
        script = bin_directory / name
        script.write_text(f'#!/bin/sh\necho "{name} $*" >> "{log}"\n{body}\n')
        script.chmod(0o755)
    environment = {**os.environ, "PATH": f"{bin_directory}:{os.environ['PATH']}"}
    return environment, log


def test_a_capture_is_saved_copied_and_announced(
    tmp_path: pathlib.Path, tools: tuple[dict, pathlib.Path]
) -> None:
    environment, log = tools
    path = tmp_path / "shots with spaces" / "Screenshots" / "a.png"
    command = shared.screenshot.capture_command("screen", str(path), SCREEN)
    subprocess.run(command, env=environment, check=True)
    assert path.read_text() == "png\n", "the directory is made and the file written"
    calls = log.read_text().splitlines()
    assert [call.split()[0] for call in calls] == ["maim", "xclip", "notify-send"]
    assert f"-i {path}" in calls[1]


# A cancelled region selection is maim exiting non-zero; nothing should be copied or announced.
def test_a_cancelled_capture_does_nothing_more(
    tmp_path: pathlib.Path, tools: tuple[dict, pathlib.Path]
) -> None:
    environment, log = tools
    command = shared.screenshot.capture_command("region", str(tmp_path / "a.png"), SCREEN)
    subprocess.run(command, env={**environment, "MAIM_FAILS": "1"}, check=False)
    assert [call.split()[0] for call in log.read_text().splitlines()] == ["maim"]
