#!/usr/bin/env bash
set -euo pipefail
cd /home/kau005/meshtastic-docker
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi
/usr/bin/docker compose pull
/usr/bin/docker compose up -d --remove-orphans
