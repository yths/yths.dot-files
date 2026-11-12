# Tips

## Switch the Active Theme

On an installed machine, migrate to the bundle rather than reinstalling:

```bash
python install.py --migrate --theme <bundle>
```

That relinks the bundle's palette and wallpapers, re-runs every patcher and reloads the
running programs, and keeps `state` — a pinned theme stays pinned. Add `--no-reload` to
write the files without touching what is running. The login screen and boot splash need
root, so they follow with their own commands; the [README](../README.md#switch-theme) has
all three on one line.

A plain `python install.py --theme <bundle>` reinstalls instead. It backs the current
`~/.config/config.json` up as `~/.config/config.json.<timestamp>.bak` and rewrites `state`
to its defaults — `theme: light`, `condition: normal`, `theme_mode: automatic` — so a
manually pinned dark theme reverts to automatic switching. Use it for a new machine.

An unknown name exits non-zero and lists the bundles it found, before anything is changed.

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

`qutebrowser` sends no screensaver inhibit during video playback, so the screen blanks and
locks over it. (Firefox does send one; `inhibit-bridge` and the idle guard in
`configuration/qtile/shared/idle_guard.py` keep the screen on for it.) The workaround is to
play the video in `mpv`, which holds the screen itself. qutebrowser's configuration binds two
hints for that:

```text
,m  →  hint a link, play it in mpv full screen
,M  →  hint a link, play it in mpv windowed
```

## Preview a Web-Greeter Theme

The web-greeter preview server under `configuration/web-greeter/preview/` serves a theme directory as the greeter would render it, so iteration doesn't require restarting LightDM.

## Debug Plymouth Boot Splash

Render and install the current palette first — the splash reads its theme from the initramfs, so nothing changes until `mkinitcpio` runs:

```bash
python helper/patch_plymouth.py --install --rebuild
```

The splash can then be exercised without rebooting:

```bash
plymouthd --debug-file=~/plymouth-test.log
plymouth --show-splash --debug
sleep 15
plymouth --quit
```

Logs land in `~/plymouth-test.log` for inspection afterwards.

## Troubleshooting

### The Keyring Hangs After the First Login

On the first login after `gnome-keyring` is installed, PAM creates the login keyring from the
login password in the same moment the keyring daemon starts, and the daemon can miss it: the
`login` collection is listed but never loaded. Anything that stores a secret then waits on a
prompt that never draws — `secret-tool store` sits after asking for the value, and VSCode
cannot keep a sign-in.

Restart the daemon, or log in once more:

```bash
systemctl --user restart gnome-keyring-daemon
```

After a restart the keyring is locked until the next login, so the next secret stored asks
for the login password once. From the second login on, the file exists before the daemon
starts, and the login unlocks it without a prompt. To check:

```bash
echo test | secret-tool store --label="keyring test" dotfiles probe && secret-tool lookup dotfiles probe
secret-tool clear dotfiles probe
```

It prints `test` with no dialog when the keyring works.
