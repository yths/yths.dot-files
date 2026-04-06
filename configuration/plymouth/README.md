# Plymouth Theme

## Installation

Copy to Plymouth theme folder and rebuild the boot image. Shows a preview after installation for a few seconds.

```bash
cp -RL yths /usr/share/plymouth/themes/yths
plymouth-set-default-theme yths -R
plymouthd --debug-file=/home/yths/plymouth-test.log; plymouth --show-splash --debug; sleep 15; plymouth --quit
```

## Configuration 

Run the patch script in `helper` to generate the necessary asset and apply the colors for the current color theme.
```bash
python helper/patch_plymouth.py configuration/plymouth/themes/yths
```

## Silent Boot

To supress any messages during boot, add the following parameters to the boot options in `/boot/loader/entries/arch.conf`:
* `quiet` - supresses messages in general
* `loglevel=0` - supresses messages by `dmesg` that are less critical; 0 is the least verbose, 7 is the most verbose
* `systemd.show_status=auto` - supress messages by `systemd`
* `rd.udev.log_level=0` - supress messages by `systemd` if it is used in `initramfs`
* `vt.global_cursor_default=0` - prevents cursor from blinking