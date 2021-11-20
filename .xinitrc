#!/bin/sh
setxkbmap de

xrandr --setprovideroffloadsink NVIDIA-0 modesetting
# xrandr --output eDP-1-1 --primary --mode 3840x2160 --pos 0x0 --rotate normal --output DP-1-1 --off --output HDMI-1-1 --off --output DP-1-2 --mode 3840x2160 --pos 3840x0 --rotate normal

#xrandr --auto
xrandr \
 --dpi 288 \
 --output eDP1 --mode 3840x2160 --rate 60 --pos 0x0  \
 --output DP1 --mode 3840x2160 --rate 60 --pos 3840x0 --primary \
 --output HDMI1 --off \
 --output DP2 --off

userresources=$HOME/.Xresources
usermodmap=$HOME/.Xmodmap
sysresources=/etc/X11/xinit/.Xresources
sysmodmap=/etc/X11/xinit/.Xmodmap

# merge in defaults and keymaps

if [ -f $sysresources ]; then
    xrdb -merge $sysresources
fi

if [ -f $sysmodmap ]; then
    xmodmap $sysmodmap
fi

if [ -f "$userresources" ]; then
    xrdb -merge "$userresources"
fi

if [ -f "$usermodmap" ]; then
    xmodmap "$usermodmap"
fi

# start some nice programs

if [ -d /etc/X11/xinit/xinitrc.d ] ; then
 for f in /etc/X11/xinit/xinitrc.d/?*.sh ; do
  [ -x "$f" ] && . "$f"
 done
 unset f
fi

# exec twm &
exec qtile start -c ~/.config/qtile/yths.qtile/config.py

# exec qtile start

# export XDG_SESSION_TYPE=x11
# export GDK_BACKEND=x11
# exec gnome-session
