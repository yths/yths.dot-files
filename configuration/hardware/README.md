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

The `_v2`/`_v3` suffixes are recalibrations of the same panel over time, not variants — a
display drifts, so it gets measured again. Dates come from each file's own ICC header:

| Panel | Current | Superseded |
|---|---|---|
| S27B550 | `S27B550_v3.icc` (2025-08-22) | `S27B550_v2.icc` (2025-06-08), `S27B550.icc` (2024-12-19) |
| U28D590 | `U28D590_v3.icc` (2025-08-22) | `U28D590_v2.icc` (2025-06-08), `U28D590.icc` (2024-12-19) |
| HP | `HP.icc` (2024-12-20) | — |
| Lenovo | `lenovo.icc` (2025-08-22) | — |

The superseded profiles are kept only because nothing recorded which was current. Now that
something does, they can be deleted — an out-of-date profile describes the display less
accurately than no profile at all.

## `edid/`

A corrected EDID dump for a monitor that reports its physical dimensions wrongly, which
throws off the DPI every scaling factor in this repository is derived from. The procedure
for producing and loading one is in [../xorg/README.md](../xorg/README.md).
