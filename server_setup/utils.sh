#!/bin/bash
LOGFILE="$HOME/logs/build.log"

handle_error() {
  echo "$(date): Error $?. Last command: $BASH_COMMAND on line $BASH_LINENO" >> "$LOGFILE"
  exit 1
}

trap handle_error ERR
