# Shared Qtile Modules

Code the qtile configuration needs that is not a bar cell. Nothing here appears in the
bar; these modules sit beside [`widgets/`](../widgets/README.md) rather than inside it, so
that directory can hold widgets and nothing else.

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
- **`hover_bar.py`** — `HoverBar`, the bar the screens are built with. `libqtile.bar.Bar`
  loses hover events: its hit test leaves a strip along the bottom edge of the bar that
  belongs to a widget visually but answers "no widget", and its dispatch stays silent unless
  a widget is on *both* sides of the move. One crossing of that strip left a cell expanded
  with the pointer elsewhere. `HoverBar` bounds the hit test to where widgets are actually
  drawn and dispatches on every change, including to and from nothing.
- **`idle_guard.py`** — `guard()` resets X's idle counter while anything holds a logind idle
  inhibitor, so a playing film does not get locked over. `xss-lock` locks from the X screen
  saver, which counts input; logind's idle clock is a separate one, and nothing joined the
  two. It also re-arms the screen saver timeout when it finds it at zero, which is how other
  software silently disables this session's automatic lock.
- **`session.py`** — `start_programs()` starts what cannot start before qtile does, skipping
  anything already running. `~/.xinitrc` starts everything else and starts it earlier; what
  lands here needs something qtile provides. Guarded rather than unconditional because the
  hook fires on every start, and qtile restarts twice a day on the theme switch — so an
  unguarded start would leave a copy behind each time.
- **`spectrum.py`** — the FFT-to-block-glyph maths behind the audio level meter. Pure: it
  takes samples and returns numbers or a string, with no reference to PortAudio, qtile or
  the bar. `widgets/audio.py` renders through it, and so does
  [`helper/preview_audio.py`](../../../helper/README.md), which is what makes that tool a
  preview of the real meter rather than a copy that drifts.

## What Belongs Here

Code that two or more widgets need, that a widget shares with a tool outside the bar, or
that the configuration itself needs and no single widget owns. A module used by exactly one
widget belongs in that widget.

The line between this directory and `widgets/` is whether the module *is* a bar cell — a
`libqtile.widget.base` subclass. `helper/gendocs.py` reads that literally, and the commit
gate refuses a module in `widgets/` that is not one.

Prefer not importing `libqtile` here: `stream`, `state`, `monitors` and `spectrum` are all
pure, which is why they can be tested, and reused by `helper/`, without a running window
manager. `hover_bar` is the exception and has to be, since it subclasses a qtile class — its
tests build the bar geometry by hand rather than starting qtile.
