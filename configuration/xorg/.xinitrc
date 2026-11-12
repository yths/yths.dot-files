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

# The repository this file is symlinked from, for the per-host setup and the hooks below.
DOTFILES_ROOT="$(dirname "$(dirname "$(dirname "$(readlink -f "$HOME/.xinitrc")")")")"

# Monitor layout and keyboard belong to a machine, not to this configuration: each lives in
# configuration/hardware/hosts/<hostname>.sh, and a host without one keeps the X defaults.
host="${HOSTNAME:-$(uname -n)}"
if [ -f "$DOTFILES_ROOT/configuration/hardware/hosts/$host.sh" ]; then
    . "$DOTFILES_ROOT/configuration/hardware/hosts/$host.sh"
fi

# Apply display colour profiles. helper/apply_icc.py reads
# configuration/hardware/icc/displays.json, matches each connected output against this
# machine's entry, and hands the profile to dispwin. It exits 0 in every failure case --
# no displaycal installed, no entry for this host, a missing profile, or
# ~/.config/icc/disabled present -- so an uncalibrated display never blocks the session.
if [ -f "$DOTFILES_ROOT/helper/apply_icc.py" ]; then
    python "$DOTFILES_ROOT/helper/apply_icc.py"
fi

# https://shallowsky.com/linux/x-screen-blanking.html
xset s 512 512
xset dpms 512 512 1024

# Lock on idle, on `loginctl lock-session`, and before suspend. xss-lock watches all three
# and runs the locker; the timer it obeys is the `xset s` above. --transfer-sleep-lock holds
# systemd's sleep inhibitor until the locker is actually up, so the machine cannot suspend
# to a state where it wakes unlocked.
if command -v xss-lock >/dev/null 2>&1; then
    xss-lock --transfer-sleep-lock -- "$HOME/.config/lock/lock.sh" &
fi

# picom -b
qtile start
