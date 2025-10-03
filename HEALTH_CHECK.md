# Meshtastic System Helserapport
**Dato**: 2025-10-03

## ✅ Status: SYSTEMET ER SUNT

### Container Status
| Container | Status | Restart Policy | Ports |
|-----------|--------|----------------|-------|
| meshtastic-map | ✅ Kjører | unless-stopped | 8080, 8081 |
| meshtastic-postgres | ✅ Kjører (healthy) | unless-stopped | 5432 |
| meshtastic-mosquitto | ✅ Kjører | unless-stopped | 1883 |
| meshtasticd | ✅ Kjører | unless-stopped | 4403, 9443 |

### Kjørende Prosesser i meshmap
- ✅ `mqtt_collector_pg.py` - MQTT collector (global network)
- ✅ `device_manager.py` - USB + WiFi device manager
- ✅ `node_api.py` - HTTP API for remote nodes
- ✅ `db_to_geojson_pg.py` - GeoJSON generator (30s interval)
- ✅ `http.server` - Web server (port 8080)
- ✅ Nightly cleanup task (kjører kl 03:00)

### Persistent Data
- ✅ `postgres-data` volume - Database persistence
- ✅ `/home/kau005/meshtastic-data` - GeoJSON files, device registry
- ✅ `meshtasticd-state` volume - meshtasticd state

### Hardware
- ✅ `/dev/ttyUSB0` - USB Meshtastic node tilgjengelig
- ✅ WiFi node: 172.19.228.51:4403
- ✅ Device registry: 2 aktive enheter

---

## 🔧 ANBEFALINGER FOR ROBUSTHET

### 1. ⚠️ KRITISK: USB-enhet persistence
**Problem**: Hvis USB-enheten frakoblet eller bytter port (/dev/ttyUSB1), vil systemet kræsje.

**Løsning**: Bruk udev rules for å sikre stabil device path
```bash
# Finn USB-enhetens ID
sudo udevadm info --query=all --name=/dev/ttyUSB0 | grep -E "ID_VENDOR_ID|ID_MODEL_ID|SERIAL"

# Opprett udev rule: /etc/udev/rules.d/99-meshtastic.rules
# SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", SYMLINK+="meshtastic-usb", GROUP="dialout", MODE="0660"

# Oppdater docker-compose.yml:
# devices:
#   - /dev/meshtastic-usb:/dev/ttyUSB0
```

### 2. ⚠️ KRITISK: Nettverkstap håndtering
**Problem**: Hvis internett går ned, vil MQTT collector miste tilkobling til mqtt.meshtastic.org

**Status**: ✅ mqtt_collector har automatisk reconnect-logikk
**Anbefaling**: Legg til lokal MQTT buffer for å unngå datatap

### 3. 🔍 device_manager logging
**Problem**: device_manager produserer ikke synlige logger

**Løsning**: Øk logging-nivå
```python
# I device_manager.py, sett:
logging.basicConfig(level=logging.INFO)  # Eller DEBUG for mer detaljer
```

### 4. ⚠️ VIKTIG: Database backup
**Problem**: Ingen automatisk backup av PostgreSQL database

**Løsning**: Legg til daglig backup i run.sh
```bash
# I map/run.sh, legg til backup-task:
(
  while true; do
    sleep $(( (86400 + $(date -d "02:00 tomorrow" +%s) - $(date +%s)) % 86400 ))
    echo "💾 Running database backup..."
    docker exec meshtastic-postgres pg_dump -U meshuser meshtastic | gzip > /home/kau005/meshtastic-data/backup/db_$(date +%Y%m%d).sql.gz
    # Slett backups eldre enn 30 dager
    find /home/kau005/meshtastic-data/backup -name "db_*.sql.gz" -mtime +30 -delete
  done
) &
```

### 5. ⚠️ VIKTIG: Healthcheck for meshmap
**Problem**: Docker healthcheck mangler for meshmap container

**Løsning**: Legg til healthcheck i docker-compose.yml
```yaml
meshmap:
  healthcheck:
    test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080')"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 40s
```

### 6. 📊 Monitoring og alerting
**Anbefaling**: Implementer basic monitoring
```bash
# Opprett monitoring script: /home/kau005/meshtastic-docker/monitor.sh
#!/bin/bash
# Sjekk om alle containere kjører
if ! docker ps | grep -q meshtastic-map; then
    echo "ALERT: meshtastic-map er nede!" | mail -s "Meshtastic Alert" admin@example.com
fi
# Sjekk database størrelse
DB_SIZE=$(docker exec meshtastic-postgres psql -U meshuser -d meshtastic -t -c "SELECT pg_size_pretty(pg_database_size('meshtastic'));")
echo "Database størrelse: $DB_SIZE"
```

### 7. 🔄 Automatisk container oppdatering
**Anbefaling**: Bruk Watchtower for automatiske image-oppdateringer
```bash
docker run -d \
  --name watchtower \
  --restart unless-stopped \
  -v /var/run/docker.sock:/var/run/docker.sock \
  containrrr/watchtower \
  --interval 86400 \  # Sjekk én gang per dag
  meshtastic-map meshtastic-postgres meshtastic-mosquitto
```

### 8. 📝 Logging best practices
**Problem**: Docker logger kan vokse ukontrollert

