#!/bin/bash
# Run from your local machine to push secrets and deploy all apps on the server.

set -a
source "$(dirname "${BASH_SOURCE[0]}")/../.env"
set +a

SERVER="ubuntu@hopsakee.top"
SSH="ssh -i ~/.ssh/tps_si"
SECRETS_DIR="/data/authelia/secrets"

echo ">>> Creating secrets directory on server..."
$SSH $SERVER "sudo mkdir -p $SECRETS_DIR && sudo chown -R ubuntu:ubuntu /data/authelia"

echo ">>> Pushing persistent secrets..."
$SSH $SERVER "echo -n '$AUTHELIA_STORAGE_ENCRYPTION_KEY' > $SECRETS_DIR/storage_encryption_key"
$SSH $SERVER "echo -n '$AUTHELIA_SMTP_USERNAME' > $SECRETS_DIR/smtp_username"
$SSH $SERVER "echo -n '$AUTHELIA_SMTP_PASSWORD' > $SECRETS_DIR/smtp_password"

echo ">>> Generating fresh jwt and session secrets..."
$SSH $SERVER "python3 -c \"import secrets; open('$SECRETS_DIR/jwt_secret','w').write(secrets.token_hex(32))\""
$SSH $SERVER "python3 -c \"import secrets; open('$SECRETS_DIR/session_secret','w').write(secrets.token_hex(32))\""

echo ">>> Pulling latest git changes and deploying..."
$SSH $SERVER "cd ~/hopsakee-server && git pull && bash ~/hopsakee-server/server_setup/server-deploy.sh"
