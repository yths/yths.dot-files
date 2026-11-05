# Installation

Installing this desktop onto a machine that already runs Arch Linux and boots to a console.
To build that machine first -- partitioning, encryption, boot loader -- see
[os-build.md](os-build.md); it ends where this begins, with `git` installed.

## Install

Three lines at the console, then a reboot. Nothing else is typed:

```bash
git clone https://github.com/yths/yths.dot-files.git ~/repositories/yths.dot-files
cd ~/repositories/yths.dot-files
./bootstrap.sh
```

It asks for the `sudo` password, and once whether to collect credentials (`y`/`n`; `n` is
fine, see [Credentials](#credentials)). When it prints `Done`:

```bash
reboot
```

The machine comes back to the login screen, and the session behind it is qtile. Everything
further down this page is done from that desktop, in a terminal, and none of it is needed to
get there.

To change the theme, the fallback font or the package list, edit
[../setup.toml](../setup.toml) between the `cd` and the `./bootstrap.sh`; it is the one file
the whole install reads. `./bootstrap.sh --dry-run` prints what would happen and stops;
`--skip-system` leaves the login screen and boot splash alone; `--dev` adds the test runner
and test tools. Ruff, NordVPN and Visual Studio Code are installed by default. It is safe to re-run.

### What it does

In order, so a failure is easy to place:

1. Installs `yay`, then every package in `[packages]` of `setup.toml` plus the fallback font.
   If X11 has no configured keyboard layout, derives it from the OS console keymap with
   `localectl`. An explicitly configured X11 layout is left unchanged.
2. Checks that `python` can import what step 1 installed, and stops if not, naming the
   import and its package. A virtualenv or `pyenv` shim on `PATH` is the usual reason;
   `deactivate`, or make sure `python` is `/usr/bin/python`, and re-run.
3. Installs the theme's own font, if `helper/fonts.py` knows the package for it -- see
   [Fonts](#fonts). Failing here is reported and not fatal.
4. Builds the packages under [../packages/](../packages/README.md), whose AUR builds are
   broken: `nody-greeter` (the login screen's greeter; minutes of npm) and
   `python-colour-science` (with its hidden `openimageio` dependency). Each is skipped when
   already installed.
5. Enables the PipeWire and PulseAudio-compatible sockets and WirePlumber user service,
   then checks the audio server with `pactl info`. Enables `valkey`, clones
   [yths.backend-service](https://github.com/yths/yths.backend-service)
   beside this repository and enables it as a user service. Installs its pacman hook and
   helper scripts so the update count refreshes after transactions from `pacman` or `yay`.
   Re-running bootstrap refreshes these root-owned copies. Backend setup failures are not fatal;
   without the hook, the backend refreshes the count hourly.
6. Runs `python install.py --system`: symlinks the configuration into `~/.config`, writes
   `~/.config/config.json` from the theme bundle, patches every application, then -- as root,
   asked for once -- installs the login screen, points LightDM at `nody-greeter`, enables
   `lightdm.service` *without starting it* (started from the console it would take the console
   over), and installs the boot splash.

The one thing it does not do is make the boot splash draw: that needs two edits to files that
decide whether the machine boots, and it says so at the end. See [Boot Splash](#boot-splash).

## After the First Login

Optional, and in no particular order.

### Keyboard Layout

The console and X11 have separate keyboard settings. A `KEYMAP=de` in `/etc/vconsole.conf`
configures the console; it does not by itself configure the graphical login screen or desktop.
Bootstrap uses `localectl set-keymap` to convert the OS console keymap into X11 settings when
the X11 layout is unset. `XKBLAYOUT` and `XKBVARIANT` entries in `/etc/vconsole.conf` are not a
substitute for the system X11 configuration.

On an existing machine whose console uses German but whose desktop still uses US, run:

```bash
sudo localectl set-keymap de
```

Log out and back in afterward. `localectl status` reports the saved settings; `setxkbmap -query`
reports the active X session's layout. For a deliberately different X11 layout, set it with
`localectl --no-convert set-x11-keymap` before running bootstrap.

### Boot Splash

Bootstrap installs and selects the configured Plymouth theme, and rebuilds the initramfs.
The `default` bundle installs as `dot-files-default`: Plymouth treats the literal name
`default` as a command to reset to the distribution's theme, not as a selectable theme name.
It deliberately does not edit the boot-critical initramfs hooks or kernel command line, so
the splash remains invisible until both are configured. Add `plymouth` to `HOOKS` in
`/etc/mkinitcpio.conf`, after `systemd` and before `sd-encrypt`:

```bash
HOOKS=(... systemd ... plymouth sd-encrypt ...)
```

Append `splash` to the `options` line of the active systemd-boot entry, normally
`/boot/loader/entries/arch.conf`. Then install/select the theme and rebuild the initramfs:

```bash
python helper/patch_plymouth.py --install --rebuild
```

The installer warns if the hook is missing. Bootstrap also verifies that the configured theme
is selected and retries the theme install if needed. Reboot for the changes to take effect.

### Credentials

`install.py` offers to collect the secrets listed under `[credentials]` in `setup.toml` into
`~/.config/credentials.json` (mode 0600). Today that is one token: `IPINFO_TOKEN`, from
[ipinfo.io](https://ipinfo.io/), which buys the location widget its sunrise and sunset and
with them the automatic light/dark switch. Declined at install, it is collected later with:

```bash
python install.py --credentials
```

That writes the file and touches nothing else; a plain `python install.py` would also reset
the machine's `state`.

### Fonts

The font is the theme's: each bundle's `config.json` names the family the whole desktop
derives from, and every other size is computed from its size. Which Arch package provides
that family is recorded in `FONT_PACKAGES` in [../helper/fonts.py](../helper/fonts.py), and a
bundle naming a plain family that has a Nerd Font build -- `Atkinson Hyperlegible Mono` for
`AtkynsonMono NF` -- gets the Nerd Font build, since that is the one with the glyphs the bar
draws.

If the theme's font did not install, or the table has no package for it, the desktop is
running in the fallback -- `[desktop] fallback_font_family` in `setup.toml`, `Iosevka NF`
from `ttf-iosevka-nerd`, always installed -- and `install.py` said so. Install the font
(extending the table if it is new) and switch:

```bash
yay -S --needed $(python helper/fonts.py --package)
python install.py --migrate
```

The fallback has to stay a Nerd Font, because the bar draws its glyphs from the private use
area.

### Backend Service

The bootstrap clones and enables it. To relocate it, change its Valkey, or if that step
failed, the backend repository's
[docs/install.md](https://github.com/yths/yths.backend-service/blob/main/docs/install.md) has
the details. The defaults are overridden by environment variables, which have to be exported
before LightDM starts the session:

```bash
BACKEND_REDIS_HOST=localhost
BACKEND_REDIS_PORT=6379
BACKEND_REDIS_DB=1
```

## Without the Bootstrap

What the script does, as commands, for a machine where one step does not apply or has to be
done differently. Skip to the step that needs it; the order is the script's.

`install.py` symlinks this repository's configuration into place for every application it
manages. A real file or directory in the way is renamed to `<name>.<timestamp>.bak` first,
so an existing setup can be recovered; a symlink it had created before is simply re-pointed.
The installer reads configuration and themes from the clone it is run from, wherever that is;
`DOTFILES_REPOSITORY_PATH` redirects it to another clone.

**The AUR helper.**

```bash
git clone https://aur.archlinux.org/yay-bin.git
cd yay-bin && makepkg -si && cd .. && rm -rf yay-bin
```

**The packages**, from the `[packages]` groups of `setup.toml` with the fallback font ahead
of them. Drop a group to leave it out -- `boot` for no login screen or splash, `optional` for
the browser, media player and shell tools:

```bash
yay -S --needed $(python - setup.toml core boot backend python optional <<'PYEOF'
import sys, tomllib
with open(sys.argv[1], "rb") as handle:
    setup = tomllib.load(handle)
names = [setup["desktop"]["fallback_font_package"]]
names += [name for group in sys.argv[2:] for name in setup["packages"].get(group, [])]
print(" ".join(dict.fromkeys(names)))
PYEOF
)
yay -S --needed $(python helper/fonts.py --package)
```

[dependencies.md](dependencies.md) says what the less obvious packages are for.

**The repository's own packages** -- `nody-greeter` and `python-colour-science`, whose AUR
builds are broken -- from [../packages/](../packages/README.md), each in a scratch directory
so `makepkg` leaves nothing in the clone. `lightdm` has to be installed first (the `boot`
group):

```bash
for package in packages/*/; do
    build_directory="$(mktemp -d)"
    cp -R "$package." "$build_directory"
    (cd "$build_directory" && makepkg -si)
    rm -rf "$build_directory"
done
```

**The services.**

```bash
sudo systemctl enable --now valkey.service
git clone https://github.com/yths/yths.backend-service.git ~/repositories/yths.backend-service
mkdir -p ~/.local/share/systemd/user
cp ~/repositories/yths.backend-service/backend.service ~/.local/share/systemd/user/
systemctl --user enable --now backend.service
```

**The dot files**, with the login screen and boot splash. Without `--system` they are left
alone, which is what `./bootstrap.sh --skip-system` does:

```bash
python install.py --system
```

The theme is `[desktop] theme` in `setup.toml`; `--theme <name>` overrides it, and an empty
value there restores an interactive prompt. Bundles are discovered under `assets/`, one
directory per preset. The installer also arms this clone's pre-commit gate (`ruff`, `pytest`,
`helper/gendocs.py --check`), reported and never prompted; see
[CONTRIBUTING.md](../CONTRIBUTING.md).

The login screen installer writes `/etc/lightdm/lightdm.conf.d/50-nody-greeter.conf` and runs
`systemctl enable lightdm.service` -- enable, not `--now`. By hand, those two are the same;
do not start the display manager from the console you are installing from. Both system
surfaces can be installed separately: `python helper/patch_web_greeter.py --install
--activate` and `python helper/patch_plymouth.py --install --rebuild`.

Then `reboot`, or `startx` to try the session without the display manager first.

## Updating

Pull, then migrate. A migration refreshes `~/.config/config.json` against the repository
and re-runs every patcher, but keeps this machine's `state`, monitors and wallpapers, and
symlinks nothing new. Without `--theme` it stays on the installed bundle:

```bash
git pull
python install.py --migrate
```

Re-running a plain `python install.py` instead resets `state` — a pinned theme goes back to
automatic switching — so keep that for a new machine.

## Switching Themes

The same migration, naming a different bundle with `--theme <bundle>`, and `--system` to
switch the root-owned login screen and boot splash with it:

```bash
python install.py --migrate --theme <bundle> --system
```

[tips.md](tips.md#switch-the-active-theme) has the details.

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
