# X Session Startup

The two files that start and configure the X session: `.xinitrc`, which runs when X starts,
and `.Xresources`, which holds the display DPI. `install.py` symlinks both into the home
directory.

## `.xinitrc`

Runs at session start, in this order: merge X resources and keymaps, run whatever
`/etc/X11/xinit/xinitrc.d/` provides, apply this machine's monitor layout and keyboard
layout, load display colour profiles, set the blanking timeouts, and finally `qtile start`.

Per-machine blocks are keyed on `$HOSTNAME`, because monitor arrangement and keyboard layout
are the two things that genuinely differ between the machines this repository is installed
on. Add a block for a new host; the rest of the file is shared.

Colour profiles are loaded by `helper/apply_icc.py`, which exits 0 in every failure case, so
an uncalibrated or misconfigured display can never stop a session from starting.

## `.Xresources`

One line, `Xft.dpi`, and it is generated rather than edited: `helper/patch_xorg.py` writes
the average DPI across the detected monitors on every theme switch. Editing it by hand lasts
until the next one.

## Correcting a Monitor That Lies About Its Size

Some monitors report wrong physical dimensions in their EDID, which throws off the DPI above
and every scaling factor derived from it. The fix is a corrected EDID blob, and it lives with
the other machine-specific files: see
[../hardware/README.md](../hardware/README.md).
