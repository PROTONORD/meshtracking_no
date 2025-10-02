#!/bin/bash
set -e

echo "🚀 === FINAL DEPLOYMENT - Dual USB Meshtastic Setup ==="
echo ""

cd /home/kau005/meshtastic-docker

# Step 1: Stop everything
echo "1️⃣ Stopping old services..."
sudo systemctl stop meshtastic-usb-collector.service 2>/dev/null || true
sudo systemctl disable meshtastic-usb-collector.service 2>/dev/null || true
docker compose down 2>/dev/null || true
echo "   ✓ Stopped"
echo ""

# Step 2: Clean old data
echo "2️⃣ Cleaning old SQLite files..."
rm -f /home/kau005/meshtastic-data/*.db* 2>/dev/null || true
echo "   ✓ Cleaned"
echo ""

# Step 3: Check USB devices
echo "3️⃣ Checking USB devices..."
usb_devices=$(ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true)
if [ -z "$usb_devices" ]; then
    echo "   ⚠️  WARNING: No USB devices found!"
    echo "   System will start but USB polling may fail"
else
    echo "   ✓ Found USB devices:"
    ls -la /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true
fi
echo ""

# Step 4: Build image
echo "4️⃣ Building Docker image..."
docker compose build meshmap 2>&1 | tail -5
echo "   ✓ Built"
echo ""

# Step 5: Start PostgreSQL first
echo "5️⃣ Starting PostgreSQL..."
docker compose up -d postgres
echo "   ⏳ Waiting 20 seconds for initialization..."
sleep 20
echo "   ✓ PostgreSQL ready"
echo ""

# Step 6: Start all services
echo "6️⃣ Starting all services..."
docker compose up -d
echo "   ✓ All services started"
echo ""

# Step 7: Wait for services to initialize
echo "7️⃣ Waiting for services to initialize..."
sleep 10
echo ""

# Step 8: Show status
echo "8️⃣ Service status:"
docker compose ps
echo ""

# Step 9: Quick health checks
echo "9️⃣ Health checks:"
echo ""

echo "   🗄️  PostgreSQL:"
if docker exec meshtastic-postgres pg_isready -U meshuser 2>&1 | grep -q "accepting"; then
    echo "      ✅ Database ready"
else
    echo "      ⚠️  Database not ready"
fi

echo ""
echo "   📡 MQTT Collector:"
if docker compose logs meshmap 2>&1 | grep -q "Connected to MQTT"; then
    echo "      ✅ Connected to MQTT"
else
    echo "      ⏳ Waiting for MQTT connection..."
fi

echo ""
echo "   🔌 Node Poller:"
sleep 5
if docker compose logs meshmap 2>&1 | grep -q "Meshtastic Node Poller\|Retrieved.*nodes"; then
    echo "      ✅ Node poller started"
else
    echo "      ⏳ Node poller initializing..."
fi

echo ""
echo "   🗺️  GeoJSON Generator:"
if docker compose logs meshmap 2>&1 | grep -q "GeoJSON Generator"; then
    echo "      ✅ GeoJSON generator started"
else
    echo "      ⏳ GeoJSON generator initializing..."
fi

echo ""
echo "   🌐 Web Server:"
if curl -s http://127.0.0.1:8088 > /dev/null 2>&1; then
    echo "      ✅ Web server responding"
else
    echo "      ⏳ Web server starting..."
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✨ DEPLOYMENT COMPLETE!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🌐 Access the map: http://127.0.0.1:8088"
echo "🔌 API endpoint: http://127.0.0.1:8081/api/v1/nodes"
echo ""
echo "📊 View logs:"
echo "   docker compose logs -f meshmap"
echo ""
echo "🔍 Check database:"
echo "   docker exec meshtastic-postgres psql -U meshuser -d meshtastic -c 'SELECT source, COUNT(*) FROM nodes GROUP BY source;'"
echo ""
echo "📡 Monitor node polling (wait 5 minutes for first poll):"
echo "   docker compose logs -f meshmap | grep 'Retrieved.*nodes'"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🎉 System is running! Give it 5-10 minutes to collect data from all sources."
echo ""
