#!/bin/bash
LOGFILE="$HOME/logs/build.log"

# Check if the log directory exists, if not create it
LOGDIR="$(dirname "$LOGFILE")"
if [ ! -d "$LOGDIR" ]; then
  mkdir -p "$LOGDIR"
fi

# Check if the log file exists, if not create it
if [ ! -f "$LOGFILE" ]; then
  touch "$LOGFILE"
fi

handle_error() {
  echo "$(date): Error $?. Last command: $BASH_COMMAND on line $BASH_LINENO" >> "$LOGFILE"
  exit 1
}

trap handle_error ERR
