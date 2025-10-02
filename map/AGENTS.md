# Meshtastic Docker Stack Notes

## Overview
- `meshtasticd` container runs Meshtastic native daemon in simulated radio mode and now bridges against the local Mosquitto broker (`meshtastic-mosquitto`) on port 1883 using user `meshlocal` / `meshLocal2025`.
- `meshtastic-mosquitto` container listens on `1883` (exposed to LAN) with persistence enabled. Password file lives in `mosquitto/config/passwd`.
- Snap mosquitto service (`sudo snap stop mosquitto && sudo snap disable mosquitto`) is kept disabled to free up port 1883. Restart only the containerised broker.
- `meshtastic-map` container builds a Python image serving:
  - `generate_geojson.py`: polls the Meshtastic API (port 4403), enriches node metadata, writes `nodes.geojson`, caches history to `/data/nodes.db` (SQLite), and emits `trails.geojson` with per-node LineStrings for the last 24 hours.
  - `run.sh`: seeds `/data/config/favorites.json`, launches the generator and a static HTTP server on port 8080.
  - Leaflet frontend (`index.html`) offers search, favorite filtering, and trail overlays.
- `tailscale` service (disabled by default due to host tailscaled conflict) can be enabled once `/dev/net/tun` is free.

## Volumes & Files
- `map-data` volume contains:
  - `index.html` (served file)
  - `nodes.geojson`, `trails.geojson`
  - `nodes.db` (SQLite history; 24h window by default)
  - `config/favorites.json` (favorite nodes, labels, notes)
- Use `docker exec meshtastic-map` to inspect data: `sqlite3 /data/nodes.db`, `cat /data/trails.geojson`, etc.
- Heltec gateway (`!db2f13c0`) is pre-loaded as favorite with label “Heltec Gateway”. Update this file to change favourites.

## Favorites & Metadata
- Edit `/var/lib/docker/volumes/meshtastic-docker_map-data/_data/config/favorites.json` (or via container) to add nodes. Structure example:
  ```json
  {
    "favorites": ["!db2f13c0"],
    "labels": {"!db2f13c0": "Heltec Gateway"},
    "notes": {"!db2f13c0": "USB gateway node on meshtracking server"}
  }
  ```
- Changes auto-load within ~60 seconds.

## Heltec Gateway
- Physical Heltec V3 is configured via USB (`/dev/ttyUSB0`) with MQTT pointed at `meshtracking.no:1883`, username `meshlocal`, password `meshLocal2025`.
- Use `sg dialout '~/.local/bin/meshtastic --port /dev/ttyUSB0 --get mqtt'` to verify or update settings.
- Keep the device on Wi-Fi so it can bridge LoRa traffic into the local broker; no traffic is sent to the public `mqtt.meshtastic.org`.

## Trails & History
- History window controlled by env var `HISTORY_WINDOW_SECONDS` (default 86400s).
- Trails rendered from the most recent `TRAIL_MAX_POINTS` (default 500) per node.

## Updating Stack
- Daily systemd timer `meshtastic-docker-update.timer` runs `/home/kau005/meshtastic-docker/update.sh` (`docker compose pull && up -d`).
- Manual rebuild after config changes: `docker compose build meshmap && docker compose up -d meshmap`.

## Access
- LAN: `http://172.19.228.175:8088/`
- Public HTTPS via Apache reverse proxy: `https://meshtracking.no/`
- Tailscale Serve: `https://meshtastic.tail952c08.ts.net/`
- Raw API: `http://127.0.0.1:4403` (Meshtastic API), `http://127.0.0.1:9443` (MeshtasticD UI).
