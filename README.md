## Keyboard Layout
```
KEYMAP=de
```
in /etc/vconsole.conf

## Bluetooth on Startup
```
[Policy]
AutoEnable=true
```
in /etc/bluetooth/main.conf

## Autoconnect to Known Network
```
[Settings]
AutoConnect=True
```
in /var/lib/iwd/network.type (replace network.type with the correct SSID)

```
[General]
EnableNetworkConfiguration=true
```
in /etc/iwd/main.conf (might need to be created)

## Firefox Scaling
```
layout.css.devPixelsPerPx = 1.75
```
in about:config

## Xorg Warnings and Errors
- (WW) acpi problem
startx -- -noacpi

- (WW) missing font directories
create directory and create file "fonts.dir" with content "0"
