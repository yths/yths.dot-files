"""Programs qtile starts because they cannot start before it.

``~/.xinitrc`` starts everything else, and starts it earlier. What lands here is the
exception: a program that needs something qtile itself provides, which for the moment means
the bar's system tray.
"""

import subprocess

#: Each entry is (argv, the name ``pgrep -x`` matches). The two are separate because a
#: program's process name is not always its argv[0] -- and because matching loosely is how a
#: guard like this ends up finding an unrelated process and skipping the start.
SESSION_PROGRAMS: tuple[tuple[list[str], str], ...] = (
    # Bridges the D-Bus screensaver inhibit a browser or video player takes to the logind
    # idle inhibit that xss-lock obeys, so a playing film stops the screen locking under it.
    # It publishes org.kde.StatusNotifierItem and needs a host to register with, which is why
    # it starts here rather than from ~/.xinitrc beside xss-lock: the bar does not exist yet.
    (["inhibit-bridge"], "inhibit-bridge"),
)


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
    and taking the session down over a missing status indicator is the wrong trade.
    """
    started = []
    for argv, process in programs:
        if is_running(process):
            continue
        try:
            subprocess.Popen(argv)
        except OSError:
            continue
        started.append(process)
    return started
