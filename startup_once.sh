#!/bin/sh

~/repositories/yths.dot-files/qtile/qtile-server/qtile-server &
nitrogen --restore &
timedatectl set-timezone "$(curl --fail https://ipapi.co/timezone)" &