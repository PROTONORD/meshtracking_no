# Meshtastic Multi-Source Tracking System

**Last Updated:** 2025-10-02 23:55 UTC  
**Status:** ✅ PRODUCTION READY - Dynamic Discovery + Enhanced Interactive UI

---

## 🚀 LATEST UPDATES (2025-10-02)

### ✨ Major UI Enhancements
- ✅ **Auto-zoom on filter** - Kartet zoomer inn på filtrerte noder automatisk
- ✅ **Smart zoom nivåer** - Tilpasset zoom basert på antall noder (1 node = zoom 14, 10+ = auto)
- ✅ **Visual distinction** - Lokale noder (USB/WiFi) har svart ring, MQTT-noder har hvit ring
- ✅ **Mobile-optimized layout** - Komplett redesign med favoritter øverst, søk nederst
- ✅ **Clickable filter badges** - Aktiv/inaktiv toggle for alle filtre
- ✅ **Favorite chips bar** - Klikk på favoritt for å zoome direkte til noden
- ✅ **Reset button** - Nullstill zoom og vis alle noder
- ✅ **Empty state messages** - Tydelig feedback når ingen noder matcher filter

### 🔧 Dynamic Device Manager
- ✅ Auto-discovery av USB og WiFi Meshtastic-enheter
- ✅ Automatisk nettverksdeteksjon med netifaces (skanner alle lokale nettverk)
- ✅ Tailscale-støtte (100.64.0.0/10 CGNAT-range)
- ✅ Redusert polling-intervall til 30 sekunder for sanntidsoppdateringer
- ✅ Persistent device registry med auto-cleanup etter 10 feil
- ✅ PostgreSQL migrering komplett (port 5434, unngår konflikt med Synapse)

### 🎯 Current System Performance
- **Active Devices:** 2/2 responding
  - USB-ttyUSB0: 27 nodes retrieved
  - WiFi-172.19.228.51: 6 nodes retrieved
- **Total Database Nodes:** 165
  - MQTT: 136 (9 med GPS)
  - USB: 23 (9 med GPS)
  - WiFi: 6 (5 med GPS)
- **Nodes on Map:** 23 (global + lokal distribusjon)
- **Discovery Interval:** 60 sekunder
- **Poll Interval:** 30 sekunder

- **Database:** PostgreSQL 16-alpine on port 5434  - 🔍 **Søkebar nederst** - Med trails/favoritt-checkboxer på samme linje

  - 🗺️ **Kart i sentrum** - Maksimal visningsflate

---

- **Color-coded status:**

## 📋 PROJECT HISTORY  - 🔵 **Blå** - Favoritt-noder (kan legges til via popup)

  - 🟢 **Grønn** - Online (last heard < 30 min)

### 2025-10-02: Dynamic Device Manager & UI Redesign  - 🟠 **Orange** - Recent (last heard < 2 hours)

- Implemented automatic device discovery system  - ⚪ **Grå** - Offline (last heard > 2 hours)

- Network auto-detection (no hardcoded IP ranges)  

- Mobile-friendly UI with clickable filters, favorites, zoom controls- **Enhanced popup info:**

- Norwegian timestamp formatting & status-based color coding  - ⭐ **Favoritt-knapp** - Klikk for å legge til/fjerne favoritter (lagres i browser)

- PostgreSQL migration (SQLite → PostgreSQL)  - Node ID, short name, hardware, role

  - Battery level (%), voltage (V), SNR (dB), altitude (m)

### 2025-09-27: M3 Server Discovery  - Channel utilization (%), Air util TX (%)

- Investigated OLD server (.199) for backup scripts  - Source (mqtt, usb-node-1, usb-node-2, iot-wifi-node)

- Documented cron/syslog configuration  - **Norwegian timestamp:** "02.10.2025 kl. 15:45" (Europe/Oslo)

  - Time since last heard: "For 15m siden"

---

---

## 🏗️ SYSTEM ARCHITECTURE

## 🏗️ Architecture

### Data Sources

