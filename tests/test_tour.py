"""The README's screenshots: what is recorded about them, and what the capture may reach.

The capture itself is not run here -- it needs a display and half a minute. What is tested is
everything around it that can be wrong without anyone looking: an image larger than the page
should carry, a file the README shows that was never captured, and the properties that keep
a capture from touching the machine it runs on.
"""

import hashlib
import json
import os
import pathlib
import stat

import capture_tour
import gendocs
import list_tour
import pytest

TOUR = pathlib.Path(capture_tour.__file__).parent / "tour"
WIDGETS = pathlib.Path(capture_tour.REPO_ROOT) / "configuration" / "qtile" / "widgets"


# ---------------------------------------------------------------------------- the images


@pytest.mark.parametrize("shot", list_tour.SHOTS, ids=lambda shot: shot.file)
def test_every_screenshot_is_the_one_that_was_captured(shot: list_tour.Shot) -> None:
    """An image edited or swapped by hand no longer shows what the tools produce."""
    recorded = list_tour.read_manifest()["files"][shot.file]
    data = (list_tour.PREVIEW_DIRECTORY / shot.file).read_bytes()
    assert hashlib.sha256(data).hexdigest() == recorded["sha256"]


@pytest.mark.parametrize("shot", list_tour.SHOTS, ids=lambda shot: shot.file)
def test_no_screenshot_is_larger_than_a_readme_should_carry(shot: list_tour.Shot) -> None:
    size = (list_tour.PREVIEW_DIRECTORY / shot.file).stat().st_size
    assert size <= list_tour.MAX_IMAGE_BYTES, f"{shot.file} is {size} bytes"


def test_nothing_else_is_kept_beside_the_screenshots() -> None:
    """A screenshot dropped from the table would otherwise stay tracked and unreferenced."""
    expected = {shot.file for shot in list_tour.SHOTS} | {list_tour.MANIFEST.name}
    assert {path.name for path in list_tour.PREVIEW_DIRECTORY.iterdir()} == expected


def test_the_tour_shows_every_screenshot_but_the_hero_once() -> None:
    body = list_tour.generate_markdown()
    for shot in list_tour.SHOTS:
        assert body.count(f"docs/preview/{shot.file}") == (0 if shot.hero else 1)


def test_the_readme_places_the_hero_with_its_recorded_alt_text() -> None:
    readme = (pathlib.Path(capture_tour.REPO_ROOT) / "README.md").read_text(encoding="utf-8")
    (hero,) = [shot for shot in list_tour.SHOTS if shot.hero]
    assert f"![{hero.alt}](docs/preview/{hero.file})" in readme


def test_a_wide_screenshot_gets_a_line_to_itself() -> None:
    """In a table cell two monitors are drawn at half the page's width."""
    for shot in list_tour.SHOTS:
        if shot.wide:
            line = next(
                line for line in list_tour.generate_markdown().splitlines() if shot.file in line
            )
            assert not line.startswith("|")


# ------------------------------------------------------------------------- staleness


