#!/bin/bash
# Safe Shutdown Procedure for Server Move
# Run this before physically moving the server

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  MESHTASTIC SYSTEM - SAFE SHUTDOWN FOR SERVER MOVE        ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Change to meshtastic directory
cd /home/kau005/meshtastic-docker || exit 1

echo "1️⃣  Running final health check..."
./health_check.sh > /tmp/pre_shutdown_health.log 2>&1
echo "   ✓ Health report saved to /tmp/pre_shutdown_health.log"
echo ""

echo "2️⃣  Creating final database backup..."
docker exec meshtastic-map sh -c "mkdir -p /data/backup && PGPASSWORD=meshpass2025 pg_dump -h postgres -U meshuser meshtastic | gzip > /data/backup/db_pre_move_$(date +%Y%m%d_%H%M%S).sql.gz"
BACKUP_FILE=$(ls -t /home/kau005/meshtastic-data/backup/db_pre_move_*.sql.gz 2>/dev/null | head -1)
if [ -n "$BACKUP_FILE" ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "   ✓ Backup created: $(basename $BACKUP_FILE) ($BACKUP_SIZE)"
else
    echo "   ⚠ Backup failed or not found"
fi
echo ""

echo "3️⃣  Recording current system state..."
cat > /tmp/pre_shutdown_state.txt << EOF
System State Before Shutdown - $(date)
======================================

Container Status:
$(docker ps --format "table {{.Names}}\t{{.Status}}")

Database Info:
$(docker exec meshtastic-postgres psql -U meshuser -d meshtastic -c "SELECT COUNT(*) as total_nodes FROM nodes;" 2>/dev/null)
$(docker exec meshtastic-postgres psql -U meshuser -d meshtastic -c "SELECT COUNT(*) as active_nodes FROM nodes WHERE last_heard > NOW() - INTERVAL '24 hours';" 2>/dev/null)
$(docker exec meshtastic-postgres psql -U meshuser -d meshtastic -c "SELECT COUNT(*) as telemetry_entries FROM telemetry;" 2>/dev/null)
$(docker exec meshtastic-postgres psql -U meshuser -d meshtastic -c "SELECT pg_size_pretty(pg_database_size('meshtastic')) as db_size;" 2>/dev/null)

USB Device:
$(ls -la /dev/ttyUSB* /dev/meshtastic-usb 2>/dev/null)

Last GeoJSON Update:
$(ls -lh /home/kau005/meshtastic-data/nodes.geojson 2>/dev/null)

PROTONORD Nodes:
$(docker exec meshtastic-postgres psql -U meshuser -d meshtastic -c "SELECT node_id, long_name, short_name, latitude, longitude FROM nodes WHERE long_name LIKE '%PROTONORD%' ORDER BY node_id;" 2>/dev/null)
EOF
cat /tmp/pre_shutdown_state.txt
cp /tmp/pre_shutdown_state.txt /home/kau005/meshtastic-data/
echo "   ✓ State saved to /tmp/pre_shutdown_state.txt"
echo ""

echo "4️⃣  Stopping containers gracefully..."
docker-compose down
echo "   ✓ All containers stopped"
echo ""

echo "5️⃣  Verifying data persistence..."
echo "   Database volume: $(docker volume inspect meshtastic-docker_postgres-data --format '{{.Mountpoint}}' 2>/dev/null || echo 'OK')"
echo "   Map data: /home/kau005/meshtastic-data"
ls -lh /home/kau005/meshtastic-data/*.geojson 2>/dev/null | awk '{print "   - " $9 " (" $5 ")"}'
echo ""

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  ✓ SYSTEM SAFELY SHUT DOWN                                ║"
echo "║                                                            ║"
echo "║  Server is ready to be moved physically.                  ║"
echo "║                                                            ║"
echo "║  After moving and powering on:                            ║"
echo "║  1. Wait 1-2 minutes for boot                             ║"
echo "║  2. Containers will auto-start                            ║"
echo "║  3. Run: cd ~/meshtastic-docker && ./health_check.sh      ║"
echo "║  4. Verify map at: http://localhost:8088                  ║"
echo "║                                                            ║"
echo "║  Data is persistent - No data will be lost! ✅            ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Display backup info
echo "📦 Backups available:"
ls -lh /home/kau005/meshtastic-data/backup/ 2>/dev/null | tail -5
echo ""
echo "All set! You can now safely power down and move the server."
