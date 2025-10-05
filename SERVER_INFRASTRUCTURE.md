# SERVER INFRASTRUCTURE OVERVIEW
**Analysert:** 2025-10-04 19:36  
**Server:** omeassistant (172.19.228.175)

---

## 🖥️ HARDWARE & OS

| Component | Specification |
|-----------|--------------|
| **OS** | Ubuntu 24.04.3 LTS (Noble Numbat) |
| **Kernel** | Linux 6.14.0-33-generic x86_64 |
| **CPU** | Intel Core i5-6500T @ 2.50GHz (4 cores) |
| **RAM** | 31GB total, 10GB used, 21GB available |
| **Disk** | 98GB total, 63GB used, 31GB available |
| **Architecture** | x86_64 |

## 🌐 NETWORK CONFIGURATION

| Interface | IP Address | Purpose |
|-----------|------------|---------|
| **LAN** | 172.19.228.175/24 | Local network |
| **Tailscale VPN** | 100.80.14.60 | Remote access |
| **Docker Networks** | 172.17.0.1, 172.18.0.1, 172.20.0.1, 172.21.0.1, 172.22.0.1 | Container isolation |
| **Hostname** | omeassistant | |

## 🐳 DOCKER ENVIRONMENT

**Docker:** 28.4.0  
**Docker Compose:** v2.39.2

### Running Containers

| Container | Image | Status | Ports |
|-----------|-------|--------|-------|
| **meshtracking** | meshtracking_no-meshtracking | Up 3 min (health: starting) | 1883, 5434→5432, 8088→8080 |
| **pgadmin** | dpage/pgadmin4 | Up 30 hours | 5050→80 |
| **wiki-tromsoskapere** | custom | Up 30 hours | 3000 |
| **protonord_settlement** | custom | Up 30 hours (healthy) | 8787 |
| **protonord_postgres** | postgres:15.6-alpine | Up 30 hours (healthy) | 5433→5432 |
| **homeassistant** | ghcr.io/home-assistant/home-assistant:stable | Up 30 hours | 8123 |
| **synapse** | matrixdotorg/synapse | Restarting | - |
| **synapse-postgres** | postgres:13-alpine | Up 30 hours | 5432 (internal) |

### Docker Projects on Server
```
/home/kau005/
├── meshtracking_no/        ← CURRENT PROJECT
├── wiki-tromsoskapere/
├── protonord_no/
├── protonord_shopify_system/
├── docmost/
├── npm-server/
├── shopify-royalties/
└── copyparty/
```

## 📊 SYSTEM SERVICES (systemd)

### Critical Services Running

| Service | Description | Port |
|---------|-------------|------|
| **apache2** | Apache HTTP Server | 80, 443 |
| **mariadb** | MariaDB 10.11.13 | 3306 (localhost) |
| **postgresql@16-main** | PostgreSQL 16 | 5432 (localhost) |
| **redis-server** | Redis cache | 6379 (localhost) |
| **docker** | Docker daemon | - |
| **tailscaled** | Tailscale VPN | - |
| **⚠️ meshtastic-usb-collector** | **Legacy USB collector** | **POTENTIAL CONFLICT** |
| **ssh** | OpenSSH server | 22 |

## ⚠️ CRITICAL FINDINGS

### 1. USB Device Conflict Risk
```
Service: meshtastic-usb-collector.service (RUNNING)
Device: /dev/ttyUSB0 (crw-rw---- root:dialout)
Risk: Legacy service may lock USB device, preventing Docker access
Action: Stop and disable old service if Docker needs USB access
```

### 2. Port Usage
Active listening ports:
- 80, 443 (Apache)
- 22 (SSH)
- 1883 (MQTT - meshtracking)
- 3000 (Wiki)
- 3001 (Project Lifecycle Manager)
- 3306 (MariaDB)
- 5050 (pgAdmin)
- 5432 (PostgreSQL local)
- 5433 (Protonord PostgreSQL)
- 5434 (Meshtracking PostgreSQL)
- 6379 (Redis)
- 7867, 8123 (Home Assistant)
- 8088 (Meshtracking Web)
- 8787 (Protonord Settlement)

### 3. Resource Usage
**Top Processes by Memory:**
1. VS Code Server (2 instances): ~4.5GB RAM
2. Home Assistant: ~400MB RAM
3. Docker Daemon: ~118MB RAM
4. Node.js apps: ~250-300MB each

**Total System Load:**
- RAM: 10GB / 31GB (32% used)
- CPU: Low load
- Disk: 63GB / 98GB (64% used)

### 4. Python Environment
- **System Python**: 3.12.3
- **Location**: /usr/bin/python3
- **Docker Python**: Same version (3.12.3)

## 🔒 USER & PERMISSIONS

**Active User:** kau005
**UID/GID:** 1000/1000
**Groups:** adm, dialout, cdrom, sudo, dip, plugdev, lxd, docker

**Critical:** User kau005 is in `dialout` group → Has USB device access

## 📋 RECOMMENDATIONS

1. **⚠️ Stop Legacy Service:**
   ```bash
   sudo systemctl stop meshtastic-usb-collector.service
   sudo systemctl disable meshtastic-usb-collector.service
   ```

2. **Verify USB Access:**
   ```bash
   docker exec meshtracking ls -la /dev/ttyUSB0
   ```

3. **Monitor Resource Usage:**
   - 31GB RAM is sufficient but monitor VS Code instances
   - Disk space at 64% - consider cleanup if approaching 80%

4. **Container Health:**
   - meshtracking showing "health: starting" - needs investigation
   - synapse container restarting - potential issue

5. **Network Optimization:**
   - Consider consolidating PostgreSQL instances (3 running)
   - Review need for all Docker networks

---

**Status:** Complete server analysis documented ✅  
**Next Steps:** Resume website debugging with full context
