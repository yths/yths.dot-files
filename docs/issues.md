# Issues

## Miscellaneous

- [ ] Add representative screenshots to `README.md`
- [x] Fix installation script
- [ ] Add missing dependencies (OS packages) to installation instructions/dependencies list
- [ ] Integrate wallpaper generation script
- [ ] Add screen lock feature
- [ ] Reference VM with dot files
- [ ] Change color names to something meaningful, also show dark theme colors

## Themes

- [ ] Add a `yths` web-greeter theme directory (currently only `nuunamnir` ships under `configuration/web-greeter/themes/`)
- [ ] Add a `nuunamnir` plymouth theme directory (currently only `yths` ships under `configuration/plymouth/themes/`)
- [ ] Document the `yths` color scheme palette in `docs/notes.md` to match the `nuunamnir` entry

## Configurations

- [ ] Map all colors for `qutebrowser`
- [ ] Handle monitor plug/unplug events gracefully in `qtile`
- [x] Add web-greeter to patch configuration
    - (2026-05-14) added `helper/patch_web_greeter.py`, wired into `patch_all`; themes parameterized via CSS variables generated into each theme's `theme.css`
- [ ] Add plymouth to patch configuration
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
