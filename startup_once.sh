#!/bin/sh

~/repositories/yths.dot-files/qtile/qtile-server/qtile-server &
# nitrogen --restore &
feh --bg-fill ~/Pictures/Wallpapers/wallpaper.jpg &
timedatectl set-timezone "$(curl --fail https://ipapi.co/timezone)" &