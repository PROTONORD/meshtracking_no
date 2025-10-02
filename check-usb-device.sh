#!/bin/bash
# Meshtastic USB Device Info & WiFi Check

echo "=== Meshtastic Device Information ==="
echo ""

PORT="/dev/ttyUSB0"

if [ ! -e "$PORT" ]; then
    echo "❌ USB device not found at $PORT"
    echo "   Check USB connection"
    exit 1
fi

echo "✅ USB device found: $PORT"
echo ""

# Get device info
echo "📡 Device Info:"
echo "----------------------------------------"
timeout 15 meshtastic --port "$PORT" --info 2>&1 | grep -E "(Owner|MyNodeInfo|MAC|Hardware|Firmware|Region)" || echo "Failed to get device info"
echo ""

# Get WiFi settings
echo "📶 WiFi/Network Settings:"
echo "----------------------------------------"
timeout 15 meshtastic --port "$PORT" --get network 2>&1 || echo "Failed to get network settings"
echo ""

# Get full node list
echo "🗺️ Node Database (from device memory):"
echo "----------------------------------------"
timeout 20 meshtastic --port "$PORT" --nodes 2>&1 | head -100
echo ""

# Try to get MAC address specifically
echo "🔍 MAC Address:"
echo "----------------------------------------"
timeout 10 meshtastic --port "$PORT" --info 2>&1 | grep -i "mac\|address" || echo "MAC not found in info output"
echo ""

# Get preferences for WiFi details
echo "⚙️ WiFi Configuration Details:"
echo "----------------------------------------"
timeout 15 meshtastic --port "$PORT" --get network.wifi_enabled 2>&1
timeout 15 meshtastic --port "$PORT" --get network.wifi_ssid 2>&1
timeout 15 meshtastic --port "$PORT" --get network.address_mode 2>&1
echo ""

echo "=== Summary ==="
echo "To find device in router:"
echo "1. Look for MAC address above"
echo "2. Check router DHCP leases for 192.168.4.x range"
echo "3. Device name/hostname may appear as 'Meshtastic' or node short name"
