#!/bin/bash
# Meshtastic IoT Network Scanner
# Scans 192.168.4.0/24 for Meshtastic devices on TCP port 4403

echo "=== Meshtastic IoT Network Scanner ==="
echo "Scanning 192.168.4.0/24 for devices on port 4403..."
echo ""

# Check if we can reach the IoT network
if ! ip route | grep -q "192.168.4"; then
    echo "⚠️  WARNING: 192.168.4.x network not found in routing table"
    echo "   This host may not have access to the IoT network"
    echo ""
    echo "Current routes:"
    ip route
    echo ""
fi

found=0
total=0

# Quick scan of common IP range
for i in {1..50}; do
    ip="192.168.4.$i"
    total=$((total + 1))
    
    # Try to connect to Meshtastic TCP port
    if timeout 0.5 bash -c "echo > /dev/tcp/$ip/4403" 2>/dev/null; then
        echo "✅ FOUND: $ip:4403"
        found=$((found + 1))
        
        # Try to get device info
        echo "   Testing connection..."
        timeout 2 curl -s "http://$ip/json/node/info" 2>/dev/null || echo "   (HTTP API not available)"
        echo ""
    else
        echo -n "."
    fi
done

echo ""
echo ""
echo "=== Scan Complete ==="
echo "Scanned: $total IPs"
echo "Found: $found Meshtastic device(s)"
echo ""

if [ $found -eq 0 ]; then
    echo "No Meshtastic devices found on 192.168.4.0/24"
    echo ""
    echo "Troubleshooting:"
    echo "1. Check if devices have WiFi enabled"
    echo "2. Verify devices are on 192.168.4.x network"
    echo "3. Check firewall rules"
    echo "4. Ensure TCP server is enabled on devices"
    echo ""
    echo "Alternative: Use USB polling instead (already configured)"
else
    echo "To add these devices to the system:"
    echo "1. Edit config/node_sources.json"
    echo "2. Add entries like:"
    echo '   {"type": "tcp", "host": "192.168.4.X", "port": 4403, "name": "node-X", "enabled": true}'
    echo "3. Restart: docker compose restart meshmap"
fi
