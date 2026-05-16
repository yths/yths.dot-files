# `~/.config/config.json` Schema

The single configuration file that every downstream consumer (qtile, the patchers, manual tools) reads. Written by `install.py` from a theme bundle merged with runtime state, and rewritten by the patchers when palette or state changes.

## Sample (abridged)

```json
{
  "name": "nuunamnir",
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
  "colors": {
    "light": { "background": "#ebebeb", "foreground": "#787878", "positive": "#6ab669", "...": "..." },
    "dark":  { "background": "#636363", "foreground": "#d3d3d3", "positive": "#6ab669", "...": "..." }
  },
  "palette": {
    "light": { "background": "#ebebeb", "foreground": "#787878", "highlight": "...", "success": "...", "failure": "..." },
    "dark":  { "background": "#636363", "foreground": "#d3d3d3", "highlight": "...", "success": "...", "failure": "..." }
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
    "mode": "automatic"
  }
}
```

## Top-Level Fields

| Field | Type | Source | Read by |
|---|---|---|---|
| `name` | string | bundle `config.json#name` | nothing functional; informational |
| `monitors` | object | `helper/screen_configuration.py` | qtile (bar geometry, per-monitor scaling) |
| `font` | object | hardcoded by `install.py` (currently `Iosevka NF`, size 14) | qtile, web-greeter (via `font_overrides`) |
| `colors` | object | bundle `config.json#colors` | patchers reading by colour name (e.g. `red`, `pastel_blue`) |
| `palette` | object | bundle `palette.pkl` | qtile widgets, patchers reading by semantic role (e.g. `success`, `failure`) |
| `wallpapers` | object | rewritten by `install.py` to installed paths | qtile, web-greeter (via `wallpaper_key`) |
| `state` | object | initialised by `install.py`; mutated at runtime | qtile, patchers — drives the active light/dark variant |

## Two Color Models

Two separate vocabularies coexist; they describe the same colors at different abstraction levels:

- **`colors`** — the *named palette* (27 tokens: `background`, `foreground`, `red`, `pastel_blue`, `effect_bright`, etc.). Lower-level, hue-named. Consumed by tools that want a specific colour by name.
- **`palette`** — the *semantic palette* (21 tokens: `background`, `foreground`, `highlight`, `success`, `failure`, `notification`, `warning`, etc.). Higher-level, role-named. Consumed by tools that want a colour by what it *means*.

When patching a new app, prefer `palette` (semantic, portable across themes). Use `colors` only when the target app's vocabulary maps one-to-one to a hue name.

See [color-semantics.md](color-semantics.md) for what each semantic token is *for*.

## `state` Subfields

| Subfield | Values | Meaning |
|---|---|---|
| `theme` | `"light"` \| `"dark"` | which palette/colors variant is currently active |
| `condition` | `"normal"` \| `"urgent"` | secondary state used to pick highlight wallpapers and emphasis colours |
| `mode` | `"automatic"` \| `"manual"` | whether `theme` is allowed to flip on its own (driven by the `location` stream's sunrise/sunset) |

When `mode` is `"automatic"`, qtile flips `theme` between `"light"` and `"dark"` on sunrise/sunset transitions. When `"manual"`, the user owns `theme` directly.

## `monitors` Subfields

One key per output (e.g. `HDMI-0`, `eDP-1`). Values mirror what `screeninfo` exposes plus a derived `scaling_factor` (`diagonal_dpi / 100`, capped to two decimals). Used by qtile to size bar fonts per monitor.

## Backup Behaviour

`install.py` backs up the existing `~/.config/config.json` to `~/.config/config.json.<unix-timestamp>.bak` before overwriting. The patchers do not back up — they assume the file is freshly written by the installer or a previous patcher run, and overwrite in place.

## Adding a New Field

A new field should:

1. Be added to the bundle's `config.json` (so `yths.themes` produces it).
2. Be passed through `install.py` (which loads the bundle's config and writes it to `~/.config/config.json`). For runtime-detected values, add a step in `install.py` that fills the field after loading the bundle.
3. Be documented here, with a `Read by` row in the top-level table.

Do not introduce duplicate fields between `colors` and `palette` — pick the abstraction level that matches the consumer.
