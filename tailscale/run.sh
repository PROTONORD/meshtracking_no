#!/bin/sh
set -e
TAILSCALED_ARGS="--state=${TS_STATE_DIR:-/var/lib/tailscale}/tailscaled.state --socket=/var/run/tailscale/tailscaled.sock"
mkdir -p "${TS_STATE_DIR:-/var/lib/tailscale}" /var/run/tailscale
/usr/local/bin/tailscaled ${TAILSCALED_ARGS} &
TS_PID=$!

# wait for tailscaled to come up
sleep 5

if [ -n "${TS_AUTHKEY}" ]; then
  tailscale up --authkey="${TS_AUTHKEY}" ${TS_EXTRA_ARGS}
else
  echo "No TS_AUTHKEY provided; tailscaled is running. Use 'docker exec tailscale tailscale up' to authenticate."
fi
wait ${TS_PID}
