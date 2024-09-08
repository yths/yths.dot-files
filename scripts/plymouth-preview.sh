#!/bin/bash

check_root_privileges () {
  if [ ! $( id -u ) -eq 0 ]; then
    echo; echo "requires root privileges"
    exit
  fi
}
check_root_privileges

DURATION=$1
if [ $# -ne 1 ]; then
    DURATION=8
fi

plymouthd; plymouth --show-splash; sleep $DURATION; plymouth quit