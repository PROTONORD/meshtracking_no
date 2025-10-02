#!/bin/bash
# Find all connected Meshtastic devices

echo "=== Scanning for Meshtastic USB Devices ==="
echo ""

# Find all USB serial devices
devices=()
for dev in /dev/ttyUSB* /dev/ttyACM*; do
    if [ -e "$dev" ]; then
        devices+=("$dev")
    fi
done

if [ ${#devices[@]} -eq 0 ]; then
    echo "❌ No USB serial devices found"
    echo ""
    echo "Troubleshooting:"
    echo "1. Check USB cables are connected"
    echo "2. Run: lsusb"
    echo "3. Check dmesg: dmesg | tail"
    exit 1
fi

echo "✅ Found ${#devices[@]} USB serial device(s):"
echo ""

# Check each device
for i in "${!devices[@]}"; do
    dev="${devices[$i]}"
    num=$((i + 1))
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Device #$num: $dev"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Check permissions
    if [ -r "$dev" ] && [ -w "$dev" ]; then
        echo "✅ Permissions: OK (readable/writable)"
    else
        echo "⚠️  Permissions: Limited"
        ls -l "$dev"
    fi
    
    # Try to get device info
    echo ""
    echo "📡 Device Info:"
    timeout 10 meshtastic --port "$dev" --info 2>&1 | grep -E "(Owner|MyNodeInfo|Hardware|MAC)" | head -10 || echo "   Failed to read device"
    
    echo ""
    echo "📶 WiFi Status:"
    timeout 8 meshtastic --port "$dev" --get network.wifi_enabled 2>&1 | head -5 || echo "   Failed to read WiFi status"
    
    echo ""
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "=== Configuration for node_sources.json ==="
echo ""
echo '{'
echo '  "sources": ['

for i in "${!devices[@]}"; do
    dev="${devices[$i]}"
    num=$((i + 1))
    
    echo '    {'
    echo '      "type": "serial",'
    echo "      \"path\": \"$dev\","
    echo "      \"name\": \"usb-node-$num\","
    echo '      "enabled": true,'
    echo "      \"description\": \"Heltec V3 #$num\""
    echo -n '    }'
    
    if [ $i -lt $((${#devices[@]} - 1)) ]; then
        echo ','
    else
        echo ''
    fi
done

echo '  ]'
echo '}'
echo ""
echo "Copy the configuration above to config/node_sources.json"
