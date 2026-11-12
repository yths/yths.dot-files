# Installation

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

The installer prompts for a theme — choose between the bundled presets (e.g. `yths`, `nuunamnir`) discovered under `assets/`. The selected theme's `config.json` is written to `~/.config/config.json`, where qtile and the helper scripts read it from.

The `DOTFILES_REPOSITORY_PATH` environment variable overrides the default repository location (`~/repositories/yths.dot-files`); the installer and the helpers under `helper/` honour it.

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

Run `displaycal` and calibrate against the `sRGB` profile targeting 120 cd/m². Copy the generated ICC profile into the system profile directory and activate it:

```bash
sudo cp ~/.local/share/icc/<profile>.icc ~/.config/icc/
dispwin -d 1 -i ~/.config/icc/<profile>.icc
```

Add the `dispwin` invocation to `~/.xinitrc` so the profile is reapplied on every X session.
