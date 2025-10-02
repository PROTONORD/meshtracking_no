# Quick Deployment Guide - Dual USB Setup

## You now have 2 Heltec V3 devices connected!

### Step 1: Find all USB devices
```bash
cd /home/kau005/meshtastic-docker
./find-all-devices.sh
```

This will show:
- All connected USB Meshtastic devices
- Their device paths (/dev/ttyUSB0, /dev/ttyUSB1, etc.)
- Device info (owner, MAC address, WiFi status)
- Ready-to-use config for node_sources.json

### Step 2: Update config with both devices

Copy the JSON output from find-all-devices.sh and update:
```bash
nano config/node_sources.json
```

Example for 2 USB devices:
```json
{
  "sources": [
    {
      "type": "serial",
      "path": "/dev/ttyUSB0",
      "name": "usb-node-1",
      "enabled": true,
      "description": "Heltec V3 #1"
    },
    {
      "type": "serial",
      "path": "/dev/ttyUSB1",
      "name": "usb-node-2",
      "enabled": true,
      "description": "Heltec V3 #2"
    }
  ]
}
```

### Step 3: Deploy the system
```bash
./deploy.sh
```

### Step 4: Verify both devices are being polled

After deployment, check logs:
```bash
docker compose logs -f meshmap | grep "Retrieved.*nodes"
```

You should see:
```
✓ Retrieved X nodes from usb-node-1 to database
✓ Retrieved X nodes from usb-node-2 to database
```

### Step 5: Check the map
Open: http://127.0.0.1:8088

You should see nodes from:
- ✅ Global MQTT (Europe: 5-10 nodes)
- ✅ USB Device #1 (Tromsø nodes)
- ✅ USB Device #2 (Tromsø nodes)
- Total: 15-20+ nodes

## Benefits of Dual USB Setup

1. **Redundancy** - If one device fails, the other keeps working
2. **Better coverage** - Each device may see different nodes
3. **More data** - Combined node database from both devices
4. **Mesh health** - Compare what each device sees

## Checking WiFi Settings

To check WiFi on each device:
```bash
# Device 1
meshtastic --port /dev/ttyUSB0 --get network

# Device 2  
meshtastic --port /dev/ttyUSB1 --get network
```

To get MAC addresses (for router lookup):
```bash
# Device 1
meshtastic --port /dev/ttyUSB0 --info | grep -i mac

# Device 2
meshtastic --port /dev/ttyUSB1 --info | grep -i mac
```

## Enabling WiFi on Devices

If WiFi is disabled and you want to enable it:
```bash
# Set WiFi SSID and password
meshtastic --port /dev/ttyUSB0 --set network.wifi_ssid "YourSSID"
meshtastic --port /dev/ttyUSB0 --set network.wifi_psk "YourPassword"
meshtastic --port /dev/ttyUSB0 --set network.wifi_enabled true

# Repeat for second device
meshtastic --port /dev/ttyUSB1 --set network.wifi_ssid "YourSSID"
meshtastic --port /dev/ttyUSB1 --set network.wifi_psk "YourPassword"
meshtastic --port /dev/ttyUSB1 --set network.wifi_enabled true
```

Then you can:
1. Find their IP addresses in router (192.168.4.x)
2. Add them to node_sources.json as TCP sources
3. Poll via both USB AND WiFi!

## Current Setup Summary

**Docker Compose includes:**
- ✅ /dev/ttyUSB0 mounted
- ✅ /dev/ttyUSB1 mounted
- ✅ dialout group (GID 20) for USB access
- ✅ PostgreSQL for concurrent data writes
- ✅ Node poller reads from both devices every 5 min
- ✅ MQTT collector for global network
- ✅ HTTP API on port 8081
- ✅ Web map on port 8088

**Ready to deploy!** 🚀
