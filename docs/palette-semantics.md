# Palette Semantics

A reference for theme authors: what the palette is, what each token means, and how to add to it. Concrete colour values live in each preset's `palette.json`; this document is about contract, not hex codes.

> Three documents cover the palette, and they answer different questions. **What a token means** is this file. **What it looks like** in each preset is [palettes/](palettes/). **Where it is used** is [palette-reference.md](palette-reference.md).

## The Palette

The palette is a dict of two keys, `light` and `dark`. Each key maps to another dict whose keys are *token names* and whose values are hex colour strings:

```json
{
  "light": {
    "background":   "#fffaf9",
    "foreground":   "#535151",
    "highlight":    "#c20082",
    "notification": "#004946",
    "warning":      "#8b5901",
    "surface":      "#e3dfde"
  },
  "dark": { "background": "#141313", "foreground": "#d5d1d0" }
}
```

Abridged: a real file carries every token below, in both modes, and nothing else.

[chromalytica](https://github.com/yths/chromalytica) writes this file as `out/palette.json`, and it is the whole interface between the two repositories: the token names, their order, and the shape above. No colour value is shared, and nothing here needs chromalytica installed. `install.py` writes the active bundle's palette into `~/.config/config.json` under `"palette"`; qtile and the patchers read it via `configuration["palette"][theme][<token>]` where `theme` is `"light"` or `"dark"`. See [config-schema.md](config-schema.md) for the surrounding schema.

## The Vocabulary

Twenty-four tokens, and the set is closed rather than a floor. [`helper/palette_tokens.py`](../helper/palette_tokens.py) holds it as `TOKENS`, in file order; chromalytica holds the same tuple in `vocabulary.TOKENS`. Each side tests the other: chromalytica reads this repository's tracked `assets/default/palette.json` and fails if the key sequences differ, and `tests/test_palette_tokens.py` holds that file to `TOKENS`. The vocabulary cannot move in one repository alone.

### The Greys

Seven, from the background outward. None of them says anything; they are what a surface or a run of text is when it has nothing to report.

| Token | Means | On `background`, as chromalytica proposes |
|---|---|---|
| `background` | the ground everything is drawn on: the bar, a terminal, an editor | — |
| `surface` | one step off the background: a cell, a hovered row, a wash that has to be seen without being a colour | just visible |
| `surface_variant` | the next step: a stronger wash, or a surface on a surface | visible |
| `neutral` | borders, dividers, an inactive label | 3:1, interface components |
| `foreground_muted` | text that is there to be read but not first: a low-urgency title, a description | 4.5:1, body text |
| `foreground` | text | 7:1 |
| `foreground_variant` | the strongest text; kitty's "black", so text printed in black stays legible | the most the display has |

The two surfaces are never text and never a structural background. A side bar matched onto `surface` stops being part of the surface the editor is, and a label matched onto one is a step off the background it has to be read against.

### The Attention Tokens

Three tokens ask for attention, and they are not interchangeable. Which one a consumer reaches for says what kind of thing happened, so each has one meaning and keeps it everywhere.

| Token | Means | Examples |
|---|---|---|
| `highlight` | what to look at now: where focus is, and what is urgent | the focused window, the selected launcher entry, a window asking for attention, being on air, a battery about to run out, a critical notification |
| `notification` | worth knowing, nothing to act on | updates are available, a tunnel is up, the sound is muted, the next sunrise, a normal notification |
| `warning` | an error state: something is broken and stays so until it is fixed | the backend is down, a sign-in stopped working |

Two rules follow from the table:

- **`warning` is never a level.** A battery at 10 % and a limit at 90 % are urgent, not broken, so they are `highlight`. A colour that also means "low" stops meaning "failed".
- **Urgency is not severity.** dunst's `critical` urgency is how soon something wants reading, so it is `highlight`; the notification's own text says whether anything failed.

`highlight` carries both focus and urgency because both answer *where should I look*. The two are told apart by form: what has focus is a filled `highlight` block with `background` text, and what is asking for attention is `highlight` text or a `highlight` outline, never a second filled block.

chromalytica chooses these colours by the same order. `highlight` is the most salient colour the palette has; `failure` and `success` come next; `warning` and `notification` follow in equal steps down to plain text. A consumer that uses `notification` for something urgent is using the quietest of them for the loudest thing.

### The Outcome Tokens

| Token | Means |
|---|---|
| `success` | something that ran, and worked: the prompt after exit status 0, a page that loaded |
| `failure` | something that ran, and did not: a failed command, a page that did not load |

An outcome is the result of one attempt. A state that persists — the service is down, whether or not anyone just tried it — is `warning`.

### The Hues

`red`, `green`, `yellow`, `blue`, `magenta`, `cyan`, and a `_variant` of each. They mean nothing: they are kitty's ANSI slots, and what the two matchers (VSCode, qutebrowser) take syntax colours from. The base hues are text colours, at text contrast; the variants are accents.

A hue and its `_variant` are a pair: `patch_kitty` builds ANSI slot *i* from the base and slot *i + 8* from the variant, so a hue shipped without its partner is half a terminal palette.

Do not reach for a hue to say something. `red` is not `failure`: a theme may draw the two differently, and only the second is promised to mean what it says.

## Light vs Dark Variants

Both `light` and `dark` keys must be present with the same token set. The active variant is selected by `state.theme` in `~/.config/config.json`. How the two relate is the generator's decision: chromalytica makes them mirror images, so a token has the same saliency against its background in both modes and a role keeps its hue across a theme switch.

## A Bundle from Before the Newest Tokens

`surface`, `surface_variant` and `foreground_muted` are the newest three. A bundle exported before them carries twenty-one tokens and still installs: `install.py` gives it stand-ins mixed from its own greys — a quarter and a half of the way from `background` to `neutral`, and halfway from `neutral` to `foreground` — and says so. qtile and `patch_configurations.py` do the same for a `~/.config/config.json` written before them, so a pull does not break a running desktop:

```bash
python install.py --migrate    # rewrite ~/.config/config.json with the stand-ins in it
```

The stand-ins approximate what the generator would choose against the whole grid. Exporting the theme again replaces them.

## Where Tokens Are Consumed

Derived rather than listed here: [palette-reference.md](palette-reference.md) carries the full
map, generated from the patcher sources, and a hand-written summary beside it would be a second
copy to keep true. To ask about one token without reading the whole document:

```bash
python helper/list_palette.py --value highlight   # every field that carries it
python helper/list_palette.py --app dunst         # everything one application reads
python helper/list_palette.py --file ~/.config/tmux/tmux.conf
```

Two consumers do not follow the active theme, which is worth knowing before a bundle is blamed
for either: the login screen pins its font size in `theme.json#font_overrides`, and the boot
splash always renders the dark variant, because it is drawn before anyone has logged in.

## Adding a New Token

When a new consumer (widget, patcher) needs a colour no token means:

1. Add the token to the tables above, with what it means — not which consumer uses it.
2. Add it to `TOKENS` in `helper/palette_tokens.py`, and to `vocabulary.TOKENS` in chromalytica with a rule for choosing its colour. Each repository's contract test fails until the other carries it too, which is the point: the two halves land together or not at all.
3. If an older bundle can be given a stand-in for it, add the mix to `DERIVED` in `helper/palette_tokens.py`.
4. Regenerate `assets/default/palette.json` and commit it.

Avoid adding tokens lightly — each one is a constraint every preset must honour.
