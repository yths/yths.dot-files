"""Qtile widget: AC/battery state.

Reads the latest entry from the ``power_supply`` Redis stream and renders the grid/battery
icon plus one battery glyph per battery. Hovering expands the cell to each battery's charge,
the present draw, the time left -- to empty, or to the charge threshold while charging --
and TLP's active profile. Right-click sends the full breakdown to dunst: energy, health
against design capacity, cycle count and charge thresholds per battery, the figures
``tlp-stat -b`` would show. ``BackgroundPoll`` based.
"""

import contextlib
import subprocess
from typing import Any

import libqtile.widget.base
import redis
import shared.hover
import shared.stream
import symbols as vocabulary


class WidgetPowerSupply(shared.hover.HoverExpand, libqtile.widget.base.BackgroundPoll):
    #: Below this the discharging symbol is tinted with ``warning_color``.
    WARNING_CAPACITY = 20

    def __init__(
        self,
        r: redis.Redis | None,
        warning_color: str = "#ff0000",
        symbols: dict[str, Any] | None = None,
        strings: dict[str, str] | None = None,
        **config: Any,
    ) -> None:
        libqtile.widget.base.BackgroundPoll.__init__(self, "", **config)
        self.r = r

        self.warning_color = warning_color
        #: The active vocabulary, from ~/.config/config.json via config.py -- the same route
        #: the colours take. Falls back to the ASCII defaults so a widget built without one
        #: still draws something.
        self.symbols = symbols or vocabulary.SYMBOLS
        self.strings = strings or vocabulary.STRINGS

        self.measurement: dict[str, Any] | None = None
        self.expanded = False

        self.add_callbacks({"Button3": self.notify})

    def _symbol(self, capacity: float, charging: bool) -> str:
        """The rung of the battery ladder this capacity sits on.

        Indexed by ``capacity // 10``, so entry *n* covers n0-n9 % and the last covers 100 %.
        The ladders are in the vocabulary rather than here: a theme swaps them, and a machine
        without the font gets ASCII instead of eleven empty boxes.
        """
        capacity = min(max(capacity, 0), 100)
        key = "battery.charging" if charging else "battery.discharging"
        symbol = self.symbols[key][int(capacity) // 10]
        if not charging and capacity < self.WARNING_CAPACITY:
            return f"<span color='{self.warning_color}'>{symbol}</span>"
        return symbol

    @staticmethod
    def _number(value: Any) -> float | None:
        if isinstance(value, bool) or value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _duration(seconds: float) -> str:
        seconds = max(int(seconds), 0)
        hours, remainder = divmod(seconds, 3600)
        return f"{hours}h{remainder // 60:02d}" if hours else f"{remainder // 60}m"

    def _batteries(self) -> list[tuple[str, dict[str, Any], float]]:
        """``(name, state, capacity)`` for every battery whose capacity is readable."""
        batteries = (self.measurement or {}).get("batteries")
        if not isinstance(batteries, dict):
            return []
        readable = []
        for name, state in batteries.items():
            if not isinstance(state, dict):
                continue
            capacity = self._number(state.get("capacity"))
            if capacity is not None:
                readable.append((name, state, capacity))
        return readable

    def _draw(self, batteries: list[tuple[str, dict[str, Any], float]]) -> float | None:
        draws = [self._number(state.get("power_w")) for _, state, _ in batteries]
        draws = [draw for draw in draws if draw is not None]
        return sum(draws) if draws else None

    def _time_left(self, batteries: list[tuple[str, dict[str, Any], float]]) -> str:
        """The longest countdown across batteries, labelled by what it counts down to.

        The longest, because a ThinkPad drains or fills its two batteries one after the
        other: the one idling now has its turn after the active one finishes.
        """
        counted = [
            (self._number(state.get("seconds_left")), state.get("status"))
            for _, state, _ in batteries
        ]
        counted = [(seconds, status) for seconds, status in counted if seconds]
        if not counted:
            return ""
        seconds, status = max(counted)
        label = self.strings["battery.to_threshold" if status == "Charging" else "battery.left"]
        return f"{self._duration(seconds)} {label}"

    def _profile(self, short: bool) -> str:
        """TLP's profile, ``performance/PRF``, as ``PRF`` in the bar or ``performance``."""
        tlp = (self.measurement or {}).get("tlp")
        profile = tlp.get("profile") if isinstance(tlp, dict) else None
        if not isinstance(profile, str) or not profile:
            return ""
        name, _, abbreviation = profile.partition("/")
        return (abbreviation or name) if short else name

    def _render(self) -> str:
        if self.measurement is None:
            return ""

        output = []
        if self.measurement.get("grid"):
            output.append(self.symbols["battery.grid"])
        batteries = self._batteries()
        for _, state, capacity in batteries:
            symbol = self._symbol(capacity, state.get("status") == "Charging")
            output.append(f"{symbol} {capacity:.0f}%" if self.expanded else symbol)
        if not self.expanded:
            return " ".join(output)

        draw = self._draw(batteries)
        if draw is not None:
            output.append(f"{draw:.1f} W")
        for detail in (self._time_left(batteries), self._profile(short=True)):
            if detail:
                output.append(detail)
        return " ".join(output)

    def _battery_summary(self, name: str, state: dict[str, Any], capacity: float) -> str:
        parts = [f"{name} {capacity:.0f}%"]
        now = self._number(state.get("energy_now_wh"))
        full = self._number(state.get("energy_full_wh"))
        if now is not None and full is not None:
            parts.append(f"{now:.1f}/{full:.1f} Wh")
        health = self._number(state.get("health"))
        if health is not None:
            parts.append(f"{self.strings['battery.health']} {health:.0f}%")
        cycles = self._number(state.get("cycle_count"))
        if cycles is not None:
            parts.append(f"{cycles:.0f} {self.strings['battery.cycles']}")
        start = self._number(state.get("charge_start_threshold"))
        end = self._number(state.get("charge_end_threshold"))
        if start is not None and end is not None:
            parts.append(f"{self.strings['battery.thresholds']} {start:.0f}-{end:.0f}%")
        return " · ".join(parts)

    def _summary(self) -> str:
        batteries = self._batteries()
        if self.measurement is None or not batteries:
            return self.strings["battery.no_data"]
        parts = [self._battery_summary(*battery) for battery in batteries]
        draw = self._draw(batteries)
        if draw is not None:
            parts.append(f"{draw:.1f} W")
        time_left = self._time_left(batteries)
        if time_left:
            parts.append(time_left)
        profile = self._profile(short=False)
        if profile:
            parts.append(f"TLP {profile}")
        return "   ".join(parts)

    def notify(self) -> None:
        # dunstrc sets ignore_newline and leaves markup at its "no" default, so the body is
        # a single line of plain text.
        with contextlib.suppress(OSError):
            subprocess.Popen(
                args=["notify-send", "-u", "low", self.strings["battery.notification_title"],
                      self._summary()]
            )

    def poll(self) -> str:
        # Assigned unconditionally: a failed read clears the cache so the cell blanks, which
        # is what every sibling widget does when Redis is unreachable.
        self.measurement = shared.stream.read_measurement(self.r, "power_supply")
        return self._render()
