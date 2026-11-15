"""Keep the system timezone at the zone the machine is geolocated in.

The sunrise/sunset cell calls ``TimezoneFollower.follow`` with the IP-derived zone on every
poll. When that zone differs from the system's, it runs ``timedatectl --no-ask-password
set-timezone``. The policy that allows this without a password is the polkit rule in
``configuration/timezone/``. Without the rule the call is refused rather than prompting: it is
logged once and that zone is not tried again this session.

The poll runs on qtile's event loop, so nothing here waits. ``timedatectl`` is started and
collected on a later poll. Once ``/etc/localtime`` names a new zone -- set here or by hand --
``time.tzset()`` makes qtile itself, and with it the stock bar clock, pick it up; every other
program reads the file afresh.
"""

import os
import subprocess
import time
import zoneinfo
from collections.abc import Callable

import libqtile.log_utils

LOCALTIME = "/etc/localtime"


def system_zone(path: str = LOCALTIME) -> str | None:
    """The zone ``/etc/localtime`` links to, e.g. ``Europe/Berlin``, or ``None``."""
    target = os.path.realpath(path)
    _, found, zone = target.partition("/zoneinfo/")
    return zone if found and zone else None


def is_known(zone: str) -> bool:
    """Whether ``zone`` is a key this machine's tz database has. ``ZoneInfo`` refuses
    absolute paths and ``..``, so a hostile string from the stream cannot name a file."""
    try:
        zoneinfo.ZoneInfo(zone)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        return False
    return True


class TimezoneFollower:
    def __init__(
        self,
        spawn: Callable[..., subprocess.Popen] = subprocess.Popen,
        current: Callable[[], str | None] = system_zone,
    ) -> None:
        self.spawn = spawn
        self.current = current
        self.pending: subprocess.Popen | None = None
        self.pending_zone: str | None = None
        #: Zones timedatectl refused. Retrying every second would only repeat the refusal;
        #: a qtile restart, say after installing the rule, clears it.
        self.refused: set[str] = set()
        self.seen = current()

    def _collect(self) -> bool:
        """Reap a finished ``timedatectl``. Returns whether one is still running."""
        if self.pending is None:
            return False
        returncode = self.pending.poll()
        if returncode is None:
            return True
        if returncode != 0:
            self.refused.add(str(self.pending_zone))
            libqtile.log_utils.logger.warning(
                "Could not set the timezone to %s (timedatectl exited %s). Run "
                "`python install.py --system` to install the rule that allows it.",
                self.pending_zone, returncode,
            )
        self.pending = None
        self.pending_zone = None
        return False

    def follow(self, zone: str | None) -> None:
        running = self._collect()
        system = self.current()
        if system != self.seen:
            # The zone changed under this process; Python caches it until told.
            time.tzset()
            self.seen = system
        if running or not zone or zone == system or zone in self.refused or not is_known(zone):
            return
        try:
            self.pending = self.spawn(
                ["timedatectl", "--no-ask-password", "set-timezone", zone],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except OSError:
            self.refused.add(zone)
            return
        self.pending_zone = zone
