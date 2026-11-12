# Qtile Widgets

The custom widgets that live in the qtile bar. Each one subscribes to a Redis stream populated by [yths.backend-service](https://github.com/yths/yths.backend-service) and renders a small status segment. System-wide context is in [../../../docs/architecture.md](../../../docs/architecture.md); this file documents the widget-development pattern.

## Base Classes

Two base classes from `libqtile.widget.base`:

- **`BackgroundPoll`** — polls a function at a fixed cadence on a background thread; suitable for fast checks (`systemctl`, reading a Redis stream). Used by every widget that doesn't have its own event source.
- **`InLoopPollText`** — polls on the qtile event loop; used by `audio.py` because it needs to receive samples from a `sounddevice` callback that runs on its own thread.

Prefer `BackgroundPoll`. Only reach for `InLoopPollText` when the widget needs to coordinate with another thread that pushes into qtile.

## Anatomy of a Widget

`service_state.py` is the canonical minimal example: it inherits from `BackgroundPoll`, implements `poll()`, and returns a string. Use it as the structural template for a new widget. The pattern, abstracted:

```python
"""Qtile widget: <one-line description>."""

from typing import Any

import libqtile.widget.base
import redis

import widgets._stream


class WidgetSomething(libqtile.widget.base.BackgroundPoll):
    def __init__(self, r: redis.Redis | None, **config: Any) -> None:
        libqtile.widget.base.BackgroundPoll.__init__(self, "", **config)
        self.r = r  # Redis client passed in from qtile config.py

    def poll(self) -> str:
        measurement = widgets._stream.read_measurement(self.r, "<stream-name>")
        if measurement is None:
            return ""
        # measurement is the decoded JSON object; render it
        return rendered_text
```

## Shared Helpers

Two private modules sit alongside the widgets. They are not widgets — `helper/gendocs.py`
only counts a file as one if it contains `libqtile.widget.base` — and the `_` prefix marks
them as internal:

- **`_stream.py`** — `read_measurement(r, stream)` returns the newest decoded `measurement`
  object from a Redis stream, or `None` for every failure a cell should survive (no client,
  unreachable server, empty stream, missing field, non-object payload). **Use this rather
  than writing another `xrevrange` block.**
- **`_state.py`** — `read_state()` / `update_state(**changes)` for `~/.config/config.json`.
  Writes go to a sibling temporary file and land via `os.replace()`, so the patchers and
  `install.py` — separate processes that read the same file — can never observe a
  half-written one.

These are the exception to the rule below about non-widget files: a shared `_`-prefixed
helper belongs here, next to its callers.

Conventions:

- The Redis client is passed in from `configuration/qtile/config.py` (one shared connection pool). Widgets must not create their own pool.
- `poll()` must never raise. An exception escaping it stops qtile rescheduling the cell for the rest of the session — permanently, and with only a single log line. `BackgroundPoll` drops the reschedule; `InLoopPollText` is worse still, because `timer_setup` only re-arms the timer *after* `tick()` returns. Return `""` instead.
- Type-annotate new code; `ruff check .` enforces it via the `ANN` rules.
- Use `pangocstr` markup (`<span color="#hex">...</span>`) to colour the rendered glyph; pull colours from the active palette in `~/.config/config.json` rather than hardcoding hex.
- Glyphs come from Iosevka Nerd Font; pick semantically meaningful icons (`` for power, `` for bluetooth, etc.).

## Available Widgets

Enumerated, with each widget's one-line description, in
[../../../docs/notes.md](../../../docs/notes.md#available-widgets). That block is generated
by `helper/gendocs.py`; this file does not repeat it.

## Adding a New Widget

1. Pick the Redis stream the widget will read; add it to the backend service if it doesn't exist yet.
2. Create `<name>.py` in this directory. Inherit from `BackgroundPoll`. Add a module docstring (one line, for `gendocs.py`).
3. Wire it into `configuration/qtile/config.py`: import it next to the existing widget imports, and add a `widgets.<name>.WidgetX(...)` entry in the bar's widget list. Pass the shared Redis client `r` in.
4. If the widget needs a palette colour, pull it from `configuration["palette"][theme][<token>]` — do not hardcode.
5. Run `python helper/gendocs.py`; commit the regenerated WIDGETS block in `docs/notes.md` along with the new widget.

## Non-Widget Files in This Directory

If `helper/gendocs.py` skips a `.py` file here, it's because the file does not import `libqtile.widget.base` and therefore does not count as a widget.

Two kinds of non-widget file are skipped, and only one of them belongs here:

- **Shared `_`-prefixed helpers** (`_stream.py`, `_state.py`) — these belong here, next to the widgets that import them. See [Shared Helpers](#shared-helpers) above.
- **Everything else** — currently just the standalone `test_audio.py` harness — should not live in this directory. See `docs/issues.md`. The symlinks that used to sit here are gone: `location.py` and `patch_configurations.py` now resolve the repository root from their own path and call `helper/` directly.
