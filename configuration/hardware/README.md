# Hardware-Specific Files

Everything here describes the author's particular monitors. Nothing in this directory
applies to another machine, and none of it is required — the desktop installs and runs
without it. It lives in one place so it is distinguishable from the per-application
configuration beside it, which *is* meant to be portable.

## `icc/`

Display calibration profiles, one per panel, generated with `displaycal`. `install.py`
symlinks this directory to `~/.config/icc/`, from where `dispwin` loads the active profile —
see the display calibration section of [../../docs/install.md](../../docs/install.md).

Replace these with your own profiles, or ignore them: an uncalibrated display changes
nothing except how faithfully the palettes render.

## `edid/`

A corrected EDID dump for a monitor that reports its physical dimensions wrongly, which
throws off the DPI every scaling factor in this repository is derived from. The procedure
for producing and loading one is in [../xorg/README.md](../xorg/README.md).
