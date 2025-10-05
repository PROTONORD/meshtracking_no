#!/bin/bash
echo "=== PORT & SERVICE CONFLICT CHECK ===" > /tmp/conflict_check.txt
echo "Date: $(date)" >> /tmp/conflict_check.txt
echo "" >> /tmp/conflict_check.txt

echo "1. MESHTRACKING CONFIGURED PORTS" >> /tmp/conflict_check.txt
echo "=================================" >> /tmp/conflict_check.txt
echo "From docker-compose.yml:" >> /tmp/conflict_check.txt
grep -A2 "ports:" /home/kau005/meshtracking_no/docker-compose.yml >> /tmp/conflict_check.txt 2>&1
echo "" >> /tmp/conflict_check.txt

echo "2. CURRENTLY LISTENING ON HOST" >> /tmp/conflict_check.txt
echo "===============================" >> /tmp/conflict_check.txt
echo "Checking meshtracking ports..." >> /tmp/conflict_check.txt
ss -tulpn | grep -E ":(1883|5434|8088|4403|9443)" >> /tmp/conflict_check.txt 2>&1
echo "" >> /tmp/conflict_check.txt

echo "3. DETAILED PORT ANALYSIS" >> /tmp/conflict_check.txt
echo "=========================" >> /tmp/conflict_check.txt

# Check each port
for port in 1883 5434 8088 4403 9443; do
    echo "Port $port:" >> /tmp/conflict_check.txt
    result=$(ss -tulpn | grep ":$port " | head -1)
    if [ -z "$result" ]; then
        echo "  ✅ FREE" >> /tmp/conflict_check.txt
    else
        echo "  ⚠️ IN USE: $result" >> /tmp/conflict_check.txt
    fi
done
echo "" >> /tmp/conflict_check.txt

echo "4. USB DEVICE CONFLICTS" >> /tmp/conflict_check.txt
echo "=======================" >> /tmp/conflict_check.txt
echo "USB device status:" >> /tmp/conflict_check.txt
ls -la /dev/ttyUSB* 2>&1 >> /tmp/conflict_check.txt
echo "" >> /tmp/conflict_check.txt
echo "Processes using USB:" >> /tmp/conflict_check.txt
lsof /dev/ttyUSB* 2>&1 >> /tmp/conflict_check.txt || echo "No processes using USB (or lsof not available)" >> /tmp/conflict_check.txt
echo "" >> /tmp/conflict_check.txt

echo "5. LEGACY MESHTASTIC SERVICE CHECK" >> /tmp/conflict_check.txt
echo "===================================" >> /tmp/conflict_check.txt
systemctl status meshtastic-usb-collector.service 2>&1 | head -15 >> /tmp/conflict_check.txt
echo "" >> /tmp/conflict_check.txt

echo "6. MESHTRACKING CONTAINER STATUS" >> /tmp/conflict_check.txt
echo "=================================" >> /tmp/conflict_check.txt
docker ps -a --filter name=meshtracking --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" >> /tmp/conflict_check.txt 2>&1
echo "" >> /tmp/conflict_check.txt

echo "7. DOCKER-COMPOSE ANALYSIS" >> /tmp/conflict_check.txt
echo "==========================" >> /tmp/conflict_check.txt
echo "Services defined in docker-compose.yml:" >> /tmp/conflict_check.txt
grep "^  [a-z]" /home/kau005/meshtracking_no/docker-compose.yml >> /tmp/conflict_check.txt 2>&1
echo "" >> /tmp/conflict_check.txt

echo "8. VOLUME CONFLICTS" >> /tmp/conflict_check.txt
echo "===================" >> /tmp/conflict_check.txt
echo "Docker volumes for meshtracking:" >> /tmp/conflict_check.txt
docker volume ls | grep meshtracking >> /tmp/conflict_check.txt 2>&1
echo "" >> /tmp/conflict_check.txt
echo "Volume usage:" >> /tmp/conflict_check.txt
docker volume inspect meshtracking_no_meshtracking_data 2>&1 | jq '.[] | {Name, Mountpoint, Driver}' >> /tmp/conflict_check.txt 2>&1
echo "" >> /tmp/conflict_check.txt

echo "9. NETWORK CONFLICTS" >> /tmp/conflict_check.txt
echo "====================" >> /tmp/conflict_check.txt
echo "Docker networks:" >> /tmp/conflict_check.txt
docker network ls | grep meshtracking >> /tmp/conflict_check.txt 2>&1
echo "" >> /tmp/conflict_check.txt
echo "Network details:" >> /tmp/conflict_check.txt
docker network inspect meshtracking_net 2>&1 | jq '.[0] | {Name, Driver, Subnet: .IPAM.Config[0].Subnet}' >> /tmp/conflict_check.txt 2>&1
echo "" >> /tmp/conflict_check.txt

echo "10. SUPERVISOR SERVICES IN CONTAINER" >> /tmp/conflict_check.txt
echo "=====================================" >> /tmp/conflict_check.txt
echo "Expected services from supervisord.conf:" >> /tmp/conflict_check.txt
docker exec meshtracking grep "^\[program:" /etc/supervisor/conf.d/supervisord.conf 2>&1 >> /tmp/conflict_check.txt || echo "Container not running" >> /tmp/conflict_check.txt
echo "" >> /tmp/conflict_check.txt

echo "11. RESOURCE LIMITS" >> /tmp/conflict_check.txt
echo "===================" >> /tmp/conflict_check.txt
echo "Docker-compose resource limits:" >> /tmp/conflict_check.txt
grep -A5 "deploy:" /home/kau005/meshtracking_no/docker-compose.yml >> /tmp/conflict_check.txt 2>&1 || echo "No resource limits defined" >> /tmp/conflict_check.txt
echo "" >> /tmp/conflict_check.txt

echo "12. STARTUP CONFLICTS" >> /tmp/conflict_check.txt
echo "=====================" >> /tmp/conflict_check.txt
echo "Services that auto-start on boot:" >> /tmp/conflict_check.txt
systemctl list-unit-files | grep -E "meshtastic|mqtt" >> /tmp/conflict_check.txt 2>&1
echo "" >> /tmp/conflict_check.txt

echo "CONFLICT CHECK COMPLETE" >> /tmp/conflict_check.txt
cat /tmp/conflict_check.txt
