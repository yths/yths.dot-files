# Notes

## Theme System

A theme is a bundle under `assets/theme-<uuid>/` produced by the [yths.themes](https://github.com/yths/yths.themes) orchestrator. Each bundle is self-describing via `config.json` (color tokens, font, monitor geometry, wallpaper paths) and ships its own `palette.pkl` plus four wallpapers. `install.py` enumerates the bundles, prompts the user to pick one, writes the chosen `config.json` to `~/.config/config.json`, and installs the wallpapers under `~/.config/qtile/`.

Two presets ship in this repo by default — `yths` and `nuunamnir`. They share the semantic token names below; only the concrete colors differ.

## Theme-Bundle Contract with yths.themes

`yths.themes` writes into `{DOTFILES_REPOSITORY_PATH}/assets/theme-<uuid>/`. The directory layout it produces is the contract `install.py` reads:

```
assets/theme-<uuid>/
  config.json                       # name, font, colors (light/dark), wallpapers, state
  palette.pkl                       # pickled palette object consumed by qtile and the patch scripts
  wallpapers/
    wallpaper-light.png
    wallpaper-light-highlight.png
    wallpaper-dark.png
    wallpaper-dark-highlight.png
  plymouth/                         # optional: .plymouth INI + tarball for plymouth-set-default-theme
  web-greeter-handoff.json          # optional: hints for the future web-greeter generator
  wallpaper-handoff.json            # optional: hints for the future wallpaper generator
```

Any change to this schema needs to land in both repos at once.

## qtile Widgets

The widgets under `configuration/qtile/widgets/` (`bluetooth`, `power_supply`, `audio`, `service_state`, `stream_state`, `updates`, `vpn`, `location`) read from the Redis streams populated by [yths.backend-service](https://github.com/yths/yths.backend-service). Each widget subscribes only to its own stream and pulls the latest entry on every poll.

The widgets use the `BackgroundPoll` mixin (`libqtile.widget.base`) so polling happens off the main qtile event loop. Earlier versions hand-rolled threaded polling; the migration to `BackgroundPoll` removed the thread management code and let qtile own the cadence.

Connection settings come from `BACKEND_REDIS_HOST` / `BACKEND_REDIS_PORT` / `BACKEND_REDIS_DB` environment variables — the same ones the backend service reads. If Redis is unreachable at qtile startup, the widgets silently fall back to empty values.

## Color Scheme: nuunamnir

The `nuunamnir` palette is designed to exploit the correlation between lightness and colorfulness with perceptual saliency, so the hue carries semantic meaning rather than arbitrary preference. Background and foreground colors stay desaturated; cues that need attention (positive, negative, neutral, effect) escalate toward the saturated and colorful end of the gamut. The full derivation is documented at [nuunamnir.color-scheme](https://www.github.com/nuunamnir/nuunamnir.color-scheme).

The dark variant is the photonegative reflection of the light variant: corresponding tokens swap hue/lightness rather than re-pick a new color. This keeps recognition consistent across mode switches.

| Name | light sRGB String | light sRGB Numeric | light Patch | dark Patch | dark sRGB Numeric | dark sRGB String |
| --------------- | -------------------- | --------------------- | -------------- | ------------- | -------------------- | -------------------- |
| cursor          | `#282828` | `(0.157, 0.157, 0.157)` | ![#282828](../assets/themes/nuunamnir/palette/282828.png) | ![#e5e5e5](../assets/themes/nuunamnir/palette/e5e5e5.png) | `(0.898, 0.898, 0.898)` | `#e5e5e5` |
| grey            | `#909090` | `(0.565, 0.565, 0.565)` | ![#909090](../assets/themes/nuunamnir/palette/909090.png) | ![#909090](../assets/themes/nuunamnir/palette/909090.png) | `(0.565, 0.565, 0.565)` | `#909090` |
| background      | `#e5e5e5` | `(0.898, 0.898, 0.898)` | ![#e5e5e5](../assets/themes/nuunamnir/palette/e5e5e5.png) | ![#282828](../assets/themes/nuunamnir/palette/282828.png) | `(0.157, 0.157, 0.157)` | `#282828` |
| foreground      | `#4d4d4d` | `(0.302, 0.302, 0.302)` | ![#4d4d4d](../assets/themes/nuunamnir/palette/4d4d4d.png) | ![#cbcbcb](../assets/themes/nuunamnir/palette/cbcbcb.png) | `(0.796, 0.796, 0.796)` | `#cbcbcb` |
| pastel_yellow   | `#69442d` | `(0.412, 0.267, 0.176)` | ![#69442d](../assets/themes/nuunamnir/palette/69442d.png) | ![#e4ba8b](../assets/themes/nuunamnir/palette/e4ba8b.png) | `(0.894, 0.729, 0.545)` | `#e4ba8b` |
| yellow          | `#7c3800` | `(0.486, 0.220, 0.000)` | ![#7c3800](../assets/themes/nuunamnir/palette/7c3800.png) | ![#ffb04c](../assets/themes/nuunamnir/palette/ffb04c.png) | `(1.000, 0.690, 0.298)` | `#ffb04c` |
| effect_light    | `#664900` | `(0.400, 0.286, 0.000)` | ![#664900](../assets/themes/nuunamnir/palette/664900.png) | ![#f0c532](../assets/themes/nuunamnir/palette/f0c532.png) | `(0.941, 0.773, 0.196)` | `#f0c532` |
| effect_light_muted | `#5c4c2e` | `(0.361, 0.298, 0.180)` | ![#5c4c2e](../assets/themes/nuunamnir/palette/5c4c2e.png) | ![#dec887](../assets/themes/nuunamnir/palette/dec887.png) | `(0.871, 0.784, 0.529)` | `#dec887` |
| effect_dark     | `#f0c532` | `(0.941, 0.773, 0.196)` | ![#f0c532](../assets/themes/nuunamnir/palette/f0c532.png) | ![#664900](../assets/themes/nuunamnir/palette/664900.png) | `(0.400, 0.286, 0.000)` | `#664900` |
| effect_dark_muted | `#dec887` | `(0.871, 0.784, 0.529)` | ![#dec887](../assets/themes/nuunamnir/palette/dec887.png) | ![#5c4c2e](../assets/themes/nuunamnir/palette/5c4c2e.png) | `(0.361, 0.298, 0.180)` | `#5c4c2e` |
| positive        | `#455600` | `(0.271, 0.337, 0.000)` | ![#455600](../assets/themes/nuunamnir/palette/455600.png) | ![#c0d958](../assets/themes/nuunamnir/palette/c0d958.png) | `(0.753, 0.851, 0.345)` | `#c0d958` |
| green           | `#455600` | `(0.271, 0.337, 0.000)` | ![#455600](../assets/themes/nuunamnir/palette/455600.png) | ![#c0d958](../assets/themes/nuunamnir/palette/c0d958.png) | `(0.753, 0.851, 0.345)` | `#c0d958` |
| pastel_green    | `#4a522f` | `(0.290, 0.322, 0.184)` | ![#4a522f](../assets/themes/nuunamnir/palette/4a522f.png) | ![#c6d397](../assets/themes/nuunamnir/palette/c6d397.png) | `(0.776, 0.827, 0.592)` | `#c6d397` |
| cyan            | `#00644e` | `(0.000, 0.392, 0.306)` | ![#00644e](../assets/themes/nuunamnir/palette/00644e.png) | ![#2de9cc](../assets/themes/nuunamnir/palette/2de9cc.png) | `(0.176, 0.914, 0.800)` | `#2de9cc` |
| pastel_cyan     | `#3e5c52` | `(0.243, 0.361, 0.322)` | ![#3e5c52](../assets/themes/nuunamnir/palette/3e5c52.png) | ![#9dd9cb](../assets/themes/nuunamnir/palette/9dd9cb.png) | `(0.616, 0.851, 0.796)` | `#9dd9cb` |
| effect_complement_dark_muted | `#9cd7e2` | `(0.612, 0.843, 0.886)` | ![#9cd7e2](../assets/themes/nuunamnir/palette/9cd7e2.png) | ![#425c66](../assets/themes/nuunamnir/palette/425c66.png) | `(0.259, 0.361, 0.400)` | `#425c66` |
| effect_complement_dark | `#00e4ff` | `(0.000, 0.894, 1.000)` | ![#00e4ff](../assets/themes/nuunamnir/palette/00e4ff.png) | ![#006179](../assets/themes/nuunamnir/palette/006179.png) | `(0.000, 0.380, 0.475)` | `#006179` |
| effect_complement_light_muted | `#425c66` | `(0.259, 0.361, 0.400)` | ![#425c66](../assets/themes/nuunamnir/palette/425c66.png) | ![#9cd7e2](../assets/themes/nuunamnir/palette/9cd7e2.png) | `(0.612, 0.843, 0.886)` | `#9cd7e2` |
| neutral         | `#006179` | `(0.000, 0.380, 0.475)` | ![#006179](../assets/themes/nuunamnir/palette/006179.png) | ![#5bd9ff](../assets/themes/nuunamnir/palette/5bd9ff.png) | `(0.357, 0.851, 1.000)` | `#5bd9ff` |
| effect_complement_light | `#006179` | `(0.000, 0.380, 0.475)` | ![#006179](../assets/themes/nuunamnir/palette/006179.png) | ![#00e4ff](../assets/themes/nuunamnir/palette/00e4ff.png) | `(0.000, 0.894, 1.000)` | `#00e4ff` |
| pastel_blue     | `#415670` | `(0.255, 0.337, 0.439)` | ![#415670](../assets/themes/nuunamnir/palette/415670.png) | ![#a3cfe0](../assets/themes/nuunamnir/palette/a3cfe0.png) | `(0.639, 0.812, 0.878)` | `#a3cfe0` |
| blue            | `#005797` | `(0.000, 0.341, 0.592)` | ![#005797](../assets/themes/nuunamnir/palette/005797.png) | ![#5bd9ff](../assets/themes/nuunamnir/palette/5bd9ff.png) | `(0.357, 0.851, 1.000)` | `#5bd9ff` |
| pastel_magenta  | `#51466e` | `(0.318, 0.275, 0.431)` | ![#51466e](../assets/themes/nuunamnir/palette/51466e.png) | ![#ccbfdf](../assets/themes/nuunamnir/palette/ccbfdf.png) | `(0.800, 0.749, 0.875)` | `#ccbfdf` |
| magenta         | `#54369c` | `(0.329, 0.212, 0.612)` | ![#54369c](../assets/themes/nuunamnir/palette/54369c.png) | ![#d4b6ff](../assets/themes/nuunamnir/palette/d4b6ff.png) | `(0.831, 0.714, 1.000)` | `#d4b6ff` |
| pastel_red      | `#6b3e4d` | `(0.420, 0.243, 0.302)` | ![#6b3e4d](../assets/themes/nuunamnir/palette/6b3e4d.png) | ![#e1b2c5](../assets/themes/nuunamnir/palette/e1b2c5.png) | `(0.882, 0.698, 0.773)` | `#e1b2c5` |
| negative        | `#83254c` | `(0.514, 0.145, 0.298)` | ![#83254c](../assets/themes/nuunamnir/palette/83254c.png) | ![#ff9fca](../assets/themes/nuunamnir/palette/ff9fca.png) | `(1.000, 0.624, 0.792)` | `#ff9fca` |
| red             | `#83254c` | `(0.514, 0.145, 0.298)` | ![#83254c](../assets/themes/nuunamnir/palette/83254c.png) | ![#ff9fca](../assets/themes/nuunamnir/palette/ff9fca.png) | `(1.000, 0.624, 0.792)` | `#ff9fca` |

## Color Scheme: yths

The `yths` palette uses the same semantic token names (`positive`, `negative`, `neutral`, `effect_*`, etc.) so widgets and configuration files can switch between presets without code changes. The concrete colors are tuned differently — see the `colors` block in `assets/theme-<yths-uuid>/config.json` for the canonical values. A dedicated palette reference for `yths`, matching the table above, has not been written yet (tracked in [issues.md](issues.md)).
