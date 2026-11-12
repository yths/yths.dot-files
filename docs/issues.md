# Issues

## Miscellaneous

- [x] Add representative screenshots to `README.md`
    - (2026-08-30) rendered rather than captured. A screenshot of the running desktop would carry whatever was on it — window titles, file names, the bar's VPN country and usage figures — so `helper/render_preview.py` draws the same surfaces from the theme bundle: the bar, a terminal with the sixteen colours `patch_kitty` assigns, a dunst notification, and the palette itself. It opens two files, both under `assets/`, and a test asserts it reaches for no session source.
    - (2026-08-30) if a real screenshot is wanted later, it can replace `docs/preview/*.png` without touching anything else; the README references the paths, not the renderer.
- [x] Fix installation script
- [x] Add missing dependencies (OS packages) to installation instructions/dependencies list
    - (2026-05-16) full inventory in `docs/dependencies.md`; `docs/install.md` references it
- [ ] Integrate wallpaper generation script
- [ ] Add screen lock feature
- [x] Reference VM with dot files
    - (2026-05-16) `docs/os-build.md` carries the QEMU walkthrough under "Setting Up the Virtual Machine"
- [x] Change color names to something meaningful, also show dark theme colors
    - (2026-05-16) semantic tokens documented in `docs/palette-semantics.md`; both `light` and `dark` modes covered

## Documentation

- [x] Manage backup/ directory — pre-refactor archive; consider deletion (git history preserves content)
    - (2026-08-29) the directory is not present in the working tree and was never tracked; the `backup/` entry in `.gitignore` is retained so a future archive stays out of the tree
- [x] Add LICENSE.md at root
    - (2026-05-16) added MIT license
- [x] Standardize documentation style under `docs/style.md`
    - (2026-05-16) all docs now follow the codified path/code-block/list-marker rules
- [x] Document the `yths` color scheme palette in `docs/notes.md`
    - (2026-05-16) semantic tokens documented in `docs/palette-semantics.md`
    - (2026-08-29) the `yths` palette table is at `docs/palettes/yths/README.md`, generated from the bundle's own `palette.pkl`
- [x] Move `configuration/qtile/widgets/test_audio.py` out of the widget directory
    - (2026-08-29) the symlink half went first: `patch_configurations.py`, `patch_vsc.py` and the two `vsc_default_*.json` links are gone. `location.py` and `patch_configurations.py` derive the repository root from `os.path.realpath(__file__)` and call `helper/` and `configuration/vscode/` directly, so nothing needs a copy parked under `~/.config/qtile/widgets/`.
    - (2026-08-29) the rest followed, and the ticket widened to every non-widget in the directory. `_stream.py` and `_state.py` moved to `configuration/qtile/shared/` as `stream.py` and `state.py`; the harness became `helper/preview_audio.py`, with `--list` and `--device` in place of the hardcoded PortAudio index. The spectrum maths it duplicated — and had already drifted from, still offsetting the block ladder from `U+2581` — moved to `shared/spectrum.py`, which `widgets/audio.py` now renders through, so the tool previews the real meter. `helper/gendocs.py` fails on any non-widget under `widgets/` rather than silently skipping it, and the pre-commit hook runs it.
- [x] Drop legacy `colors` block from `~/.config/config.json`
    - (2026-05-16) `install.py` now strips it before writing; docs/config-schema.md, docs/palette-semantics.md, docs/notes.md, helper/README.md updated to describe `palette` as the sole colour vocabulary
- [x] `nuunamnir` palette is missing tokens required by qtile (`highlight`, `notification`, `warning`); qtile will `KeyError` if the preset is selected
    - (2026-05-16) added the three keys to the nuunamnir `palette.pkl` as aliases (`highlight` → `effect_complement_dark`, `notification` → `negative`, `warning` → `yellow`)
    - (2026-05-16) yths.themes domain `ColorToken` enum extended to 30 tokens with the same three additions; auto-seeding aliases them onto their semantic partners; tests, schema version, and downstream writer tests updated. **Partial only**: yths.themes' palette.pkl pipeline currently writes the raw chromalytica `_LibPalette` object rather than the `{mode: {token: hex}}` dict yths.dot-files consumes — so regenerated bundles still won't produce a working palette.pkl until that pipeline is completed
- [ ] Have `yths.themes` export to `assets/<name>/` rather than `assets/theme-<uuid>/`
    - (2026-08-30) done on this side: the repository tracks one bundle, `assets/default/`, and discovery no longer filters on a `theme-` prefix — a bundle is any directory under `assets/` holding a `config.json`, so an export under either layout is found. The generator still emits the UUID directory, which would appear beside the tracked one rather than replacing it.
    - (2026-08-30) the previous audit declined this, on the grounds that the generator owned the layout. Overridden: a directory name that requires parsing the JSON inside it to identify is worse than a contract change, and the readers that filtered on the prefix no longer do.
