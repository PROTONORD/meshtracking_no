# 🔐 Secrets Configuration Guide

This guide explains every secret in `production.env` and what it's used for.

---

## 📁 What's in this folder?

- **`production.env`** - Your actual secrets (NEVER commit to git!)
- **`production.env.example`** - Template with placeholder values (safe to share)
- **`SECRETS_GUIDE.md`** - This file (explains everything)

---

## 🗄️ Database Secrets

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=meshtastic
DB_USER=meshuser
DB_PASSWORD=SecureMesh2025_DB_9k3L
```

**What it does:**
- PostgreSQL database stores all your Meshtastic data:
  - Node information (ID, name, hardware)
  - GPS positions
  - Telemetry (battery, temperature, etc.)
  - Messages

**Who uses it:**
- `device_manager.py` - Saves data from USB/WiFi devices
- `mqtt_collector_pg.py` - Saves data from MQTT messages
- `db_to_geojson_pg.py` - Reads data to create map

**What to change:**
- ✅ **MUST change:** `DB_PASSWORD` - Use a strong unique password
- ❌ **Don't change:** `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` (unless you know what you're doing)

**Generate secure password:**
```bash
openssl rand -base64 32
```

---

## 📡 Local MQTT Broker

```env
MQTT_HOST=localhost
MQTT_PORT=1883
MQTT_USER=meshlocal
MQTT_PASS=SecureMQTT2025_LOCAL_8x9W
MQTT_TOPIC=msh/#
```

**What it does:**
- Mosquitto MQTT broker collects messages from:
  1. Your USB/WiFi connected devices
  2. Global Meshtastic network (bridged)

**Message flow:**
```
Your devices → device_manager.py → Local MQTT
Global MQTT → Bridge → Local MQTT
Local MQTT → mqtt_collector_pg.py → Database
```

**Who uses it:**
- `device_manager.py` - Publishes messages from local devices
- `mqtt_collector_pg.py` - Subscribes to all messages (`msh/#`)
- Mosquitto bridge - Forwards global messages here

**What to change:**
- ✅ **MUST change:** `MQTT_PASS` - Use a strong unique password
- ❌ **Don't change:** Other values (standard local setup)

---

## 🔑 API Key

```env
NODE_API_KEY=meshtastic-secret-2025
```

**What it does:**
- Used by the web frontend (`index.html`) for API authentication
- Currently used for: Nominatim (OpenStreetMap) location search
- Flask server injects this into the HTML when serving the page

**How it works:**
```javascript
// In index.html
fetch('https://nominatim.openstreetmap.org/search', {
    headers: {
        'Authorization': 'Bearer meshtastic-secret-2025'
    }
})
```

**What to change:**
- ✅ **SHOULD change:** Generate a unique key for your installation

**Generate unique key:**
```bash
openssl rand -base64 24
```

---

## 🌍 Global MQTT Bridge

```env
MQTT_BRIDGE_USER=meshdev
MQTT_BRIDGE_PASS=large4cats
```

**What it does:**
- Connects to the global Meshtastic network at `mqtt.meshtastic.org:1883`
- Receives messages from Meshtastic devices worldwide
- Bridges them to your local MQTT broker

**IMPORTANT:**
- ❌ **DO NOT CHANGE THESE!**
- These are **official public credentials** provided by Meshtastic
- Everyone uses the same credentials for read-only access
- More info: https://meshtastic.org/docs/software/integrations/mqtt/

---

## ⚙️ Device Manager Settings

```env
DISCOVERY_INTERVAL=60
POLL_INTERVAL=30
MAX_FAIL_COUNT=10
```

**What each setting does:**

### DISCOVERY_INTERVAL=60
- **What:** How often (seconds) to scan for new devices
- **Default:** 60 seconds
- **Tune:** Lower = find devices faster, but uses more CPU
- **Example:** `30` for faster discovery, `120` for less CPU usage

### POLL_INTERVAL=30
- **What:** How often (seconds) to get data from each connected device
- **Default:** 30 seconds
- **Tune:** Lower = more frequent updates, higher CPU usage
- **Example:** `15` for real-time updates, `60` for less frequent

### MAX_FAIL_COUNT=10
- **What:** Disconnect device after this many failed connection attempts
- **Default:** 10 attempts
- **Tune:** Higher = more tolerant of network issues
- **Example:** `5` for quick disconnect, `20` for very tolerant

---

## 🔍 Network Discovery

```env
AUTO_DETECT_NETWORKS=false
MANUAL_SCAN_NETWORKS=172.19.228.0/24
MESHTASTIC_TCP_PORT=4403
SERIAL_PORT=/dev/ttyUSB0
```

**What each setting does:**

### AUTO_DETECT_NETWORKS=false
- **What:** Automatically scan all local networks for WiFi devices
- **Default:** `false` (disabled for security)
- **Security:** `true` = scans entire network, `false` = only manual networks
- **When to enable:** If you want automatic discovery across all networks

