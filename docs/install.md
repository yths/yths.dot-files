# Installation

> One command does all of this, including the boot splash and login screen: `./bootstrap.sh`
> from a clone, or `--skip-system` to leave those two. This page is the long form —
> what each step changes, and what to do when one of them does not apply to your machine.
> Edit [../setup.toml](../setup.toml) first if you want a different theme, font or package
> set; every command below reads it.

Installing this desktop onto a machine that already runs Arch Linux. To build that machine
first -- partitioning, encryption, boot loader -- see [os-build.md](os-build.md).

All `yay -S` commands below quote rows from [dependencies.md](dependencies.md), which maps
every Python import in the repo to the Arch package that provides it. When adding a
dependency, update both this file and that one.

## Prerequisites

Before starting, ensure you have:

- A working Arch Linux installation with network access
- A user account with `sudo` rights
- `git` and `python` available

`install.py` symlinks this repository's configuration into place for every application it
manages. A real file or directory in the way is renamed to `<name>.<timestamp>.bak` first,
so an existing setup can be recovered; a symlink it had created before is simply
re-pointed.

## Installing the AUR Helper

Log in as your user and install `yay`:

```bash
git clone https://aur.archlinux.org/yay-bin.git
cd yay-bin
makepkg -si
cd ..
rm -rf yay-bin
```

## Installing the Display Manager

Install LightDM with the `web-greeter` (provided by `nody-greeter`):

```bash
yay -S lightdm nody-greeter xinit-xsession
```

Point LightDM at the greeter by setting the following in `/etc/lightdm/lightdm.conf`:

```ini
greeter-session=nody-greeter
```

Enable the service:

```bash
systemctl enable --now lightdm.service
```

## Installing the Graphical Boot

Install Plymouth:

```bash
yay -S plymouth
```

Add the `plymouth` hook to `/etc/mkinitcpio.conf` between `systemd` and `sd-encrypt`:

```bash
HOOKS=(... systemd ... plymouth sd-encrypt ...)
```

Regenerate the initramfs and append `splash` to the kernel parameters in `/boot/loader/entries/arch.conf`:

```bash
mkinitcpio -P
```

## Installing the Desktop Environment

Install the window manager and its runtime dependencies:

```bash
yay -S xorg-server xorg-xinit qtile ttc-iosevka python-dbus-fast python-numpy python-screeninfo
```

### Backend Service

Install the Redis-compatible store used by the qtile widgets:

```bash
yay -S valkey python-redis
sudo systemctl enable --now valkey
```

Override the defaults via environment variables if needed (make sure they are exported before LightDM starts the session):

```bash
BACKEND_REDIS_HOST=localhost
BACKEND_REDIS_PORT=6379
BACKEND_REDIS_DB=1
```

Clone and install the backend service:

```bash
cd ~/repositories
git clone https://github.com/yths/yths.backend-service.git
cd yths.backend-service
mkdir -p ~/.local/share/systemd/user
cp backend.service ~/.local/share/systemd/user/
systemctl --user enable --now backend
```

Full setup details are in the backend repo's [docs/install.md](https://github.com/yths/yths.backend-service/blob/main/docs/install.md).

## Installing the Dot Files

Clone this repository and run the installer:

```bash
cd ~/repositories
git clone https://github.com/yths/yths.dot-files.git
cd yths.dot-files
python install.py
```

The theme comes from `[desktop] theme` in [../setup.toml](../setup.toml); `--theme <name>` overrides it, and clearing it in setup.toml restores an interactive prompt. Bundles are discovered under `assets/`, one directory per preset, named for the preset. The selected one's `config.json` is assembled into `~/.config/config.json`, which qtile and every helper read.

The installer also arms this clone's pre-commit gate, so `ruff` and `helper/gendocs.py` run on every commit — see [CONTRIBUTING.md](../CONTRIBUTING.md). It is reported, never prompted, and a failure to arm it does not stop the install.

The `DOTFILES_REPOSITORY_PATH` environment variable overrides the default repository location (`~/repositories/yths.dot-files`); the installer and the helpers under `helper/` honour it. Hook arming deliberately ignores it, so redirecting where configuration is read from cannot arm a different clone.

## Calibrating the Display

Optional, but recommended before generating themes that rely on perceptually accurate color.

Install `displaycal`:

```bash
yay -S displaycal
```

Disable any "intelligent" or automatic color/brightness adjustment on the monitor. For laptop screens, set the backlight brightness to a value that measures around 120 cd/m² with the calibration device:

```bash
echo <value> | sudo tee /sys/class/backlight/intel_backlight/brightness
cat /sys/class/backlight/intel_backlight/max_brightness
```

Run `displaycal` and calibrate against the `sRGB` profile targeting 120 cd/m². Then import
the generated profile, naming the display it belongs to:

```bash
python helper/apply_icc.py --import-profile ~/.local/share/icc/<profile>.icc --display HDMI-1
```

That copies it into `configuration/hardware/icc/` under a canonical name and records the
mapping for this machine in `configuration/hardware/icc/displays.json`. Commit both: the
profile keeps a stable filename, so recalibrating the same panel later overwrites it and git
carries the history rather than the directory accumulating `_v2`, `_v3` files.

`--display` takes the xrandr output name (`HDMI-1`, `eDP-1`) — `python helper/apply_icc.py
--list` shows what is connected and which profile each display resolves to. A display index
works too, if the output name is not stable on that machine.

Re-run `python install.py` to link the new profile into `~/.config/icc/`. From then on
`~/.xinitrc` applies it at every session start.

### Running uncalibrated

Calibration is optional and every failure path is non-fatal — no `displaycal` installed, no
profile recorded for this machine, a missing file, or no display to query all leave the
session running with the display untouched. To switch it off deliberately:

```bash
touch ~/.config/icc/disabled
```
