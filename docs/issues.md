# Issues

## Miscellaneous

- [ ] Add representative screenshots to `README.md`
- [x] Fix installation script
- [x] Add missing dependencies (OS packages) to installation instructions/dependencies list
    - (2026-05-16) full inventory in `docs/dependencies.md`; `docs/install.md` references it
- [ ] Integrate wallpaper generation script
- [ ] Add screen lock feature
- [x] Reference VM with dot files
    - (2026-05-16) `docs/os-build.md` carries the QEMU walkthrough under "Setting Up the Virtual Machine"
- [x] Change color names to something meaningful, also show dark theme colors
    - (2026-05-16) semantic tokens documented in `docs/color-semantics.md`; both `light` and `dark` modes covered

## Documentation

- [ ] Manage backup/ directory — pre-refactor archive; consider deletion (git history preserves content)
- [x] Add LICENSE.md at root
    - (2026-05-16) added MIT license
- [x] Standardize documentation style under `docs/style.md`
    - (2026-05-16) all docs now follow the codified path/code-block/list-marker rules
- [x] Document the `yths` color scheme palette in `docs/notes.md`
    - (2026-05-16) semantic tokens documented in `docs/color-semantics.md`
    - (2026-08-29) the `yths` palette table is at `docs/palettes/yths/README.md`, generated from the bundle's own `palette.pkl`
- [ ] Move `configuration/qtile/widgets/test_audio.py` out of the widget directory. It is a standalone harness, not a widget — `helper/gendocs.py` skips it because it does not import `libqtile.widget.base`, and `configuration/qtile/widgets/README.md` says such files do not belong here.
    - (2026-08-29) the symlink half is done: `patch_configurations.py`, `patch_vsc.py` and the two `vsc_default_*.json` links are removed. `location.py` and `patch_configurations.py` derive the repository root from `os.path.realpath(__file__)` and call `helper/` and `configuration/vscode/` directly, so nothing needs a copy parked under `~/.config/qtile/widgets/` any more. Only the harness is left, and it has a hardcoded PortAudio device index that works on one machine — moving it to `helper/` would list it in the generated helper inventory, so it needs a home decision rather than a move.
- [x] Drop legacy `colors` block from `~/.config/config.json`
    - (2026-05-16) `install.py` now strips it before writing; docs/config-schema.md, docs/color-semantics.md, docs/notes.md, helper/README.md updated to describe `palette` as the sole colour vocabulary
- [x] `nuunamnir` palette is missing tokens required by qtile (`highlight`, `notification`, `warning`); qtile will `KeyError` if the preset is selected
    - (2026-05-16) added the three keys to the nuunamnir `palette.pkl` as aliases (`highlight` → `effect_complement_dark`, `notification` → `negative`, `warning` → `yellow`)
    - (2026-05-16) yths.themes domain `ColorToken` enum extended to 30 tokens with the same three additions; auto-seeding aliases them onto their semantic partners; tests, schema version, and downstream writer tests updated. **Partial only**: yths.themes' palette.pkl pipeline currently writes the raw chromalytica `_LibPalette` object rather than the `{mode: {token: hex}}` dict yths.dot-files consumes — so regenerated bundles still won't produce a working palette.pkl until that pipeline is completed
- [ ] Stop `yths.themes` emitting `monitors` in the bundle manifest
    - (2026-08-29) dropped from both checked-in bundles: it recorded the geometry of the machine that generated the theme, which `install.py` replaces with detected hardware at install time, and no reader ever consulted the bundle's copy. `docs/notes.md` and `docs/architecture.md` no longer list it. The generator side still needs to follow, or the next export reintroduces it — the contract note says schema changes land in both repos at once.
- [ ] Extend `helper/gendocs.py` with an import scanner that diffs the actual imports against `docs/dependencies.md`
- [x] Replace misleading `requirements*.txt` files with `docs/dependencies.md`
    - (2026-05-16) removed both `requirements.txt` and `requirements-dev.txt`; dependency surface now lives in `docs/dependencies.md` mapping each Python import to its Arch package

## Themes

- [ ] Add a `nuunamnir` plymouth theme directory (currently only `yths` ships under `configuration/plymouth/themes/`)

## Configurations

- [ ] Map all colors for `qutebrowser`
- [ ] Handle monitor plug/unplug events gracefully in `qtile`
- [x] Add web-greeter to patch configuration
    - (2026-05-14) added `helper/patch_web_greeter.py`, wired into `patch_all`; themes parameterized via CSS variables generated into each theme's `theme.css`
- [x] Add plymouth to patch configuration
    - (2026-05-16) `helper/patch_plymouth.py` is wired into `helper/patch_configurations.py:patch_all`
- [ ] Automate installation of web-greeter
- [ ] Automate installation of plymouth
- [ ] Automatically patch README.md on color theme change
- [x] Create VSC color theme
    - (2026-01-02) added crude VSC theme color mapping script (does not work well in light mode)
- [x] Improve VSC color mapping - currently selection is not visible
    - (2026-05-23) `helper/patch_vsc.py` drops the `background` palette label from candidates for any selection/highlight/hover/focus/match/range `*Background` key, so the nearest-neighbour mapper can no longer collapse selection colours onto the editor background

## Background Service

- [x] Monitor and display audio levels (`qtile` widget)
- [x] Monitor screen recording/streaming status (`qtile` widget) and wallpaper change
    - (2026-01-03) implemented widget and updated backend service to also detect running obs

## Bugs

- [x] qtile uses additional resources if the configuration is reloaded
    - (2025-12-21) seemed to be resolved by switching from `pkill` to `qtile cmd-obj`
- [x] Prevent monitor energy saving when running video in `qutebrowser`
    - (2026-01-03) apparently not supported, workaround implemented via `mpv` and keybind `,m`
- [x] picom has some strange effect on video and games (initial black screen)
    - (2025-12-07) resolved by changing the picom backend from `egl` to `glx`
- [x] x server(?) crashes when theme switches mode
    - (2025-12-21) resolved by switching from `pkill` to `qtile cmd-obj`
- [x] picom makes gtk gui flicker
    - (2026-01-01) might be fixed by applying configurations from [https://bbs.archlinux.org/viewtopic.php?id=259288](https://bbs.archlinux.org/viewtopic.php?id=259288)
