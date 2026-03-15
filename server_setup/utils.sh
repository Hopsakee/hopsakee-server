#!/bin/bash
LOGFILE="$HOME/logs/build.log"

# Check if the log file exists, if not create it
# (the LOGDIR is created at server creation time `tps_cloud_init.yaml`)
if [ ! -f "$LOGFILE" ]; then
  touch "$LOGFILE"
fi

handle_error() {
  echo "$(date): Error $?. Last command: $BASH_COMMAND on line $BASH_LINENO" >> "$LOGFILE"
  exit 1
}

trap handle_error ERR
