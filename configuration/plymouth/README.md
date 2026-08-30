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

One command does all three, prompting for root once:

```bash
python helper/patch_plymouth.py --install --rebuild
```

Drop `--rebuild` to copy the files without the (slow) initramfs rebuild — useful when
several changes are coming and one rebuild at the end will do. Drop `--install` as well to
render and throw the result away, which is only useful for checking that rendering works.

`--theme light` or `--theme dark` renders a specific variant; the default follows
`state.theme` in `~/.config/config.json`.

## In the Automatic Pipeline

`patch_plymouth` is in `patch_all`'s registry, so a theme switch re-renders the splash. It
**never prompts**: a password dialog at dawn and dusk would be worse than a boot splash that
lags a theme behind. It installs only where root costs nothing — already root, or a live
`sudo` timestamp — and otherwise logs the command above and moves on.

So on a normal machine the automatic run keeps the render honest and the boot splash
updates the next time you run the install command yourself.

## Silent Boot

To suppress messages during boot, add the following parameters to the boot options in
`/boot/loader/entries/arch.conf`:

- `quiet` — suppresses messages in general
- `loglevel=0` — suppresses messages by `dmesg` that are less critical; 0 is the least verbose, 7 is the most verbose
- `systemd.show_status=auto` — suppresses messages by `systemd`
- `rd.udev.log_level=0` — suppresses messages by `systemd` if it is used in `initramfs`
- `vt.global_cursor_default=0` — prevents cursor from blinking
