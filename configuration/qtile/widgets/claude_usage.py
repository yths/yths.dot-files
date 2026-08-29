"""Qtile widget: Claude session and weekly usage limits.

Reads the latest entry from the ``claude_usage`` Redis stream and renders a robot glyph
followed by two block bars — the five-hour session window and the overall weekly window —
each coloured by the severity the backend service already computed. Hovering expands the
cell to percentages and reset countdowns; right-click sends the full breakdown to dunst.
Polls every few seconds rather than every second like its siblings, because the producer
only publishes every 30 seconds. ``BackgroundPoll`` based.
"""

import contextlib
import datetime
import subprocess
from typing import Any

import libqtile.widget.base
import redis
import widgets._stream


class WidgetClaudeUsage(libqtile.widget.base.BackgroundPoll):
    ICON = "󰚩"
    # The robot glyph's ink overruns its cell by 0.418em where the bluetooth headset only
    # overruns by 0.250em, so a single space leaves it visually glued to the bars. Iosevka
    # forces every space character to a full cell, so the shortfall is made up with a
    # fractionally sized second space — a percentage, so it tracks fontsize per monitor.
    ICON_GAP = ' <span size="34%"> </span>'
    #: Shown instead of ICON when the backend cannot authenticate at all. The producer
    #: reads ~/.claude/.credentials.json and deliberately never refreshes it, so an
    #: expired token is a normal steady state, not a blip -- worth its own glyph.
    ICON_DEAD = "󱚡"  # U+F16A1 md-robot_dead
    #: ``reason`` values that mean "re-authenticate". Everything else (network_error,
    #: bad_response, a non-auth http_*) is transient and keeps the live glyph, dimmed.
    AUTH_FAILURES = frozenset({"no_credentials", "token_expired", "http_401", "http_403"})
    LEVELS = ("▁", "▂", "▃", "▄", "▅", "▆", "▇", "█")
    DIM_ALPHA = 24576

    def __init__(
        self,
        r: redis.Redis | None,
        warning_color: str = "#ff0000",
        notification_color: str = "#ff0000",
        warning_threshold: float = 75,
        critical_threshold: float = 90,
        **config: Any,
    ) -> None:
        libqtile.widget.base.BackgroundPoll.__init__(self, "", **config)
        self.r = r

        self.warning_color = warning_color
        self.notification_color = notification_color
        # Consulted only when a payload arrives without its own precomputed severity.
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

        self.measurement = None
        self.expanded = False

        self.add_callbacks({"Button3": self.notify})

    def _icon_only(self, icon: str) -> str:
        """An icon with nothing after it.

        qtile sizes each cell from the text's *advance* width and clips the blit to it
        (``drawer.draw(width=self.width)``). Both robot glyphs paint 0.418em past their
        advance, so without the trailing space the right edge is cut off.
        """
        return icon + " "

    def _dict(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _number(self, value: Any) -> float | None:
        if isinstance(value, bool) or value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _scale(
        self, value: float, in_min: float, in_max: float, out_min: float, out_max: float
    ) -> float:
        return (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

    def _level(self, percent: float) -> str:
        percent = min(max(percent, 0), 100)
        return self.LEVELS[round(self._scale(percent, 0, 100, 0, len(self.LEVELS) - 1))]

    def _duration(self, seconds: Any) -> str:
        seconds = self._number(seconds)
        if seconds is None:
            return ""
        seconds = max(int(seconds), 0)
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes = remainder // 60
        if days:
            return f"{days}d{hours:02d}"
        if hours:
            return f"{hours}h{minutes:02d}"
        return f"{minutes}m"

    def _limit(self, measurement: dict[str, Any], kind: str) -> dict[str, Any] | None:
        for limit in measurement.get("limits") or []:
            if isinstance(limit, dict) and limit.get("kind") == kind:
                return limit
        return None

    def _severity(self, limit: Any, percent: float) -> str:
        severity = self._dict(limit).get("severity")
        if severity in ("normal", "warning", "critical"):
            return severity
        if percent >= self.critical_threshold:
            return "critical"
        if percent >= self.warning_threshold:
            return "warning"
        return "normal"

    def _reading(
        self, measurement: dict[str, Any], kind: str, window_key: str
    ) -> dict[str, Any] | None:
        limit = self._dict(self._limit(measurement, kind))
        window = self._dict(measurement.get(window_key))

        percent = self._number(limit.get("percent"))
        if percent is None:
            percent = self._number(window.get("utilization"))
        if percent is None:
            return None

        resets_in = limit.get("resets_in")
        if resets_in is None:
            resets_in = window.get("resets_in")
        resets_at = limit.get("resets_at")
        if resets_at is None:
            resets_at = window.get("resets_at")

        return {
            "percent": percent,
            "severity": self._severity(limit, percent),
            "resets_in": resets_in,
            "resets_at": resets_at,
        }

    def _colorize(self, text: str, severity: str) -> str:
        if severity == "critical":
            return f"<span color='{self.notification_color}'>{text}</span>"
        if severity == "warning":
            return f"<span color='{self.warning_color}'>{text}</span>"
        return text

    def _scoped(self, measurement: dict[str, Any]) -> dict[str, Any] | None:
        scoped = self._dict(self._limit(measurement, "weekly_scoped"))
        percent = self._number(scoped.get("percent"))
        model = self._dict(self._dict(scoped.get("scope")).get("model")).get("display_name")
        if percent is None or not model:
            return None
        return {"model": model, "percent": percent, "severity": self._severity(scoped, percent)}

    def _detail(self, reading: dict[str, Any]) -> str:
        block = self._colorize(self._level(reading["percent"]), reading["severity"])
        countdown = self._duration(reading["resets_in"])
        text = f"{block} {reading['percent']:.0f}%"
        if countdown:
            text = f"{text} {countdown}"
        return text

    def _render(self) -> str:
        measurement = self.measurement
        if not measurement:
            return ""

        if not measurement.get("available"):
            reason = measurement.get("reason") or "unavailable"
            if reason in self.AUTH_FAILURES:
                # Full opacity, unlike the transient states below: this one needs acting
                # on, and the dim "no data right now" treatment would bury it.
                if self.expanded:
                    return f"{self.ICON_DEAD}{self.ICON_GAP}{reason}"
                return self._icon_only(self.ICON_DEAD)
            body = self._icon_only(self.ICON)
            if self.expanded:
                body = f"{self.ICON}{self.ICON_GAP}{reason}"
            return f"<span alpha='{self.DIM_ALPHA}'>{body}</span>"

        readings = [
            self._reading(measurement, "session", "five_hour"),
            self._reading(measurement, "weekly_all", "seven_day"),
        ]
        readings = [reading for reading in readings if reading is not None]
        if not readings:
            return f"<span alpha='{self.DIM_ALPHA}'>{self._icon_only(self.ICON)}</span>"

        if self.expanded:
            parts = [self._detail(reading) for reading in readings]
            scoped = self._scoped(measurement)
            if scoped is not None:
                parts.append(
                    self._colorize(
                        f"{scoped['model']} {scoped['percent']:.0f}%", scoped["severity"]
                    )
                )
            output = f"{self.ICON}{self.ICON_GAP}" + "  ".join(parts)
        else:
            blocks = "".join(
                self._colorize(self._level(reading["percent"]), reading["severity"])
                for reading in readings
            )
            output = f"{self.ICON}{self.ICON_GAP}{blocks}"

        if measurement.get("stale"):
            output = f"<span alpha='{self.DIM_ALPHA}'>{output}</span>"
        return output

    def _reset_clock(self, reading: dict[str, Any]) -> str:
        resets_at = reading.get("resets_at")
        if isinstance(resets_at, str):
            try:
                moment = datetime.datetime.fromisoformat(resets_at).astimezone()
            except ValueError:
                moment = None
            if moment is not None:
                if moment.date() == datetime.datetime.now().astimezone().date():
                    return moment.strftime("%H:%M")
                return moment.strftime("%a %H:%M")
        countdown = self._duration(reading["resets_in"])
        return f"in {countdown}" if countdown else "unknown"

    def _summary(self) -> str:
        measurement = self.measurement
        if not measurement:
            return "no data"
        if not measurement.get("available"):
            return f"unavailable ({measurement.get('reason') or 'unknown'})"

        parts = []
        for label, kind, window_key in (
            ("session", "session", "five_hour"),
            ("weekly", "weekly_all", "seven_day"),
        ):
            reading = self._reading(measurement, kind, window_key)
            if reading is not None:
                parts.append(
                    f"{label} {reading['percent']:.0f}% · resets {self._reset_clock(reading)}"
                )

        if not parts:
            return "no data"

        scoped = self._scoped(measurement)
        if scoped is not None:
            parts.append(f"{scoped['model']} {scoped['percent']:.0f}%")

        extra_usage = self._dict(measurement.get("extra_usage"))
        parts.append("credits " + ("enabled" if extra_usage.get("is_enabled") else "disabled"))
        if measurement.get("stale"):
            parts.append("stale")

        return "   ".join(parts)

    def notify(self) -> None:
        # dunstrc sets ignore_newline and leaves markup at its "no" default, so the body is
        # a single line of plain text.
        with contextlib.suppress(OSError):
            subprocess.Popen(
                args=["notify-send", "-u", "low", "Claude usage", self._summary()]
            )

    def mouse_enter(self, x: int, y: int) -> None:
        self.expanded = True
        self._refresh()

    def mouse_leave(self, x: int, y: int) -> None:
        self.expanded = False
        self._refresh()

    def _refresh(self) -> None:
        """Re-render from the current state. Always called on the event loop."""
        libqtile.widget.base.BackgroundPoll.update(self, self._render())

    def update(self, text: str) -> None:
        """Apply the *current* state, not the text handed in.

        Two separate problems make the argument untrustworthy, and both showed up as
        hover misbehaving:

        ``poll()`` runs on a worker thread, so the string it produced can predate a
        pointer that entered or left while the Redis read was still in flight. Applying
        that stale snapshot made hover sometimes fail to expand, and sometimes fail to
        contract on leave.

        Separately, ``Bar.process_pointer_motion`` clears its ``_has_cursor`` *without*
        calling ``mouse_leave`` when the pointer lands somewhere no widget occupies -- a
        gap between cells, or the bar's own border. The cell is then never told it lost
        the pointer and stays expanded indefinitely. Reconciling against what the bar
        believes heals that within one poll.

        Only the poll path may reconcile: ``process_pointer_enter`` calls
        ``mouse_enter`` *before* it assigns ``_has_cursor``, so doing this on the hover
        path would cancel every expansion the moment it started. The hover handlers call
        ``_refresh`` directly for that reason.
        """
        bar = getattr(self, "bar", None)
        if self.expanded and bar is not None and getattr(bar, "_has_cursor", self) is not self:
            self.expanded = False
        self._refresh()

    def poll(self) -> str:
        # Assigned unconditionally: a failed read clears the cache so the cell blanks,
        # which is what every sibling widget does when Redis is unreachable.
        self.measurement = widgets._stream.read_measurement(self.r, "claude_usage")
        return self._render()
