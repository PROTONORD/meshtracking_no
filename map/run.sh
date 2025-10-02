#!/usr/bin/env bash
set -euo pipefail
DATA_DIR=/data
CONFIG_DIR="$DATA_DIR/config"

mkdir -p "$DATA_DIR"
mkdir -p "$CONFIG_DIR" 2>/dev/null || true  # Create if writable

# Seed default favorites file if none exists yet and directory is writable
FAV_FILE="$CONFIG_DIR/favorites.json"
if [ ! -f "$FAV_FILE" ] && [ -w "$CONFIG_DIR" ]; then
  cat >"$FAV_FILE" <<'EOF'
{
  "favorites": ["!db2f13c0"],
  "labels": {"!db2f13c0": "Heltec Gateway"},
  "notes": {"!db2f13c0": "USB gateway node on meshtracking server"}
}
EOF
fi

cp /app/index.html "$DATA_DIR/"

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" 2>/dev/null; do
  sleep 1
done
echo "✓ PostgreSQL is ready"

echo "Starting MQTT collector (global network)..."
python /app/mqtt_collector_pg.py &

echo "Starting dynamic device manager (USB + WiFi auto-discovery)..."
python /app/device_manager.py &

echo "Starting node API (HTTP endpoint for remote nodes)..."
python /app/node_api.py &

echo "Waiting 5 seconds for initial data..."
sleep 5

echo "Starting GeoJSON generator..."
python /app/db_to_geojson_pg.py &

echo "Starting web server on port 8080..."
python -m http.server 8080 --directory "$DATA_DIR"
