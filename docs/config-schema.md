# `~/.config/config.json` Schema

The single configuration file that every downstream consumer (qtile, the patchers, manual tools) reads. Written by `install.py` from a theme bundle merged with runtime state, and rewritten by the patchers when palette or state changes.

## Sample (abridged)

```json
{
  "name": "default",
  "monitors": {
    "HDMI-1": {
      "width": 3840, "width_mm": 620, "width_dpi": 157,
      "height": 2160, "height_mm": 345, "height_dpi": 159,
      "diagonal": 4405.81, "diagonal_mm": 709.52, "diagonal_dpi": 158,
      "scaling_factor": 1.58,
      "is_primary": true
    }
  },
  "font": {
    "size": 14,
    "family": "Iosevka NF"
  },
  "palette": {
    "light": { "background": "#ebebeb", "foreground": "#787878", "neutral": "...", "highlight": "...", "notification": "...", "warning": "..." },
    "dark":  { "background": "#636363", "foreground": "#d3d3d3", "neutral": "...", "highlight": "...", "notification": "...", "warning": "..." }
  },
  "wallpapers": {
    "light":           "~/.config/qtile/wallpaper-light.png",
    "light-highlight": "~/.config/qtile/wallpaper-light-highlight.png",
    "dark":            "~/.config/qtile/wallpaper-dark.png",
    "dark-highlight":  "~/.config/qtile/wallpaper-dark-highlight.png"
  },
  "state": {
    "theme": "light",
    "condition": "normal",
    "theme_mode": "automatic",
    "audio_mode": "automatic"
  }
}
```

## Top-Level Fields

| Field | Type | Source | Read by |
|---|---|---|---|
| `name` | string | bundle `config.json#name` | nothing functional; informational |
| `monitors` | object | `helper/screen_configuration.py` | qtile (bar geometry, per-monitor scaling) |
| `font` | object | hardcoded by `install.py` (currently `Iosevka NF`, size 14) | qtile, web-greeter (via `font_overrides`) |
| `palette` | object | bundle `palette.pkl` | qtile widgets, patchers reading by semantic role (e.g. `success`, `failure`) |
| `wallpapers` | object | rewritten by `install.py` to installed paths | qtile, web-greeter (via `wallpaper_key`) |
| `state` | object | initialised by `install.py`; mutated at runtime | qtile, patchers — drives the active light/dark variant |
| `symbols` | object | `helper/symbols.py` ASCII defaults, with the bundle's `config.json#symbols` merged over them | qtile widgets, plymouth, dunst, rofi, starship, web-greeter — see [symbols.md](symbols.md) |
| `strings` | object | `helper/symbols.py` ASCII defaults, with the bundle's `config.json#strings` merged over them | plymouth's boot messages, tmux, the bar's one widget with words |
| `bluetooth_devices` | object | bundle `config.json#bluetooth_devices`, copied as-is | the qtile bluetooth widget |

## Symbols and Strings

The two non-colour things a theme sets. Every default is ASCII so the desktop renders without
a Nerd Font; a bundle overrides what it cares about, and an override is partial — naming one
key keeps the rest. A value is either a string (one icon, one message) or a list (a ramp
indexed by a level, such as the battery's eleven rungs). See [symbols.md](symbols.md) for the
full vocabulary, what each key falls back to, and which file reads it.

`bluetooth_devices` maps a device's MAC address to the icon the bar draws for it, in either
case. A value naming a symbol key (`"bluetooth.headphones"`) resolves through the vocabulary,
so it keeps its ASCII fallback; any other value is drawn as written. A connected device the
block does not name is drawn as `bluetooth.device`.

```json
"bluetooth_devices": {
    "CC:98:8B:99:F4:E5": "bluetooth.headphones",
    "AC:80:0A:A4:66:EB": "\udb80\udf7d"
}
```

## Palette

`palette` is the only colour vocabulary downstream consumers read. Both `light` and `dark` keys are required; each maps to a dict of token name → hex string. The token set is bundle-defined, but a minimum subset is required by the qtile widgets — see [palette-semantics.md](palette-semantics.md) for the contract.

## `state` Subfields

| Subfield | Values | Meaning |
|---|---|---|
| `theme` | `"light"` \| `"dark"` | which palette variant is currently active |
| `condition` | `"normal"` \| `"urgent"` | secondary state used to pick highlight wallpapers and emphasis colours |
| `theme_mode` | `"automatic"` \| `"manual"` | whether `theme` is allowed to flip on its own (driven by the `location` stream's sunrise/sunset) |
| `audio_mode` | `"automatic"` \| `"manual"` | whether the audio widget tracks the system's active capture device or stays on the device the user picked; defaults to `"automatic"` if absent |

The two `*_mode` keys answer the same question for different things — does this follow the system, or did the user pin it — so they share one name shape and one pair of values.

When `theme_mode` is `"automatic"`, qtile flips `theme` between `"light"` and `"dark"` on sunrise/sunset transitions. When `"manual"`, the user owns `theme` directly.

When `audio_mode` is `"automatic"`, the audio widget snaps to the ALSA `default` capture device (the alsa-pulse bridge that follows whichever sink PipeWire/Pulse currently routes) — flipped on by middle-click. Scrolling the widget cycles devices manually and persists the choice as `"manual"`.

> A configuration written before this rename used `mode` for `theme_mode`, and spelled `audio_mode`'s automatic value `"auto"`. `configuration/qtile/shared/state.py` translates both on read and persists the current form on the next write, so an existing file keeps working and migrates itself. Delete that translation once no machine is running an older file — it is tracked in [issues.md](issues.md).

## `monitors` Subfields

One key per output (e.g. `HDMI-0`, `eDP-1`). Values mirror what `screeninfo` exposes plus a derived `scaling_factor` (`diagonal_dpi / 100`, capped to two decimals). Used by qtile to size bar fonts per monitor.

## Backup Behaviour

`install.py` backs up the existing `~/.config/config.json` to `~/.config/config.json.<unix-timestamp>.bak` before overwriting. The patchers do not back up — they assume the file is freshly written by the installer or a previous patcher run, and overwrite in place.

## Adding a New Field

A new field should:

1. Be added to the bundle's `config.json` (so `yths.themes` produces it).
2. Be passed through `install.py` (which loads the bundle's config and writes it to `~/.config/config.json`). For runtime-detected values, add a step in `install.py` that fills the field after loading the bundle.
3. Be documented here, with a `Read by` row in the top-level table.