def test_the_digest_follows_the_palette(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "assets" / "default"
    bundle.mkdir(parents=True)
    (bundle / "config.json").write_text('{"name": "default"}')
    (bundle / "palette.json").write_text('{"dark": {"background": "#000000"}}')
    monkeypatch.setattr(list_tour, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(list_tour, "read_setup", lambda: {"desktop": {"theme": "default"}})
    before = list_tour.inputs_digest()
    (bundle / "palette.json").write_text('{"dark": {"background": "#111111"}}')
    assert list_tour.inputs_digest() != before


def test_screenshots_of_another_palette_are_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(list_tour, "inputs_digest", lambda: "not the recorded one")
    assert gendocs.stale_tour()


def test_screenshots_never_captured_are_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(list_tour, "read_manifest", dict)
    assert gendocs.stale_tour() == ["docs/preview/ has never been captured"]


# Nobody can re-take a screenshot from inside a commit hook, so a stale one is said, not
# refused. A missing one is refused, through the dead link the README is left with.
def test_stale_screenshots_are_a_warning_and_not_an_invariant() -> None:
    assert not any("screenshot" in title.lower() for title, _, _ in gendocs.invariants())


def test_recording_one_capture_keeps_the_others(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The boot frames and the desktop are captured separately; neither may forget the other."""
    first, second = list_tour.SHOTS[0].file, list_tour.SHOTS[1].file
    for name in (first, second):
        (tmp_path / name).write_bytes(name.encode())
    monkeypatch.setattr(list_tour, "PREVIEW_DIRECTORY", tmp_path)
    monkeypatch.setattr(list_tour, "MANIFEST", tmp_path / "captured-from.json")
    list_tour.record([first])
    list_tour.record([second])
    assert set(json.loads((tmp_path / "captured-from.json").read_text())["files"]) == {
        first, second,
    }


# ------------------------------------------------------------------------- isolation
#
# A capture applies the shipped theme and performs a theme switch. Run against the wrong
# session, that rethemes a desktop, kills its notification daemon and restarts its window
# manager -- so what the staged session can reach is asserted, not left to review.


def test_the_session_inherits_nothing_that_names_the_real_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS", "WAYLAND_DISPLAY"):
        monkeypatch.setenv(name, "the-real-one")
    environment = capture_tour.session_environment()
    assert "the-real-one" not in environment.values()
    assert not {"DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS"} & set(environment)


def test_no_staged_path_is_under_the_real_home() -> None:
    home = os.path.expanduser("~")
    for value in capture_tour.session_environment().values():
        assert home not in value.split(":"), value
        assert not value.startswith(home + "/"), value


def test_the_sandbox_has_its_own_processes_network_and_host() -> None:
    """What confines ``killall dunst`` and the reload signals to the staged programs."""
    command = capture_tour.sandbox_command(pathlib.Path("/scratch"), ["true"])
    for flag in ("--unshare-pid", "--unshare-net", "--unshare-uts", "--clearenv",
                 "--die-with-parent"):
        assert flag in command
    assert command[-2:] == ["--", "true"]


def test_the_system_is_mounted_read_only() -> None:
    command = capture_tour.sandbox_command(pathlib.Path("/scratch"), ["true"])
    for directory in ("/usr", "/etc"):
        index = command.index(directory)
        assert command[index - 1] == "--ro-bind" and command[index + 1] == directory


def test_the_only_writable_mount_is_the_scratch_home() -> None:
    command = capture_tour.sandbox_command(pathlib.Path("/scratch"), ["true"], as_root=True)
    writable = [command[index + 1] for index, flag in enumerate(command) if flag == "--bind"]
    assert all(source.startswith("/scratch/") for source in writable), writable


def test_the_boot_capture_cannot_see_the_theme_this_machine_boots_with() -> None:
    """An empty directory is mounted over plymouth's, then the staged theme into it."""
    command = capture_tour.sandbox_command(pathlib.Path("/scratch"), ["true"], as_root=True)
    cover = command.index(capture_tour.BOOT_THEME_ROOT)
    assert command[cover - 1] == "--tmpfs"
    staged = command.index(f"{capture_tour.BOOT_THEME_ROOT}/{capture_tour.BOOT_THEME}")
    assert staged > cover and command[staged - 2] == "--bind"


def test_the_boot_theme_has_a_name_no_install_gives_one() -> None:
    assert capture_tour.BOOT_THEME not in {"default", "dot-files-default"}


def test_nothing_in_the_capture_installs_a_boot_theme() -> None:
    """Rendering is reused; installing sets the default theme and rebuilds the initramfs."""
    source = pathlib.Path(capture_tour.__file__).read_text(encoding="utf-8")
    for name in ("install_theme", "install_system", "plymouth-set-default-theme", "mkinitcpio",
                 "sudo"):
        assert name not in source, name


# ---------------------------------------------------------------------- staged content


def test_every_bar_cell_has_a_staged_reading() -> None:
    """A cell without one draws empty, and an empty bar is what the screenshots replaced."""
    cells = {path.stem for path in WIDGETS.glob("*.py")} - {"service_state"}
    assert set(capture_tour.STREAMS) == cells


def test_the_staged_location_cannot_move_the_clock() -> None:
    """``timezone`` is the field the bar follows with ``timedatectl``."""
    assert "timezone" not in capture_tour.STREAMS["location"]


def test_no_staged_reading_names_a_place_or_a_tunnel() -> None:
    assert capture_tour.STREAMS["vpn"] == {"connected": False}
    assert set(capture_tour.STREAMS["location"]) == {"sunrise", "sunset", "vpn"}


@pytest.mark.parametrize("name", ["systemctl", "timedatectl", "xss-lock", "inhibit-bridge"])
def test_the_programs_that_reach_past_a_session_are_stood_in_for(name: str) -> None:
    shim = TOUR / "shims" / name
    assert shim.stat().st_mode & stat.S_IXUSR
    assert capture_tour.session_environment()["PATH"].startswith(
        f"{capture_tour.SANDBOX_REPOSITORY}/helper/tour/shims:"
    )


def test_the_lock_prompt_never_asks_pam() -> None:
    """The stand-in must not be named like a real helper: xsecurelock refuses those."""
    stub = TOUR / "authproto_stub"
    assert stub.stat().st_mode & stat.S_IXUSR
    assert not stub.name.startswith("auth_")
    assert "authproto_pam" not in pathlib.Path(capture_tour.__file__).read_text(encoding="utf-8")


def test_every_capture_can_be_selected_by_name() -> None:
    assert set(capture_tour.CAPTURES) >= capture_tour.ROOT_CAPTURES
