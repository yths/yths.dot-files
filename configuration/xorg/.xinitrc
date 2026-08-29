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
    xrandr --output HDMI-0 --left-of HDMI-1 --mode 1920x1080 --filter bilinear --scale-from 3840x2160 --pos 0x0
    xrandr --output HDMI-1 --primary --pos 3840x0 --mode 3840x2160
    setxkbmap -layout us -variant altgr-intl -option nodeadkeys
fi

if [ "$HOSTNAME" = "nippur" ]; then
    xrandr --output eDP-1 --primary
    xrandr --output DP-1-6 --right-of eDP-1 --mode 1920x1080
    xrandr --output DP-1-5 --right-of DP-1-5 --mode 1920x1080
    setxkbmap -layout de 
fi

if [ "$HOSTNAME" = "shuruppak" ]; then
    setxkbmap -layout de 
fi
# Apply display colour profiles. helper/apply_icc.py reads
# configuration/hardware/icc/displays.json, matches each connected output against this
# machine's entry, and hands the profile to dispwin. It exits 0 in every failure case --
# no displaycal installed, no entry for this host, a missing profile, or
# ~/.config/icc/disabled present -- so an uncalibrated display never blocks the session.
DOTFILES_ROOT="$(dirname "$(dirname "$(dirname "$(readlink -f "$HOME/.xinitrc")")")")"
if [ -f "$DOTFILES_ROOT/helper/apply_icc.py" ]; then
    python "$DOTFILES_ROOT/helper/apply_icc.py"
fi

# https://shallowsky.com/linux/x-screen-blanking.html
xset s 512 512
xset dpms 512 512 1024

# picom -b
qtile start
