#!/bin/sh

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

if [ "$HOSTNAME" = "assur" ]; then
    xrandr --output HDMI-1 --mode 1920x1080 --filter bilinear --scale-from 3840x2160
    dispwin -d 1 -i ~/.config/icc_profiles/SamsungHD.icc 
    dispwin -d 2 -i ~/.config/icc_profiles/SamsungV2.icc 
fi

if [ "$HOSTNAME" = "nippur" ]; then
    dispwin -d 1 -i ~/.config/icc_profiles/HP.icc
fi

setxkbmap -layout us -variant intl
theme=minimal
qtile start
