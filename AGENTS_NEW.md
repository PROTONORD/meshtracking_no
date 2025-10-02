# Meshtastic Multi-Source Map - Agent Context

**Last Updated:** 2025-10-02  
**System Status:** ✅ Production-ready PostgreSQL architecture

---

## 🎯 Project Purpose

Self-hosted Meshtastic node visualization system that:
- Tracks nodes from **multiple sources** (MQTT, USB, WiFi, Tailscale)
- Stores data in **PostgreSQL** for concurrent multi-source writes
- Provides **REST API** for remote node data submission
- Displays **real-time map** with node positions and trails
- Polls Meshtastic devices for their full node database every 5 minutes

---

## 🏗️ Architecture Evolution

### Original Design (SQLite)
- Single SQLite database (`nodes.db`)
- MQTT collector + USB collector writing simultaneously
- **PROBLEM:** SQLite database locking issues
- systemd service conflicting with Docker

### Current Design (PostgreSQL)
- PostgreSQL 16 with proper concurrent access
- 4 independent data collectors:
  1. **MQTT Collector** - Global network (mqtt.meshtastic.org)
  2. **Node Poller** - USB/TCP polling every 5 minutes
  3. **HTTP API** - Remote push submissions
  4. **Direct MQTT** - Local Heltec V3 (if WiFi enabled)
- Each source tagged with `source` field
- No more database locks or conflicts

---

## 📦 Services

### 1. postgres (Container)
- **Image:** postgres:16-alpine
- **Purpose:** Multi-source concurrent database
- **Schema:** `init.sql` (nodes, positions, telemetry, messages tables)
- **Port:** 127.0.0.1:5432
- **Credentials:** meshuser/meshpass2025/meshtastic

### 2. mosquitto (Container)
- **Image:** eclipse-mosquitto:latest
- **Purpose:** MQTT broker with bridge to global network
- **Config:** `mosquitto/config/mosquitto.conf`
- **Bridge:** mqtt.meshtastic.org:1883
- **Subscriptions:** msh/EU_868/#, msh/2/e/#
- **Port:** 0.0.0.0:1883

### 3. meshmap (Container - Multi-service)
Built from `./map/Dockerfile`

**Sub-services:**
- **mqtt_collector_pg.py** - Decodes protobuf from Mosquitto → PostgreSQL
- **node_poller.py** - Polls Meshtastic devices via serial/TCP every 5 min
- **node_api.py** - Flask REST API on port 8081
- **db_to_geojson_pg.py** - Generates GeoJSON every 60 seconds
- **HTTP Server** - python -m http.server on port 8080 → 8088

**Volumes:**
- `/home/kau005/meshtastic-data:/data` - GeoJSON output
- `./config:/data/config:ro` - Node sources configuration

**Devices:**
- `/dev/ttyUSB0` - Heltec V3 USB access

---

## 🗄️ Database Schema

### nodes (Main table)
```sql
CREATE TABLE nodes (
    node_id TEXT PRIMARY KEY,           -- !12345678 format
    node_num BIGINT UNIQUE,             -- Numeric ID
    long_name TEXT,                     -- Full name
    short_name TEXT,                    -- 4-char name
    hw_model TEXT,                      -- HELTEC_V3, etc
    role TEXT,                          -- CLIENT/ROUTER/REPEATER
    latitude DOUBLE PRECISION,          -- GPS
    longitude DOUBLE PRECISION,         -- GPS
    altitude DOUBLE PRECISION,          -- Meters
    battery_level INTEGER,              -- 0-100%
    voltage DOUBLE PRECISION,           -- Volts
    snr DOUBLE PRECISION,               -- Signal quality
    rssi DOUBLE PRECISION,              -- Signal strength
    hops_away INTEGER,                  -- Network distance
    first_seen TIMESTAMP WITH TIME ZONE,
    last_heard TIMESTAMP WITH TIME ZONE,
    last_updated TIMESTAMP WITH TIME ZONE,
    source TEXT DEFAULT 'unknown',      -- mqtt/local-usb/node-name
    is_active BOOLEAN DEFAULT TRUE
);
```

### positions (Trail history)
Stores GPS positions over time for generating trails.

### telemetry (Device metrics)
Battery, temperature, uptime, channel utilization.

### messages (Text messages)
Meshtastic text messages between nodes.

---

## 📡 Data Sources

