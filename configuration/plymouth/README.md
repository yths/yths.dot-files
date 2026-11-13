# Plymouth Theme

The boot-splash theme. For where Plymouth fits in the system, see
[../../docs/architecture.md](../../docs/architecture.md); for debugging the splash without
rebooting, see [../../docs/tips.md](../../docs/tips.md).

This directory holds theme *sources* only — the `.plymouth` INI, the script template, the
keymap render, and a link to the active wallpaper. Everything else the splash draws is rendered from the palette
by `helper/patch_plymouth.py` and never written back here: the eight glyph and panel images
would otherwise be rewritten on every theme switch, and they are build artefacts, not
source. They were tracked once, and the committed copies had been stale since May.

## Why This One Is Different

Every other patcher writes under `~`. Plymouth themes live in
`/usr/share/plymouth/themes/`, which is root-owned, so patching happens in two stages:

- **Render** — copy the source into a staging directory and rewrite it for the active
  palette. No privileges, nothing here touched.
- **Install** — copy the staged theme into the system path, under the active theme's name,
  and make it plymouth's default theme. Needs root. Once it is the default, splashes this
  repository installed for earlier themes are removed.

A third step matters for the result to be visible: the splash reads its theme from the
initramfs, so the files being in place is necessary but not sufficient until
`mkinitcpio` runs again.

The `default` bundle installs as `dot-files-default`, because the theme chooser interprets
the literal argument `default` as a reset command. Other bundles use their normalised names.

## Installing and Updating

`./bootstrap.sh` does this as its last step, and a theme switch with `--system` does it
too (`python install.py --migrate --theme <bundle> --system`). On its own, one command does
all three, prompting for root once:

```bash
python helper/patch_plymouth.py --install --rebuild
```

Drop `--rebuild` to copy the files without the (slow) initramfs rebuild — useful when
several changes are coming and one rebuild at the end will do. Drop `--install` as well to
render and throw the result away, which is only useful for checking that rendering works.

`--theme light` or `--theme dark` renders a specific variant. The default is dark, whatever
`state.theme` says: the splash shows before anyone logs in, so there is no session whose
preference could apply.

## Always Dark, and Not on a Theme Switch

The splash is rendered from the dark palette whatever the desktop's current theme, and it is
not in `patch_all`'s registry — a day/night switch does not touch it.

Both follow from when it is drawn. The splash appears before anyone logs in, so there is no
user whose light-or-dark preference could apply; `state.theme` describes a session that does
not exist yet. It also matches `background-tile.png`, which links to the dark wallpaper, and
a screen coming up in a dark room.

Leaving it out of the pipeline follows from what updating it costs: root, and an
`mkinitcpio` run. Doing that twice a day would prompt for a password and rebuild the
initramfs to change something nobody is looking at.

So this is a system decision, made once. Re-run the command above when the palette itself
changes.

## Resolution-independent Layout

The script plugin gives the throbber and subtitle a shared left edge, five percent of each
display's width from its edge. The title starts 16 pixels after the cropped throbber image,
not at a separate percentage of the screen width. Longer text scales down to fit the display.
The same layout runs independently on each output and is recalculated when outputs change.

The former `two-step` plugin positioned the throbber by its centre and each text label by
its own width. Percentage adjustments only lined them up at particular resolutions.
`theme.script.in` now defines the layout; rendering adds the active fonts, colours, glyphs,
and per-mode messages to produce `theme.script`. Password and question prompts remain
interactive, with masked password input and keyboard-layout/caps-lock indicators.
Password masks repeat the theme's pre-rendered `bullet.png`, vertically centered against
the lock icon, so the configured glyph does
not depend on font availability in the initramfs. The keyboard layout is shown only when
Plymouth supplies a non-empty name; it updates if that information becomes available later.

## Silent Boot

To suppress messages during boot, add the following parameters to the boot options in
`/boot/loader/entries/arch.conf`:

- `quiet` — suppresses messages in general
- `loglevel=0` — suppresses messages by `dmesg` that are less critical; 0 is the least verbose, 7 is the most verbose
- `systemd.show_status=auto` — suppresses messages by `systemd`
- `rd.udev.log_level=0` — suppresses messages by `systemd` if it is used in `initramfs`
- `vt.global_cursor_default=0` — prevents cursor from blinking
