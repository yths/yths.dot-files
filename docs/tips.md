# Tips

## Switch the Active Theme

Re-run `install.py` to pick a different preset. The current `~/.config/config.json` is preserved as `~/.config/config.json.<timestamp>.bak` first, so the previous selection can be recovered.

Re-running also rewrites `state` to its defaults — `theme: light`, `condition: normal`, `theme_mode: automatic` — so a manually pinned dark theme reverts to automatic switching. Restore it by editing `~/.config/config.json`, or with the location widget's middle- and right-click bindings.

```bash
python install.py
```

For non-interactive use (e.g. provisioning), name the theme instead of answering the prompt:

```bash
python install.py --theme yths
```

An unknown name exits non-zero and lists the bundles it found, before anything is installed.

Copying a bundle's `config.json` into place does not work, and never did: the installer
assembles `~/.config/config.json` from several sources — the palette comes from
`palette.pkl`, the monitor geometry from the detected hardware, the wallpaper paths from
where it installed them -- and a bundle manifest carries none of that. Only `name` is
taken from it.

## List Available Themes

`helper/list_themes.py` dumps the `config.json` and pickled palette of every bundle discovered under `assets/`. Useful when scripting against the installed themes or when verifying that a fresh export from `yths.themes` landed correctly.

```bash
DOTFILES_REPOSITORY_PATH=$(pwd) python helper/list_themes.py
```

## Speed Up `yay` with `rate-mirrors`

Auto-rank Arch mirrors before updates so package downloads pick the fastest endpoint. Install `rate-mirrors-bin` from AUR, then add the following aliases to `~/.bashrc`:

```bash
alias yay-drop-caches='sudo paccache -rk3; yay -Sc --aur --noconfirm'
alias yay-update-all='export TMPFILE="$(mktemp)"; \
  sudo true; \
  rate-mirrors --entry-country=<country-code> --save=$TMPFILE arch --max-delay=21600 \
  && sudo mv /etc/pacman.d/mirrorlist /etc/pacman.d/mirrorlist-backup \
  && sudo mv $TMPFILE /etc/pacman.d/mirrorlist \
  && yay-drop-caches \
  && yay -Syyu --noconfirm'
```

Replace `<country-code>` with your ISO country code (e.g. `DE`, `US`, `GB`).

## Prevent Monitor Energy Saving in Videos

`qutebrowser` does not currently inhibit the screensaver during video playback. The workaround is to pipe the page through `mpv` instead; the qtile config binds this to `,m`:

```text
,m  →  mpv "$current_url"
```

## Preview a Web-Greeter Theme

The web-greeter preview server under `configuration/web-greeter/preview/` serves a theme directory as the greeter would render it, so iteration doesn't require restarting LightDM.

## Debug Plymouth Boot Splash

Plymouth's splash can be exercised without rebooting:

```bash
plymouthd --debug-file=~/plymouth-test.log
plymouth --show-splash --debug
sleep 15
plymouth --quit
```

Logs land in `~/plymouth-test.log` for inspection afterwards.
