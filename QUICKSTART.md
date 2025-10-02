# Quick Start Commands for Meshtastic Multi-Source Map

## Step 1: System Check
cd /home/kau005/meshtastic-docker
./check-system.sh

## Step 2: Deploy System
./deploy.sh

# This will:
# - Stop old services
# - Clean SQLite files
# - Build new PostgreSQL-based image
# - Start PostgreSQL
# - Start all services
# - Show logs

## Step 3: Verify Deployment

# Check all services running
docker compose ps

# Check PostgreSQL health
docker exec meshtastic-postgres pg_isready -U meshuser

# Check database has nodes
docker exec meshtastic-postgres psql -U meshuser -d meshtastic -c "SELECT COUNT(*) FROM nodes WHERE latitude IS NOT NULL;"

# Check GeoJSON file
curl -s http://127.0.0.1:8088/nodes.geojson | jq '.nodeCount'

# View logs
docker compose logs -f meshmap

## Step 4: Access Map
# Open browser to:
http://127.0.0.1:8088

## Useful Monitoring Commands

# View all node sources
docker exec meshtastic-postgres psql -U meshuser -d meshtastic -c "SELECT source, COUNT(*) as nodes FROM nodes GROUP BY source;"

# View recent nodes
docker exec meshtastic-postgres psql -U meshuser -d meshtastic -c "SELECT node_id, long_name, last_heard, source FROM nodes ORDER BY last_heard DESC LIMIT 10;"

# Check MQTT messages
docker compose logs meshmap | grep "📡"

# Check node polling
docker compose logs meshmap | grep "Retrieved.*nodes"

# API test
curl http://127.0.0.1:8081/api/v1/nodes | jq '.count'

## Troubleshooting

# Restart everything
docker compose restart

# Rebuild image
docker compose build meshmap
docker compose up -d

# View PostgreSQL logs
docker compose logs postgres

# Interactive database access
docker exec -it meshtastic-postgres psql -U meshuser -d meshtastic

# Check for errors
docker compose logs meshmap | grep -i error
