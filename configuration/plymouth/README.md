# Plymouth Theme

The boot-splash theme. For where Plymouth fits in the system, see
[../../docs/architecture.md](../../docs/architecture.md); for debugging the splash without
rebooting, see [../../docs/tips.md](../../docs/tips.md).

This directory holds theme *sources* only — the `.plymouth` INI, the keymap render, and a
link to the active wallpaper. Everything else the splash draws is rendered from the palette
by `helper/patch_plymouth.py` and never written back here: the eight glyph and panel images
would otherwise be rewritten on every theme switch, and they are build artefacts, not
source. They were tracked once, and the committed copies had been stale since May.

## Why This One Is Different

Every other patcher writes under `~`. Plymouth themes live in
`/usr/share/plymouth/themes/`, which is root-owned, so patching happens in two stages:

- **Render** — copy the source into a staging directory and rewrite it for the active
  palette. No privileges, nothing here touched.
- **Install** — copy the staged theme into the system path. Needs root.

A third step matters for the result to be visible: the splash reads its theme from the
initramfs, so the files being in place is necessary but not sufficient until
`mkinitcpio` runs again.

## Installing and Updating

`./bootstrap.sh` does this as its last step. By hand, one command does all three, prompting
for root once:

```bash
python helper/patch_plymouth.py --install --rebuild
```

Drop `--rebuild` to copy the files without the (slow) initramfs rebuild — useful when
several changes are coming and one rebuild at the end will do. Drop `--install` as well to
render and throw the result away, which is only useful for checking that rendering works.

`--theme light` or `--theme dark` renders a specific variant; the default follows
`state.theme` in `~/.config/config.json`.

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

## Silent Boot

To suppress messages during boot, add the following parameters to the boot options in
`/boot/loader/entries/arch.conf`:

- `quiet` — suppresses messages in general
- `loglevel=0` — suppresses messages by `dmesg` that are less critical; 0 is the least verbose, 7 is the most verbose
- `systemd.show_status=auto` — suppresses messages by `systemd`
- `rd.udev.log_level=0` — suppresses messages by `systemd` if it is used in `initramfs`
- `vt.global_cursor_default=0` — prevents cursor from blinking