### 1. Global MQTT Bridge
- **Source tag:** `mqtt`
- **Coverage:** Europe (EU_868), some Africa/Asia
- **Update rate:** Real-time (50-200 msg/min)
- **Nodes visible:** 5-20 depending on activity

### 2. Local USB Radio (Heltec V3)
- **Source tag:** `local-usb`
- **Device:** `/dev/ttyUSB0`
- **Poll interval:** 5 minutes
- **Method:** `meshtastic.serial_interface`
- **Data:** Full node database from Heltec memory
- **Tromsø nodes:** 7+ local mesh network

### 3. WiFi Nodes (Optional)
- **Source tag:** `node-{name}`
- **Protocol:** TCP port 4403
- **Config:** `config/node_sources.json`
- **Example:** 192.168.1.100:4403

### 4. Tailscale Nodes (Optional)
- **Source tag:** `tailscale-{name}`
- **Protocol:** TCP port 4403 over VPN
- **Config:** `config/node_sources.json`
- **Example:** 100.64.0.5:4403

### 5. HTTP API Push (Optional)
- **Source tag:** Custom (provided in JSON)
- **Endpoint:** POST /api/v1/nodes
- **Auth:** Bearer token
- **Use case:** Remote nodes pushing their data

---

## 🔧 Key Files

### Python Services
- `map/mqtt_collector_pg.py` - MQTT → PostgreSQL (341 lines)
- `map/node_poller.py` - USB/TCP polling (270 lines)
- `map/node_api.py` - Flask REST API (230 lines)
- `map/db_to_geojson_pg.py` - GeoJSON generator (194 lines)

### Configuration
- `docker-compose.yml` - Service definitions
- `config/node_sources.json` - Polled device list
- `mosquitto/config/mosquitto.conf` - MQTT bridge config
- `map/init.sql` - PostgreSQL schema

### Deployment
- `deploy.sh` - Automated deployment script
- `run.sh` - Container entrypoint (starts all services)

### Documentation
- `README.md` - Full user documentation
- `AGENTS.md` - This file (AI agent context)

---

## 🚀 Deployment Process

### Initial Setup
```bash
cd /home/kau005/meshtastic-docker
./deploy.sh
```

**Steps:**
1. Stop old systemd service (obsolete)
2. Docker compose down
3. Clean old SQLite files
4. Build new image with PostgreSQL support
5. Start PostgreSQL first (wait 20s)
6. Start all other services
7. Follow logs

### Checking Status
```bash
docker compose ps                    # All services
docker compose logs -f meshmap       # Map services
docker compose logs -f postgres      # Database
docker compose logs -f mosquitto     # MQTT broker
```

### Accessing Services
- **Map:** http://127.0.0.1:8088
- **API:** http://127.0.0.1:8081/api/v1/nodes
- **Database:** psql -h 127.0.0.1 -U meshuser -d meshtastic

---

## 🐛 Known Issues & Solutions

### Issue: No Tromsø nodes visible
**Cause:** Heltec V3 WiFi disabled, no live mesh traffic  
**Solution:** Node poller retrieves historical data from Heltec memory  
**Status:** ✅ Resolved - 7 Tromsø nodes imported

### Issue: Database locks (SQLite)
**Cause:** Multiple processes writing simultaneously  
**Solution:** ✅ Migrated to PostgreSQL  
**Status:** Resolved

### Issue: systemd vs Docker conflict
**Cause:** Both trying to access /dev/ttyUSB0  
**Solution:** ✅ Disabled systemd service, USB polling now in Docker  
**Status:** Resolved

### Issue: Protobuf API change
**Cause:** packet.from_field → packet.from in meshtastic 2.7.x  
**Solution:** ✅ Fixed with getattr(packet, 'from', None) fallback  
**Status:** Resolved

---

## 📝 Change Log

### 2025-10-02: PostgreSQL Migration
- ✅ Replaced SQLite with PostgreSQL 16
- ✅ Added concurrent multi-source support
- ✅ Created node_poller.py for device polling
- ✅ Created node_api.py for HTTP push
- ✅ Refactored all collectors to use psycopg2
- ✅ Added config/node_sources.json for extensibility
- ✅ Disabled conflicting systemd service
- ✅ Full documentation (README.md)

### Previous (2025-09-27)
- Created original SQLite-based system
- MQTT collector with protobuf decoding
- USB collector via systemd
- Database lock issues identified

---

**End of Agent Context** 🤖
