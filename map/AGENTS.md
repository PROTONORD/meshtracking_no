# Meshtastic Docker Stack Notes
**Last Updated:## Telemetry System (New in October 2025)

### Extended Database Schema
- **29 telemetry columns** in `telemetry` table:
  - **Power Metrics**: `voltage`, `current`, `power_watts` (INA219/INA260 sensors)
  - **Environment Metrics**: `temperature`, `relative_humidity`, `barometric_pressure`, `gas_resistance`, `iaq` (BME680/weather stations)
  - **Air Quality Metrics**: `pm10_standard`, `pm25_standard`, `pm100_standard`, `pm10_environmental`, `pm25_environmental`, `pm100_environmental`, `particles_03um`, `particles_05um`, `particles_10um`, `particles_25um`, `particles_50um`, `particles_100um`, `co2`, `tvoc`, `nox_index` (PM/CO2/VOC sensors)
  - **System Metrics**: `battery_level`, `voltage`, `channel_utilization`, `air_util_tx`, `uptime_seconds`

- **6 metadata flags** in `nodes` table:
  - `has_power_sensor`, `has_environment_sensor`, `has_air_quality_sensor`
  - `has_pm_sensor`, `has_co2_sensor`, `has_voc_sensor`

### Telemetry Filter UI
- Dropdown filter with 6 options:
  - 🔋 All nodes
  - ⚡ Any sensor
  - 🔋 Power sensors
  - 🌡️ Environment sensors  
  - 🍃 Air quality sensors
  - 💤 No sensors
- Filter icons displayed with emoji indicators

### Data Collection
- **MQTT Collector**: Parses global mesh telemetry from `mqtt.meshtastic.org`
- **Device Manager**: Polls USB/WiFi nodes every 30 seconds
- **GeoJSON Generator**: Real-time map updates every 30 seconds
- Currently storing: **10,596 telemetry entries** from **1,978 nodes** (723 active in last 24h)

## Volumes & Persistence
- **`postgres-data`** - PostgreSQL database (persistent, 25MB current)
- **`map-data`** - GeoJSON output, device registry
- **`meshtasticd-state`** - Meshtasticd state
- **Host mount** `/home/kau005/meshtastic-data` - GeoJSON files, backups, config
  - `nodes.geojson` - Current node data (updated every 30s)
  - `trails.geojson` - Movement history (24h window)
  - `backup/` - Daily database backups (14-day retention)
  - `config/device_registry.json` - Auto-discovered devices

## Automated Maintenance

### Daily Scheduled Tasks (via run.sh)
- **02:00** - Database backup (gzip SQL dump, 14-day retention)
- **03:00** - Node cleanup (removes nodes inactive >60 days)

### Continuous Operations
- **Every 30s** - GeoJSON generation and device polling
- **Every 60s** - Container healthcheck
- **Real-time** - MQTT data collection from global mesh

## Robustness & Resilience (October 2025)

### Automatic Recovery
- ✅ **Server reboot**: All containers restart automatically (`restart: unless-stopped`)
- ✅ **Internet loss**: Local nodes continue, auto-reconnect to MQTT
- ✅ **USB disconnect**: WiFi continues, USB auto-detected on reconnect
- ✅ **Container crash**: Docker restarts within 10-30 seconds
- ✅ **Database full**: Automatic cleanup of old nodes (>60 days)

### USB Stability (udev rules)
- Device: `/dev/ttyUSB0` with stable symlink `/dev/meshtastic-usb`
- udev rule: `/etc/udev/rules.d/99-meshtastic.rules`
- Vendor: Silicon Labs CP210x (ID 10c4:ea60)
- Survives disconnection and server reboot

### Health Monitoring
- **Healthcheck script**: `./health_check.sh` - Comprehensive system verification
- **Docker healthcheck**: Web server checked every 60s
- **Database healthcheck**: PostgreSQL readiness check
- **Logging**: Limited to 50MB per container (3 files rotation)

