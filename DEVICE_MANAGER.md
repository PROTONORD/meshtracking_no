# 🌐 Dynamic Meshtastic Device Manager

Automatisk discovery og polling av Meshtastic-enheter via USB og WiFi.

## 📋 Funksjonalitet

### Auto-Discovery
- **USB Serial**: Automatisk deteksjon av alle tilkoblede USB Meshtastic-enheter
- **WiFi/TCP**: Skanner lokale nettverk for Meshtastic på port 4403
- **Network Detection**: Detekterer automatisk serverens egne nettverk
- **Persistent State**: Husker enheter mellom restarter

### Intelligent Polling
- Poller aktive enheter hvert 30. sekund (konfigurerbart)
- Henter node-database fra hver enhet
- Lagrer alle node-data i PostgreSQL
- Auto-cleanup: Fjerner døde enheter etter 10 feil

### Resilient Design
- Enheter som mister forbindelse fjernes automatisk
- Enheter som kommer tilbake oppdages på nytt
- Tråler gjennom flere nettverk parallelt
- Fallback-metoder når nmap ikke er tilgjengelig

## ⚙️ Konfigurasjon

Alle innstillinger i `docker-compose.yml`:

```yaml
environment:
  # Discovery settings
  DISCOVERY_INTERVAL: "60"              # Scan hvert 60. sekund
  AUTO_DETECT_NETWORKS: "true"          # Auto-detect lokale nettverk
  MANUAL_SCAN_NETWORKS: ""              # Ekstra nettverk (CIDR, comma-separated)
  
  # Polling settings
  POLL_INTERVAL: "30"                   # Poll enheter hvert 30. sekund
  MAX_FAIL_COUNT: "10"                  # Fjern etter 10 feile forsøk
  MESHTASTIC_TCP_PORT: "4403"           # Meshtastic TCP port
```

## 🚀 Bruksscenarier

### Scenario 1: Stationary Gateway
- Koble til USB Meshtastic permanent
- Oppdages automatisk ved oppstart
- Poller kontinuerlig for nodeinfo

### Scenario 2: Mobile Data Collector
1. Ta med Meshtastic på tur (samle nodes)
2. Koble til WiFi når du kommer hjem
3. Auto-discovery finner enheten
4. Dumper all innsamlet node-data til database
5. Alle noder vises på kartet!

### Scenario 3: Multi-Gateway Setup
- Flere USB-enheter samtidig
- Flere WiFi-enheter på nettet
- Alle poller parallelt
- Data aggregeres i felles database

## 📊 Device Registry

State lagres i `/data/config/device_registry.json`:

```json
{
  "/dev/ttyUSB0": {
    "type": "serial",
    "address": "/dev/ttyUSB0",
    "name": "USB-ttyUSB0",
    "fail_count": 0,
    "node_count": 23,
    "last_success": 1727906157.23
  },
  "172.19.228.51:4403": {
    "type": "tcp",
    "address": "172.19.228.51:4403",
    "name": "WiFi-172.19.228.51",
    "fail_count": 0,
    "node_count": 6,
    "last_success": 1727906157.20
  }
}
```

## 🔍 Monitoring

### Se aktive enheter:
```bash
cat /home/kau005/meshtastic-data/config/device_registry.json | jq
```

### Se live logs:
```bash
docker logs -f meshtastic-map | grep "device\|discovery\|polling"
```

### Database query:
```sql
-- Vis noder fra lokale enheter
SELECT node_id, short_name, long_name, source, last_heard 
FROM nodes 
WHERE source LIKE '%WiFi%' OR source LIKE '%USB%'
ORDER BY last_heard DESC;
```

## 🌐 Network Auto-Detection

Systemet detekterer automatisk alle aktive nettverksinterface:

```
2025-10-02 19:35:07 - INFO - 🌐 Detected local network: 172.21.0.0/16 (interface: eth0)
2025-10-02 19:35:07 - INFO - 🔍 Scanning 1 network(s) for Meshtastic devices...
```

**Ignorerer automatisk:**
- Loopback (127.0.0.1)
- Docker bridges (docker0, br-*)
- Andre virtuelle interfaces

## 🛠️ Manual Scan

For å scanne et spesifikt nettverk:

```bash
docker exec meshtastic-map /app/scan_network.sh 192.168.1.0/24
```

## 📈 Statistics

Se device manager status i logs:
```
2025-10-02 19:36:08 - INFO - 💓 Status: 2/2 devices responding
2025-10-02 19:36:08 - INFO - ✅ USB-ttyUSB0: Retrieved 23 nodes
2025-10-02 19:36:08 - INFO - ✅ WiFi-172.19.228.51: Retrieved 6 nodes
2025-10-02 19:36:08 - INFO - 💾 Saved 29 nodes to database
```

## 🎯 Benefits

✅ **Plug & Play**: Koble til ny enhet → oppdages automatisk  
✅ **Mobile Friendly**: Ta med Meshtastic ut → samle data → dump ved hjemkomst  
✅ **Resilient**: Enheter kan forsvinne og komme tilbake  
✅ **Scalable**: Støtter mange enheter samtidig  
✅ **Zero Config**: Fungerer uten manuell konfigurasjon  
✅ **Network Agnostic**: Fungerer på ethvert nettverk serveren er på  

## 🔧 Troubleshooting

### Enhet oppdages ikke?
```bash
# Sjekk at port 4403 er åpen
nc -zv 172.19.228.51 4403

# Manuell scan
docker exec meshtastic-map /app/scan_network.sh 172.19.228.0/24
```

### Ingen noder returneres?
- Vent 2-3 minutter (interface trenger tid til å bygge nodeDB)
- Sjekk at Meshtastic har WiFi/BT enabled
- Verifiser at enheten faktisk har mottatt nodes

### Device fjernes feilaktig?
- Øk `MAX_FAIL_COUNT` i docker-compose.yml
- Sjekk nettverksstabilitet
- Se logs for feilmeldinger

## 📝 Logs

Relevante loggmeldinger:
```
🔌 New USB device discovered: /dev/ttyUSB0
📡 New WiFi device discovered: 172.19.228.51:4403
✅ USB-ttyUSB0: Retrieved 23 nodes
❌ WiFi-192.168.1.100: Poll failed - timeout
⚠️  USB-ttyUSB1: No nodes returned
🗑️  Removing dead device: WiFi-192.168.1.100 (failed 10 times)
💾 Saved 29 nodes to database
💓 Status: 2/2 devices responding
```

## 🚦 Status Emojis

- 🔌 USB device discovered
- 📡 WiFi device discovered  
- ✅ Successful poll
- ❌ Failed poll
- ⚠️  Warning (no nodes)
- 🗑️  Device removed
- 💾 Database saved
- 💓 Heartbeat status
- 🔍 Discovery scan
- 🔄 Polling cycle
- 🌐 Network detected

---

**Sist oppdatert:** 2025-10-02  
**Polling interval:** 30 sekunder  
**Discovery interval:** 60 sekunder  
**Max fail count:** 10  
