# Meshtastic Multi-Source Map Visualization

**Robust, skalerbar Meshtastic node tracking med PostgreSQL og dynamisk device discovery**

## 🎯 Funksjonalitet

### 📡 Multi-Source Data Collection
- **Global MQTT bridge** (mqtt.meshtastic.org - EU_868)
- **Auto-discovery av USB Meshtastic-enheter** (automatisk deteksjon)
- **Auto-discovery av WiFi-noder** (nettverksskanning med nmap)
- **Tailscale-støtte** (VPN-tilkoblede enheter)
- **Dynamisk nettverksdeteksjon** med netifaces (alle lokale nettverk)

### 🗺️ Interaktivt Kart
- **Mobile-optimized UI** - Komplett redesign for mobil og desktop
- **Auto-zoom på filter** - Kartet zoomer automatisk inn på filtrerte noder
- **Smart zoom-nivåer** - Tilpasser zoom basert på antall synlige noder
- **Visual distinction** - Lokale noder (sort ring) vs MQTT (hvit ring)
- **Clickable filter badges** - Favoritter, Online, Nylige, Offline
- **Favorite chips bar** - Klikk på favoritt-chip for direkte zoom
- **Search & filter** - Søk etter node-ID eller navn
- **Trail visualization** - Historiske GPS-spor for mobile noder
- **Norwegian timestamps** - DD.MM.YYYY kl. HH:MM format

### 💾 Database & API
- **PostgreSQL** - Håndterer concurrent writes fra flere kilder (port 5434)
- **HTTP API** - Remote noder kan pushe data via REST API (port 8081)
- **Node polling** - Automatisk henting av node-database hvert 30. sekund
- **Persistent registry** - Device state lagres i JSON-fil
- **Auto-cleanup** - Fjerner døde enheter etter 10 påfølgende feil

---

## 🚀 Quickstart

### 1. Deploy systemet

```bash
cd /home/kau005/meshtastic-docker
./deploy.sh
```

Scriptet stopper gamle tjenester, bygger nye images, starter PostgreSQL og alle services.

### 2. Sjekk status

```bash
docker compose ps
docker compose logs -f meshmap
```

### 3. Åpne kartet

http://127.0.0.1:8088

---

## 📊 Arkitektur

```
┌─────────────────────────────────────────────────────────┐
│                  Meshtastic Map System                   │
└─────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Global MQTT  │────▶│   Mosquitto  │────▶│     MQTT     │
│ EU_868/2/e   │     │    Bridge    │     │  Collector   │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                  │
┌──────────────┐                                  │
│  Heltec V3   │────▶┌──────────────┐            │
│  USB Radio   │     │     Node     │            │
└──────────────┘     │    Poller    │            │
                     │  (USB/TCP)   │            │
┌──────────────┐     └──────┬───────┘            │
│ Remote Nodes │────▶       │                    │
│ via Tailscale│            │                    │
└──────────────┘            │                    │
                            │                    │
┌──────────────┐            │                    │
│ HTTP API     │◀───────────┼────────────────────┤
│  Port 8081   │            │                    │
└──────────────┘            ▼                    ▼
                     ┌─────────────────────────────┐
                     │     PostgreSQL Database     │
                     │  - nodes                    │
                     │  - positions                │
                     │  - telemetry                │
                     │  - messages                 │
                     └──────────┬──────────────────┘
                                │
                                ▼
                     ┌─────────────────────────────┐
                     │    GeoJSON Generator        │
                     │  (Every 60 seconds)         │
                     └──────────┬──────────────────┘
                                │
                                ▼
                     ┌─────────────────────────────┐
                     │     HTTP Server :8088       │
                     │  - index.html               │
                     │  - nodes.geojson            │
                     │  - trails.geojson           │
                     └─────────────────────────────┘
```

---

## 📁 Services

### 1. **postgres** (Port 5434)
PostgreSQL 16 database for concurrent multi-source writes.

**Note:** Port 5434 is used to avoid conflict with Synapse on port 5432.

**Environment:**
- `POSTGRES_DB=meshtastic`
- `POSTGRES_USER=meshuser`
- `POSTGRES_PASSWORD=meshpass2025`

### 2. **mosquitto** (Port 1883)
MQTT broker with bridge to mqtt.meshtastic.org

**Subscriptions:**
- `msh/EU_868/#` - European nodes (868 MHz)
- `msh/2/e/#` - Public encryption channel

