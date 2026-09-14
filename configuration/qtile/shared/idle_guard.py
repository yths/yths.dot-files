"""Keep X's idle counter in step with what applications are actually asking for.

``xss-lock`` locks the session from the X screen saver, and X's idle counter measures
*input*. A playing film produces none, so to X it is indistinguishable from an empty room.
Applications say otherwise over D-Bus -- ``org.freedesktop.ScreenSaver`` -- and
``inhibit-bridge`` turns that into a logind idle inhibitor, but nothing here was listening:
logind's idle logic and X's idle counter are two separate clocks, and ``xss-lock`` consults
the second one. Measured with two inhibitors held, the counter ran on regardless::

    now                    idle= 237156 ms
    after 3s               idle= 240156 ms
    after 'xset s reset'   idle=      0 ms

This is the half that was missing. While anything holds an idle inhibitor, the counter is
reset before it can reach the timeout -- which defers the lock and the monitor's power-down
together, since DPMS hangs off the same counter.

It also puts the timeout back when it finds it at zero. A timeout of zero is not a longer
wait, it is no automatic lock at all, and it is set by other people's software: this machine
was found at ``timeout: 0`` with Steam running, having silently stopped locking itself.
"""

import json
import re
import subprocess

#: How often to look. The X timeout is several minutes, so this only has to be comfortably
#: shorter than it; each pass is one D-Bus call and, at most, one xset.
CHECK_SECONDS = 60

#: ``xset q`` reports the screen saver timeout in seconds on this line.
TIMEOUT_LINE = re.compile(r"^\s*timeout:\s*(\d+)", re.MULTILINE)


def idle_inhibitors() -> list[tuple[str, str]]:
    """Everything currently asking the session not to be considered idle, as (who, why).

    Read from logind rather than from ``org.freedesktop.ScreenSaver`` directly, because
    ``inhibit-bridge`` owns that name and answering it is its job, not ours. Its output is
    the queryable form of every application's request, which is what makes it useful here
    even though logind's own idle action is disabled on this machine.

    An empty list when the question cannot be asked. The consequence of guessing wrong is a
    screen that stays unlocked, so silence has to mean "nothing is inhibiting".
    """
    try:
        result = subprocess.run(
            ["busctl", "--json=short", "call", "org.freedesktop.login1",
             "/org/freedesktop/login1", "org.freedesktop.login1.Manager", "ListInhibitors"],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        return []
    if result.returncode != 0:
        return []
    try:
        rows = json.loads(result.stdout)["data"][0]
    except (ValueError, KeyError, IndexError):
        return []
    # Each row is (what, who, why, mode, uid, pid); `what` is colon-separated, so an
    # inhibitor of "idle:sleep" counts and one of "sleep" alone does not.
    return [
        (row[1], row[2])
        for row in rows
        if len(row) >= 3 and "idle" in str(row[0]).split(":")
    ]


def screensaver_timeout() -> int | None:
    """X's configured idle timeout in seconds, or ``None`` if it cannot be read."""
    try:
        result = subprocess.run(["xset", "q"], capture_output=True, text=True, check=False)
    except OSError:
        return None
    if result.returncode != 0:
        return None
    match = TIMEOUT_LINE.search(result.stdout)
    return int(match.group(1)) if match else None


def _xset(*arguments: str) -> bool:
    try:
        return subprocess.run(
            ["xset", *arguments], capture_output=True, check=False
        ).returncode == 0
    except OSError:
        return False


def reset_idle_counter() -> bool:
    """Put X's idle counter back to zero, deferring both the lock and DPMS."""
    return _xset("s", "reset")


def restore_timeout(seconds: int) -> bool:
    """Re-arm the screen saver, keeping the cycle X already has."""
    return _xset("s", str(seconds))


def guard(configured_timeout: int | None) -> tuple[bool, list[tuple[str, str]]]:
    """One pass. Returns (whether the timeout had to be restored, who is inhibiting).

    The two halves are independent: a disabled timeout is put back whether or not anything
    is inhibiting, because the inhibitors will go away and the timeout has to be there when
    they do.
    """
    restored = False
    if configured_timeout and screensaver_timeout() == 0:
        restored = restore_timeout(configured_timeout)

    inhibitors = idle_inhibitors()
    if inhibitors:
        reset_idle_counter()
    return restored, inhibitors
