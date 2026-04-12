#!/bin/bash
# Run from your local machine to pull latest git changes and redeploy all apps on the server.

ssh -i ~/.ssh/tps_si ubuntu@hopsakee.top '
  cd ~/hopsakee-server && git pull
  bash ~/hopsakee-server/server_setup/deploy.sh
'
