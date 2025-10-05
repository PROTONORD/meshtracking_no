# Meshtracking.no - Real-time Meshtastic Node Tracking

**v3.29.0 - Desktop-First Production System** 🚀

## Overview

A comprehensive, all-in-one Docker solution for real-time tracking and visualization of Meshtastic mesh network nodes. This production-ready system provides live monitoring, interactive maps, and comprehensive telemetry tracking.

## ✨ Key Features

### Frontend (v3.29.0)
- 🖥️ **Desktop-First Interface** - Optimized for desktop use
- 🗺️ **Interactive Leaflet Map** - Real-time node visualization
- ⭐ **Favorites System** - Star nodes and persist across sessions (localStorage)
- 🌍 **Region Filtering** - Filter by LoRa region (EU_868, US, etc.)
- 📡 **Source Filtering** - Toggle between Radio (USB/WiFi) and MQTT nodes
- 🔍 **Search Functionality** - Find nodes by ID or name
- 📊 **Live Status Counts** - Real-time node statistics by status
- 🎯 **Smart Clustering** - Stacked node labels at same location
- 💾 **Persistent Filters** - All filters survive page refresh

### Backend
- 🐘 **PostgreSQL Database** - Full telemetry history and node tracking
- 📡 **MQTT Bridge** - Connect to mqtt.meshtastic.org
- 📻 **Radio Collection** - USB/WiFi device polling (device_manager.py)
- 🌐 **Flask API** - RESTful endpoints with GeoJSON support
- 🔄 **Real-time Updates** - Live data from multiple sources
- � **Comprehensive Telemetry** - Environment, power, air quality sensors
- 🏷️ **Node Tagging** - Custom tags and notes per node
- 📍 **Region Detection** - Automatic LoRa region from device config

## 🔧 Architecture

Single Docker container with:
- PostgreSQL 16
- Mosquitto MQTT Broker
- Python 3.12 applications:
  - `device_manager.py` - USB/WiFi device discovery and polling
  - `mqtt_collector_pg.py` - MQTT bridge data collection
  - `db_to_geojson_pg.py` - GeoJSON API generation
  - `combined_server.py` - Flask web server
- Supervisord for process management

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- USB Meshtastic device (optional, for radio collection)
- Access to mqtt.meshtastic.org (optional, for MQTT bridge)

### Installation

1. **Clone repository**
```bash
git clone https://github.com/PROTONORD/meshtracking_no.git
cd meshtracking_no
```

2. **Configure secrets** (⚠️ IMPORTANT!)
```bash
mkdir -p secrets
cp SECURITY.md secrets/  # Read security instructions
nano secrets/production.env  # Edit with your passwords
```

See [SECURITY.md](SECURITY.md) for detailed instructions.

3. **Start the system**
```bash
docker compose up -d
```

4. **Access the interface**
```
http://localhost:8088
```

## 📋 Configuration

### Environment Variables (secrets/production.env)

```bash
# Database
DB_PASSWORD=your_secure_password_here

# MQTT Internal
MQTT_PASS=your_mqtt_password_here

# API Key (required for frontend access)
NODE_API_KEY=your_secure_api_key_here

# MQTT Bridge (optional)
MQTT_BRIDGE_USER=meshdev
MQTT_BRIDGE_PASS=your_meshtastic_org_password

# Device Manager
DISCOVERY_INTERVAL=60
POLL_INTERVAL=30
MANUAL_SCAN_NETWORKS=172.19.228.0/24
SERIAL_PORT=/dev/ttyUSB0
```

See [SECURITY.md](SECURITY.md) for complete configuration.

## 🗺️ Frontend Features

### Filters & Search
- **Status Filter**: Online, Recent, Offline, Favorites
- **Source Filter**: Radio (USB/WiFi) vs MQTT nodes
- **Region Filter**: EU_868, US, TW, PL, CZ, etc.
- **Text Search**: Search by node ID or name

### Node Visualization
- **Color Coding**:
  - 🟢 Green: Online (< 15 min)
  - 🟠 Orange: Recent (15-60 min)
  - ⚪ Gray: Offline (> 60 min)
- **Ring Colors**:
  - White ring: MQTT nodes
  - Black ring: Radio (local) nodes

### Node Popup
- Node information (name, hardware, battery, etc.)
- ⭐ Favorite button (persists across sessions)
- Real-time telemetry (if available)
- Edit notes and tags

## 🔌 API Endpoints

- `GET /nodes.geojson` - All nodes in GeoJSON format
- `GET /api/nodes` - Node list with status
- `GET /api/health` - System health check
- `POST /api/node/:id/tags` - Update node tags
- `POST /api/node/:id/notes` - Update node notes
- `POST /api/node/:id/position` - Manual position override

## 📊 Database Schema

See [init.sql/schema.sql](init.sql/schema.sql) for complete schema.

Key tables:
- `nodes` - Node information and current state
- `telemetry` - Historical telemetry data
- `node_history` - Position history
- `node_tags` - Custom tags per node

## 🔒 Security

**IMPORTANT**: Never commit secrets to git!

- All passwords in `secrets/production.env` (gitignored)
- No hardcoded credentials in source
- See [SECURITY.md](SECURITY.md) for security best practices

## 🐛 Troubleshooting

### Check logs
```bash
docker logs meshtracking --tail 100
```

### Restart services
```bash
docker compose restart
```

### Database issues
```bash
docker exec meshtracking psql -U meshuser -d meshtastic
```

## 📝 Version History

- **v3.29.0** - Region detection from device config for radio nodes
- **v3.28.x** - Region filter with localStorage persistence
- **v3.27.x** - Fixed favorite styling, source filter counts
- **v3.26.x** - Favorites system with localStorage
- **v3.25.x** - Favorite star buttons
- **v3.24.x** - Desktop-only mode enforced
- **v3.21.x** - Initial mobile UI polish

## 🤝 Contributing

This is an active development project. Contributions welcome!

## 📄 License

[Add your license here]

## 👤 Author

**PROTONORD / IBICO74**

## 🔗 Links

- GitHub: https://github.com/PROTONORD/meshtracking_no
- Meshtastic: https://meshtastic.org

---

**Current Version**: 3.29.0 (October 2025)