- [ ] Rename the `stream` Redis stream to `broadcast` in `yths.backend-service`
    - (2026-08-30) done on the reading side: the widget is `broadcast.py` / `WidgetBroadcast` and asks for a `broadcast` stream. Every other widget's module name is its stream name, and this one could not be, because `stream` already means the transport — `shared.stream.read_measurement(self.r, "stream")` said two different things in one line. Until the backend publishes under the new name, `LEGACY_STREAM_NAMES` in `configuration/qtile/shared/stream.py` retries the old one; delete that entry once no machine runs an older backend.
- [ ] Stop `yths.themes` emitting `monitors` and the stale `state` vocabulary in the bundle manifest
    - (2026-08-29) the `state.mode` key was renamed to `state.theme_mode` in both bundles at the same time as the code, for the same reason the generator has to follow: `install.py` rebuilds `state` from scratch and never reads the bundle's copy, so it rots unnoticed. A transitional translation lives in `configuration/qtile/shared/state.py` and should be deleted once no machine runs an older configuration file.
    - (2026-08-29) dropped from both checked-in bundles: it recorded the geometry of the machine that generated the theme, which `install.py` replaces with detected hardware at install time, and no reader ever consulted the bundle's copy. `docs/notes.md` and `docs/architecture.md` no longer list it. The generator side still needs to follow, or the next export reintroduces it — the contract note says schema changes land in both repos at once.
- [x] Extend `helper/gendocs.py` with an import scanner that diffs the actual imports against `docs/dependencies.md`
    - (2026-08-30) unblocked first: the scanner has to resolve the names in that page to compare them with real imports, and it could not while the "Used by" column mixed bare module names, bare filenames and paths rooted at three different directories.
    - (2026-08-30) shipped as `helper/list_dependencies.py`. The "Used by" column is generated from the imports rather than diffed against them, which is the stronger form — it cannot disagree. What is still diffed is the part no scanner can derive: `gendocs.py` fails when an import has no Arch package recorded, when a recorded package is no longer imported, or when a package is recorded but `setup.toml` never installs it.
- [x] Replace misleading `requirements*.txt` files with `docs/dependencies.md`
    - (2026-05-16) removed both `requirements.txt` and `requirements-dev.txt`; dependency surface now lives in `docs/dependencies.md` mapping each Python import to its Arch package

## Themes


## Configurations

- [ ] Map all colors for `qutebrowser`
- [ ] Handle monitor plug/unplug events gracefully in `qtile`
- [x] Add web-greeter to patch configuration
    - (2026-05-14) added `helper/patch_web_greeter.py`, wired into `patch_all`; themes parameterized via CSS variables generated into each theme's `theme.css`
- [x] Add plymouth to patch configuration
    - (2026-05-16) `helper/patch_plymouth.py` is wired into `helper/patch_configurations.py:patch_all`
    - (2026-08-30) correction: it was not, and had never been. The module exposed no importable function — every line sat under `if __name__` — so there was nothing for `patch_all` to call, and nothing else invoked it either.
    - (2026-08-30) `patch_plymouth(configuration)` exists and is importable. The blocker was that the theme installs into root-owned `/usr/share/plymouth/themes/`, so the patcher was split: rendering goes to a staging directory and needs no privileges, and installing promotes via `sudo -n` or `pkexec`.
    - (2026-08-30) deliberately *not* in the `PATCHERS` registry, which settles the question this ticket left open. The splash is drawn before login, so no user's theme preference applies to it; it is always rendered dark; and updating it costs root and an `mkinitcpio` run. It is a system decision made once, not a per-session one.
- [x] Automate installation of web-greeter
    - (2026-08-30) `helper/patch_web_greeter.py --install --activate` copies the patched theme into `/usr/share/web-greeter/themes/` and points LightDM at it, promoting through the same `utils.root_prefix` the plymouth installer uses. Activation is a separate flag because it changes what the next login looks like, and the theme already deployed on a machine need not be one of these. `./bootstrap.sh` runs it; `--skip-system` opts out.
- [x] Automate installation of plymouth
    - (2026-08-30) partly done: `python helper/patch_plymouth.py --install --rebuild` performs the copy into `/usr/share/plymouth/themes/` and the `mkinitcpio` rebuild that used to be two manual commands in the theme README, prompting for root once.
    - (2026-08-30) finished by `./bootstrap.sh` running it, rather than `install.py`. The installer writes into `$HOME` and never asks for root; the bootstrap script already holds a sudo context from the package install, and is the step a reader runs deliberately on a new machine. Both privileged installs are its last action, so everything reversible happens first, and `--skip-system` leaves them.
- [x] Automatically patch README.md on color theme change
    - (2026-08-30) as a generated block rather than a patcher, which is the distinction that matters: the README describes the repository, not the running session, so a dusk/dawn switch must not touch it. `helper/list_configured.py` derives the application table from `install.py`'s install table and the theme name from `setup.toml`, so the block changes exactly when an application is added or the default theme changes.
    - (2026-08-30) the preview images are rendered by `helper/render_preview.py` from the theme bundle, and `gendocs.py` fails when they no longer match the palette that ships — so a theme change cannot leave the README showing the old one.
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
