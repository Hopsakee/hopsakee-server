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

deploy_app "caddy"     "$SCRIPT_DIR/deploy-caddy.sh"
deploy_app "infoflow"  "$SCRIPT_DIR/deploy-infoflow.sh"
