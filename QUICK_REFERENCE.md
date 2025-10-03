# 🚀 MESHTASTIC SYSTEM - QUICK REFERENCE

## 📊 System Status: PRODUCTION READY ✅

**Last Updated:** 2025-10-03  
**Health Score:** 9.5/10  
**Resilience:** Excellent

---

## ⚡ QUICK COMMANDS

### Health Check
```bash
cd /home/kau005/meshtastic-docker
./health_check.sh
```

### View Logs
```bash
# All logs
docker logs meshtastic-map --tail 50

# Only errors
docker logs meshtastic-map --tail 100 | grep -E "ERROR|WARNING"

# Follow live
docker logs meshtastic-map -f
```

### Restart System
```bash
cd /home/kau005/meshtastic-docker

# Restart single container
docker restart meshtastic-map

# Restart all
docker-compose restart

# Full rebuild (after code changes)
docker-compose down
docker-compose up -d --build
```

### Database Queries
```bash
# Node count
docker exec meshtastic-postgres psql -U meshuser -d meshtastic -c "SELECT COUNT(*) FROM nodes;"

# Active nodes (24h)
docker exec meshtastic-postgres psql -U meshuser -d meshtastic -c "SELECT COUNT(*) FROM nodes WHERE last_heard > NOW() - INTERVAL '24 hours';"

# Database size
docker exec meshtastic-postgres psql -U meshuser -d meshtastic -c "SELECT pg_size_pretty(pg_database_size('meshtastic'));"

# PROTONORD nodes
docker exec meshtastic-postgres psql -U meshuser -d meshtastic -c "SELECT node_id, long_name, latitude, longitude FROM nodes WHERE long_name LIKE '%PROTONORD%';"
```

### Backup Operations
```bash
# Manual backup
docker exec meshtastic-map sh -c "PGPASSWORD=meshpass2025 pg_dump -h postgres -U meshuser meshtastic | gzip > /data/backup/db_manual_$(date +%Y%m%d_%H%M%S).sql.gz"

# List backups
ls -lh /home/kau005/meshtastic-data/backup/

# Restore from backup (CAREFUL!)
# gunzip < /home/kau005/meshtastic-data/backup/db_YYYYMMDD_HHMMSS.sql.gz | docker exec -i meshtastic-postgres psql -U meshuser meshtastic
```

### USB Device
```bash
# Check USB devices
ls -la /dev/ttyUSB* /dev/meshtastic-usb

# Test USB node
docker exec meshtastic-map meshtastic --port /dev/ttyUSB0 --info | head -20

# Reset USB node database
docker exec meshtastic-map meshtastic --port /dev/ttyUSB0 --reset-nodedb
```

### Container Status
```bash
# Quick status
docker ps | grep meshtastic

# Detailed status with health
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Resource usage
docker stats meshtastic-map --no-stream
```

---

## 📁 IMPORTANT FILES

### Configuration
- `/home/kau005/meshtastic-docker/docker-compose.yml` - Main config
- `/home/kau005/meshtastic-docker/map/run.sh` - Startup script
- `/etc/udev/rules.d/99-meshtastic.rules` - USB stability

### Data
- `/home/kau005/meshtastic-data/nodes.geojson` - Current node data
- `/home/kau005/meshtastic-data/backup/` - Database backups
- `/home/kau005/meshtastic-data/config/device_registry.json` - Connected devices

### Documentation
- `HEALTH_CHECK.md` - Detailed health report
- `RESILIENCE_REPORT.md` - Robustness testing
- `SYSTEM_SUMMARY.md` - Implementation summary
- `INSTALL_IMPROVEMENTS.md` - Setup instructions
- `README.md` - Original documentation

### Scripts
- `health_check.sh` - Automated health check
- `cleanup_old_nodes.py` - Node cleanup (runs at 03:00)
- `configure_nodes_with_reboot.py` - Node configuration

---

## 🔥 TROUBLESHOOTING

### Container won't start
```bash
docker logs meshtastic-map --tail 100
docker-compose down
docker-compose up -d --build
```

### Database connection issues
```bash
docker exec meshtastic-postgres pg_isready -U meshuser -d meshtastic
docker restart meshtastic-postgres
docker restart meshtastic-map
```

### USB device not found
```bash
ls -la /dev/ttyUSB* /dev/meshtastic-usb
sudo udevadm control --reload-rules
sudo udevadm trigger
docker restart meshtastic-map
```

### GeoJSON not updating
```bash
docker exec meshtastic-map ls -lah /data/nodes.geojson
docker logs meshtastic-map | grep -i geojson
docker restart meshtastic-map
```

### High disk usage
```bash
df -h /home/kau005/meshtastic-data
docker system df
docker system prune -a --volumes  # CAREFUL - removes unused data
```

---

## 🎯 SCHEDULED TASKS

### Automatic (No Action)
- **02:00** - Database backup (14-day retention)
- **03:00** - Node cleanup (>60 days)
- **Every 30s** - GeoJSON generation
- **Every 30s** - Device polling
- **Every 60s** - Healthcheck

### Recommended Manual
- **Weekly** - Run `./health_check.sh`
- **Monthly** - Check database size
- **Quarterly** - Test backup restore

---

## 🌐 ACCESS POINTS

- **Web Map:** http://localhost:8088
- **Node API:** http://localhost:8081
- **Database:** localhost:5434 (user: meshuser, db: meshtastic)
- **MQTT:** localhost:1883

---

## 🚨 EMERGENCY PROCEDURES

### Complete System Reset
```bash
cd /home/kau005/meshtastic-docker
docker-compose down
# Optional: Remove all data
# docker volume rm meshtastic-docker_postgres-data meshtastic-docker_map-data
docker-compose up -d --build
```

### Restore from Backup
```bash
# 1. Find latest backup
ls -lh /home/kau005/meshtastic-data/backup/

# 2. Stop services
docker-compose down

# 3. Restore
gunzip < /home/kau005/meshtastic-data/backup/db_YYYYMMDD_HHMMSS.sql.gz | docker exec -i meshtastic-postgres psql -U meshuser meshtastic

# 4. Restart
docker-compose up -d
```

### Factory Reset Single Node
```bash
# USB node
docker exec meshtastic-map meshtastic --port /dev/ttyUSB0 --factory-reset

# WiFi node
docker exec meshtastic-map meshtastic --host 172.19.228.51 --factory-reset
```

---

## ✅ VERIFICATION CHECKLIST

After any changes, verify:
```bash
# 1. All containers running
docker ps | grep meshtastic

# 2. Healthchecks passing
docker ps --format "table {{.Names}}\t{{.Status}}"

# 3. Database accessible
docker exec meshtastic-postgres pg_isready -U meshuser -d meshtastic

# 4. GeoJSON updating
ls -lh /home/kau005/meshtastic-data/nodes.geojson

# 5. Full health check
./health_check.sh
```

---

## 📞 SUPPORT

- **Health Report:** `./health_check.sh`
- **Logs:** `docker logs meshtastic-map --tail 100`
- **Documentation:** See `*.md` files in `/home/kau005/meshtastic-docker/`

---

**Last Verified:** 2025-10-03 13:30  
**Status:** All systems operational ✅
