#!/bin/bash
ADIR="$HOME/apps"
IDIR="$ADIR/pkw-web"
CDIR="$HOME/hopsakee-server/config/pkw-web"

source "$(dirname "${BASH_SOURCE[0]}")/utils.sh"

if [ -d "$IDIR" ]; then
  cd "$IDIR" && git fetch origin && git reset --hard origin/main
else
  cd "$ADIR" && git clone https://github.com/Hopsakee/pkw-web.git
fi
cd "$CDIR"
docker compose up --build -d
