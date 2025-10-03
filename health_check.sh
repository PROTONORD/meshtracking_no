#!/bin/bash
# Meshtastic System Health Check
# Run this weekly to verify system health

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     MESHTASTIC SYSTEM HELSEKONTROLL                        ║"
echo "║     $(date '+%Y-%m-%d %H:%M:%S')                                  ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check function
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $1"
        return 0
    else
        echo -e "${RED}✗${NC} $1"
        return 1
    fi
}

ERRORS=0

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. DOCKER CONTAINERE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check each container
for container in meshtastic-map meshtastic-postgres meshtastic-mosquitto meshtasticd; do
    if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        check_status "$container er kjørende"
    else
        check_status "$container er NEDE"
        ((ERRORS++))
    fi
done
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. RESTART POLICIES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

for container in meshtastic-map meshtastic-postgres meshtastic-mosquitto; do
    policy=$(docker inspect $container --format='{{.HostConfig.RestartPolicy.Name}}' 2>/dev/null)
    if [ "$policy" = "unless-stopped" ]; then
        echo -e "${GREEN}✓${NC} $container: $policy"
    else
        echo -e "${YELLOW}⚠${NC} $container: $policy (anbefalt: unless-stopped)"
    fi
done
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. DATABASE HELSE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if docker exec meshtastic-postgres pg_isready -U meshuser -d meshtastic > /dev/null 2>&1; then
    check_status "PostgreSQL aksepterer tilkoblinger"
    
    # Database size
    DB_SIZE=$(docker exec meshtastic-postgres psql -U meshuser -d meshtastic -t -c "SELECT pg_size_pretty(pg_database_size('meshtastic'));" 2>/dev/null | tr -d ' ')
    echo "   Database størrelse: $DB_SIZE"
    
    # Node count
    NODE_COUNT=$(docker exec meshtastic-postgres psql -U meshuser -d meshtastic -t -c "SELECT COUNT(*) FROM nodes;" 2>/dev/null | tr -d ' ')
    echo "   Antall noder: $NODE_COUNT"
    
    # Active nodes (last 24h)
    ACTIVE_NODES=$(docker exec meshtastic-postgres psql -U meshuser -d meshtastic -t -c "SELECT COUNT(*) FROM nodes WHERE last_heard > NOW() - INTERVAL '24 hours';" 2>/dev/null | tr -d ' ')
    echo "   Aktive noder (24t): $ACTIVE_NODES"
    
    # Telemetry entries
    TELEMETRY_COUNT=$(docker exec meshtastic-postgres psql -U meshuser -d meshtastic -t -c "SELECT COUNT(*) FROM telemetry;" 2>/dev/null | tr -d ' ')
    echo "   Telemetri oppføringer: $TELEMETRY_COUNT"
else
    check_status "PostgreSQL tilkobling FEILET"
    ((ERRORS++))
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. HARDWARE ENHETER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check USB devices
if [ -e /dev/ttyUSB0 ]; then
    check_status "/dev/ttyUSB0 tilgjengelig"
    ls -l /dev/ttyUSB0 | awk '{print "   Permissions: " $1 " Owner: " $3 ":" $4}'
else
    echo -e "${YELLOW}⚠${NC} /dev/ttyUSB0 ikke funnet"
fi

# Check device registry
if docker exec meshtastic-map cat /data/config/device_registry.json > /dev/null 2>&1; then
    DEVICE_COUNT=$(docker exec meshtastic-map sh -c "cat /data/config/device_registry.json | grep -o '\"type\"' | wc -l" 2>/dev/null)
    check_status "Device registry: $DEVICE_COUNT enheter registrert"
else
    echo -e "${YELLOW}⚠${NC} Device registry ikke tilgjengelig"
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5. PYTHON-PROSESSER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

PYTHON_COUNT=$(docker exec meshtastic-map sh -c "ls -la /proc/*/exe 2>/dev/null | grep python | wc -l" 2>/dev/null)
if [ "$PYTHON_COUNT" -ge 5 ]; then
    check_status "$PYTHON_COUNT Python-prosesser kjører (forventet: 6+)"
else
    echo -e "${RED}✗${NC} Kun $PYTHON_COUNT Python-prosesser (forventet: 6+)"
    ((ERRORS++))
fi

# Check specific processes
echo "   Verifiserer kritiske prosesser:"
docker exec meshtastic-map sh -c "find /proc -name cmdline -exec cat {} \; 2>/dev/null | tr '\0' ' '" | grep -q "mqtt_collector_pg.py" && echo -e "   ${GREEN}✓${NC} mqtt_collector_pg.py" || echo -e "   ${RED}✗${NC} mqtt_collector_pg.py"
docker exec meshtastic-map sh -c "find /proc -name cmdline -exec cat {} \; 2>/dev/null | tr '\0' ' '" | grep -q "device_manager.py" && echo -e "   ${GREEN}✓${NC} device_manager.py" || echo -e "   ${RED}✗${NC} device_manager.py"
docker exec meshtastic-map sh -c "find /proc -name cmdline -exec cat {} \; 2>/dev/null | tr '\0' ' '" | grep -q "db_to_geojson_pg.py" && echo -e "   ${GREEN}✓${NC} db_to_geojson_pg.py" || echo -e "   ${RED}✗${NC} db_to_geojson_pg.py"
docker exec meshtastic-map sh -c "find /proc -name cmdline -exec cat {} \; 2>/dev/null | tr '\0' ' '" | grep -q "node_api.py" && echo -e "   ${GREEN}✓${NC} node_api.py" || echo -e "   ${RED}✗${NC} node_api.py"
docker exec meshtastic-map sh -c "find /proc -name cmdline -exec cat {} \; 2>/dev/null | tr '\0' ' '" | grep -q "http.server" && echo -e "   ${GREEN}✓${NC} http.server" || echo -e "   ${RED}✗${NC} http.server"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "6. DATA PERSISTENCE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check volumes
for volume in postgres-data meshtasticd-state map-data; do
    if docker volume ls | grep -q "meshtastic-docker_$volume"; then
        check_status "Volume: meshtastic-docker_$volume"
    else
        echo -e "${RED}✗${NC} Volume meshtastic-docker_$volume mangler"
        ((ERRORS++))
    fi