1. **MQTT Collector**: Global Meshtastic network (msh/#)```

2. **Device Manager**: Auto-discovers and polls local devicesGlobal MQTT (mqtt.meshtastic.org)

   - USB serial devices         ↓

   - WiFi/TCP devices      Mosquitto Bridge ──────→ mqtt_collector_pg.py

   - Persistent state management         ↓                            ↓

                              PostgreSQL

### Technology Stack         ↓                            ↑

- **Frontend**: Leaflet 1.9.4, localStorage, FlexboxHeltec #1 (/dev/ttyUSB0) ─┐          │

- **Backend**: Python 3.12, PostgreSQL 16, MQTT, FlaskHeltec #2 (/dev/ttyUSB1) ─┼→ node_poller.py (5min)

- **Discovery**: netifaces, nmap, meshtastic libraryWiFi IoT (192.168.4.50)  ─┘          │

                                     │

---                              db_to_geojson_pg.py (60s)

                                     ↓

## 🎨 USER INTERFACE                              nodes.geojson

                                     ↓

### Features                            Web Map (:8088)

- Interactive map with clustered markers                            API (:8081)

- Status colors: 🔵 Favorites | 🟢 Online | 🟠 Recent | ⚫ Offline```

- Clickable filter badges with auto-zoom

- Favorite chips bar with click-to-zoom---

- Full-width search bar

- Empty state feedback## 📦 Services

- Reset button

### docker-compose.yml

---- **postgres** - PostgreSQL 16 (port 5432)

- **mosquitto** - MQTT bridge (port 1883)

## 🚀 DEPLOYMENT- **meshmap** - Python multi-service container

  - mqtt_collector_pg.py

```bash  - node_poller.py

cd /home/kau005/meshtastic-docker  - node_api.py  

docker compose build meshmap  - db_to_geojson_pg.py

docker compose up -d  - HTTP server (ports 8088, 8081)

```

### config/node_sources.json (FINAL CONFIG)

### Access```json

- **Map**: http://server-ip:8088{

- **API**: http://server-ip:8081  "sources": [

- **PostgreSQL**: localhost:5434    {

      "type": "serial",

---      "path": "/dev/ttyUSB0",

      "name": "usb-node-1",

## 📊 MONITORING      "enabled": true

    },

```bash    {

# Live logs      "type": "serial",

docker logs -f meshtastic-map | grep "✅\|📡\|🔌"      "path": "/dev/ttyUSB1",

      "name": "usb-node-2",

# Device registry      "enabled": true

cat /home/kau005/meshtastic-data/config/device_registry.json    },

    {

# Database stats      "type": "tcp",

docker exec meshtastic-postgres psql -U meshuser -d meshtastic -c \      "host": "192.168.4.50",

  "SELECT source, COUNT(*) FROM nodes GROUP BY source;"      "port": 4403,

```      "name": "iot-wifi-node",

      "enabled": true

---    }

  ]

## 📝 KNOWN NODES (Tromsø Area)}

```

- **!433ae8bc** - Tromsøskapere

- **!b1012987** - UiT Router 1---

- **!f9ae3e44** - PROTONORD Meshtastic

- **!435ba518** - Voyager## 🚀 DEPLOYMENT

- **!433af6d4** - torbis

- **!433ad9f8** - Nord GA3### One-command deployment:

```bash

Total: 29 local nodescd /home/kau005/meshtastic-docker

./deploy-final.sh

---```



## 🔍 TROUBLESHOOTING### What it does:

1. Stops old systemd service

### Device Not Discovered2. Stops Docker containers

```bash3. Cleans old SQLite files

nc -zv 172.19.228.51 44034. Builds new PostgreSQL-based image

docker exec meshtastic-map /app/scan_network.sh 172.19.228.0/245. Starts PostgreSQL (waits 20s)

```6. Starts all services

7. Shows health checks

### No Nodes Retrieved

- Wait 2-3 minutes for initialization---

- Check Meshtastic WiFi/BT enabled

- Verify logs: `docker logs meshtastic-map | grep "Retrieved"`## ✅ VERIFICATION



---### Check all services running:

```bash

## 📚 DOCUMENTATIONdocker compose ps

```

- `DEVICE_MANAGER.md` - Device manager guide

- `README.md` - Project overview### Watch node polling:

- `docker-compose.yml` - Configuration```bash

- `map/init.sql` - Database schemadocker compose logs -f meshmap | grep "Retrieved"

```

---

### Check database sources:

## 👥 PROJECT```bash

docker exec meshtastic-postgres psql -U meshuser -d meshtastic \

**Repository:** https://github.com/PROTONORD/meshtracking_no    -c "SELECT source, COUNT(*) as nodes FROM nodes GROUP BY source;"

**Maintained by:** PROTONORD```



**Status:** 🟢 OPERATIONAL  Expected output:

**Last Check:** 2025-10-02 21:40 UTC```

     source      | nodes
-----------------+-------
 mqtt            |  8
 usb-node-1      |  7
 usb-node-2      |  9
 iot-wifi-node   |  12
