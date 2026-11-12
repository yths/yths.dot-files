# Qtile Widgets

One module per cell in the qtile bar. Each renders a short status segment — an icon, a level meter, a countdown — and eight of the nine get their data by reading the newest entry of one Redis stream. The ninth is the exception described below.

A widget never collects system state itself. A separate service does that and publishes to Redis; a widget reads and renders. That is what keeps a slow or failing probe out of the bar's event loop.

Every `.py` file in this directory is a widget. Code shared between widgets lives one level up in [../shared/](../shared/README.md); standalone tools live in [../../../helper/](../../../helper/README.md).

## Base Classes

Two base classes from `libqtile.widget.base`:

- **`BackgroundPoll`** — polls a function at a fixed cadence on a background thread; suitable for fast checks (`systemctl`, reading a Redis stream). Used by every widget that doesn't have its own event source.
- **`InLoopPollText`** — polls on the qtile event loop; used by `audio.py` because it needs to receive samples from a `sounddevice` callback that runs on its own thread.

Prefer `BackgroundPoll`. Only reach for `InLoopPollText` when the widget needs to coordinate with another thread that pushes into qtile.

## Anatomy of a Widget

`vpn.py` is the canonical minimal example: 46 lines that inherit from `BackgroundPoll`, read one stream, and return a string. Every convention below is visible in it. Use it as the structural template for a new widget. The pattern, abstracted:

```python
"""Qtile widget: <one-line description>."""

from typing import Any

import libqtile.widget.base
import redis
import shared.stream


class WidgetSomething(libqtile.widget.base.BackgroundPoll):
    def __init__(self, r: redis.Redis | None, **config: Any) -> None:
        libqtile.widget.base.BackgroundPoll.__init__(self, "", **config)
        self.r = r  # Redis client passed in from qtile config.py

    def poll(self) -> str:
        measurement = shared.stream.read_measurement(self.r, "<stream-name>")
        if measurement is None:
            return ""
        # measurement is the decoded JSON object; render it
        return rendered_text
```

`shared` resolves because qtile puts its configuration directory — the parent of both `widgets/` and `shared/` — on `sys.path`, which is the same mechanism that makes `import widgets.audio` work from `config.py`. Neither directory needs an `__init__.py`.

Conventions:

- The Redis client is passed in from `configuration/qtile/config.py` (one shared connection pool). Widgets must not create their own pool.
- Read the stream through `shared.stream.read_measurement()` rather than writing another `xrevrange` block; persist state through `shared.state.update_state()` rather than rewriting `~/.config/config.json` in place. See [../shared/README.md](../shared/README.md).
- `poll()` must never raise. An exception escaping it stops qtile rescheduling the cell for the rest of the session — permanently, and with only a single log line. `BackgroundPoll` drops the reschedule; `InLoopPollText` is worse still, because `timer_setup` only re-arms the timer *after* `tick()` returns. Return `""` instead.
- Type-annotate new code; `ruff check .` enforces it via the `ANN` rules.
- Use `pangocstr` markup (`<span color="#hex">...</span>`) to colour the rendered glyph; pull colours from the active palette in `~/.config/config.json` rather than hardcoding hex.
- Glyphs come from Iosevka Nerd Font; pick semantically meaningful icons — `power_supply.py` walks the Material battery ramp from `U+F0079`, `claude_usage.py` uses `U+F06A9` (robot) and `U+F16A1` (robot-dead). Name them as class constants with the codepoint in a trailing comment, the way `location.py` does. They are invisible in editors, diffs and terminals without the font, so an inlined glyph is silently dropped by anything that rewrites the line — which is how the two examples that used to sit in this sentence were lost.

## The One That Reads No Stream

`service_state.py` polls `systemctl --user is-active` directly rather than reading a stream.
That is deliberate, not an oversight to correct: its job is to report whether
`backend.service` — the process that publishes every other widget's stream — is running. An
indicator that took its answer from a stream published by the thing it monitors could not
tell *the service is down* from *the stream is stale*, and would go blind at exactly the
moment it matters. It is also why the bar still says something true when Redis itself is
unreachable.

So follow `vpn.py` for anything the backend already collects. Reach for a direct poll only
when the thing being reported is the backend, or Redis.

## Adding a New Widget

1. Pick the Redis stream the widget will read; add it to the backend service if it doesn't exist yet.
2. Create `<name>.py` in this directory. Inherit from `BackgroundPoll`. Add a module docstring (one line, for `gendocs.py`).
3. Wire it into `configuration/qtile/config.py`: import it next to the existing widget imports, and add a `widgets.<name>.WidgetX(...)` entry in the bar's widget list. Pass the shared Redis client `r` in.
4. If the widget needs a palette colour, pull it from `configuration["palette"][theme][<token>]` — do not hardcode.
5. Run `python helper/gendocs.py`; commit the regenerated WIDGETS block in `docs/notes.md` along with the new widget.

## What Belongs Here

Only widgets — modules that build on `libqtile.widget.base`. `helper/gendocs.py` enforces
this: anything else in this directory fails `gendocs.py --check`, which the pre-commit hook
runs, so a stray file cannot be committed.

The rule exists because it was broken. This directory accumulated two shared modules, a
standalone audio harness and four symlinks into `helper/` and `configuration/vscode/`,
because the enumeration in `gendocs.py` skipped whatever it did not recognise instead of
complaining. Where each kind of file goes now:

| Kind | Home |
| --- | --- |
| Bar cell | here |
| Code two or more widgets share | [`../shared/`](../shared/README.md) |
| Script run by hand or by another program | `helper/`, at the repository root |
