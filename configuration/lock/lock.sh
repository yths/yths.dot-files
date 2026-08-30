#!/bin/sh
# Lock the screen.
#
# Bound to mod+control+x and to XF86ScreenSaver in qtile, and run by xss-lock when the X
# idle timer fires, when systemd asks for a session lock, and before suspend.
#
# The colours and the font come from `environment`, which helper/patch_lock.py generates from
# the active palette on every theme switch. This script holds no appearance of its own, so a
# theme change reaches the lock screen without touching it.

set -eu

environment="${XDG_CONFIG_HOME:-$HOME/.config}/lock/environment"
[ -f "$environment" ] && . "$environment"

# exec, not a subshell: xss-lock tracks this process to know whether the screen is still
# locked, and a wrapper that outlived the locker would leave it thinking it is.
exec xsecurelock
