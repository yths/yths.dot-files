# Hardware-Specific Files

Everything here describes the author's particular monitors. Nothing in this directory
applies to another machine, and none of it is required — the desktop installs and runs
without it. It lives in one place so it is distinguishable from the per-application
configuration beside it, which *is* meant to be portable.

## `icc/`

Display calibration profiles, one per panel, generated with `displaycal`. `install.py`
symlinks this directory to `~/.config/icc/`, and `~/.xinitrc` runs
[`helper/apply_icc.py`](../../helper/apply_icc.py) at session start to load them.

Files are named `<panel>.icc` — lowercase, hyphen-separated, no version suffix. The name is
stable so that recalibrating a panel overwrites the same path and git carries the history;
a directory of `_v2`/`_v3` files cannot say which is current, which is what it used to be.

`displays.json` maps hostname to `{display: profile}`. A key is an xrandr output name
(preferred, survives a reordering) or a dispwin display index. Nothing here is required:
a machine with no entry runs uncalibrated.

```bash
python helper/apply_icc.py --list          # what is connected, and what would apply
python helper/apply_icc.py                 # apply now (also run from ~/.xinitrc)
python helper/apply_icc.py --import-profile <file>.icc --display HDMI-1
touch ~/.config/icc/disabled               # run uncalibrated
```

Replace these with your own profiles, or ignore them: an uncalibrated display changes
nothing except how faithfully the palettes render.

## `edid/`

A corrected EDID dump for a monitor that reports its physical dimensions wrongly, which
throws off the DPI every scaling factor in this repository is derived from. The procedure
for producing and loading one is in [../xorg/README.md](../xorg/README.md).
