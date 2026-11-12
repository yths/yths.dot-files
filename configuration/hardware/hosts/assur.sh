# assur: monitor layout and keyboard, sourced by ~/.xinitrc on this host only.

xrandr --output HDMI-0 --left-of HDMI-1 --mode 1920x1080 --filter bilinear --scale-from 3840x2160 --pos 0x0
xrandr --output HDMI-1 --primary --pos 3840x0 --mode 3840x2160
setxkbmap -layout us -variant altgr-intl -option nodeadkeys