```

### Check GeoJSON:
```bash
curl -s http://127.0.0.1:8088/nodes.geojson | jq '.nodeCount'
```

Should show 30+

---

## 🌐 ACCESS

- **Web Map:** http://127.0.0.1:8088
- **API:** http://127.0.0.1:8081/api/v1/nodes  
- **PostgreSQL:** localhost:5432 (meshuser/meshpass2025/meshtastic)

---

## 📊 SUCCESS INDICATORS

### Logs should show:
```
✓ Connected to MQTT broker at mosquitto:1883
✓ Subscribed to topic: msh/#
✓ Connected to Meshtastic device
✓ Listening for packets...
Polling source: usb-node-1 (serial)
✓ Retrieved 7 nodes from usb-node-1 to database
Polling source: usb-node-2 (serial)
✓ Retrieved 9 nodes from usb-node-2 to database
Polling source: iot-wifi-node (tcp)
✓ Retrieved 12 nodes from iot-wifi-node to database
📡 position: !433ad9f8 via msh/EU_868/2/e/...
📍 Found 36 nodes with coordinates
✓ Wrote 36 nodes to /data/nodes.geojson
```

### Map should show:
- 30+ colored markers (nodes)
- Node names on hover/click
- Position trails (lines)
- Mix of European and Norwegian nodes

---

## Database Schema (PostgreSQL)

```sql
CREATE TABLE nodes (
    node_id TEXT PRIMARY KEY,           -- !12345678
    node_num BIGINT UNIQUE,
    long_name TEXT,
    short_name TEXT,
    hw_model TEXT,
    role TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    altitude DOUBLE PRECISION,
    battery_level INTEGER,
    voltage DOUBLE PRECISION,
    snr DOUBLE PRECISION,
    last_heard TIMESTAMP WITH TIME ZONE,
    source TEXT,                        -- 'mqtt', 'usb-node-1', etc
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE positions (
    node_id TEXT REFERENCES nodes(node_id),
    timestamp TIMESTAMP WITH TIME ZONE,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    altitude DOUBLE PRECISION,
    source TEXT
);

CREATE TABLE telemetry (
    node_id TEXT REFERENCES nodes(node_id),
    timestamp TIMESTAMP WITH TIME ZONE,
    battery_level INTEGER,
    voltage DOUBLE PRECISION,
    channel_utilization DOUBLE PRECISION,
    air_util_tx DOUBLE PRECISION,
    source TEXT
);

CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    node_id TEXT,
    message TEXT,
    timestamp TIMESTAMP WITH TIME ZONE,
    to_node TEXT,
    channel INTEGER,
    source TEXT
);
```

---

## 🔧 Troubleshooting

### No USB devices:
```bash
ls -la /dev/ttyUSB*
sudo usermod -a -G dialout $USER
# Log out and back in
```

### WiFi node not responding:
```bash
timeout 2 bash -c "echo > /dev/tcp/192.168.4.50/4403" && echo "OK"
```

### No nodes on map:
```bash
# Check GeoJSON
curl -s http://127.0.0.1:8088/nodes.geojson | jq '.features | length'

# Check database
docker exec meshtastic-postgres psql -U meshuser -d meshtastic \
  -c "SELECT COUNT(*) FROM nodes WHERE latitude IS NOT NULL;"

# Restart
docker compose restart meshmap
```

### View errors:
```bash
docker compose logs meshmap | grep -i error
```

---

## 📝 Files Created/Modified

### Python Services:
- `map/mqtt_collector_pg.py` - MQTT → PostgreSQL
- `map/node_poller.py` - USB/TCP polling (reads config)
- `map/node_api.py` - HTTP REST API
- `map/db_to_geojson_pg.py` - PostgreSQL → GeoJSON

### Configuration:
- `config/node_sources.json` - 3 sources configured
- `docker-compose.yml` - Triple source setup
- `map/init.sql` - PostgreSQL schema
- `map/Dockerfile` - Updated with PostgreSQL deps

### Scripts:
- `deploy-final.sh` - Main deployment
- `find-all-devices.sh` - USB scanner
- `scan-iot-network.sh` - WiFi scanner
- `check-system.sh` - Health checks

### Documentation:
- `README.md` - Full user guide (4000+ lines)
- `AGENTS.md` - This file
- `QUICKSTART.md` - Quick reference
- `DUAL-USB-SETUP.md` - USB guide

---

## 📈 Performance

### Expected Metrics:
- MQTT messages: 50-200/min
- Node polling: Every 5 min (300s)
- GeoJSON generation: Every 60s
- Database size: ~50MB/month
- CPU: <10% average
- Memory: ~500MB total (all containers)

---

## 🎉 Migration Complete

### From:
- ❌ SQLite with locking issues
- ❌ Single USB collector (systemd)
- ❌ systemd vs Docker conflicts
- ❌ Limited concurrent writes

### To:
- ✅ PostgreSQL (concurrent writes)
- ✅ Multi-source polling (3 devices)
- ✅ Everything in Docker
- ✅ Scalable architecture
- ✅ HTTP API for remote nodes
- ✅ 30+ nodes visible

---

## 🔐 Security Notes

### Change defaults:
```yaml
# docker-compose.yml
NODE_API_KEY: "your-secret-here"
POSTGRES_PASSWORD: "your-password-here"
DB_PASSWORD: "your-password-here"
```

### Firewall:
```bash
# Restrict to localhost only
sudo ufw allow from 127.0.0.1 to any port 8088
sudo ufw allow from 127.0.0.1 to any port 8081
```

---

## 📚 Key Commands

```bash
# Deploy
./deploy-final.sh

# Status
docker compose ps
docker compose logs -f meshmap

# Database
docker exec meshtastic-postgres psql -U meshuser -d meshtastic

