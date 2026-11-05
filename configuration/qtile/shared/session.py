"""Start guarded session programs for both LightDM and startx logins."""

import os
import subprocess

#: Each entry is (argv, the name ``pgrep -x`` matches). The two are separate because a
#: program's process name is not always its argv[0] -- and because matching loosely is how a
#: guard like this ends up finding an unrelated process and skipping the start.
SESSION_PROGRAMS: tuple[tuple[list[str], str], ...] = (
    (["xss-lock", "--transfer-sleep-lock", "--", os.path.join(
        os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "lock", "lock.sh"
    )], "xss-lock"),
    (["inhibit-bridge"], "inhibit-bridge"),
)


def configure_locking() -> bool:
    """Set X idle and DPMS timeouts before starting the lock daemon."""
    try:
        idle = subprocess.run(["xset", "s", "512", "512"], check=False)
        dpms = subprocess.run(["xset", "dpms", "512", "512", "1024"], check=False)
    except OSError:
        return False
    return idle.returncode == 0 and dpms.returncode == 0


def is_running(process: str) -> bool:
    """Whether a process of exactly this name is running.

    ``False`` when the question cannot be asked -- no pgrep, or it failed to run. Starting a
    second copy is a smaller fault than silently starting none, which is what the opposite
    default would do on a machine missing procps.
    """
    try:
        result = subprocess.run(["pgrep", "-x", process], capture_output=True, check=False)
    except OSError:
        return False
    return result.returncode == 0


def start_programs(programs: tuple[tuple[list[str], str], ...] = SESSION_PROGRAMS) -> list[str]:
    """Start each program that is not already running. Returns the names actually started.

    Guarded rather than unconditional because the hook that calls this fires on every qtile
    start, and qtile restarts on each theme switch -- twice a day -- and again whenever a
    display is plugged in. Starting unconditionally would leave another copy behind every
    time. The guard also means a program that has died is started again by the next restart.

    A program that is not installed is skipped rather than raised: this runs during startup,
    and missing session utilities must not take the desktop down.
    """
    started = []
    for argv, process in programs:
        if is_running(process):
            continue
        if process == "xss-lock":
            configure_locking()
        try:
            subprocess.Popen(argv)
        except OSError:
            continue
        started.append(process)
    return started