### MANUAL_SCAN_NETWORKS=172.19.228.0/24
- **What:** Specific network ranges to scan for WiFi devices
- **Format:** CIDR notation (e.g., `192.168.1.0/24`)
- **Multiple networks:** Separate with commas: `192.168.1.0/24,10.0.0.0/24`
- **Find your network:** Run `ip addr show` to see your network

**Example setups:**
```env
# Home network
MANUAL_SCAN_NETWORKS=192.168.1.0/24

# Multiple networks
MANUAL_SCAN_NETWORKS=192.168.1.0/24,192.168.2.0/24

# Large network
MANUAL_SCAN_NETWORKS=10.0.0.0/16
```

### MESHTASTIC_TCP_PORT=4403
- **What:** Default port for Meshtastic WiFi devices
- **Default:** 4403 (standard Meshtastic port)
- **Don't change:** Unless you've reconfigured your devices

### SERIAL_PORT=/dev/ttyUSB0
- **What:** USB port for directly connected devices
- **Common values:** `/dev/ttyUSB0`, `/dev/ttyUSB1`, `/dev/ttyACM0`
- **Find your port:** Run `ls -l /dev/ttyUSB*` or `ls -l /dev/ttyACM*`

---

## 🌐 Web Server

```env
WEB_PORT=8088
```

**What it does:**
- Port where Flask web server listens
- Access your map at: `http://localhost:8088` or `http://your-server-ip:8088`

**What to change:**
- Change if port 8088 is already in use
- Common alternatives: `8080`, `8090`, `3000`, `5000`

---

## 🚀 Quick Setup for New Installation

### Step 1: Copy template
```bash
cp production.env.example production.env
```

### Step 2: Generate secure passwords
```bash
echo "Database password:"
openssl rand -base64 32

echo "MQTT password:"
openssl rand -base64 32

echo "API key:"
openssl rand -base64 24
```

### Step 3: Edit production.env
```bash
nano production.env
```

Replace these values:
- `DB_PASSWORD=` → Paste database password
- `MQTT_PASS=` → Paste MQTT password
- `NODE_API_KEY=` → Paste API key
- `MANUAL_SCAN_NETWORKS=` → Your network (find with `ip addr show`)

### Step 4: Secure the file
```bash
chmod 600 production.env
```

### Step 5: Start system
```bash
cd /home/meshtracking/meshtracking_no
docker compose up -d
```

---

## ✅ What Must You Change?

| Setting | Must Change? | Why? |
|---------|-------------|------|
| `DB_PASSWORD` | ✅ YES | Security - use unique password |
| `MQTT_PASS` | ✅ YES | Security - use unique password |
| `NODE_API_KEY` | 🔸 RECOMMENDED | Security - use unique key |
| `MANUAL_SCAN_NETWORKS` | 🔸 MAYBE | Set to your actual network if using WiFi devices |
| `MQTT_BRIDGE_USER/PASS` | ❌ NO | Public credentials - don't change! |
| `DB_HOST`, `MQTT_HOST` | ❌ NO | localhost is correct |
| `*_INTERVAL` settings | 🔸 MAYBE | Tune for performance vs resources |
| `WEB_PORT` | 🔸 MAYBE | Change if port 8088 conflicts |

---

## 🔒 Security Checklist

- ✅ File is in `.gitignore` - NEVER commit to git
- ✅ Use long random passwords (20+ characters)
- ✅ Set file permissions: `chmod 600 production.env`
- ✅ Different passwords for each service
- ✅ Don't share passwords in chat/email
- ✅ Keep bridge credentials as-is (public)
- ✅ Backup this file securely (encrypted)

---

## 🐛 Troubleshooting

### Can't connect to database
```bash
# Check PostgreSQL logs
docker compose logs postgres

# Verify password matches
docker compose exec postgres psql -U meshuser -d meshtastic
```

### Can't connect to MQTT
```bash
# Check Mosquitto logs
docker compose logs mosquitto

# Test connection
mosquitto_sub -h localhost -u meshlocal -P "your-password" -t 'msh/#' -v
```

### Can't find WiFi devices
```bash
# Check your network
ip addr show

# Update MANUAL_SCAN_NETWORKS to match
# Or enable AUTO_DETECT_NETWORKS=true
```

### No devices found at all
```bash
# Check USB devices
ls -l /dev/ttyUSB* /dev/ttyACM*

# Check device manager logs
docker compose logs device_manager
```

---

## 📚 More Information

- **Main README:** `../README.md`
- **Docker setup:** `../docker-compose.yml`
- **Meshtastic MQTT:** https://meshtastic.org/docs/software/integrations/mqtt/
- **PostgreSQL docs:** https://www.postgresql.org/docs/

---

**Remember:** This file contains sensitive information. Keep it secure! 🔐