# Restart
docker compose restart meshmap

# Full restart
docker compose down
docker compose up -d

# Rebuild
docker compose build meshmap
docker compose up -d meshmap
```

---

## 🎯 Next Steps

Potential expansions:
- Add more WiFi nodes from 192.168.4.0/24
- Add Tailscale remote nodes
- Web UI for managing sources
- Prometheus metrics
- Grafana dashboard
- Coverage heatmap
- Historical replay

---

## ✨ READY TO DEPLOY

**Status:** All configured ✅  
**Command:** `./deploy-final.sh`  
**Expected:** 30+ nodes on map  
**Timeline:** 10 minutes to full operation  

**LET'S GO! 🚀**

---

**End of Agent Context** 🤖


**Location**: `/var/lib/docker/volumes/meshtastic-docker_map-data/_data/nodes.db`

### Nodes Table
```sql
CREATE TABLE IF NOT EXISTS nodes (
    node_id TEXT PRIMARY KEY,
    long_name TEXT,
    short_name TEXT,
    hw_model TEXT,
    latitude REAL,
    longitude REAL,
    altitude INTEGER,
    battery_level INTEGER,
    snr REAL,
    last_heard INTEGER,
    first_seen INTEGER,
    channel_util REAL,
    tx_air_util REAL,
    UNIQUE(node_id)
);
```

### Position History Table
```sql
CREATE TABLE IF NOT EXISTS position_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    altitude INTEGER,
    timestamp INTEGER NOT NULL,
    FOREIGN KEY(node_id) REFERENCES nodes(node_id)
);
```

**Data Retention**: 24 hours (controlled by `HISTORY_WINDOW_SECONDS=86400`)

## MQTT Message Format

The system handles two message formats:

### 1. JSON Messages
**Topics**: `msh/EU_868/*/json/*`
```json
{
  "id": "!433ad9f8",
  "from": 1127743992,
  "type": "nodeinfo",
  "payload": {
    "longname": "Nord GA3",
    "shortname": "GA3",
    "hardware": "HELTEC_V3",
    "latitude": 69.7041,
    "longitude": 19.0579
  }
}
```

### 2. Protobuf Messages
**Topics**: 
- `msh/EU_868/*/map/` - Map reports with position
- `msh/EU_868/*/e/*` - Encrypted mesh packets

**Decoding**: Uses `meshtastic` Python library
```python
from meshtastic.protobuf import mqtt_pb2, mesh_pb2
envelope = mqtt_pb2.ServiceEnvelope()
envelope.ParseFromString(payload)
```

## Key Files Reference

### Configuration Files
```
meshtastic-docker/
├── docker-compose.yml          # Container orchestration
├── mosquitto/
│   └── config/
│       ├── mosquitto.conf      # Broker + bridge config
│       └── passwd              # MQTT authentication
├── config/
│   ├── config.yaml             # MeshtasticD main config
│   └── config.d/
│       └── mqtt.yaml           # MeshtasticD MQTT settings
└── map/
    ├── Dockerfile              # Map container build
    ├── requirements.txt        # Python dependencies
    ├── mqtt_collector.py       # NEW: MQTT subscriber
    ├── generate_geojson.py     # GeoJSON generator
    ├── run.sh                  # Container entrypoint
    └── index.html              # Web map interface
```

### Data Volumes
```
/var/lib/docker/volumes/meshtastic-docker_map-data/_data/
├── nodes.geojson               # Current node positions
├── trails.geojson              # Movement history trails
├── nodes.db                    # SQLite database
├── index.html                  # Web map (copied from build)
└── config/
    └── favorites.json          # Favorite nodes configuration
```rk visualization system. Last updated: 2025-10-02

## System Architecture Overview

This is a **hybrid mesh network tracking system** that combines:
1. **Global mesh data** from `mqtt.meshtastic.org` (worldwide Meshtastic network)
2. **Local LoRa radio data** from physical Heltec V3 gateway in Tromsø, Norway

All data flows into a centralized database and is visualized on an interactive web map.

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA SOURCES                                  │
├─────────────────────────────────────────────────────────────────┤
│  Global MQTT                    Local LoRa Radio                │
│  mqtt.meshtastic.org     →      Heltec V3 (USB/WiFi)           │
│  (EU_868 region)                (Tromsø mesh network)           │
└──────────────┬──────────────────────────┬───────────────────────┘
               │                          │
               └────────► MQTT Bridge ◄───┘
                              │
                    ┌─────────▼─────────┐
                    │ Mosquitto Broker  │
                    │ (meshtastic-      │
                    │  mosquitto:1883)  │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────────┐
                    │ MQTT Collector        │
                    │ (mqtt_collector.py)   │
                    │ - Subscribes msh/#    │
                    │ - Decodes protobuf    │
                    │ - Parses JSON         │
                    └─────────┬─────────────┘
                              │
                    ┌─────────▼─────────────┐
                    │ SQLite Database       │
                    │ (nodes.db)            │
                    │ - Nodes table         │
                    │ - Position history    │
                    │ - 24h window          │
                    └─────────┬─────────────┘
                              │
                    ┌─────────▼─────────────┐
                    │ GeoJSON Generator     │
                    │ (generate_geojson.py) │
                    │ - nodes.geojson       │
                    │ - trails.geojson      │
                    └─────────┬─────────────┘
                              │
                    ┌─────────▼─────────────┐
                    │ Leaflet Web Map       │
                    │ (index.html)          │
                    │ :8088                 │
                    └───────────────────────┘
```

## Container Stack

### 1. `meshtastic-mosquitto` (Eclipse Mosquitto 2.0.22)
**Role**: Central MQTT message broker with bridge functionality

**Key Features**:
- Listens on port `1883` (LAN exposed: `0.0.0.0:1883`)
- Authentication required: `meshlocal` / `meshLocal2025`
- **MQTT Bridge** to `mqtt.meshtastic.org`:
  - Subscribes to `msh/EU_868/#` (European mesh network)
  - Subscribes to `msh/2/e/#` (encrypted messages)
  - Acts as aggregation point for global + local data

**Configuration**:
- `mosquitto/config/mosquitto.conf` - Main config with bridge settings
- `mosquitto/config/passwd` - Password file (mosquitto_passwd format)
- `mosquitto/data/` - Persistence storage
- `mosquitto/log/mosquitto.log` - Activity logs

**Bridge Config**:
```conf
connection meshtastic-global
address mqtt.meshtastic.org:1883
remote_username meshdev
remote_password large4cats
topic msh/EU_868/# in 0 "" ""
topic msh/2/e/# in 0 "" ""
bridge_protocol_version mqttv311
```

### 2. `meshtasticd` (MeshtasticD native daemon)
**Role**: Originally intended as MQTT gateway, currently **deprecated** in favor of direct MQTT collection

**Status**: Running in simulator mode but not actively used for data processing
- Port 4403: API interface
- Port 9443: Web UI
- Issue: MQTT proxy mode doesn't reliably process incoming messages

**Note for AI agents**: This container may be removed in future iterations as `mqtt_collector.py` replaced its functionality.

### 3. `meshtastic-map` (Custom Python + HTTP server)
**Role**: Data collection, processing, and web serving

**Components**:
1. **`mqtt_collector.py`** (NEW - 2025-10-02)
   - Subscribes to Mosquitto broker (`mosquitto:1883`)
   - Topics: `msh/#` (all Meshtastic messages)
   - Decodes Meshtastic protobuf messages
   - Parses JSON formatted messages
   - Stores to SQLite database (`/data/nodes.db`)
   - Runs continuously as background process

2. **`generate_geojson.py`**
   - Reads from SQLite database
   - Generates `nodes.geojson` for current positions
   - Generates `trails.geojson` for movement history
   - Updates every 60 seconds (configurable via `POLL_INTERVAL`)
   - Applies favorites/labels from `config/favorites.json`

3. **`run.sh`**
   - Initializes `/data` directory structure
   - Seeds `config/favorites.json` if missing
   - Starts `mqtt_collector.py` in background
   - Starts `generate_geojson.py` in background  
   - Launches HTTP server on port 8080

4. **Leaflet Web Frontend** (`index.html`)
   - Interactive map interface
   - Search functionality
   - Favorites filtering
   - Trail visualization
   - Node popups with metadata

**Environment Variables**:
```bash
MQTT_BROKER=mosquitto
MQTT_PORT=1883
MQTT_USERNAME=meshlocal
MQTT_PASSWORD=meshLocal2025
OUTPUT_PATH=/data/nodes.geojson
TRAILS_OUTPUT_PATH=/data/trails.geojson
POLL_INTERVAL=60
DB_PATH=/data/nodes.db
FAVORITES_FILE=/data/config/favorites.json
HISTORY_WINDOW_SECONDS=86400  # 24 hours
TRAIL_MAX_POINTS=500
```

### 4. `tailscale` (Tailscale VPN - Optional)
**Status**: Disabled by default due to host conflicts
- Can provide secure remote access to map
- Requires `/dev/net/tun` device access

## Volumes & Files
- `map-data` volume contains:
  - `index.html` (served file)
  - `nodes.geojson`, `trails.geojson`
  - `nodes.db` (SQLite history; 24h window by default)
  - `config/favorites.json` (favorite nodes, labels, notes)
- Use `docker exec meshtastic-map` to inspect data: `sqlite3 /data/nodes.db`, `cat /data/trails.geojson`, etc.
- Heltec gateway (`!db2f13c0`) is pre-loaded as favorite with label “Heltec Gateway”. Update this file to change favourites.

## Common Operations

### Monitoring and Debugging

**Check container status**:
```bash
cd /home/kau005/meshtastic-docker
docker compose ps
```

**View MQTT traffic**:
```bash
# Subscribe to all topics
docker exec -i meshtastic-mosquitto mosquitto_sub -h 127.0.0.1 -u meshlocal -P meshLocal2025 -t 'msh/#' -v

# Filter for specific node
docker exec -i meshtastic-mosquitto mosquitto_sub -h 127.0.0.1 -u meshlocal -P meshLocal2025 -t 'msh/#' -v | grep "db2f13c0"
```

**Check Mosquitto bridge status**:
```bash
docker exec meshtastic-mosquitto tail -f /mosquitto/log/mosquitto.log | grep -i bridge
```

**Inspect database**:
```bash
# Count nodes
docker exec meshtastic-map sqlite3 /data/nodes.db "SELECT COUNT(*) FROM nodes;"

# List nodes with positions
docker exec meshtastic-map sqlite3 /data/nodes.db "SELECT node_id, long_name, latitude, longitude, last_heard FROM nodes WHERE latitude IS NOT NULL ORDER BY last_heard DESC LIMIT 10;"

# View position history
docker exec meshtastic-map sqlite3 /data/nodes.db "SELECT * FROM position_history WHERE node_id='!db2f13c0' ORDER BY timestamp DESC LIMIT 5;"
```

**View logs**:
```bash
docker logs -f meshtastic-map          # Map container
docker logs -f meshtastic-mosquitto    # Mosquitto broker
docker logs -f meshtasticd             # MeshtasticD (if used)
```

**Check local Heltec gateway**:
```bash
# View MQTT config
sg dialout '~/.local/bin/meshtastic --port /dev/ttyUSB0 --get mqtt'

# List nodes seen by gateway
sg dialout '~/.local/bin/meshtastic --port /dev/ttyUSB0 --nodes'

# Device info
sg dialout '~/.local/bin/meshtastic --port /dev/ttyUSB0 --info'
```

### Maintenance

**Restart services**:
```bash
cd /home/kau005/meshtastic-docker
docker compose restart mosquitto    # Restart broker only
docker compose restart meshmap      # Restart map + collectors
docker compose restart              # Restart all
```

**Rebuild after code changes**:
```bash
cd /home/kau005/meshtastic-docker
docker compose build meshmap
docker compose up -d meshmap
```

**Clear database and start fresh**:
```bash
docker exec meshtastic-map rm /data/nodes.db
docker compose restart meshmap
```

**Update Mosquitto password**:
```bash
cd /home/kau005/meshtastic-docker
docker run --rm -v "$PWD/mosquitto/config:/mosquitto/config" eclipse-mosquitto mosquitto_passwd -b /mosquitto/config/passwd <username> <password>
docker compose restart mosquitto
```

### Configuration Changes

**Modify favorites** (marks nodes on map):
```bash
docker exec -it meshtastic-map sh -c 'cat > /data/config/favorites.json << EOF
{
  "favorites": ["!db2f13c0", "!433ad9f8"],
  "labels": {
    "!db2f13c0": "Heltec Gateway", 
    "!433ad9f8": "Nord GA3"
  },
  "notes": {
    "!db2f13c0": "USB gateway node on meshtracking server",
    "!433ad9f8": "Remote node in northern Tromsø"
  }
}
EOF'
```
*Changes auto-load within ~60 seconds*

**Adjust data retention** (default 24h):
Edit `docker-compose.yml`:
```yaml
environment:
  HISTORY_WINDOW_SECONDS: "172800"  # 48 hours
```

**Change update interval** (default 60s):
Edit `docker-compose.yml`:
```yaml
environment:
  POLL_INTERVAL: "30"  # 30 seconds
```

## Network Access

### Local Access
- **LAN**: `http://172.19.228.175:8088/`
- **Localhost**: `http://127.0.0.1:8088/` (from server)

### Public Access
- **HTTPS**: `https://meshtracking.no/` (via Apache reverse proxy)
- **Tailscale**: `https://meshtastic.tail952c08.ts.net/` (when enabled)

### API Endpoints
- **MeshtasticD API**: `http://127.0.0.1:4403` (not actively used)
- **MeshtasticD Web UI**: `http://127.0.0.1:9443` (not actively used)
- **MQTT Broker**: `mqtt://172.19.228.175:1883` (requires auth)

## Development History & Architecture Decisions

### 2025-10-02 (Evening): Protobuf API Fix - System Now Operational ✅

**BREAKTHROUGH**: Fixed critical protobuf parsing bug - system now fully functional!

**Problem Identified**:
- mqtt_collector.py connected to MQTT successfully
- Received 100+ messages/minute from global bridge
- But ALL messages failed parsing with:
  - `AttributeError: from_field` (most common)
  - `DecodeError: Error parsing message` (JSON messages)
- **0 nodes appeared on map despite MQTT traffic**

**Root Cause**:
Meshtastic Python library updated protobuf API in version 2.7.0+:
- OLD API: `packet.from_field` and `packet.to`
- NEW API: `packet.from` and `packet.to`
- Code was using old `from_field` attribute which no longer exists

**Solution Implemented**:
```python
# BEFORE (broken):
from_id = f"!{packet.from_field:08x}"
from_num = packet.from_field

# AFTER (fixed):
from_num = getattr(packet, 'from', None) or getattr(packet, 'from_field', None)
from_id = f"!{from_num:08x}" if from_num else None
```

**Additional Fixes**:
1. Added `flush=True` to all print() statements (Docker background process logging)
2. Changed exception handling from silent `pass` to logging `DEBUG:` messages
3. Enabled line buffering with `sys.stdout.reconfigure(line_buffering=True)`

**Verification Results**:
```
✓ !7116235a (1897276250) - ['LongFast', '!fa75f7c0']  ← Netherlands
✓ !55c72b20 (1439116064) - ['LongFast', '!55c73294']  ← South Africa  
✓ !16c3f6dc (...)                                       ← Germany
✓ !9ea1f790 (...)                                       ← Germany

Nodes with coordinates: 4
Total positions: 217
Map displays: 4 active nodes across Europe/Africa
```

**Status**: ✅ **SYSTEM FULLY OPERATIONAL**
- MQTT bridge: ✅ Receiving global traffic
- mqtt_collector.py: ✅ Parsing and storing messages
- Database: ✅ Nodes table populating with GPS coordinates
- GeoJSON: ✅ Generating valid features
- Map: ✅ Displaying live global mesh network

---

### 2025-10-02 (Morning): Major Architecture Redesign

**Problem Identified**:
- Initial design used MeshtasticD as MQTT gateway
- MeshtasticD's MQTT proxy mode (`ProxyToClientEnabled: true`) failed to process incoming MQTT messages
- Data from global MQTT bridge never reached the map
- Local Heltec V3 data wasn't being visualized

**Root Cause**:
- MeshtasticD is designed to **publish** LoRa packets to MQTT, not **consume** from MQTT
- Simulator mode doesn't process external MQTT topics effectively
- API-based data retrieval from MeshtasticD only showed simulator node

**Solution Implemented**:
Created **direct MQTT→Database pipeline**:

1. **`mqtt_collector.py`** (NEW):
   - Direct subscription to Mosquitto broker
   - Handles both protobuf and JSON message formats
   - Decodes Meshtastic packets using official Python library
   - Stores directly to SQLite database
   - Runs as persistent background process

2. **Modified `generate_geojson.py`**:
   - Removed dependency on MeshtasticD API
   - Now reads exclusively from SQLite database
   - Simpler, more reliable data flow

3. **Benefits**:
   - ✅ Eliminates MeshtasticD bottleneck
   - ✅ Processes 100+ messages/minute from global MQTT
   - ✅ Captures local Heltec V3 radio packets
   - ✅ Single source of truth (SQLite database)
   - ✅ Easier to debug and maintain

**Architecture Evolution**:

```
BEFORE (Failed):
[Global MQTT + Heltec] → [Mosquitto] → [MeshtasticD API] → [generate_geojson.py] → [Map]
                                            ❌ Bottleneck

AFTER (Working):
[Global MQTT + Heltec] → [Mosquitto] → [mqtt_collector.py] → [SQLite DB] → [generate_geojson.py] → [Map]
                                            ✅ Direct pipeline
```

### Key Mosquitto Bridge Configuration

The bridge is crucial for hybrid data collection:

```conf
# Bridge to public Meshtastic MQTT
connection meshtastic-global
address mqtt.meshtastic.org:1883
remote_username meshdev
remote_password large4cats

# Subscribe to European region
topic msh/EU_868/# in 0 "" ""

# Subscribe to encrypted packets
topic msh/2/e/# in 0 "" ""

# Protocol settings
bridge_protocol_version mqttv311
cleansession true
try_private false
```

**Why this works**:
- Mosquitto acts as transparent proxy
- Local clients (mqtt_collector.py) see both:
  - Global traffic from mqtt.meshtastic.org
  - Local traffic from Heltec V3 gateway
- Single subscription point (`msh/#`)

### System Requirements

**Host System**:
- Ubuntu Server (tested on Ubuntu 22.04+)
- Docker & Docker Compose
- Snap mosquitto service must be **disabled** (port conflict)
```bash
sudo snap stop mosquitto
sudo snap disable mosquitto
```

**User Permissions**:
- User must be in `dialout` group for Heltec V3 USB access:
```bash
sudo usermod -a -G dialout $USER
# Re-login required
```

**Python Dependencies** (in container):
- meshtastic>=2.3.0
- paho-mqtt>=1.6.0
- protobuf>=4.0.0

## Troubleshooting Guide

### **CRITICAL: Protobuf API Changes (meshtastic >= 2.7.0)**

**Problem**: mqtt_collector.py shows `AttributeError: from_field` or DecodeError  
**Cause**: Meshtastic Python library changed protobuf attribute names

**Solution**: In `mqtt_collector.py`, replace:
```python
# OLD (broken in meshtastic >= 2.7.0):
from_id = f"!{packet.from_field:08x}"
to_id = f"!{packet.to:08x}"
from_num = packet.from_field

# NEW (compatible):
from_num = getattr(packet, 'from', None) or getattr(packet, 'from_field', None)
to_num = getattr(packet, 'to', None)
from_id = f"!{from_num:08x}" if from_num else None
to_id = f"!{to_num:08x}" if to_num else None
```

**Verification**:
```bash
docker logs meshtastic-map 2>&1 | grep "✓"
```
Should show: `✓ !7116235a (1897276250) - ['LongFast', '!fa75f7c0']`

**Background**: The protobuf field `from_field` was renamed to `from` in newer versions. The code now uses `getattr()` with fallback for compatibility with both old and new versions.

### No nodes appearing on map

**Check 1**: Verify MQTT broker is receiving data
```bash
timeout 10 docker exec -i meshtastic-mosquitto mosquitto_sub -h 127.0.0.1 -u meshlocal -P meshLocal2025 -t 'msh/#' -v -C 5
```
Should show messages. If empty, bridge is not working.

**Check 2**: Verify mqtt_collector is running
```bash
docker exec meshtastic-map ps aux | grep mqtt_collector
```

**Check 3**: Check database for nodes
```bash
docker exec meshtastic-map sqlite3 /data/nodes.db "SELECT COUNT(*) FROM nodes;"
```

**Check 4**: Look for errors in logs
```bash
docker logs meshtastic-map 2>&1 | grep -i error
```

### Heltec V3 not publishing data

**Check 1**: Verify device is connected
```bash
ls -la /dev/ttyUSB*
```

**Check 2**: Check MQTT configuration
```bash
sg dialout '~/.local/bin/meshtastic --port /dev/ttyUSB0 --get mqtt'
```
Should show:
- `mqtt.enabled: True`
- `mqtt.address: meshtracking.no`

**Check 3**: Verify WiFi is connected
```bash
sg dialout '~/.local/bin/meshtastic --port /dev/ttyUSB0 --get wifi'
```

**Check 4**: Monitor Mosquitto for Heltec traffic
```bash
docker exec -i meshtastic-mosquitto mosquitto_sub -h 127.0.0.1 -u meshlocal -P meshLocal2025 -t 'msh/EU_868/#' -v | grep "db2f13c0"
```

### Mosquitto bridge not connecting

**Check 1**: View bridge status in logs
```bash
docker exec meshtastic-mosquitto grep -i "bridge\|connect" /mosquitto/log/mosquitto.log | tail -20
```

**Check 2**: Test connectivity to public MQTT
```bash
docker exec meshtastic-mosquitto nc -zv mqtt.meshtastic.org 1883
```

**Check 3**: Restart bridge
```bash
docker compose restart mosquitto
```

### Database not updating

**Check 1**: Verify write permissions
```bash
docker exec meshtastic-map ls -la /data/nodes.db
```

**Check 2**: Check for database locks
```bash
docker exec meshtastic-map fuser /data/nodes.db
```

**Check 3**: Restart collectors
```bash
docker compose restart meshmap
```

## Future Improvements / TODO

- [ ] **Add historical data export** (CSV/KML format)
- [ ] **Implement node alerting** (notify when specific nodes appear/disappear)
- [ ] **Add more physical nodes** to Tromsø mesh network
- [ ] **Configure private mesh channel** with custom PSK
- [ ] **Optimize database** (indexes for frequent queries)
- [ ] **Add heatmap visualization** (node density over time)
- [ ] **Implement API endpoint** for programmatic access to node data
- [ ] **Add Prometheus metrics** for monitoring
- [ ] **Consider removing MeshtasticD container** entirely (no longer needed)
- [ ] **Add automated backups** of nodes.db
- [ ] **Implement node statistics dashboard** (uptime, message counts, etc.)

## References & Documentation

- **Meshtastic Official**: https://meshtastic.org/
- **Meshtastic Python API**: https://github.com/meshtastic/python
- **Meshtastic Protobufs**: https://buf.build/meshtastic/protobufs
- **Mosquitto Bridge**: https://mosquitto.org/man/mosquitto-conf-5.html
- **Public MQTT Server**: `mqtt.meshtastic.org:1883`
- **EU_868 Frequency**: 868 MHz (European ISM band)

## License & Credits

This is a custom implementation combining:
- Eclipse Mosquitto (Eclipse Public License)
- MeshtasticD (GPL-3.0)
- Meshtastic Python library (GPL-3.0)
- Leaflet maps (BSD-2-Clause)

**Setup Location**: Tromsø, Norway
**Maintained by**: kau005
**Last Major Update**: 2025-10-02 - Direct MQTT pipeline implementation

---

*This documentation is designed for AI agents. For questions or context gaps, examine the actual source code in `/home/kau005/meshtastic-docker/` or query the running containers.*

