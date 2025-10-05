#!/bin/bash
LOG="/home/kau005/meshtracking_no/website_analysis.log"

echo "MESHTASTIC WEBSITE ANALYSIS - $(date)" > $LOG
echo "=====================================" >> $LOG
echo "" >> $LOG

echo "PHASE 1: CONTAINER STATUS" >> $LOG
echo "-------------------------" >> $LOG
docker ps --filter name=meshtracking --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" >> $LOG 2>&1
echo "" >> $LOG

echo "PHASE 2: SERVICE STATUS (from supervisor)" >> $LOG
echo "----------------------------------------" >> $LOG
docker exec meshtracking supervisorctl status >> $LOG 2>&1
echo "" >> $LOG

echo "PHASE 3: DATABASE CHECK" >> $LOG
echo "----------------------" >> $LOG
echo "Database connection test:" >> $LOG
docker exec meshtracking psql -U meshuser -d meshtastic -c "\dt" >> $LOG 2>&1
echo "" >> $LOG
echo "Node count:" >> $LOG
docker exec meshtracking psql -U meshuser -d meshtastic -c "SELECT COUNT(*) FROM nodes;" >> $LOG 2>&1
echo "" >> $LOG
echo "Nodes with GPS:" >> $LOG
docker exec meshtracking psql -U meshuser -d meshtastic -c "SELECT COUNT(*) FROM nodes WHERE latitude IS NOT NULL AND longitude IS NOT NULL;" >> $LOG 2>&1
echo "" >> $LOG
echo "Sample node data:" >> $LOG
docker exec meshtracking psql -U meshuser -d meshtastic -c "SELECT node_id, short_name, long_name, latitude, longitude, last_updated FROM nodes WHERE latitude IS NOT NULL LIMIT 3;" >> $LOG 2>&1
echo "" >> $LOG

echo "PHASE 4: API ENDPOINT CHECK" >> $LOG
echo "---------------------------" >> $LOG
echo "Testing /nodes.geojson endpoint:" >> $LOG
curl -s http://localhost:8088/nodes.geojson | head -50 >> $LOG 2>&1
echo "" >> $LOG
echo "Feature count:" >> $LOG
curl -s http://localhost:8088/nodes.geojson | jq '.features | length' >> $LOG 2>&1
echo "" >> $LOG
echo "First feature structure:" >> $LOG
curl -s http://localhost:8088/nodes.geojson | jq '.features[0]' >> $LOG 2>&1
echo "" >> $LOG

echo "PHASE 5: WEB FILES CHECK" >> $LOG
echo "------------------------" >> $LOG
echo "index.html locations and sizes:" >> $LOG
docker exec meshtracking ls -lh /app/index.html /data/index.html >> $LOG 2>&1
echo "" >> $LOG
echo "index.html version info:" >> $LOG
docker exec meshtracking grep -i "VERSION\|version" /data/index.html | head -3 >> $LOG 2>&1
echo "" >> $LOG
echo "JavaScript node loading check:" >> $LOG
docker exec meshtracking grep -n "function loadNodes\|function renderNodes" /data/index.html | head -5 >> $LOG 2>&1
echo "" >> $LOG
echo "Property name usage in JavaScript:" >> $LOG
docker exec meshtracking grep -o "props\.longName\|props\.long_name\|properties\.longName\|properties\.long_name" /data/index.html | sort | uniq -c >> $LOG 2>&1
echo "" >> $LOG

echo "PHASE 6: PYTHON SERVER CODE CHECK" >> $LOG
echo "---------------------------------" >> $LOG
echo "combined_server.py GeoJSON property names:" >> $LOG
docker exec meshtracking grep -A15 '"properties"' /app/combined_server.py | head -20 >> $LOG 2>&1
echo "" >> $LOG

echo "PHASE 7: RECENT LOGS" >> $LOG
echo "-------------------" >> $LOG
echo "Last 30 lines from container:" >> $LOG
docker logs meshtracking --tail 30 >> $LOG 2>&1
echo "" >> $LOG

echo "PHASE 8: DEVICE MANAGER STATUS" >> $LOG
echo "------------------------------" >> $LOG
echo "Device manager recent activity:" >> $LOG
docker logs meshtracking 2>&1 | grep -i "device.manager\|wifi\|discovered" | tail -20 >> $LOG 2>&1
echo "" >> $LOG

echo "ANALYSIS COMPLETE - $(date)" >> $LOG
echo "========================================" >> $LOG
