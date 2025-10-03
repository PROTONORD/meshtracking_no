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

echo "Waiting 5 seconds for initial data..."
sleep 5

echo "Starting GeoJSON generator..."
python /app/db_to_geojson_pg.py &

echo "Starting daily cleanup task (removes nodes inactive >60 days)..."
(
  while true; do
    # Run at 03:00 every night
    sleep $(( (86400 + $(date -d "03:00 tomorrow" +%s) - $(date +%s)) % 86400 ))
    echo "🧹 Running nightly node cleanup..."
    python /app/cleanup_old_nodes.py
  done
) &

echo "Starting nightly database backup task (runs at 02:00)..."
(
  while true; do
    # Run at 02:00 every night
    sleep $(( (86400 + $(date -d "02:00 tomorrow" +%s) - $(date +%s)) % 86400 ))
    echo "💾 Running database backup..."
    mkdir -p /data/backup
    PGPASSWORD=meshpass2025 pg_dump -h postgres -U meshuser meshtastic | gzip > /data/backup/db_$(date +%Y%m%d_%H%M%S).sql.gz
    echo "✓ Database backup completed: db_$(date +%Y%m%d_%H%M%S).sql.gz"
    # Keep only last 14 days of backups
    find /data/backup -name "db_*.sql.gz" -mtime +14 -delete
    echo "✓ Old backups cleaned up (kept last 14 days)"
  done
) &

echo "Starting combined web and API server on port 8080..."
python /app/combined_server.py