**Løsning**: Legg til logging limits i docker-compose.yml
```yaml
services:
  meshmap:
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "3"
```

---

## 🚨 KRITISKE SCENARIOS OG RECOVERY

### Scenario 1: Server reboot
**Status**: ✅ HÅNDTERT
- Alle containere har `restart: unless-stopped`
- Volumes sikrer data persistence
- Automatisk reconnect til MQTT

**Test**:
```bash
sudo reboot
# Etter reboot, sjekk:
docker ps | grep meshtastic
```

### Scenario 2: Internett nede
**Status**: ⚠️ DELVIS HÅNDTERT
- Lokal USB/WiFi nodes vil fortsette å fungere
- MQTT global data vil ikke mottas før nett er tilbake
- Database og GeoJSON vil fortsette å oppdateres lokalt

**Forbedring**: Legg til healthcheck som detekterer nettverkstap

### Scenario 3: USB-enhet frakoblet
**Status**: ⚠️ RISIKO
- device_manager vil logge feil
- WiFi node vil fortsette å fungere
- Systemet vil ikke kræsje

**Test**:
```bash
# Simuler USB-frakobling
docker exec meshtastic-map ls /dev/ttyUSB0
```

### Scenario 4: Database full
**Status**: ⚠️ RISIKO
- Nightly cleanup fjerner noder eldre enn 60 dager
- Telemetri kan vokse ukontrollert

**Monitoring**:
```bash
docker exec meshtastic-postgres psql -U meshuser -d meshtastic -c "SELECT pg_size_pretty(pg_database_size('meshtastic'));"
```

### Scenario 5: Docker daemon restart
**Status**: ✅ HÅNDTERT
- Alle containere vil restarte automatisk

---

## 📋 DAGLIG VEDLIKEHOLD SJEKKLISTE

### Automatisk (ingen handling nødvendig)
- ✅ 03:00: Cleanup av noder eldre enn 60 dager
- ✅ Kontinuerlig: GeoJSON generering (hver 30. sekund)
- ✅ Kontinuerlig: Device manager polling (hver 30. sekund)
- ✅ Kontinuerlig: MQTT data collection

### Anbefalt manuell sjekk (ukentlig)
```bash
# Kjør helsekontroll
cd /home/kau005/meshtastic-docker
./health_check.sh

# Sjekk database størrelse
docker exec meshtastic-postgres psql -U meshuser -d meshtastic -c "SELECT pg_size_pretty(pg_database_size('meshtastic'));"

# Sjekk antall noder
docker exec meshtastic-postgres psql -U meshuser -d meshtastic -c "SELECT COUNT(*) FROM nodes;"

# Sjekk disk usage
df -h /home/kau005/meshtastic-data
```

---

## 🛠️ RECOVERY PROSEDYRER

### Full system restore
```bash
cd /home/kau005/meshtastic-docker

# 1. Stopp alle containere
docker-compose down

# 2. Restore database backup (hvis tilgjengelig)
gunzip < /home/kau005/meshtastic-data/backup/db_YYYYMMDD.sql.gz | \
  docker exec -i meshtastic-postgres psql -U meshuser meshtastic

# 3. Start systemet
docker-compose up -d

# 4. Verifiser
docker ps
docker logs meshtastic-map --tail 20
```

### Reset node database
```bash
# USB node
docker exec meshtastic-map meshtastic --port /dev/ttyUSB0 --reset-nodedb

# WiFi node
docker exec meshtastic-map meshtastic --host 172.19.228.51 --reset-nodedb
```

### Clean start (behold database)
```bash
docker-compose restart meshmap
```

### Nuclear option (slett alt data)
```bash
docker-compose down -v
docker volume rm meshtastic-docker_postgres-data meshtastic-docker_map-data
docker-compose up -d
```

---

## 📊 SYSTEM METRICS

### Database statistikk
```bash
# Antall noder totalt
docker exec meshtastic-postgres psql -U meshuser -d meshtastic -c "SELECT COUNT(*) as total_nodes FROM nodes;"

# Noder siste 24 timer
docker exec meshtastic-postgres psql -U meshuser -d meshtastic -c "SELECT COUNT(*) as active_24h FROM nodes WHERE last_heard > NOW() - INTERVAL '24 hours';"

# Telemetri entries
docker exec meshtastic-postgres psql -U meshuser -d meshtastic -c "SELECT COUNT(*) as telemetry_entries FROM telemetry;"

# Database størrelse
docker exec meshtastic-postgres psql -U meshuser -d meshtastic -c "SELECT pg_size_pretty(pg_total_relation_size('nodes')) as nodes_size, pg_size_pretty(pg_total_relation_size('telemetry')) as telemetry_size;"
```

---

## ✅ KONKLUSJON

**System helse**: 9/10
- Alle kritiske komponenter kjører stabilt
- Restart policies er konfigurert riktig
- Data persistence er sikret

**Prioriterte forbedringer**:
1. 🔴 Legg til USB udev rules for stabil device path
2. 🟡 Implementer database backup
3. 🟡 Legg til healthcheck for meshmap
4. 🟢 Øk logging-nivå for bedre debugging

**Neste steg**: Implementer anbefalinger 1-3 innen en uke.