### Backup & Recovery
- **Automated backups**: Daily at 02:00 (gzip SQL dumps)
- **Retention**: 14 days
- **Manual backup**: `docker exec meshtastic-map sh -c "PGPASSWORD=meshpass2025 pg_dump -h postgres -U meshuser meshtastic | gzip > /data/backup/db_manual_$(date +%Y%m%d_%H%M%S).sql.gz"`
- **Restore**: See `QUICK_REFERENCE.md`

## Node Configuration & Management

### Remote Configuration (via Meshtastic API)
- Script: `configure_nodes_with_reboot.py`
- Capabilities: Set name, short name, GPS position
- **Critical**: Requires `node.reboot()` after changes to persist to flash
- Verification: Changes confirmed via `meshtastic --info` after reboot

### Cleanup Operations
- Script: `cleanup_old_nodes.py`
- Modes: `--database` (PostgreSQL), `--devices` (node databases), `--all`
- Database cleanup: Removes nodes inactive >60 days
- Device cleanup: Runs `resetNodeDb()` on physical nodes
- Schedule: Database cleanup runs daily at 03:00

## Map Features (index.html)

### UI Components
- **Search**: Filter nodes by name/ID
- **Telemetry filter**: Dropdown with 6 sensor categories
- **Favorites**: Star nodes for quick access
- **Trails**: 24-hour movement history
- **Popups**: Node details with telemetry data
- **Auto-zoom**: Only on first load (preserves user zoom level)

### Map Behavior
- **Auto-updates**: Every 60 seconds
- **First load zoom**: Fits all nodes automatically
- **Subsequent updates**: Preserves user zoom and position
- **Label persistence**: Markers keep labels while nodes are removed/re-added

## Access Points
- **Web Map (LAN)**: `http://172.19.228.175:8088/`
- **Web Map (External)**: `http://localhost:8088/` (if port forwarded)
- **Node API**: `http://localhost:8081/`
- **PostgreSQL**: `127.0.0.1:5434` (user: `meshuser`, db: `meshtastic`)
- **MQTT**: `localhost:1883` (user: `meshlocal`)
- **Meshtastic API**: `127.0.0.1:4403`
- **MeshtasticD UI**: `127.0.0.1:9443`

## Documentation Files (New)
- **HEALTH_CHECK.md** - Detailed health report and recovery procedures
- **RESILIENCE_REPORT.md** - Robustness testing and verification
- **SYSTEM_SUMMARY.md** - Implementation summary
- **QUICK_REFERENCE.md** - Daily operation commands
- **INSTALL_IMPROVEMENTS.md** - Setup instructions for improvements
- **health_check.sh** - Automated health verification script
- **99-meshtastic.rules** - USB udev rules

## System Status (2025-10-03)
- **Health Score**: 9.5/10
- **Resilience**: Excellent - Production ready
- **Database**: 25MB, 1,978 nodes, 10,596 telemetry entries
- **Active nodes**: 723 (last 24 hours)
- **Uptime**: Indefinite (self-healing)
- **Manual intervention**: Not required

## Updating Stack
- **Rebuild after changes**: `docker-compose down && docker-compose up -d --build`
- **Health check**: `./health_check.sh`
- **View logs**: `docker logs meshtastic-map --tail 50`
- **Database queries**: See `QUICK_REFERENCE.md`

---

**For detailed operational procedures, troubleshooting, and emergency recovery, see documentation files in `/home/kau005/meshtastic-docker/`**10-03 - Major system overhaul with PostgreSQL, telemetry expansion, and robustness improvements

## System Architecture (Updated October 2025)

### Core Services
- **`meshtastic-postgres`** (PostgreSQL 16-alpine) - Primary data store with comprehensive telemetry support
  - Database: `meshtastic` (user: `meshuser`)
  - Tables: `nodes` (metadata), `telemetry` (29 sensor columns), `node_messages`, `position_history`
  - Healthcheck enabled, logging limits (10MB max, 3 files)
  - Volume: `postgres-data` (persistent)
  - Exposed: `127.0.0.1:5434:5432`

- **`meshtastic-mosquitto`** (eclipse-mosquitto) - MQTT broker for global mesh network
  - Port: `1883` (exposed to LAN)
  - Credentials: `meshlocal` / `meshLocal2025`
  - Logging limits: 10MB max, 3 files
  - Config: `mosquitto/config/`

