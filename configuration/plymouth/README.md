# Plymouth Theme

The boot-splash theme installed by `plymouth-set-default-theme`. For where Plymouth fits in the system, see [../../docs/architecture.md](../../docs/architecture.md); for debugging the splash without rebooting, see [../../docs/tips.md](../../docs/tips.md).

## Installation

Copy the theme directory into the system Plymouth theme folder and rebuild the boot image:

```bash
cp -RL yths /usr/share/plymouth/themes/yths
plymouth-set-default-theme yths -R
```

## Patching

Run the patch script to render palette values from `~/.config/config.json` into the theme's assets:

```bash
python helper/patch_plymouth.py configuration/plymouth/themes/yths
```

This is also invoked by `helper/patch_configurations.py:patch_all` (see [../../helper/README.md](../../helper/README.md)).

## Silent Boot

To suppress messages during boot, add the following parameters to the boot options in `/boot/loader/entries/arch.conf`:

- `quiet` — suppresses messages in general
- `loglevel=0` — suppresses messages by `dmesg` that are less critical; 0 is the least verbose, 7 is the most verbose
- `systemd.show_status=auto` — suppresses messages by `systemd`
- `rd.udev.log_level=0` — suppresses messages by `systemd` if it is used in `initramfs`
- `vt.global_cursor_default=0` — prevents cursor from blinking
