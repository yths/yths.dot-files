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
- **`stream.py`**'s `read_latest(r, stream, accept)` is for the one stream whose newest
  entry may be one to skip: it returns the newest of the last few that `accept` takes. The
  location cell uses it to pass over positions looked up through the VPN.
- **`timezone.py`** — `TimezoneFollower` moves the system timezone to the geolocated one with
  `timedatectl --no-ask-password`, never waiting on the event loop and never retrying a
  refusal, and calls `time.tzset()` once `/etc/localtime` changes so qtile's own clock follows.
  The permission comes from [configuration/timezone/](../../timezone/README.md).
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
- **`glyph_gap.py`** — the space after an icon, sized per icon. Nerd Font icons overhang
  their cell by different amounts, so one space character left whatever followed a
  different distance from each. This lays the icon out off screen with the bar's own Pango,
  reads where its ink ends, and scales the space so the clear distance is half a cell for
  every icon. The bluetooth widget uses it between a device's icon and its battery meter.
- **`glyph_centre.py`** — the top of a line, placed so its ink is centred in the bar. qtile
  centres the font's line box, and where a glyph sits inside that box differs per face: the
  backend indicator's dot was 0.7px low in one font and 1.8px low in another. This lays the
  text out off screen with the bar's own Pango, reads which rows its ink covers, and returns
  the whole-pixel position that puts their middle on the bar's. The service-state widget
  uses it, so its dot is centred for any font, size or symbol a theme picks.
- **`task_list.py`** — `CentredTaskList`, the window-title cell. qtile's `TaskList` draws
  its text at a fixed padding from the top of the bar instead of centring it like every
  other cell, which left the titles seven pixels above the icons beside them. This derives
  the padding from the font's line height, so the titles share the bar's centre line at any
  size. Its `markup_urgent` wraps the title of a window asking for attention, which `TaskList`
  can only mark by filling the cell — the way it marks the focused one. `AdaptiveTaskBar` moves the list to a bottom `SecondaryTaskBar` when its available
  width falls below 18 scaled font sizes; it returns to the top at 27. The bottom bar reserves
  space only while needed and retains the focused-screen outline when collapsed.
- **`launcher.py`** — `rofi_command(mode, output, clearance, script)`, the argv the rofi key
  bindings spawn, the power menu's script mode included. It names the focused screen's output, because rofi's own default is the monitor
  under the pointer, and passes that screen's geometry inside the focus outline as a
  `-theme-str`, because the theme's averaged width and offset covered the outline's edges
  and the bottom of the bar.
- **`screenshot.py`** — `capture_command(kind, path, screen, window)`, the argv behind the
  three Print keys: a dragged region, the focused screen or the focused window, saved under
  the XDG pictures directory, copied to the clipboard and announced. qtile passes the screen
  geometry and window id, because `maim` alone captures every monitor at once.
- **`idle_guard.py`** — `guard()` resets X's idle counter while anything holds a logind idle
  inhibitor, so a playing film does not get locked over. `xss-lock` locks from the X screen
  saver, which counts input; logind's idle clock is a separate one, and nothing joined the
  two. It also re-arms the screen saver timeout when it finds it at zero, which is how other
  software silently disables this session's automatic lock.
- **`session.py`** — `start_programs()` sets the X idle and DPMS timers and starts `xss-lock`
  and `inhibit-bridge`, skipping anything already running. It works for LightDM's direct Qtile
  session as well as `startx`, without relying on `~/.xinitrc`. Guarded because the
  hook fires on every start, and qtile restarts twice a day on the theme switch — so an
  unguarded start would leave a copy behind each time.
- **`spectrum.py`** — the FFT-to-block-glyph maths behind the audio level meter. Pure: it
  takes samples and returns numbers or a string, with no reference to PortAudio, qtile or
  the bar. `widgets/audio.py` renders through it, and so does
  [`helper/preview_audio.py`](../../../helper/README.md), which is what makes that tool a
  preview of the real meter rather than a copy that drifts.
- **`audio_capture.py`** — captures PipeWire/Pulse output monitors in a spawned child process.
  The widget reads ready spectrum frames without waiting and restarts a failed worker after
  a backoff. Automatic mode follows the default output; manual mode selects an output monitor.
  Native audio failures during dock removal cannot abort the window manager.

## What Belongs Here

Code that two or more widgets need, that a widget shares with a tool outside the bar, or
that the configuration itself needs and no single widget owns. A module used by exactly one
widget belongs in that widget.

The line between this directory and `widgets/` is whether the module *is* a bar cell — a
`libqtile.widget.base` subclass. `helper/gendocs.py` reads that literally, and the commit
gate refuses a module in `widgets/` that is not one.

Prefer not importing `libqtile` here: `stream`, `state`, `monitors` and `spectrum` are all
pure, which is why they can be tested, and reused by `helper/`, without a running window
manager. `hover_bar` and `task_list` are the exceptions and have to be, since each
subclasses a qtile class — their tests build the bar geometry by hand rather than starting
qtile.
