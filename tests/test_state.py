"""``shared.state``: the atomic write, and the vocabulary migration."""

import json
import os
from pathlib import Path

import pytest
from shared import state


def write(path: Path, configuration: dict) -> Path:
    path.write_text(json.dumps(configuration))
    return path


# The rename of `mode` to `theme_mode` had to reach an installed file that no longer matches
# the code. Reading `theme_mode` off a legacy file gives None, which reads as "the user
# pinned this" -- so without this translation the automatic theme switch would have stopped
# at the next dusk, silently, on every machine not reinstalled since.
@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        ({"mode": "automatic"}, {"theme_mode": "automatic"}),
        ({"mode": "manual"}, {"theme_mode": "manual"}),
        ({"audio_mode": "auto"}, {"audio_mode": "automatic"}),
        ({"mode": "automatic", "audio_mode": "auto"},
         {"theme_mode": "automatic", "audio_mode": "automatic"}),
        # Already current: unchanged.
        ({"theme_mode": "manual"}, {"theme_mode": "manual"}),
        # Both keys present: the current one wins and the legacy one goes.
        ({"mode": "manual", "theme_mode": "automatic"}, {"theme_mode": "automatic"}),
        # Nothing to translate.
        ({"theme": "dark"}, {"theme": "dark"}),
        ({}, {}),
    ],
)
def test_normalise_state_translates_the_old_vocabulary(stored: dict, expected: dict) -> None:
    assert state.normalise_state(stored) == expected


def test_normalise_state_does_not_mutate_its_argument() -> None:
    stored = {"mode": "automatic"}
    state.normalise_state(stored)
    assert stored == {"mode": "automatic"}


def test_read_state_normalises(tmp_path: Path) -> None:
    path = write(tmp_path / "config.json", {"state": {"mode": "manual", "audio_mode": "auto"}})
    assert state.read_state(str(path))["state"] == {
        "theme_mode": "manual", "audio_mode": "automatic"
    }


# A legacy file must migrate itself, or the translation above is load-bearing forever.
def test_first_write_persists_the_current_vocabulary(tmp_path: Path) -> None:
    path = write(tmp_path / "config.json", {"state": {"mode": "automatic", "audio_mode": "auto"}})
    state.update_state(str(path), theme="light")
    stored = json.loads(path.read_text())["state"]
    assert stored == {"theme_mode": "automatic", "audio_mode": "automatic", "theme": "light"}
    assert "mode" not in stored


@pytest.mark.parametrize("content", ["", "{", "[]", '"a string"', "null"])
def test_read_state_survives_anything_that_is_not_an_object(tmp_path: Path, content: str) -> None:
    # poll() must never raise: an exception escaping it stops qtile rescheduling the cell for
    # the rest of the session.
    path = tmp_path / "config.json"
    path.write_text(content)
    assert state.read_state(str(path)) == {}


def test_read_state_survives_a_missing_file(tmp_path: Path) -> None:
    assert state.read_state(str(tmp_path / "absent.json")) == {}


# install.py and the patchers read this file from other processes while the bar writes it.
# A plain open(path, "w") truncates before it refills, so a reader landing in that window
# sees a partial file; the write goes to a sibling temporary and lands via os.replace.
def test_write_leaves_no_window_where_the_file_is_partial(tmp_path: Path) -> None:
    path = write(tmp_path / "config.json", {"state": {"theme": "dark"}})
    state.write_state({"state": {"theme": "light"}}, str(path))
    assert json.loads(path.read_text()) == {"state": {"theme": "light"}}
    # The temporary is gone, and nothing else was left behind.
    assert [p.name for p in tmp_path.iterdir()] == ["config.json"]


def test_write_cleans_up_when_the_payload_cannot_be_serialised(tmp_path: Path) -> None:
    path = write(tmp_path / "config.json", {"state": {"theme": "dark"}})
    assert state.write_state({"bad": {1, 2}}, str(path)) is False
    assert json.loads(path.read_text()) == {"state": {"theme": "dark"}}, "target untouched"
    assert [p.name for p in tmp_path.iterdir()] == ["config.json"], "temporary removed"


def test_update_state_on_a_missing_file_writes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "absent.json"
    assert state.update_state(str(path), theme="light") == {}
    assert not os.path.exists(path)
