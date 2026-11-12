# Palette Semantics

A reference for theme authors: what the palette is, which tokens consumers in this repo expect, and how to add to it. Concrete colour values live in each preset's `palette.pkl`; this document is about contract, not hex codes.

> Three documents cover the palette, and they answer different questions. **What a token means** is this file. **What it looks like** in each preset is [palettes/](palettes/). **Where it is used** is [palette-reference.md](palette-reference.md).

## The Palette

The palette is a dict of two keys, `light` and `dark`. Each key maps to another dict whose keys are *token names* (free-form strings) and whose values are hex colour strings:

```python
{
  "light": {
    "background":   "#ebebeb",
    "foreground":   "#787878",
    "neutral":      "#a5aa49",
    "highlight":    "#4bb4b7",
    "notification": "#fb8087",
    "warning":      "#bfa06e",
    ...
  },
  "dark":  { ...same keys, different hexes... },
}
```

`install.py` writes the active bundle's palette into `~/.config/config.json` under `"palette"`; qtile and the patchers read it via `configuration["palette"][theme][<token>]` where `theme` is `"light"` or `"dark"`. See [config-schema.md](config-schema.md) for the surrounding schema.

## Minimum Required Tokens

The qtile config and widgets in this repo currently read these six tokens. A bundle whose palette omits any of them will raise `KeyError` at qtile startup.

| Token | Used for |
|---|---|
| `background` | bar background, surfaces |
| `foreground` | primary text and glyphs |
| `neutral` | borders, dividers, de-emphasised state |
| `highlight` | focal accent (current group, active selection) |
| `notification` | attention cue (urgent windows, notifications) |
| `warning` | non-critical attention cue (e.g. a failing service in the bar) |

Adding new consumers (a new widget, a new patcher) widens this set; track changes here so theme authors know what to ship.

## The Rest of the Vocabulary

The six above are what qtile needs before it draws. The patchers need more, and they are not optional in practice — a bundle without them installs and then fails at the first theme switch:

| Token | Read by |
|---|---|
| `foreground_variant` | `patch_kitty` (the "black" ANSI slot, so black text stays legible, and the cursor) |
| `success`, `failure` | `patch_starship` (the prompt's two outcome colours) |
| `red`, `green`, `yellow`, `blue`, `magenta`, `cyan` | `patch_kitty`, ANSI slots 1–6 |
| `red_variant`, `green_variant`, `yellow_variant`, `blue_variant`, `magenta_variant`, `cyan_variant` | `patch_kitty`, ANSI slots 9–14 |

Twenty-one tokens in total, and the set is closed rather than a floor: [yths.themes](https://github.com/yths/yths.themes) holds the same list as an enum and has a contract test that reads this repository's tracked `assets/default/palette.pkl` and fails if the two ever disagree. That test exists because they did — the generator emitted a thirty-token vocabulary from a preset that no longer ships, and every bundle it produced would have raised `KeyError` in `patch_kitty`.

A hue and its `_variant` are a pair: `patch_kitty` builds ANSI slot *i* from the base and slot *i + 8* from the variant, so a hue shipped without its partner is half a terminal palette.

## Light vs Dark Variants

Both `light` and `dark` keys must be present with the same token set. The active variant is selected by `state.theme` in `~/.config/config.json`. How the two relate is a per-preset design decision; the shipped preset maps them photonegatively, so a token keeps its hue and swaps its lightness.

## Where Tokens Are Consumed

- **qtile widgets** — `configuration["palette"][theme][<token>]`. The six minimum-required tokens above.
- **`helper/patch_web_greeter.py`** — each web-greeter theme's `theme.json#role_map` maps web-greeter role names to palette tokens; the patcher writes CSS variables (`--<role>: <hex>`).
- **`helper/patch_vsc.py`** — perceptual nearest-colour matching from VSCode's editor/token vocabulary into the palette.
- **`helper/patch_plymouth.py`** — renders the boot background using selected palette tokens.

For an authoritative usage map, grep:

```bash
git grep -nE 'palette\[[^]]+\]\[[^]]+\]' configuration/ helper/
```

## Adding a New Required Token

When a new consumer (widget, patcher) reads a palette token the minimum set doesn't yet contain:

1. Add the token to the table above, with a one-line description of what the consumer uses it for.
2. Add it to `ColorToken` in `yths.themes`, and give the seeding there a rule for choosing its colour. Its contract test fails until this repository's tracked bundle carries it too, which is the point: the two halves land together or not at all.
3. Regenerate `assets/default/palette.pkl` by exporting in `default` mode, and commit it.

Avoid adding required tokens lightly — each one is a constraint every preset must honour.