### 3. **meshmap** (Ports 8080→8088, 8081)
Main application container with 5 services:

#### a. **mqtt_collector_pg.py**
- Subscribes to Mosquitto
- Decodes protobuf messages
- Stores to PostgreSQL
- Source: `mqtt`

#### b. **node_poller.py**
- Connects to Meshtastic devices every 5 minutes
- Retrieves full node database via serial/TCP
- Configurable via `/data/config/node_sources.json`
- Sources: `local-usb`, `node-*`, `tailscale-*`

#### c. **node_api.py** (Port 8081)
- HTTP REST API for remote node submissions
- Endpoint: `POST /api/v1/nodes`
- Authorization: `Bearer meshtastic-secret-2025`
- GET `/api/v1/nodes` - List all active nodes

#### d. **db_to_geojson_pg.py**
- Generates `nodes.geojson` every 60 seconds
- Generates `trails.geojson` for position history
- Prunes old positions (24h window)

#### e. **HTTP Server** (Port 8080 → 8088)
- Serves `index.html`, GeoJSON files
- Static file server for web UI

#### f. **device_manager.py** (NEW)
- Auto-discovers USB Meshtastic devices (`/dev/ttyUSB*`, `/dev/ttyACM*`)
- Scans local networks for WiFi devices (TCP port 4403)
- Uses netifaces for automatic network detection
- Supports Tailscale (100.64.0.0/10 CGNAT range)
- Persistent device registry in `/data/config/device_registry.json`
- Polls every 30 seconds, auto-cleanup after 10 failures

---

## 🎨 Web UI Features

### Mobile-Optimized Layout
- **Top bar:** Favorite chips + filter badges (Online, Nylige, Offline)
- **Map:** Fullscreen flex layout with Leaflet
- **Bottom bar:** Search input + Trails toggle + Reset button

### Interactive Filters
- **Filter badges:** Click to filter by status (online, recent, offline, favorite)
- **Auto-zoom:** Map automatically zooms to filtered nodes
- **Smart zoom levels:**
  - 1 node → zoom 14 (close-up)
  - 2-3 nodes → zoom 13 (moderate)
  - 4-10 nodes → zoom 12 (wider view)
  - 10+ nodes → auto-fit all

### Visual Distinction
- **Local nodes (USB/WiFi):**
  - Larger markers (radius 7)
  - Black ring (2.5px thick)
  - Higher opacity (0.9)
- **Global nodes (MQTT):**
  - Smaller markers (radius 6)
  - White ring (1.5px thin)
  - Lower opacity (0.7)

### Favorite Management
- **Add favorite:** Click node popup → ⭐ button
- **Favorite chips:** Click chip to zoom directly to node
- **Remove favorite:** Click ✕ on favorite chip
- **Stored locally:** Uses browser localStorage

### Status Colors
- 🔵 **Blue:** Favorite nodes
- 🟢 **Green:** Online (<30 min since last seen)
- 🟠 **Orange:** Recent (30min - 2h)
- ⚫ **Grey:** Offline (>2h)

### Search & Reset
- **Search:** Filter nodes by ID, long name, short name, or label
- **Reset:** Clear filters and zoom to show all nodes
- **Trails:** Toggle GPS trail visualization on/off

---

## ⚙️ Configuration

### Dynamic Device Discovery (Automatic)

The system automatically discovers devices - no manual configuration needed!

**Environment variables** (in `docker-compose.yml`):
- `AUTO_DETECT_NETWORKS=true` - Enable auto-discovery (default)
- `MANUAL_SCAN_NETWORKS=""` - Optional manual network ranges (e.g., "192.168.1.0/24,10.0.0.0/24")
- `DISCOVERY_INTERVAL=60` - How often to scan for new devices (seconds)
- `POLL_INTERVAL=30` - How often to poll discovered devices (seconds)
- `MAX_FAIL_COUNT=10` - Remove device after this many failures

**Device registry:** `/home/kau005/meshtastic-docker/config/device_registry.json`
- Auto-generated and maintained by device_manager.py
- Contains discovered USB and WiFi devices
- Tracks failure counts and last poll times

### Manual Node Configuration (Legacy)

Edit `/home/kau005/meshtastic-docker/config/node_sources.json`:

```json
{
  "sources": [
    {
      "type": "serial",
      "path": "/dev/ttyUSB0",
      "name": "local-usb",
      "enabled": true,
      "description": "Heltec V3 gateway"
    },
    {
      "type": "tcp",
      "host": "192.168.1.150",
      "port": 4403,
      "name": "node-livingroom",
      "enabled": true,
      "description": "Heltec in living room"
    },
    {
      "type": "tcp",
      "host": "100.64.0.5",
      "port": 4403,
      "name": "tailscale-cabin",
      "enabled": true,
      "description": "Remote cabin node"
    }
  ]
}
```

**Restart after config change:**
```bash
docker compose restart meshmap
```

### Environment Variables

In `docker-compose.yml` under `meshmap.environment`:

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | postgres | PostgreSQL hostname |
| `DB_PORT` | 5432 | PostgreSQL port |
| `DB_NAME` | meshtastic | Database name |
| `DB_USER` | meshuser | Database username |
| `DB_PASSWORD` | meshpass2025 | Database password |
| `MQTT_HOST` | mosquitto | MQTT broker hostname |
| `MQTT_PORT` | 1883 | MQTT broker port |
| `MQTT_TOPIC` | msh/# | MQTT subscription topic |
| `NODE_POLL_INTERVAL` | 300 | Node polling interval (seconds) |
| `POLL_INTERVAL` | 60 | GeoJSON generation interval |
| `HISTORY_WINDOW_SECONDS` | 86400 | Position history window (24h) |
| `NODE_API_PORT` | 8081 | HTTP API port |
| `NODE_API_KEY` | meshtastic-secret-2025 | API authentication token |

---

## 🔌 Using the HTTP API

Remote Meshtastic nodes can push data to the system:

### Authentication
```bash
Authorization: Bearer meshtastic-secret-2025
```

### Push Node Data

**Endpoint:** `POST http://your-server:8081/api/v1/nodes`

**Example:**
```bash
curl -X POST http://127.0.0.1:8081/api/v1/nodes \
  -H "Authorization: Bearer meshtastic-secret-2025" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "remote-cabin",
    "nodes": [
      {
        "node_id": "!433ad9f8",
        "node_num": 1128140280,
        "long_name": "Cabin Router",
        "short_name": "CABN",
        "hw_model": "HELTEC_V3",
        "role": "ROUTER",
        "latitude": 69.7041,
        "longitude": 19.0579,
        "altitude": 48,
        "battery_level": 100,
        "voltage": 4.2,
        "last_heard": "2025-10-02T19:00:00Z"
      }
    ]
  }'
```

**Response:**
```json
{
  "success": true,
  "stored": 1,
  "total": 1,
  "source": "remote-cabin"
}
```

### Get All Nodes

**Endpoint:** `GET http://your-server:8081/api/v1/nodes`

```bash
curl http://127.0.0.1:8081/api/v1/nodes
```

---

## 🗄️ Database Schema

### nodes
| Column | Type | Description |
|--------|------|-------------|
| node_id | TEXT (PK) | Node ID (!12345678) |
| node_num | BIGINT | Numeric node ID |
| long_name | TEXT | Full node name |
| short_name | TEXT | 4-char short name |
| hw_model | TEXT | Hardware model |
| role | TEXT | CLIENT/ROUTER/REPEATER |
| latitude | DOUBLE | GPS latitude |
| longitude | DOUBLE | GPS longitude |
| altitude | DOUBLE | GPS altitude (m) |
| battery_level | INTEGER | Battery % (0-100) |
| voltage | DOUBLE | Battery voltage |
| snr | DOUBLE | Signal-to-noise ratio |
| rssi | DOUBLE | Signal strength |
| last_heard | TIMESTAMP | Last packet received |
| source | TEXT | Data source identifier |
| is_active | BOOLEAN | Active in last 7 days |

### positions
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL (PK) | Auto-increment ID |
| node_id | TEXT (FK) | Reference to nodes |
| timestamp | TIMESTAMP | Position timestamp |
| latitude | DOUBLE | GPS latitude |
| longitude | DOUBLE | GPS longitude |
| altitude | DOUBLE | GPS altitude |
| source | TEXT | Data source |

### telemetry
Device metrics history (battery, temperature, uptime, etc.)

### messages
Text messages sent between nodes

---

## 🛠️ Maintenance

### View Logs
```bash
docker compose logs -f meshmap
docker compose logs -f postgres
docker compose logs -f mosquitto
```

