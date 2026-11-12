# nippur: monitor layout and keyboard, sourced by ~/.xinitrc on this host only.

xrandr --output eDP-1 --primary
xrandr --output DP-1-6 --right-of eDP-1 --mode 1920x1080
xrandr --output DP-1-5 --right-of DP-1-5 --mode 1920x1080
setxkbmap -layout de
