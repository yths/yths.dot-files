# Tips

## Switch the Active Theme

On an installed machine, migrate to the bundle rather than reinstalling:

```bash
python install.py --migrate --theme <bundle>
```

That relinks the bundle's palette and wallpapers, re-runs every patcher and reloads the
running programs, and keeps `state` — a pinned theme stays pinned. Add `--no-reload` to
write the files without touching what is running. Add `--system` to switch the login screen
and boot splash too: they need root, which it asks for once, before anything changes.

A plain `python install.py --theme <bundle>` reinstalls instead. It backs the current
`~/.config/config.json` up as `~/.config/config.json.<timestamp>.bak` and rewrites `state`
to its defaults — `theme: light`, `condition: normal`, `theme_mode: automatic` — so a
manually pinned dark theme reverts to automatic switching. Use it for a new machine.

An unknown name exits non-zero and lists the bundles it found, before anything is changed.

To make the bundle the default for a fresh install too, set `theme` in
[setup.toml](../setup.toml). The optional
[lock feedback package](../configuration/lock/README.md#what-a-wrong-password-looks-like) is
not part of a switch; install or upgrade it on its own with
`python helper/patch_lock.py --install-pam`.

Copying a bundle's `config.json` into place does not work, and never did: the installer
assembles `~/.config/config.json` from several sources — the palette comes from
`palette.json`, the monitor geometry from the detected hardware, the wallpaper paths from
where it installed them -- and a bundle manifest carries none of that. Only `name` is
taken from it.

## List Available Themes

`helper/list_themes.py` dumps the `config.json` and `palette.json` of every bundle discovered under `assets/`. Useful when scripting against the installed themes or when verifying that a fresh export from `yths.themes` landed correctly.

```bash
DOTFILES_REPOSITORY_PATH=$(pwd) python helper/list_themes.py
```

## Speed Up `yay` with `rate-mirrors`

`yay-update-all`, defined in the installed `~/.bashrc`, ranks the Arch mirrors before
updating, so package downloads pick the fastest endpoint. It then drops old package caches
(`yay-drop-caches`) and runs `yay -Syyu`. `rate-mirrors-bin` is in setup.toml's `optional`
group, so the bootstrap installs it; on a machine set up before that, install it with
`yay -S rate-mirrors-bin`.

The alias ranks from `--entry-country=DE`. Change that in
[configuration/bash/.bashrc](../configuration/bash/.bashrc) to your own ISO country code
(e.g. `US`, `GB`).

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

## Retake the Screenshots

The images in the README are captured, not drawn. After changing the shipped theme, or
anything a screenshot shows:

```bash
python helper/capture_tour.py              # all of them, about three minutes
python helper/capture_tour.py --only dark  # one capture; --help lists them
python helper/gendocs.py                   # if the table in helper/list_tour.py changed
```

It needs no root and does not touch the running desktop: a copy of the repository is
installed into a scratch home, and the real programs run there on a virtual display, inside
a sandbox, with staged content. Look at every image before committing it. `--keep` leaves
the scratch home behind, with each program's log under `logs/`, for when one comes out
wrong.

The boot splash is included: the sandbox runs the real `plymouthd` against the virtual
display, so it is also the quickest way to see a change to the splash — no install, no
`mkinitcpio`, no reboot.

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
