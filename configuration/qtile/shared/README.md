# Shared Qtile Modules

Code used by more than one bar cell. These are not widgets and do not appear in the bar;
they sit beside [`widgets/`](../widgets/README.md) rather than inside it, so that directory
can hold widgets and nothing else.

`shared` is importable from a widget as `import shared.stream` because qtile puts its
configuration directory — the parent of both `shared/` and `widgets/` — on `sys.path`.
Neither directory needs an `__init__.py`.

## Modules

- **`stream.py`** — `read_measurement(r, stream)` returns the newest decoded `measurement`
  object from a Redis stream, or `None` for every failure a cell should survive: no client,
  an unreachable server, an empty stream, a missing field, a payload that is not a JSON
  object. Use this rather than writing another `xrevrange` block; eight widgets each carried
  their own transcription of that read, in two different error-handling dialects, before it
  was collected here.
- **`state.py`** — `read_state()` / `update_state(**changes)` for `~/.config/config.json`.
  Writes go to a sibling temporary file and land via `os.replace()`, so the patchers and
  `install.py` — separate processes that read the same file — can never observe a
  half-written one.
- **`monitors.py`** — `detect()` reads the connected displays and their physical size;
  `refresh()` records them in `~/.config/config.json` and says whether anything changed.
  `config.py` calls it when a display is plugged in or unplugged, and
  `helper/screen_configuration.py` calls it at install time, so the geometry every scaled
  size derives from has one definition.
- **`spectrum.py`** — the FFT-to-block-glyph maths behind the audio level meter. Pure: it
  takes samples and returns numbers or a string, with no reference to PortAudio, qtile or
  the bar. `widgets/audio.py` renders through it, and so does
  [`helper/preview_audio.py`](../../../helper/README.md), which is what makes that tool a
  preview of the real meter rather than a copy that drifts.

## What Belongs Here

Code that two or more widgets need, or that a widget shares with a tool outside the bar.
A module used by exactly one widget belongs in that widget.

Nothing here may import `libqtile` — that is the line between this directory and
`widgets/`, and `helper/gendocs.py` reads it literally when it checks that `widgets/`
contains only widgets.
