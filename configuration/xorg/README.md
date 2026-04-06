# Patching EDID Files

## Rational

Sometimes monitors are shipped with erroneous EDID information. For example, in my case, the horizontal dimension of my screen was wrong, leading to false calculation of the DPI.

### Retrieving the EDID File

Copy the current EDID file via the following command, adjust the path according to your specific hardware setup
```bash
sudo cp /sys/class//drm/card1-HDMI-A-2/edid ~/edid_HDMI-A-2.bin
```

### Modifying the EDID File

Install `wxedid` and open the retrieved EDID file; adjust the erroneous parameters and save the file.
```bash
yay -S wxedid
wxedid ~/edid_HDMI-A-2.bin
```

### Installing the EDID File

Copy the EDID file to `/etc/X11/`. To find out the correct monitor identifier, run:
```bash
cat /var/log/Xorg.0.log | grep DFP-
```
and look for the `connected` montiors, let's assume it is `DFP-3`.
Then add the following options to `/etc/X11/xorg.conf` in the `Device` section.
```bash
Section "Device"
# ...
    Option "CustomEDID" "DFP-3:/etc/X11/edid_HDMI-A-2.bin" 
    Option "IgnoreEDID" "false"
    Option "UseEDID" "true"
EndSection
```
