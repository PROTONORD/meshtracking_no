#!/bin/bash
# Quick network scanner for Meshtastic devices on TCP port 4403

NETWORK="${1:-172.19.228.0/24}"
PORT="${2:-4403}"

echo "🔍 Scanning $NETWORK for Meshtastic devices on port $PORT..."
echo ""

if command -v nmap >/dev/null 2>&1; then
    echo "Using nmap (fast scan)..."
    nmap -p $PORT --open -T4 $NETWORK | grep -B 4 "open"
else
    echo "nmap not found, using nc fallback (slower)..."
    
    # Extract base IP from CIDR
    BASE_IP=$(echo $NETWORK | cut -d'/' -f1 | cut -d'.' -f1-3)
    
    for i in {1..254}; do
        IP="$BASE_IP.$i"
        timeout 1 bash -c "echo >/dev/tcp/$IP/$PORT" 2>/dev/null && {
            echo "✅ Found device at $IP:$PORT"
        }
    done
fi

echo ""
echo "Scan complete!"
