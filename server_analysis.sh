#!/bin/bash
echo "=== COMPLETE SERVER ANALYSIS ===" > /tmp/server_analysis.txt
echo "Date: $(date)" >> /tmp/server_analysis.txt
echo "" >> /tmp/server_analysis.txt

echo "1. OPERATING SYSTEM" >> /tmp/server_analysis.txt
echo "==================" >> /tmp/server_analysis.txt
cat /etc/os-release >> /tmp/server_analysis.txt
echo "" >> /tmp/server_analysis.txt
uname -a >> /tmp/server_analysis.txt
echo "" >> /tmp/server_analysis.txt

echo "2. HARDWARE INFO" >> /tmp/server_analysis.txt
echo "================" >> /tmp/server_analysis.txt
echo "CPU:" >> /tmp/server_analysis.txt
lscpu | grep -E "Model name|CPU\(s\)|Architecture" >> /tmp/server_analysis.txt
echo "" >> /tmp/server_analysis.txt
echo "Memory:" >> /tmp/server_analysis.txt
free -h >> /tmp/server_analysis.txt
echo "" >> /tmp/server_analysis.txt
echo "Disk:" >> /tmp/server_analysis.txt
df -h / /home >> /tmp/server_analysis.txt
echo "" >> /tmp/server_analysis.txt

echo "3. NETWORK CONFIGURATION" >> /tmp/server_analysis.txt
echo "========================" >> /tmp/server_analysis.txt
ip addr show | grep -E "inet |link/ether" >> /tmp/server_analysis.txt
echo "" >> /tmp/server_analysis.txt
echo "Hostname: $(hostname)" >> /tmp/server_analysis.txt
echo "IP: $(hostname -I)" >> /tmp/server_analysis.txt
echo "" >> /tmp/server_analysis.txt

echo "4. DOCKER INSTALLATION" >> /tmp/server_analysis.txt
echo "======================" >> /tmp/server_analysis.txt
docker --version >> /tmp/server_analysis.txt
docker-compose --version >> /tmp/server_analysis.txt
echo "" >> /tmp/server_analysis.txt
echo "Running Containers:" >> /tmp/server_analysis.txt
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" >> /tmp/server_analysis.txt
echo "" >> /tmp/server_analysis.txt

echo "5. INSTALLED SERVICES (systemd)" >> /tmp/server_analysis.txt
echo "================================" >> /tmp/server_analysis.txt
systemctl list-units --type=service --state=running --no-pager | head -30 >> /tmp/server_analysis.txt
echo "" >> /tmp/server_analysis.txt

echo "6. PYTHON ENVIRONMENT" >> /tmp/server_analysis.txt
echo "=====================" >> /tmp/server_analysis.txt
python3 --version >> /tmp/server_analysis.txt
which python3 >> /tmp/server_analysis.txt
echo "" >> /tmp/server_analysis.txt

echo "7. USER & GROUPS" >> /tmp/server_analysis.txt
echo "================" >> /tmp/server_analysis.txt
echo "Current user: $(whoami)" >> /tmp/server_analysis.txt
echo "User ID: $(id)" >> /tmp/server_analysis.txt
echo "" >> /tmp/server_analysis.txt

echo "8. USB DEVICES" >> /tmp/server_analysis.txt
echo "==============" >> /tmp/server_analysis.txt
ls -la /dev/ttyUSB* 2>/dev/null || echo "No USB devices found" >> /tmp/server_analysis.txt
echo "" >> /tmp/server_analysis.txt

echo "9. RUNNING PROCESSES (top 20)" >> /tmp/server_analysis.txt
echo "==============================" >> /tmp/server_analysis.txt
ps aux --sort=-%mem | head -20 >> /tmp/server_analysis.txt
echo "" >> /tmp/server_analysis.txt

echo "10. LISTENING PORTS" >> /tmp/server_analysis.txt
echo "===================" >> /tmp/server_analysis.txt
ss -tulpn | grep LISTEN >> /tmp/server_analysis.txt
echo "" >> /tmp/server_analysis.txt

echo "11. DOCKER CONTAINERS DETAIL" >> /tmp/server_analysis.txt
echo "============================" >> /tmp/server_analysis.txt
docker inspect meshtracking --format='{{json .}}' | jq '{Name, State, NetworkSettings: {IPAddress, Ports}, Mounts, Config: {Image, Env}}' >> /tmp/server_analysis.txt 2>/dev/null || echo "Container not found" >> /tmp/server_analysis.txt
echo "" >> /tmp/server_analysis.txt

echo "12. MESHTRACKING CONTAINER INTERNALS" >> /tmp/server_analysis.txt
echo "=====================================" >> /tmp/server_analysis.txt
docker exec meshtracking ps aux 2>/dev/null >> /tmp/server_analysis.txt || echo "Container not running" >> /tmp/server_analysis.txt
echo "" >> /tmp/server_analysis.txt

echo "13. INSTALLED DOCKER PROJECTS" >> /tmp/server_analysis.txt
echo "==============================" >> /tmp/server_analysis.txt
find /home/kau005 -maxdepth 2 -name "docker-compose.yml" -o -name "Dockerfile" 2>/dev/null >> /tmp/server_analysis.txt
echo "" >> /tmp/server_analysis.txt

echo "ANALYSIS COMPLETE" >> /tmp/server_analysis.txt
cat /tmp/server_analysis.txt
