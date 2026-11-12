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

- [x] Manage backup/ directory — pre-refactor archive; consider deletion (git history preserves content)
    - (2026-08-29) the directory is not present in the working tree and was never tracked; the `backup/` entry in `.gitignore` is retained so a future archive stays out of the tree
- [x] Add LICENSE.md at root
    - (2026-05-16) added MIT license
- [x] Standardize documentation style under `docs/style.md`
    - (2026-05-16) all docs now follow the codified path/code-block/list-marker rules
- [x] Document the `yths` color scheme palette in `docs/notes.md`
    - (2026-05-16) semantic tokens documented in `docs/color-semantics.md`
    - (2026-08-29) the `yths` palette table is at `docs/palettes/yths/README.md`, generated from the bundle's own `palette.pkl`
- [x] Move `configuration/qtile/widgets/test_audio.py` out of the widget directory
    - (2026-08-29) the symlink half went first: `patch_configurations.py`, `patch_vsc.py` and the two `vsc_default_*.json` links are gone. `location.py` and `patch_configurations.py` derive the repository root from `os.path.realpath(__file__)` and call `helper/` and `configuration/vscode/` directly, so nothing needs a copy parked under `~/.config/qtile/widgets/`.
    - (2026-08-29) the rest followed, and the ticket widened to every non-widget in the directory. `_stream.py` and `_state.py` moved to `configuration/qtile/shared/` as `stream.py` and `state.py`; the harness became `helper/preview_audio.py`, with `--list` and `--device` in place of the hardcoded PortAudio index. The spectrum maths it duplicated — and had already drifted from, still offsetting the block ladder from `U+2581` — moved to `shared/spectrum.py`, which `widgets/audio.py` now renders through, so the tool previews the real meter. `helper/gendocs.py` fails on any non-widget under `widgets/` rather than silently skipping it, and the pre-commit hook runs it.
- [x] Drop legacy `colors` block from `~/.config/config.json`
    - (2026-05-16) `install.py` now strips it before writing; docs/config-schema.md, docs/color-semantics.md, docs/notes.md, helper/README.md updated to describe `palette` as the sole colour vocabulary
- [x] `nuunamnir` palette is missing tokens required by qtile (`highlight`, `notification`, `warning`); qtile will `KeyError` if the preset is selected
    - (2026-05-16) added the three keys to the nuunamnir `palette.pkl` as aliases (`highlight` → `effect_complement_dark`, `notification` → `negative`, `warning` → `yellow`)
    - (2026-05-16) yths.themes domain `ColorToken` enum extended to 30 tokens with the same three additions; auto-seeding aliases them onto their semantic partners; tests, schema version, and downstream writer tests updated. **Partial only**: yths.themes' palette.pkl pipeline currently writes the raw chromalytica `_LibPalette` object rather than the `{mode: {token: hex}}` dict yths.dot-files consumes — so regenerated bundles still won't produce a working palette.pkl until that pipeline is completed
- [ ] Stop `yths.themes` emitting `monitors` and the stale `state` vocabulary in the bundle manifest
    - (2026-08-29) the `state.mode` key was renamed to `state.theme_mode` in both bundles at the same time as the code, for the same reason the generator has to follow: `install.py` rebuilds `state` from scratch and never reads the bundle's copy, so it rots unnoticed. A transitional translation lives in `configuration/qtile/shared/state.py` and should be deleted once no machine runs an older configuration file.
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
