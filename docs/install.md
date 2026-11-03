# Installation

> One command does all of this, including the boot splash and login screen: `./bootstrap.sh`
> from a clone, or `--skip-system` to leave those two. This page is the long form —
> what each step changes, and what to do when one of them does not apply to your machine.
> Edit [../setup.toml](../setup.toml) first if you want a different theme, fallback font or
> package set; the package command below and the installer both read it.

Installing this desktop onto a machine that already runs Arch Linux. To build that machine
first -- partitioning, encryption, boot loader -- see [os-build.md](os-build.md).

The steps run in the order `./bootstrap.sh` runs them: packages first, then the dot files,
and the two things that change how the machine boots and logs in -- the login screen and the
boot splash -- last, by `install.py --system`. Nothing starts the display manager before
that: everything up to it is undone by re-running, while a display manager started against a
half-installed desktop takes over the console you are working from and has nothing to show.

[dependencies.md](dependencies.md) maps every Python import in the repo to the Arch package
that provides it, and says what the non-Python packages are for. When adding a dependency,
update [../setup.toml](../setup.toml) and that file.

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

## Cloning the Repository

The installer and the themes are read from the clone, wherever it is:

```bash
mkdir -p ~/repositories
cd ~/repositories
git clone https://github.com/yths/yths.dot-files.git
cd yths.dot-files
```

Now is the time to edit [../setup.toml](../setup.toml): the theme, the fallback font and the
package groups below are all read from it.

## Installing the Packages

The packages are listed once, in `[packages]` of [../setup.toml](../setup.toml), grouped by
what stops working without them. This installs the same groups `./bootstrap.sh` does, with
the fallback font ahead of them:

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
```

Drop a group from the list to leave it out -- `boot` if this machine should not get the
login screen and boot splash, `optional` for the browser, media player and shell tools.

| Group | What it is |
|---|---|
| `core` | X, qtile, the terminal, launcher, notifications, compositor, screen lock, polkit agent and keyring. Without these there is nothing to log into. |
| `boot` | LightDM and Plymouth. Configured in the next two sections, installed by `install.py --system`. The greeter LightDM runs is built separately, below. |
| `backend` | Valkey and the client the bar reads it through. |
| `python` | What the helper scripts import. `helper/list_dependencies.py` checks this group against the code. |
| `optional` | Everything that works without a specific thing missing. |

## Installing the Theme's Font

The font is the theme's: each bundle's `config.json` names the family the whole desktop
derives from, and every other size is computed from its size. Which Arch package provides
that family is recorded in `FONT_PACKAGES` in [../helper/fonts.py](../helper/fonts.py), and a
bundle naming a plain family that has a Nerd Font build -- `Atkinson Hyperlegible Mono` for
`AtkynsonMono NF` -- gets the Nerd Font build, since that is the one with the glyphs the bar
draws. This prints the package for the theme `setup.toml` selects, and installs it:

```bash
yay -S --needed $(python helper/fonts.py --package)
```

It prints nothing when `setup.toml` leaves the theme to the prompt, or when the family is
one the table has no package for -- extend the table, or install the font by hand. Either
way, and if this install fails, the desktop still renders: the fallback font went in with
the packages above, and `install.py` writes it into the configuration whenever fontconfig
cannot see the theme's family. The fallback is `[desktop] fallback_font_family` in
[../setup.toml](../setup.toml) -- `Iosevka NF`, from `ttf-iosevka-nerd` -- and has to stay
a Nerd Font, because the bar draws its glyphs from the private use area. Install the
theme's font later and `python install.py --migrate` switches to it.

## Building the Greeter

`nody-greeter` is the web-greeter runtime LightDM renders the login screen with. The AUR
package no longer builds, so this repository carries it with a patch applied, under
[../configuration/web-greeter/nody-greeter/](../configuration/web-greeter/nody-greeter/).
Build it from a scratch copy, so `makepkg` leaves nothing in the clone; `-s` fetches the make
dependencies (Node, npm) and `lightdm` is already in place from the `boot` group:

```bash
build_directory="$(mktemp -d)"
cp -R configuration/web-greeter/nody-greeter/. "$build_directory"
(cd "$build_directory" && makepkg -si)
rm -rf "$build_directory"
```

The build is a few minutes of npm. `./bootstrap.sh` skips it when `nody-greeter` is already
installed.

## Configuring the Display Manager

LightDM has to be told which greeter to run; nothing in this repository writes
`/etc/lightdm/lightdm.conf`. Set, under `[Seat:*]`:

```ini
greeter-session=nody-greeter
```

Enable the service, but do not start it:

```bash
sudo systemctl enable lightdm.service
```

Not `--now`. At this point there is no greeter theme installed and nothing has pointed
`/etc/lightdm/web-greeter.yml` at one -- `install.py --system` does both further down -- so a
display manager started here switches the machine to a graphical VT with a greeter that
cannot render, and leaves the console you are following this from behind it. It starts at
the reboot that ends this page, with everything in place.

## Configuring the Graphical Boot

Add the `plymouth` hook to `/etc/mkinitcpio.conf` between `systemd` and `sd-encrypt`:

```bash
HOOKS=(... systemd ... plymouth sd-encrypt ...)
```

Append `splash` to the kernel parameters in `/boot/loader/entries/arch.conf`. The initramfs
does not need regenerating by hand: `install.py --system` runs
`plymouth-set-default-theme -R` when it installs the splash, which rebuilds it with the hook
in place. Skip the rebuild and this section is inert until the next one; the desktop is
unaffected.

## Installing the Backend Service

Start the Redis-compatible store the qtile widgets read from:

```bash
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

From the clone, run the installer. `--system` is what installs the login screen and the
boot splash; without it they are left alone, which is `./bootstrap.sh --skip-system`:

```bash
cd ~/repositories/yths.dot-files
python install.py --system
```

It asks for root once, before changing anything, and installs the two system surfaces last:
the patched greeter theme into `/usr/share/web-greeter/themes/<theme>/` with
`/etc/lightdm/web-greeter.yml` pointed at it, and the rendered boot splash made the default,
initramfs rebuilt. Each can be re-run on its own later with `python install.py --migrate
--system`, or separately via `python helper/patch_web_greeter.py --install --activate` and
`python helper/patch_plymouth.py --install --rebuild`.

The theme comes from `[desktop] theme` in [../setup.toml](../setup.toml); `--theme <name>` overrides it, and clearing it in setup.toml restores an interactive prompt. Bundles are discovered under `assets/`, one directory per preset, named for the preset. The selected one's `config.json` is assembled into `~/.config/config.json`, which qtile and every helper read.

The font in that file is the bundle's, unless fontconfig cannot find the family -- then it
is the fallback from setup.toml, at the bundle's size, and the installer says so. See
[Installing the Theme's Font](#installing-the-themes-font).

The installer also arms this clone's pre-commit gate, so `ruff`, `pytest` and `helper/gendocs.py --check` run on every commit — see [CONTRIBUTING.md](../CONTRIBUTING.md). It is reported, never prompted, and a failure to arm it does not stop the install.

The installer reads configuration and themes from the clone it is run from, wherever that is. The `DOTFILES_REPOSITORY_PATH` environment variable redirects it to another clone; the installer and the helpers under `helper/` honour it. Hook arming deliberately ignores it, so redirecting where configuration is read from cannot arm a different clone.

## Starting the Desktop

Reboot. Plymouth draws the splash, LightDM starts into the greeter installed above, and the
session it launches is qtile:

```bash
reboot
```

To try the session first without the display manager, `startx` from the console runs the
same `~/.xinitrc`.

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