### Restart Services
```bash
docker compose restart meshmap
```

### Database Access
```bash
docker exec -it meshtastic-postgres psql -U meshuser -d meshtastic
```

**Useful queries:**
```sql
-- Count active nodes
SELECT COUNT(*) FROM nodes WHERE is_active = TRUE;

-- List nodes with GPS
SELECT node_id, long_name, latitude, longitude, last_heard 
FROM nodes 
WHERE latitude IS NOT NULL 
ORDER BY last_heard DESC;

-- Check position history
SELECT node_id, COUNT(*) as positions 
FROM positions 
GROUP BY node_id 
ORDER BY positions DESC;

-- Sources breakdown
SELECT source, COUNT(*) as nodes 
FROM nodes 
GROUP BY source;
```

### Backup Database
```bash
docker exec meshtastic-postgres pg_dump -U meshuser meshtastic > backup.sql
```

### Restore Database
```bash
cat backup.sql | docker exec -i meshtastic-postgres psql -U meshuser -d meshtastic
```

---

## 🐛 Troubleshooting

### No nodes visible on map

**Check logs:**
```bash
docker compose logs meshmap | grep -i "error\|warning"
```

**Verify database:**
```bash
docker exec -it meshtastic-postgres psql -U meshuser -d meshtastic \
  -c "SELECT COUNT(*) FROM nodes WHERE latitude IS NOT NULL;"
```

**Check GeoJSON file:**
```bash
curl -s http://127.0.0.1:8088/nodes.geojson | jq '.nodeCount'
```

### USB device not accessible

**Check permissions:**
```bash
ls -l /dev/ttyUSB0
sudo usermod -a -G dialout $(whoami)
```

**Verify in container:**
```bash
docker exec meshtastic-map ls -l /dev/ttyUSB0
```

### MQTT not receiving messages

**Test Mosquitto:**
```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -u meshlocal -P meshLocal2025 -t 'msh/#' -v
```

### PostgreSQL connection failed

**Check health:**
```bash
docker compose ps postgres
docker exec meshtastic-postgres pg_isready -U meshuser
```

---

## 📈 Performance

### Expected Metrics
- **MQTT messages:** 50-200/minute (global bridge)
- **Node polling:** Every 5 minutes per source
- **GeoJSON generation:** Every 60 seconds
- **Database size:** ~10-50 MB per month
- **CPU usage:** <5% idle, <20% during polling
- **Memory:** ~200 MB per container

### Optimization

**Increase polling interval** (less frequent updates):
```yaml
NODE_POLL_INTERVAL: "600"  # 10 minutes
```

**Reduce history window** (less disk usage):
```yaml
HISTORY_WINDOW_SECONDS: "43200"  # 12 hours
```

**Disable trails** (faster rendering):
Edit `index.html` and remove trails layer.

---

## 🔒 Security

### Change API Key
Edit `docker-compose.yml`:
```yaml
NODE_API_KEY: "your-secure-token-here"
```

### Database Password
```yaml
POSTGRES_PASSWORD: "your-secure-password"
DB_PASSWORD: "your-secure-password"
```

### Firewall
```bash
# Allow only localhost access
sudo ufw allow from 127.0.0.1 to any port 8088
sudo ufw allow from 127.0.0.1 to any port 8081
```

### Tailscale Access
Expose API to Tailscale network:
```yaml
ports:
  - "100.64.0.1:8081:8081"  # Only Tailscale IP
```

---

## 📚 Further Reading

- [Meshtastic Documentation](https://meshtastic.org/docs/)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [Leaflet.js Documentation](https://leafletjs.com/reference.html)
- [MQTT Bridge Configuration](https://www.eclipse.org/mosquitto/man/mosquitto-conf-5.html)

---

## 🎉 Success Indicators

After deployment, you should see:

✅ **PostgreSQL:** Healthy and accepting connections  
✅ **MQTT Collector:** Receiving 50+ messages/minute from EU_868  
✅ **Node Poller:** Successfully polling USB device every 5 minutes  
✅ **GeoJSON Generator:** Creating files with 10+ nodes  
✅ **Web Map:** Showing nodes from Tromsø + Europe on http://127.0.0.1:8088  
✅ **Database:** Growing with positions and telemetry data  

**Enjoy your multi-source Meshtastic visualization! 📡🗺️**
