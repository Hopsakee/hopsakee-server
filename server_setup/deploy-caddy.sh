#!/bin/bash
CDIR="$HOME/hopsakee-server/config/caddy"

source "$(dirname "${BASH_SOURCE[0]}")/utils.sh"

cd "$CDIR"
docker compose up --build -d
