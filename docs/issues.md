# Issues

## Miscellaneous

- [ ] Add representative screenshots to `README.md`
- [x] Fix installation script
- [x] Add missing dependencies (OS packages) to installation instructions/dependencies list
    - (2026-05-16) full inventory in `docs/dependencies.md`; `docs/install.md` references it
- [ ] Integrate wallpaper generation script
- [ ] Add screen lock feature
- [x] Reference VM with dot files
    - (2026-05-16) `docs/install.md` carries the QEMU walkthrough under "Setting Up the Virtual Machine"
- [x] Change color names to something meaningful, also show dark theme colors
    - (2026-05-16) semantic tokens documented in `docs/color-semantics.md`; both `light` and `dark` modes covered

## Documentation

- [ ] Manage backup/ directory — pre-refactor archive; consider deletion (git history preserves content)
- [x] Add LICENSE.md at root
    - (2026-05-16) added MIT license
- [x] Standardize documentation style under `docs/style.md`
    - (2026-05-16) all docs now follow the codified path/code-block/list-marker rules
- [x] Document the `yths` color scheme palette in `docs/notes.md`
    - (2026-05-16) semantic tokens documented in `docs/color-semantics.md`; concrete palette table for `yths` still to be authored
- [ ] Remove stray non-widget files from `configuration/qtile/widgets/` (`patch_configurations.py` and `patch_vsc.py` are duplicates of `helper/`; `test_audio.py` is experimental)
- [x] Drop legacy `colors` block from `~/.config/config.json`
    - (2026-05-16) `install.py` now strips it before writing; docs/config-schema.md, docs/color-semantics.md, docs/notes.md, helper/README.md updated to describe `palette` as the sole colour vocabulary
- [x] `nuunamnir` palette is missing tokens required by qtile (`highlight`, `notification`, `warning`); qtile will `KeyError` if the preset is selected
    - (2026-05-16) added the three keys to the nuunamnir `palette.pkl` as aliases (`highlight` → `effect_complement_dark`, `notification` → `negative`, `warning` → `yellow`)
    - (2026-05-16) yths.themes domain `ColorToken` enum extended to 30 tokens with the same three additions; auto-seeding aliases them onto their semantic partners; tests, schema version, and downstream writer tests updated. **Partial only**: yths.themes' palette.pkl pipeline currently writes the raw chromalytica `_LibPalette` object rather than the `{mode: {token: hex}}` dict yths.dot-files consumes — so regenerated bundles still won't produce a working palette.pkl until that pipeline is completed
- [ ] Extend `helper/gendocs.py` with an import scanner that diffs the actual imports against `docs/dependencies.md`
- [x] Replace misleading `requirements*.txt` files with `docs/dependencies.md`
    - (2026-05-16) removed both `requirements.txt` and `requirements-dev.txt`; dependency surface now lives in `docs/dependencies.md` mapping each Python import to its Arch package

## Themes

- [ ] Add a `yths` web-greeter theme directory (currently only `nuunamnir` ships under `configuration/web-greeter/themes/`)
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
- [ ] Improve VSC color mapping - currently selection is not visible

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
