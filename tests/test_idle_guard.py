"""Keeping the screen awake for a film, and armed the rest of the time.

xss-lock locks from the X screen saver, whose counter measures input. A playing film
produces none, so applications say so over D-Bus instead and `inhibit-bridge` turns that
into a logind idle inhibitor — but logind's idle logic and X's counter are separate clocks,
and nothing joined them. Measured on the running desktop with two inhibitors held, the
counter ran straight through them: 237156 ms, then 240156 ms three seconds later.

Verified end to end against the real X server and a real `systemd-inhibit`: with an
inhibitor held, one pass took the counter from 6010 ms to 1 ms; with none, it does nothing.
"""

import json
import subprocess

import pytest
from shared import idle_guard

#: One row as logind returns it: (what, who, why, mode, uid, pid).
SLEEP_ONLY = ["sleep", "xss-lock", "Lock screen first", "delay", 1000, 2104]
IDLE = ["idle", "inhibit-bridge", "firefox Playing video", "block", 1000, 2245]
IDLE_AND_SLEEP = ["idle:sleep", "some-player", "playing", "block", 1000, 999]


class FakeCommands:
    """Stands in for busctl and xset, recording what was run."""

    def __init__(self, rows: list | None = None, timeout: int = 512) -> None:
        self.rows = rows if rows is not None else []
        self.timeout = timeout
        self.run: list[list[str]] = []
        self.busctl_fails = False
        self.busctl_output: str | None = None

    def __call__(self, argv: list[str], **_: object) -> subprocess.CompletedProcess:
        self.run.append(argv)
        if argv[0] == "busctl":
            if self.busctl_fails:
                return subprocess.CompletedProcess(argv, 1, "", "refused")
            out = (self.busctl_output if self.busctl_output is not None
                   else json.dumps({"type": "a(ssssuu)", "data": [self.rows]}))
            return subprocess.CompletedProcess(argv, 0, out, "")
        if argv[:2] == ["xset", "q"]:
            return subprocess.CompletedProcess(
                argv, 0, f"Screen Saver:\n  prefer blanking: yes\n  timeout:  {self.timeout}    cycle:  512\n", ""
            )
        if argv[0] == "xset" and argv[1] == "s" and argv[2].isdigit():
            self.timeout = int(argv[2])
        return subprocess.CompletedProcess(argv, 0, "", "")


@pytest.fixture
def commands(monkeypatch: pytest.MonkeyPatch) -> FakeCommands:
    fake = FakeCommands()
    monkeypatch.setattr(idle_guard.subprocess, "run", fake)
    return fake


def _reset_calls(commands: FakeCommands) -> list[list[str]]:
    return [c for c in commands.run if c[:3] == ["xset", "s", "reset"]]


# ------------------------------------------------------------------ what counts as idle

def test_an_idle_inhibitor_is_found(commands: FakeCommands) -> None:
    commands.rows = [IDLE]
    assert idle_guard.idle_inhibitors() == [("inhibit-bridge", "firefox Playing video")]


def test_a_sleep_inhibitor_is_not_one(commands: FakeCommands) -> None:
    """xss-lock holds one of these permanently; treating it as idle would mean the screen
    never locked again."""
    commands.rows = [SLEEP_ONLY]
    assert idle_guard.idle_inhibitors() == []


def test_a_combined_inhibitor_counts(commands: FakeCommands) -> None:
    """`what` is colon-separated, so "idle:sleep" is an idle inhibitor too."""
    commands.rows = [IDLE_AND_SLEEP]
    assert idle_guard.idle_inhibitors() == [("some-player", "playing")]


def test_sleep_does_not_mask_idle(commands: FakeCommands) -> None:
    commands.rows = [SLEEP_ONLY, IDLE]
    assert [who for who, _ in idle_guard.idle_inhibitors()] == ["inhibit-bridge"]


# --------------------------------------------------- silence has to mean "nothing is held"

def test_an_unreadable_answer_inhibits_nothing(commands: FakeCommands) -> None:
    """The cost of guessing wrong is a screen that stays unlocked, so every failure here
    has to fall towards locking."""
    commands.busctl_fails = True
    assert idle_guard.idle_inhibitors() == []


def test_unparseable_output_inhibits_nothing(commands: FakeCommands) -> None:
    commands.busctl_output = "not json at all"
    assert idle_guard.idle_inhibitors() == []


def test_a_missing_busctl_inhibits_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    def absent(*_: object, **__: object) -> None:
        raise OSError(2, "No such file or directory")
    monkeypatch.setattr(idle_guard.subprocess, "run", absent)
    assert idle_guard.idle_inhibitors() == []
    assert idle_guard.screensaver_timeout() is None


# ------------------------------------------------------------------------------ the pass

def test_the_counter_is_reset_while_something_is_inhibiting(commands: FakeCommands) -> None:
    commands.rows = [IDLE]
    _, inhibitors = idle_guard.guard(512)
    assert [who for who, _ in inhibitors] == ["inhibit-bridge"]
    assert len(_reset_calls(commands)) == 1


def test_nothing_is_reset_when_nothing_is_inhibiting(commands: FakeCommands) -> None:
    """Otherwise the session would never go idle and the screen would never lock."""
    restored, inhibitors = idle_guard.guard(512)
    assert (restored, inhibitors) == (False, [])
    assert _reset_calls(commands) == []


def test_a_disabled_timeout_is_put_back(commands: FakeCommands) -> None:
    """The measured case: this machine was found at timeout 0 with Steam running, having
    silently stopped locking itself."""
    commands.timeout = 0
    restored, _ = idle_guard.guard(512)
    assert restored
    assert commands.timeout == 512


def test_a_deliberate_timeout_is_left_alone(commands: FakeCommands) -> None:
    """Only zero is treated as broken. Zero is not a longer wait, it is no lock at all."""
    commands.timeout = 900
    restored, _ = idle_guard.guard(512)
    assert not restored
    assert commands.timeout == 900


def test_the_timeout_is_restored_even_while_inhibited(commands: FakeCommands) -> None:
    """The inhibitors will go away; the timeout has to be there when they do."""
    commands.timeout = 0
    commands.rows = [IDLE]
    restored, inhibitors = idle_guard.guard(512)
    assert restored and inhibitors
    assert commands.timeout == 512


def test_nothing_is_restored_without_a_configured_timeout(commands: FakeCommands) -> None:
    """If it was already 0 when qtile started there is no value to put back, and inventing
    one would be this file deciding the machine's lock policy."""
    commands.timeout = 0
    restored, _ = idle_guard.guard(None)
    assert not restored
    assert commands.timeout == 0


def test_the_interval_is_well_inside_a_plausible_timeout() -> None:
    """A pass has to land between the counter starting and the timeout firing."""
    assert idle_guard.CHECK_SECONDS < 512 / 4
