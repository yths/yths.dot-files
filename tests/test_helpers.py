"""The pure helpers: monitor geometry, dependency bookkeeping, calibration decisions."""

import os
from pathlib import Path
from typing import Any

import apply_icc
import list_dependencies
import pytest
import utils


def monitors(**named: dict[str, Any]) -> dict[str, Any]:
    return {"monitors": named}


# patch_xorg opened ~/.Xresources for writing and *then* divided by the monitor count, so a
# machine reporting none truncated the file to zero bytes and raised, aborting every patcher
# after it. Callers now read None as "leave this app alone".
def test_monitor_average_of_nothing_is_none() -> None:
    assert utils.monitor_average(monitors(), "width") is None
    assert utils.monitor_average({}, "width") is None
    assert utils.monitor_average({"monitors": None}, "width") is None


def test_monitor_average_ignores_monitors_missing_the_key() -> None:
    configuration = monitors(a={"width": 100}, b={"height": 50})
    assert utils.monitor_average(configuration, "width") == 100


def test_monitor_average_of_all_missing_is_none() -> None:
    assert utils.monitor_average(monitors(a={"height": 50}), "width") is None


def test_monitor_average_is_the_mean() -> None:
    assert utils.monitor_average(monitors(a={"dpi": 100}, b={"dpi": 200}), "dpi") == 150


def test_template_path_points_into_the_repository() -> None:
    path = utils.template_path("tmux", "tmux.conf.template")
    assert os.path.isfile(path), "the template a patcher reads must exist"
    assert path.startswith(utils.REPOSITORY_ROOT)


# The dependency table is generated from the imports; these two halves drifting apart is the
# failure it exists to prevent, so the check runs in the gate.
def test_recorded_packages_and_real_imports_agree() -> None:
    assert list_dependencies.mismatches(list_dependencies.third_party_imports()) == []


def test_a_missing_package_is_reported() -> None:
    assert any("no Arch package recorded" in problem
               for problem in list_dependencies.mismatches({"nonexistent": ["a.py"]}))


def test_a_package_nothing_imports_is_reported() -> None:
    problems = list_dependencies.mismatches({})
    assert problems and all("nothing imports it" in problem for problem in problems)


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        (["helper/a.py"], "`helper/a.py`"),
        (["helper/a.py", "helper/b.py"], "`helper/a.py`, `helper/b.py`"),
    ],
)
def test_few_users_are_named_individually(paths: list[str], expected: str) -> None:
    assert list_dependencies.describe_users(paths) == expected


def test_many_users_collapse_to_their_directory() -> None:
    paths = [f"widgets/{name}.py" for name in "abcde"]
    assert list_dependencies.describe_users(paths) == "`widgets/` (5 files)"


def test_a_directory_contributing_one_file_is_still_named(tmp_path: Path) -> None:
    described = list_dependencies.describe_users(
        ["a/one.py", "b/1.py", "b/2.py", "b/3.py", "b/4.py"]
    )
    assert "`a/one.py`" in described, "a lone file reads better than a count of one"
    assert "`b/` (4 files)" in described


# Every one of these is an ordinary state, not an error: the desktop installs and runs
# uncalibrated, and apply_icc exits 0 in all of them so a session never fails to start.
def test_no_profiles_for_this_host_is_a_reason_to_skip() -> None:
    assert "no display profiles configured" in apply_icc.skip_reason({}, [("1", "HDMI-1")])


def test_no_displays_is_a_reason_to_skip() -> None:
    assert apply_icc.skip_reason({"HDMI-1": "u28d590"}, []) == "dispwin reported no displays"


def test_a_configured_host_with_displays_goes_ahead() -> None:
    assert apply_icc.skip_reason({"HDMI-1": "u28d590"}, [("1", "HDMI-1")]) == ""


@pytest.mark.parametrize(
    ("given", "expected"),
    [("U28D590.icc", "u28d590"), ("S27B550_v3.icc", "s27b550-v3"), ("HP", "hp")],
)
def test_profile_names_are_canonicalised(given: str, expected: str) -> None:
    assert apply_icc.canonicalise(given) == expected
