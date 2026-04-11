#!/bin/bash

# Get the directory this script lives in, so it works no matter where you call it from
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Helper: deploy one app, but don't stop if it fails
deploy_app() {
    local name=$1
    local script=$2
    echo ">>> Deploying $name..."
    if bash "$script"; then
        echo "✅ $name deployed successfully"
    else
        echo "❌ $name failed — skipping"
    fi
}

# These must succeed - exit immediately on failure
bash "$SCRIPT_DIR/deploy-caddy.sh" || { echo "❌ Caddy failed — aborting"; exit 1; }
bash "$SCRIPT_DIR/deploy-authelia.sh" || { echo "❌ Authelia failed — aborting"; exit 1; }


# These can fail independently
deploy_app "infoflow"  "$SCRIPT_DIR/deploy-infoflow.sh"
deploy_app "govchat"   "$SCRIPT_DIR/deploy-govchat.sh"
