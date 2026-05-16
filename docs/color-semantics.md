# Color Semantics

A reference for theme authors: what every semantic token *means*, and how to decide which token to reach for. Concrete colour values live in each preset's `config.json`; this document is about intent, not hex codes.

Two vocabularies are in play; see [config-schema.md](config-schema.md#two-color-models) for the distinction. This page covers the **`palette`** (semantic, role-named) vocabulary — the one most patchers and widgets consume.

## Structural Tokens

These describe surfaces and basic chrome. Every theme defines them; they carry no semantic weight beyond "where things sit."

| Token | Role |
|---|---|
| `background` | The primary surface colour. Bar background, terminal background, web-greeter page background. |
| `foreground` | The primary text/glyph colour against `background`. |
| `cursor` | Caret colour in editors and terminals. Usually high-contrast against `background`. |
| `grey` | A neutral mid-tone for borders, dividers, disabled state. |
| `light_grey` | A lighter neutral, used for hover and secondary surfaces. |
| `dark_grey` | A darker neutral, used for emphasised dividers and active state. |
| `light_muted` | A near-`background` tone for tertiary surfaces. |
| `dark_muted` | A near-`foreground` tone for de-emphasised text. |

## Status Tokens

These carry meaning. Use them to communicate state (good/bad/neutral/attention) consistently across every app.

| Token | Role |
|---|---|
| `positive` | Success, OK, healthy state. (Confirm buttons, "succeeded" indicators, healthy widget glyphs.) |
| `negative` | Failure, error, danger. (Failed builds, error toasts, low-battery warnings.) |
| `neutral` | Informational, in-progress, no judgement. (Pending state, neutral notifications.) |

The `nuunamnir` palette deliberately ties hue to perceptual salience: `positive` skews green (recognised at low attention cost), `negative` skews red (recognised even peripherally), `neutral` skews toward blue (low salience).

## Effect Tokens

The accent set — used for highlights, animations, transient emphasis. Reach for these when something needs to *catch* the eye without claiming "success" or "failure."

| Token | Role |
|---|---|
| `effect_bright` | Highest-attention accent. Used sparingly for the focal cue. |
| `effect_dark` | Inverse of `effect_bright` in the opposite mode (light/dark). |
| `effect_muted` | A desaturated accent for less-emphasised highlights. |
| `effect_pastel` | The softest accent variant, for ambient highlights. |

## Pastel Variants

Pastel tokens (`pastel_red`, `pastel_green`, `pastel_blue`, `pastel_yellow`, `pastel_magenta`, `pastel_cyan`) exist as desaturated companions to the named-hue colours. Use them for elements that need a hue identity but should not pull focus from `effect_*` or status tokens.

## Named-Hue Tokens

`red`, `green`, `blue`, `yellow`, `magenta`, `cyan` (and their `pastel_*` variants) are the lowest-level vocabulary. Reach for them only when:

1. The target app's config uses hue names directly (e.g. ANSI 0–15 in a terminal).
2. The semantic intent is genuinely "this thing should be visually identifiable as blue."

For anything else, prefer a semantic token — palettes can be re-themed without breaking semantic usage; named hues lock you to the theme's specific hue choices.

## Light vs Dark Variants

Every palette has a `light` and `dark` block with the same token names but different hex values. The active variant is selected by `state.theme` in `~/.config/config.json`.

In the `nuunamnir` palette, the dark variant is the photonegative of the light variant: corresponding tokens swap lightness while keeping chroma and hue family stable, so muscle-memory transfers between modes. Other presets are free to choose their own light↔dark relationship.

## Where Tokens Are Consumed

Tokens are read by:

- **qtile widgets** — via `configuration["palette"][theme][<token>]` (theme is the current state value). Widgets reach for status tokens (`positive`/`negative`/`neutral`) and `foreground`/`background`.
- **`helper/patch_web_greeter.py`** — each web-greeter theme's `theme.json#role_map` maps web-greeter-internal role names (`highlight`, `failure`, `success`, `notification`) to palette tokens. CSS variables are generated as `--<role>: <hex>`.
- **`helper/patch_vsc.py`** — perceptual mapping from VSCode's editor/token colour vocabulary onto the palette.
- **`helper/patch_plymouth.py`** — renders the boot background using selected palette tokens.

For an authoritative usage map, grep:

```bash
git grep -nE 'palette\[[^]]+\]\[[^]]+\]' configuration/ helper/
```

## Adding a New Token

1. Add the token (with concrete colour values for `light` and `dark`) to every preset's `palette.pkl` (i.e. in the `yths.themes` orchestrator).
2. Document its role in the *Structural*, *Status*, *Effect*, *Pastel*, or *Named-hue* section above — pick whichever family it belongs to.
3. Update the consumers that should reach for it (widget code, patchers, web-greeter `role_map`s).

Do not add tokens whose role overlaps an existing one — pick a different role or refine the existing one. A bloated palette is harder to use consistently than a small one.
