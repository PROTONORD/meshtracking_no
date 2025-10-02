#!/bin/bash
# Meshtastic System Verification Script

echo "=== Meshtastic Multi-Source Map - System Check ==="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# 1. Check Docker
echo "1. Checking Docker..."
if command -v docker &> /dev/null; then
    check_pass "Docker is installed"
else
    check_fail "Docker is not installed"
    exit 1
fi

# 2. Check Docker Compose
echo ""
echo "2. Checking Docker Compose..."
if docker compose version &> /dev/null; then
    check_pass "Docker Compose is installed"
else
    check_fail "Docker Compose is not installed"
    exit 1
fi

# 3. Check USB device
echo ""
echo "3. Checking USB device..."
if [ -e "/dev/ttyUSB0" ]; then
    check_pass "USB device /dev/ttyUSB0 exists"
    ls -l /dev/ttyUSB0
else
    check_warn "USB device /dev/ttyUSB0 not found (polling will fail)"
fi

# 4. Check dialout group
echo ""
echo "4. Checking dialout group..."
if groups | grep -q dialout; then
    check_pass "Current user is in dialout group"
else
    check_warn "Current user not in dialout group"
    echo "  Run: sudo usermod -a -G dialout \$USER"
fi

# 5. Check directory structure
echo ""
echo "5. Checking directory structure..."
if [ -d "/home/kau005/meshtastic-docker" ]; then
    check_pass "Project directory exists"
    cd /home/kau005/meshtastic-docker
else
    check_fail "Project directory not found"
    exit 1
fi

required_files=(
    "docker-compose.yml"
    "deploy.sh"
    "README.md"
    "map/mqtt_collector_pg.py"
    "map/node_poller.py"
    "map/node_api.py"
    "map/db_to_geojson_pg.py"
    "map/run.sh"
    "map/init.sql"
    "map/Dockerfile"
)

echo ""
echo "6. Checking required files..."
for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        check_pass "$file"
    else
        check_fail "$file missing"
    fi
done

# 7. Check config directory
echo ""
echo "7. Checking configuration..."
if [ -d "config" ]; then
    check_pass "Config directory exists"
else
    check_warn "Config directory missing, creating..."
    mkdir -p config
fi

if [ -f "config/node_sources.json" ]; then
    check_pass "node_sources.json exists"
else
    check_warn "node_sources.json missing (will use defaults)"
fi

# 8. Check data directory
echo ""
echo "8. Checking data directory..."
if [ -d "/home/kau005/meshtastic-data" ]; then
    check_pass "Data directory exists"
    ls -lh /home/kau005/meshtastic-data/
else
    check_warn "Data directory missing, creating..."
    mkdir -p /home/kau005/meshtastic-data
fi

# 9. Check for old SQLite files
echo ""
echo "9. Checking for old SQLite files..."
if ls /home/kau005/meshtastic-data/*.db* 2>/dev/null; then
    check_warn "Old SQLite files found (will be removed on deploy)"
else
    check_pass "No old SQLite files"
fi

# 10. Check systemd service
echo ""
echo "10. Checking systemd service..."
if systemctl is-active --quiet meshtastic-usb-collector.service; then
    check_warn "Old systemd service is running (will be stopped on deploy)"
elif systemctl is-enabled --quiet meshtastic-usb-collector.service 2>/dev/null; then
    check_warn "Old systemd service is enabled (will be disabled on deploy)"
else
    check_pass "No conflicting systemd service"
fi

# 11. Check Docker containers
echo ""
echo "11. Checking Docker containers..."
if docker compose ps --services &> /dev/null; then
    running=$(docker compose ps --services --filter "status=running" 2>/dev/null | wc -l)
    if [ "$running" -gt 0 ]; then
        check_warn "Docker containers are running (will be restarted on deploy)"
        docker compose ps
    else
        check_pass "No running containers"
    fi
else
    check_pass "No existing deployment"
fi

# 12. Check ports
echo ""
echo "12. Checking ports..."
ports=(1883 5432 8088 8081)
for port in "${ports[@]}"; do
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        check_warn "Port $port is in use"
    else
        check_pass "Port $port is available"
    fi
done

# Summary
echo ""
echo "========================================="
echo "System Check Complete!"
echo ""
echo "Next steps:"
echo "1. Review any warnings above"
echo "2. Run: ./deploy.sh"
echo "3. Access map at: http://127.0.0.1:8088"
echo "========================================="
