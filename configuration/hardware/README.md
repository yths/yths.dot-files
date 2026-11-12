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
throws off the DPI every scaling factor in this repository is derived from. One panel here
reported the wrong horizontal size.

Producing one, for a monitor that needs it:

```bash
# 1. Copy the monitor's own EDID; adjust the card and connector to match.
sudo cp /sys/class/drm/card1-HDMI-A-2/edid ~/edid_HDMI-A-2.bin

# 2. Correct the wrong field and save.
yay -S wxedid
wxedid ~/edid_HDMI-A-2.bin
```

Loading it means telling X to prefer the file over what the monitor reports. Find the
identifier of the connected output:

```bash
grep DFP- /var/log/Xorg.0.log        # look for the one marked connected
```

then copy the blob to `/etc/X11/` and add its identifier to the `Device` section of
`/etc/X11/xorg.conf`:

```
Section "Device"
    Option "CustomEDID" "DFP-3:/etc/X11/edid_HDMI-A-2.bin"
    Option "IgnoreEDID" "false"
    Option "UseEDID"    "true"
EndSection
```
