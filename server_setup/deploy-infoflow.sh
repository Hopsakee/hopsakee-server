#!/bin/bash
ADIR="$HOME/apps"
IDIR="$ADIR/infoflow"
CDIR="$HOME/hopsakee-server/config/infoflow"

source "$(dirname "${BASH_SOURCE[0]}")/utils.sh"

if [ -d "$IDIR" ]; then
  cd "$IDIR" && git pull
else
  cd "$ADIR" && git clone https://github.com/Hopsakee/infoflow.git
fi
cd "$CDIR"
docker compose up --build -d