done

# Check data directory
if [ -d "/home/kau005/meshtastic-data" ]; then
    DATA_SIZE=$(du -sh /home/kau005/meshtastic-data 2>/dev/null | awk '{print $1}')
    check_status "Data directory: /home/kau005/meshtastic-data ($DATA_SIZE)"
else
    echo -e "${RED}✗${NC} Data directory mangler"
    ((ERRORS++))
fi

# Check backups
if [ -d "/home/kau005/meshtastic-data/backup" ]; then
    BACKUP_COUNT=$(find /home/kau005/meshtastic-data/backup -name "db_*.sql.gz" 2>/dev/null | wc -l)
    if [ "$BACKUP_COUNT" -gt 0 ]; then
        LATEST_BACKUP=$(ls -t /home/kau005/meshtastic-data/backup/db_*.sql.gz 2>/dev/null | head -1 | xargs basename)
        BACKUP_AGE=$(find /home/kau005/meshtastic-data/backup -name "db_*.sql.gz" -mtime -2 2>/dev/null | wc -l)
        if [ "$BACKUP_AGE" -gt 0 ]; then
            check_status "Database backup: $BACKUP_COUNT backups, siste: $LATEST_BACKUP"
        else
            echo -e "${YELLOW}⚠${NC} Database backup: Siste backup er eldre enn 2 dager"
        fi
    else
        echo -e "${YELLOW}⚠${NC} Ingen database backups funnet"
    fi
else
    echo -e "${YELLOW}⚠${NC} Backup directory mangler (vil bli opprettet ved neste backup)"
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "7. NETTVERKS-TESTER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Test web server
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8088/nodes.geojson | grep -q "200"; then
    check_status "Web server (port 8088) svarer"
else
    echo -e "${RED}✗${NC} Web server (port 8088) svarer ikke"
    ((ERRORS++))
fi

# Test node API
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/ | grep -q "200"; then
    check_status "Node API (port 8081) svarer"
else
    echo -e "${YELLOW}⚠${NC} Node API (port 8081) svarer ikke"
fi

# Test MQTT
if docker exec meshtastic-mosquitto sh -c "mosquitto_sub -t 'msh/#' -C 1 -W 2" > /dev/null 2>&1; then
    check_status "MQTT broker (port 1883) svarer"
else
    echo -e "${YELLOW}⚠${NC} MQTT broker test timeout"
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "8. FILSYSTEM OG DISK"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check disk space
DISK_USAGE=$(df -h / | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -lt 80 ]; then
    check_status "Disk usage: ${DISK_USAGE}% (OK)"
elif [ "$DISK_USAGE" -lt 90 ]; then
    echo -e "${YELLOW}⚠${NC} Disk usage: ${DISK_USAGE}% (Vurder opprydding)"
else
    echo -e "${RED}✗${NC} Disk usage: ${DISK_USAGE}% (KRITISK - disk nesten full)"
    ((ERRORS++))
fi

# Check key files
if [ -f "/home/kau005/meshtastic-data/nodes.geojson" ]; then
    GEOJSON_SIZE=$(stat -c%s "/home/kau005/meshtastic-data/nodes.geojson" 2>/dev/null)
    GEOJSON_AGE=$(stat -c%Y "/home/kau005/meshtastic-data/nodes.geojson" 2>/dev/null)
    NOW=$(date +%s)
    AGE_SEC=$((NOW - GEOJSON_AGE))
    if [ "$AGE_SEC" -lt 120 ]; then
        check_status "nodes.geojson oppdatert nylig (${AGE_SEC}s siden)"
    else
        echo -e "${YELLOW}⚠${NC} nodes.geojson ikke oppdatert på ${AGE_SEC}s"
    fi
else
    echo -e "${RED}✗${NC} nodes.geojson mangler"
    ((ERRORS++))
fi
echo ""

echo "╔════════════════════════════════════════════════════════════╗"
if [ $ERRORS -eq 0 ]; then
    echo -e "║  ${GREEN}✓ SYSTEM HELSE: UTMERKET${NC}                                  ║"
    echo "║  Alle tester bestått!                                      ║"
elif [ $ERRORS -le 2 ]; then
    echo -e "║  ${YELLOW}⚠ SYSTEM HELSE: BRA MED ADVARSLER${NC}                        ║"
    echo "║  $ERRORS mindre problemer funnet                                  ║"
else
    echo -e "║  ${RED}✗ SYSTEM HELSE: PROBLEMER FUNNET${NC}                          ║"
    echo "║  $ERRORS feil/advarsler funnet                                 ║"
fi
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

if [ $ERRORS -gt 0 ]; then
    echo "Anbefaling: Sjekk feilene ovenfor og kjør 'docker-compose restart' hvis nødvendig."
    echo "Se HEALTH_CHECK.md for detaljerte recovery prosedyrer."
    exit 1
fi

exit 0
