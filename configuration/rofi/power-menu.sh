#!/bin/sh
# The power menu, as a rofi script mode: rofi runs this with no argument for the entries, and
# again with the chosen entry as $1. Whatever it prints becomes the next list; printing
# nothing closes rofi.
#
# Log out, reboot and shut down answer with a confirmation entry rather than acting, so a
# stray Enter on the menu cannot end the session. Lock and suspend act at once: both are
# undone by unlocking.

case "$1" in
    "")
        printf '%s\n' "lock" "suspend" "log out" "reboot" "shut down"
        ;;
    "lock")
        # xss-lock handles the request and runs the locker, the same path idle takes.
        loginctl lock-session
        ;;
    "suspend")
        # xss-lock locks before the machine sleeps (--transfer-sleep-lock in ~/.xinitrc).
        systemctl suspend
        ;;
    "log out" | "reboot" | "shut down")
        printf '%s\n' "yes, $1" "no"
        ;;
    "yes, log out")
        qtile cmd-obj -o cmd -f shutdown
        ;;
    "yes, reboot")
        systemctl reboot
        ;;
    "yes, shut down")
        systemctl poweroff
        ;;
esac
