#!/bin/bash
set -e

echo "=== Meshtastic PostgreSQL Migration ==="
echo ""

# Step 1: Stop everything
echo "1. Stopping all services..."
sudo systemctl stop meshtastic-usb-collector.service 2>/dev/null || true
sudo systemctl disable meshtastic-usb-collector.service 2>/dev/null || true
cd /home/kau005/meshtastic-docker
docker compose down
echo "   ✓ Services stopped"
echo ""

# Step 2: Clean old SQLite files
echo "2. Cleaning old SQLite database..."
rm -f /home/kau005/meshtastic-data/*.db*
echo "   ✓ SQLite files removed"
echo ""

# Step 3: Build new image
echo "3. Building new Docker image with PostgreSQL support..."
docker compose build meshmap
echo "   ✓ Image built"
echo ""

# Step 4: Start PostgreSQL first
echo "4. Starting PostgreSQL..."
docker compose up -d postgres
echo "   ⏳ Waiting for PostgreSQL to initialize (20 seconds)..."
sleep 20
echo "   ✓ PostgreSQL ready"
echo ""

# Step 5: Start all services
echo "5. Starting all services..."
docker compose up -d
echo "   ✓ All services started"
echo ""

# Step 6: Show status
echo "6. Service status:"
docker compose ps
echo ""

# Step 7: Follow logs
echo "7. Following logs (Ctrl+C to exit)..."
echo ""
sleep 3
docker compose logs -f meshmap