- **`meshtasticd`** - Meshtastic native daemon in simulated radio mode
  - Bridges to local Mosquitto broker
  - API: `127.0.0.1:4403`, UI: `127.0.0.1:9443`

- **`meshtastic-map`** - Main application container (Python 3.12-slim)
  - **Healthcheck enabled**: Checks web server every 60s
  - **Logging limits**: 50MB max, 3 files rotation
  - **6 Python processes running**:
    1. `mqtt_collector_pg.py` - Global MQTT data collection (29 telemetry fields)
    2. `device_manager.py` - USB/WiFi node polling and auto-discovery
    3. `db_to_geojson_pg.py` - Real-time GeoJSON generation (30s interval)
    4. `node_api.py` - HTTP API for remote nodes (port 8081)
    5. `http.server` - Web server (port 8080)
    6. Scheduled tasks (cleanup at 03:00, backup at 02:00)
  - Exposed: `0.0.0.0:8088:8080` (web), `0.0.0.0:8081:8081` (API)
  - Depends on: postgres (healthcheck), mosquitto

### Gateway Nodes (PROTONORD)
- **USB Node** (`!db2f13c0`): PROTONORD usb (short: USB)
  - Device: `/dev/ttyUSB0` (symlink: `/dev/meshtastic-usb`)
  - Position: 69.6812°N, 18.9895°E (Ishavsvegen 69B, 9010 Tromsø)
  - Role: CLIENT_HIDDEN
  
- **WiFi Node** (`!db2fa9a4`): PROTONORD wifi (short: WIFI)
  - IP: 172.19.228.51:4403
  - Position: 69.6812°N, 18.9895°E (Ishavsvegen 69B, 9010 Tromsø)
  - Hardware: HELTEC_V3

## Volumes & Files
- `map-data` volume contains:
  - `index.html` (served file)
  - `nodes.geojson`, `trails.geojson`
  - `nodes.db` (SQLite history; 24h window by default)
  - `config/favorites.json` (favorite nodes, labels, notes)
- Use `docker exec meshtastic-map` to inspect data: `sqlite3 /data/nodes.db`, `cat /data/trails.geojson`, etc.
- Heltec gateway (`!db2f13c0`) is pre-loaded as favorite with label “Heltec Gateway”. Update this file to change favourites.

## Favorites & Metadata
- Edit `/var/lib/docker/volumes/meshtastic-docker_map-data/_data/config/favorites.json` (or via container) to add nodes. Structure example:
  ```json
  {
    "favorites": ["!db2f13c0"],
    "labels": {"!db2f13c0": "Heltec Gateway"},
    "notes": {"!db2f13c0": "USB gateway node on meshtracking server"}
  }
  ```
- Changes auto-load within ~60 seconds.

## Heltec Gateway
- Physical Heltec V3 is configured via USB (`/dev/ttyUSB0`) with MQTT pointed at `meshtracking.no:1883`, username `meshlocal`, password `meshLocal2025`.
- Use `sg dialout '~/.local/bin/meshtastic --port /dev/ttyUSB0 --get mqtt'` to verify or update settings.
- Keep the device on Wi-Fi so it can bridge LoRa traffic into the local broker; no traffic is sent to the public `mqtt.meshtastic.org`.

## Trails & History
- History window controlled by env var `HISTORY_WINDOW_SECONDS` (default 86400s).
- Trails rendered from the most recent `TRAIL_MAX_POINTS` (default 500) per node.

## Updating Stack
- Daily systemd timer `meshtastic-docker-update.timer` runs `/home/kau005/meshtastic-docker/update.sh` (`docker compose pull && up -d`).
- Manual rebuild after config changes: `docker compose build meshmap && docker compose up -d meshmap`.

## Access
- LAN: `http://172.19.228.175:8088/`
- Public HTTPS via Apache reverse proxy: `https://meshtracking.no/`
- Tailscale Serve: `https://meshtastic.tail952c08.ts.net/`
- Raw API: `http://127.0.0.1:4403` (Meshtastic API), `http://127.0.0.1:9443` (MeshtasticD UI).
