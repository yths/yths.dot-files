# Tips

## Switch the Active Theme

`install.py` is idempotent — re-run it to pick a different preset without touching anything outside the wallpaper and color paths. The current `~/.config/config.json` is preserved as `~/.config/config.json.<timestamp>.bak` so the previous selection can be recovered.

```bash
python install.py
```

For non-interactive use (e.g. provisioning), copy the desired bundle's `config.json` directly:

```bash
cp assets/theme-<uuid>/config.json ~/.config/config.json
```

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
