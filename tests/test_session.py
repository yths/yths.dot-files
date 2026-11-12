"""Starting the programs that cannot start before qtile does.

The guard is the whole of it. This runs from `startup_complete`, which fires on every qtile
start — and qtile restarts on each theme switch, twice a day, and again on a monitor hotplug.
Starting unconditionally would leave one more copy of every program behind each time.
"""

import subprocess

import pytest
import shared.session
from utils import read_setup


class Recorder:
    """Stands in for subprocess, recording what would have been started."""

    def __init__(
        self, *, running: set[str] | None = None, missing: set[str] | None = None
    ) -> None:
        self.running = running or set()
        self.missing = missing or set()
        self.started: list[list[str]] = []

    def run(self, argv: list[str], **_: object) -> subprocess.CompletedProcess:
        assert argv[:2] == ["pgrep", "-x"], argv
        return subprocess.CompletedProcess(argv, 0 if argv[2] in self.running else 1)

    def popen(self, argv: list[str], **_: object) -> None:
        if argv[0] in self.missing:
            raise OSError(2, "No such file or directory")
        self.started.append(argv)


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> Recorder:
    made = Recorder()
    monkeypatch.setattr(shared.session.subprocess, "run", made.run)
    monkeypatch.setattr(shared.session.subprocess, "Popen", made.popen)
    return made


PROGRAMS = ((["some-daemon", "--flag"], "some-daemon"),)


def test_a_program_that_is_not_running_is_started(recorder: Recorder) -> None:
    assert shared.session.start_programs(PROGRAMS) == ["some-daemon"]
    assert recorder.started == [["some-daemon", "--flag"]]


def test_a_program_already_running_is_left_alone(recorder: Recorder) -> None:
    """The regression this guard exists for: a second copy per qtile restart."""
    recorder.running = {"some-daemon"}
    assert shared.session.start_programs(PROGRAMS) == []
    assert recorder.started == []


def test_restarting_qtile_repeatedly_starts_one_copy(recorder: Recorder) -> None:
    shared.session.start_programs(PROGRAMS)
    recorder.running = {"some-daemon"}          # it is running now
    for _ in range(5):
        shared.session.start_programs(PROGRAMS)
    assert recorder.started == [["some-daemon", "--flag"]]


def test_a_program_that_died_is_started_again(recorder: Recorder) -> None:
    recorder.running = {"some-daemon"}
    assert shared.session.start_programs(PROGRAMS) == []
    recorder.running = set()                     # it exited
    assert shared.session.start_programs(PROGRAMS) == ["some-daemon"]


def test_a_missing_program_does_not_take_the_session_down(recorder: Recorder) -> None:
    """This runs during startup. A missing status indicator must not stop the desktop."""
    recorder.missing = {"some-daemon"}
    assert shared.session.start_programs(PROGRAMS) == []


def test_one_missing_program_does_not_stop_the_others(recorder: Recorder) -> None:
    recorder.missing = {"absent"}
    programs = ((["absent"], "absent"), (["present"], "present"))
    assert shared.session.start_programs(programs) == ["present"]


def test_without_pgrep_the_program_is_started_rather_than_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Skipping would silently start nothing, which is the worse of the two failures."""
    def no_pgrep(*_: object, **__: object) -> None:
        raise OSError(2, "No such file or directory")
    monkeypatch.setattr(shared.session.subprocess, "run", no_pgrep)
    assert shared.session.is_running("anything") is False


def test_the_match_is_exact(recorder: Recorder) -> None:
    """`pgrep -x`, not a substring: a loose match finds an unrelated process and skips."""
    shared.session.is_running("some-daemon")
    # Recorder.run asserts the -x flag is present; reaching here is the assertion.


def test_the_bridge_is_what_the_session_starts() -> None:
    """It is in the registry, and named the way pgrep will find it."""
    assert ([" ".join(argv) for argv, _ in shared.session.SESSION_PROGRAMS]
            == ["inhibit-bridge"])
    assert [name for _, name in shared.session.SESSION_PROGRAMS] == ["inhibit-bridge"]


def test_the_bridge_is_in_the_install_list() -> None:
    """qtile starting it is no use if bootstrap.sh never installed it."""
    assert "inhibit-bridge-git" in read_setup()["packages"]["core"]
