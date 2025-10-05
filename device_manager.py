#!/usr/bin/env python3
"""
Dynamic Meshtastic Device Manager
Continuously discovers, manages and polls USB and TCP Meshtastic devices.
Devices that disappear are removed after a configurable number of failed attempts.
"""

import os
import time
import json
import logging
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
import meshtastic
import meshtastic.tcp_interface
import meshtastic.serial_interface
from meshtastic.util import findPorts
import subprocess
import threading
import socket
import netifaces
from ipaddress import IPv4Network, IPv4Address

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Meshtastic LoRa Region Code mapping
REGION_CODE_MAP = {
    0: 'UNSET',
    1: 'US',
    2: 'EU_433',
    3: 'EU_868',
    4: 'CN',
    5: 'JP',
    6: 'ANZ',
    7: 'KR',
    8: 'TW',
    9: 'RU',
    10: 'IN',
    11: 'NZ_865',
    12: 'TH',
    13: 'UA_433',
    14: 'UA_868',
    15: 'MY_433',
    16: 'MY_919',
    17: 'SG_923',
    18: 'LORA_24',
}

class DeviceInfo:
    """Represents a discovered Meshtastic device"""
    def __init__(self, device_type: str, address: str, name: str = None):
        self.type = device_type  # 'serial' or 'tcp'
        self.address = address  # USB port or IP:port
        self.name = name or address
        self.last_seen = time.time()
        self.fail_count = 0
        self.node_count = 0
        self.last_success = None
        # Primary/Standby properties
        self.is_primary = False
        self.priority_score = 0.0
        self.standby_poll_counter = 0
        
    def mark_success(self, node_count: int):
        """Mark successful poll"""
        self.last_seen = time.time()
        self.last_success = time.time()
        self.fail_count = 0
        self.node_count = node_count
        
    def mark_failure(self):
        """Mark failed poll attempt"""
        self.fail_count += 1
        self.last_seen = time.time()
        
    def should_remove(self, max_fails: int) -> bool:
        """Check if device should be removed from active list"""
        return self.fail_count >= max_fails
    
    def calculate_priority_score(self) -> float:
        """
        Calculate device priority based on coverage, reliability, and recency.
        Higher score = better candidate for primary role.
        """
        if self.node_count == 0:
            return 0.0
            
        # Base score: node count (primary factor)
        score = float(self.node_count)
        
        # Reliability penalty: reduce score based on fail rate (max 50% reduction)
        reliability = max(0.5, 1.0 - (self.fail_count * 0.1))
        score *= reliability
        
        # Recency bonus: prefer devices with recent successful polls (up to 10% bonus)
        if self.last_success:
            age_seconds = time.time() - self.last_success
            recency_bonus = max(1.0, 1.1 - (age_seconds / 3600))  # Decay over 1 hour
            score *= recency_bonus
            
        return score
        
    def to_dict(self) -> dict:
        """Serialize device info"""
        return {
            'type': self.type,
            'address': self.address,
            'name': self.name,
            'last_seen': self.last_seen,
            'fail_count': self.fail_count,
            'node_count': self.node_count,
            'last_success': self.last_success,
            'is_primary': self.is_primary,
            'priority_score': self.priority_score
        }

class MeshtasticDeviceManager:
    """Manages discovery and polling of Meshtastic devices"""
    
    def __init__(self):
        self.db_config = {
            'host': os.environ.get('DB_HOST', 'localhost'),
            'port': int(os.environ.get('DB_PORT', 5432)),
            'database': os.environ.get('DB_NAME', 'meshtastic'),
            'user': os.environ.get('DB_USER', 'meshuser'),
            'password': os.environ.get('DB_PASSWORD')  # Required - no default
        }
        
        # Configuration
        self.discovery_interval = int(os.environ.get('DISCOVERY_INTERVAL', '60'))  # seconds
        self.poll_interval = int(os.environ.get('POLL_INTERVAL', '300'))  # seconds
        self.max_fail_count = int(os.environ.get('MAX_FAIL_COUNT', '10'))  # remove after X fails
        self.tcp_port = int(os.environ.get('MESHTASTIC_TCP_PORT', '4403'))
        self.auto_detect_networks = os.environ.get('AUTO_DETECT_NETWORKS', 'true').lower() == 'true'
        self.manual_networks = os.environ.get('MANUAL_SCAN_NETWORKS', '').split(',') if os.environ.get('MANUAL_SCAN_NETWORKS') else []
        
        # Primary/Standby configuration
        self.primary_failover_threshold = int(os.environ.get('PRIMARY_FAILOVER_THRESHOLD', '3'))
        self.standby_poll_divisor = int(os.environ.get('STANDBY_POLL_DIVISOR', '5'))
        
        # Active devices registry
        self.devices: Dict[str, DeviceInfo] = {}
        self.devices_lock = threading.Lock()
        
        # Config file for manual device registry
        self.config_file = '/data/config/device_registry.json'
        
        logging.info(f"Device Manager initialized:")
        logging.info(f"  Discovery interval: {self.discovery_interval}s")
        logging.info(f"  Poll interval: {self.poll_interval}s")
        logging.info(f"  Max fails before removal: {self.max_fail_count}")
        logging.info(f"  Auto-detect networks: {self.auto_detect_networks}")
        if self.manual_networks:
            logging.info(f"  Manual networks: {self.manual_networks}")
        
        # Initialize MQTT client for publishing node data
        try:
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.username_pw_set(MQTT_CONFIG['user'], MQTT_CONFIG['password'])
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
            
            logging.info(f"📡 Connecting to MQTT broker at {MQTT_CONFIG['host']}:{MQTT_CONFIG['port']}")
            self.mqtt_client.connect(MQTT_CONFIG['host'], MQTT_CONFIG['port'], 60)
            self.mqtt_client.loop_start()
            
        except Exception as e:
            logging.error(f"❌ MQTT initialization failed: {e}")
            self.mqtt_client = None
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback when MQTT connection is established"""
        if rc == 0:
            self.mqtt_connected = True
            logging.info("✅ MQTT broker connected - node publishing enabled")
        else:
            self.mqtt_connected = False
            logging.error(f"❌ MQTT connection failed with code {rc}")
    
    def _on_mqtt_disconnect(self, client, userdata, rc):
        """Callback when MQTT connection is lost"""
        self.mqtt_connected = False
        if rc != 0:
            logging.warning(f"⚠️ MQTT disconnected unexpectedly (code {rc})")
        else:
            logging.info("📡 MQTT disconnected")
    
    def publish_node_info(self, node_data: Dict):
        """Publish node information to MQTT broker"""
        if not self.mqtt_connected or not self.mqtt_client:
            return
        
        try:
            node_id = node_data.get('node_id', 'unknown')
            topic = f"msh/nodes/{node_id}"
            
            # Create clean payload (remove None values)
            payload = {k: v for k, v in node_data.items() if v is not None}
            payload_json = json.dumps(payload)
            
            result = self.mqtt_client.publish(topic, payload_json, qos=1, retain=True)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logging.debug(f"📤 Published node {node_id} to MQTT")
            else:
                logging.warning(f"⚠️ MQTT publish failed for {node_id}: {result.rc}")
                
        except Exception as e:
            logging.error(f"❌ Failed to publish node info: {e}")
        
    def load_manual_devices(self):
        """Load manually configured devices from config file (read fresh every time)"""
        manual_devices = {}
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    for addr, info in data.items():
                        # Only add if not already discovered
                        if addr not in self.devices:
                            device = DeviceInfo(
                                device_type=info['type'],
                                address=addr,
                                name=info.get('name', addr)
                            )
                            manual_devices[addr] = device
                            logging.info(f"📋 Loaded manual device: {device.name} ({addr})")
        except Exception as e:
            logging.warning(f"Failed to load config file: {e}")
        return manual_devices
            
    def discover_usb_devices(self) -> Set[str]:
        """Discover USB serial devices"""
        discovered = set()
        try:
            ports = findPorts()
            for port in ports:
                discovered.add(port)
                with self.devices_lock:
                    if port not in self.devices:
                        logging.info(f"🔌 New USB device discovered: {port}")
                        self.devices[port] = DeviceInfo('serial', port, f"USB-{port.split('/')[-1]}")
        except Exception as e:
            logging.error(f"USB discovery failed: {e}")
        return discovered
        
    def get_local_networks(self) -> Set[str]:
        """Auto-detect local network ranges from server's interfaces"""
        networks = set()
        
        try:
            # Get all network interfaces
            for interface in netifaces.interfaces():
                # Skip loopback but INCLUDE tailscale
                if interface.startswith('lo'):
                    continue
                
                # Skip docker bridges (but not tailscale)
                if interface.startswith(('docker', 'br-')) and not interface.startswith('tailscale'):
                    continue
                    
                addrs = netifaces.ifaddresses(interface)
                
                # Check IPv4 addresses
                if netifaces.AF_INET in addrs:
                    for addr_info in addrs[netifaces.AF_INET]:
                        ip = addr_info.get('addr')
                        netmask = addr_info.get('netmask')
                        
                        if ip and netmask and not ip.startswith('127.'):
                            try:
                                # Calculate network CIDR
                                network = IPv4Network(f"{ip}/{netmask}", strict=False)
                                
                                # Special handling for Tailscale CGNAT range (100.64.0.0/10)
                                if ip.startswith('100.'):
                                    logging.info(f"🔗 Detected Tailscale network: {network} (interface: {interface})")
                                    networks.add(str(network))
                                else:
                                    networks.add(str(network))
                                    logging.info(f"🌐 Detected local network: {network} (interface: {interface})")
                            except Exception as e:
                                logging.debug(f"Failed to parse network {ip}/{netmask}: {e}")
                                
        except Exception as e:
            logging.error(f"Failed to detect local networks: {e}")
            
        return networks
    
    def discover_wifi_devices(self) -> Set[str]:
        """Discover WiFi/TCP devices on local networks"""
        discovered = set()
        
        # Get networks to scan
        scan_networks = set()
        
        if self.auto_detect_networks:
            scan_networks.update(self.get_local_networks())
            
        if self.manual_networks:
            scan_networks.update([n.strip() for n in self.manual_networks if n.strip()])
        
        if not scan_networks:
            logging.warning("No networks to scan. Enable AUTO_DETECT_NETWORKS or set MANUAL_SCAN_NETWORKS")
            return discovered
            
        logging.info(f"🔍 Scanning {len(scan_networks)} network(s) for Meshtastic devices...")
        
        for network in scan_networks:
            try:
                # Use nmap for fast ping scan if available
                result = subprocess.run(
                    ['nmap', '-sn', '-oG', '-', network],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                # Parse nmap output for active hosts
                for line in result.stdout.split('\n'):
                    if 'Up' in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            ip = parts[1].replace('(', '').replace(')', '')
                            # Try to connect to Meshtastic TCP port
                            address = f"{ip}:{self.tcp_port}"
                            if self.test_tcp_device(ip):
                                discovered.add(address)
                                with self.devices_lock:
                                    if address not in self.devices:
                                        logging.info(f"📡 New WiFi device discovered: {address}")
                                        self.devices[address] = DeviceInfo('tcp', address, f"WiFi-{ip}")
            except subprocess.TimeoutExpired:
                logging.warning(f"Network scan timeout for {network}")
            except FileNotFoundError:
                logging.warning("nmap not found, trying fallback method...")
                self.fallback_network_scan(network)
            except Exception as e:
                logging.warning(f"WiFi discovery failed for {network}: {e}")
                
        return discovered
        
    def fallback_network_scan(self, network_cidr: str):
        """Fallback network scan without nmap (slower)"""
        try:
            network = IPv4Network(network_cidr)
            
            # Only scan class C or smaller to avoid huge scans
            if network.num_addresses > 256:
                logging.warning(f"Network {network_cidr} too large for fallback scan (>256 hosts)")
                return
                
            logging.info(f"Fallback scan of {network_cidr} ({network.num_addresses} hosts)...")
            
            for ip in network.hosts():
                ip_str = str(ip)
                if self.test_tcp_device(ip_str):
                    address = f"{ip_str}:{self.tcp_port}"
                    with self.devices_lock:
                        if address not in self.devices:
                            logging.info(f"📡 New WiFi device discovered: {address}")
                            self.devices[address] = DeviceInfo('tcp', address, f"WiFi-{ip_str}")
                            
        except Exception as e:
            logging.error(f"Fallback scan failed for {network_cidr}: {e}")
                        
    def test_tcp_device(self, ip: str) -> bool:
        """Quick test if TCP port is open and responding"""
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((ip, self.tcp_port))
            sock.close()
            return result == 0
        except:
            return False
            
    def poll_device(self, device: DeviceInfo) -> Optional[List[dict]]:
        """Poll a single device for node information"""
        try:
            interface = None
            if device.type == 'serial':
                logging.debug(f"Connecting to serial device: {device.address}")
                interface = meshtastic.serial_interface.SerialInterface(device.address)
            else:  # tcp
                # Parse address - can be "ip" or "ip:port"
                if ':' in device.address:
                    ip, port = device.address.split(':')
                else:
                    ip = device.address
                    port = None
                logging.debug(f"Connecting to TCP device: {ip}")
                interface = meshtastic.tcp_interface.TCPInterface(hostname=ip)
                
            # Wait a bit for interface to initialize
            time.sleep(2)
            
            # Get the device's own node ID for prioritization
            my_node_info = interface.getMyNodeInfo()
            my_node_id = f"!{my_node_info.get('num', 0):08x}" if my_node_info else None
            
            # Get device region from local config (for radio nodes)
            device_region = None
            try:
                if hasattr(interface, 'localNode') and interface.localNode:
                    local_config = interface.localNode.localConfig
                    if hasattr(local_config, 'lora') and hasattr(local_config.lora, 'region'):
                        region_code = local_config.lora.region
                        device_region = REGION_CODE_MAP.get(region_code, f'UNKNOWN_{region_code}')
                        logging.info(f"📡 Device {device.name} region: {device_region} (code {region_code})")
            except Exception as e:
                logging.debug(f"Could not get region from {device.name}: {e}")
            
            nodes_data = []
            if interface.nodes:
                for node_id, node in interface.nodes.items():
                    try:
                        # Get lastHeard timestamp from node database
                        last_heard = node.get('lastHeard')
                        
                        # Check if this node has fixed position
                        position = node.get('position', {})
                        has_fixed_position = position.get('fixedPosition', False)
                        
                        # Determine if this is a self-report (device reporting its own position)
                        is_self_report = (node_id == my_node_id)
                        
                        # Convert role string to integer for database storage
                        role_text = node.get('user', {}).get('role')
                        role_mapping = {
                            'CLIENT': 0,
                            'CLIENT_MUTE': 1, 
                            'ROUTER': 2,
                            'ROUTER_CLIENT': 3,
                            'REPEATER': 4,
                            'TRACKER': 5,
                            'SENSOR': 6,
                            'TAK': 7,
                            'CLIENT_HIDDEN': 8,
                            'LOST_AND_FOUND': 9,
                            'TAK_TRACKER': 10
                        }
                        role_int = role_mapping.get(role_text) if role_text else None
                        
                        # Extract ALL telemetry data from node
                        device_metrics = node.get('deviceMetrics', {})
                        env_metrics = node.get('environmentMetrics', {})
                        air_metrics = node.get('airQualityMetrics', {})
                        power_metrics = node.get('powerMetrics', {})
                        
                        node_data = {
                            'node_id': node_id,
                            'node_num': node.get('num'),
                            'long_name': node.get('user', {}).get('longName'),
                            'short_name': node.get('user', {}).get('shortName'),
                            'hw_model': node.get('user', {}).get('hwModel'),
                            'role': role_int,
                            'latitude': position.get('latitude'),
                            'longitude': position.get('longitude'),
                            'altitude': position.get('altitude'),
                            
                            # Device Metrics
                            'battery_level': device_metrics.get('batteryLevel'),
                            'voltage': device_metrics.get('voltage'),
                            'channel_utilization': device_metrics.get('channelUtilization'),
                            'air_util_tx': device_metrics.get('airUtilTx'),
                            'uptime_seconds': device_metrics.get('uptimeSeconds'),
                            
                            # Environment Metrics
                            'temperature': env_metrics.get('temperature'),
                            'relative_humidity': env_metrics.get('relativeHumidity'),
                            'barometric_pressure': env_metrics.get('barometricPressure'),
                            'gas_resistance': env_metrics.get('gasResistance'),
                            'iaq': env_metrics.get('iaq'),
                            'distance': env_metrics.get('distance'),
                            'lux': env_metrics.get('lux'),
                            'white_lux': env_metrics.get('whiteLux'),
                            'ir_lux': env_metrics.get('irLux'),
                            'uv_lux': env_metrics.get('uvLux'),
                            'wind_direction': env_metrics.get('windDirection'),
                            'wind_speed': env_metrics.get('windSpeed'),
                            'wind_gust': env_metrics.get('windGust'),
                            'wind_lull': env_metrics.get('windLull'),
                            'weight': env_metrics.get('weight'),
                            
                            # Air Quality Metrics
                            'pm10_standard': air_metrics.get('pm10Standard'),
                            'pm25_standard': air_metrics.get('pm25Standard'),
                            'pm100_standard': air_metrics.get('pm100Standard'),
                            'co2': air_metrics.get('co2'),
                            'voc_idx': air_metrics.get('vocIdx'),
                            'nox_idx': air_metrics.get('noxIdx'),
                            
                            # Power Metrics (multi-channel)
                            'ch1_voltage': power_metrics.get('ch1Voltage'),
                            'ch1_current': power_metrics.get('ch1Current'),
                            'ch2_voltage': power_metrics.get('ch2Voltage'),
                            'ch2_current': power_metrics.get('ch2Current'),
                            'ch3_voltage': power_metrics.get('ch3Voltage'),
                            'ch3_current': power_metrics.get('ch3Current'),
                            
                            # Network metrics
                            'snr': node.get('snr'),
                            'rssi': node.get('rssi'),
                            'hops_away': node.get('hopsAway'),
                            
                            # Region (from device config)
                            'region': device_region,
                            
                            # Metadata
                            'last_heard': last_heard,
                            'source': device.name,
                            'has_fixed_position': has_fixed_position,
                            'is_self_report': is_self_report,
                            
                            # Sensor capability flags
                            'has_power_sensor': bool(power_metrics),
                            'has_environment_sensor': bool(env_metrics),
                            'has_air_quality_sensor': bool(air_metrics)
                        }
                        nodes_data.append(node_data)
                    except Exception as e:
                        logging.warning(f"Failed to parse node {node_id}: {e}")
                        
            interface.close()
            
            if nodes_data:
                logging.info(f"✅ {device.name}: Retrieved {len(nodes_data)} nodes")
                device.mark_success(len(nodes_data))
                self.save_node_data(nodes_data)
                return nodes_data
            else:
                logging.warning(f"⚠️  {device.name}: No nodes returned")
                device.mark_failure()
                
        except Exception as e:
            logging.error(f"❌ {device.name}: Poll failed - {e}")
            device.mark_failure()
            
        return None
        
    def save_node_data(self, nodes_data: List[dict]):
        """Save node data to PostgreSQL database with smart position update logic"""
        if not nodes_data:
            return
            
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            for node in nodes_data:
                node_id = node['node_id']
                is_self_report = node.get('is_self_report', False)
                has_fixed_position = node.get('has_fixed_position', False)
                new_lat = node.get('latitude')
                new_lon = node.get('longitude')
                
                # Get current position from database
                cur.execute("""
                    SELECT latitude, longitude, source 
                    FROM nodes 
                    WHERE node_id = %s
                """, (node_id,))
                existing = cur.fetchone()
                
                # Determine if we should update position
                should_update_position = True
                skip_reason = None
                
                if existing:
                    old_lat, old_lon, old_source = existing
                    
                    # Rule 1: Skip if node has fixed position and this is NOT a self-report
                    if has_fixed_position and not is_self_report:
                        should_update_position = False
                        skip_reason = f"fixed position node, ignoring 3rd-party update from {node['source']}"
                    
                    # Rule 2: Skip if position hasn't changed (within 0.0001 degrees ~11 meters)
                    elif old_lat and old_lon and new_lat and new_lon:
                        lat_diff = abs(float(old_lat) - float(new_lat))
                        lon_diff = abs(float(old_lon) - float(new_lon))
                        if lat_diff < 0.0001 and lon_diff < 0.0001:
                            should_update_position = False
                            skip_reason = "position unchanged"
                    
                    # Rule 3: Prioritize self-reports over 3rd-party reports
                    # If existing source is self-report, only update from another self-report
                    elif old_source and is_self_report == False:
                        # Check if old source was a self-report (contains the node_id in source name)
                        # This is a heuristic - self-reports typically come from the node's own gateway
                        pass  # For now, allow update
                
                if not should_update_position:
                    logging.debug(f"⏭️  Skipping position update for {node_id}: {skip_reason}")
                    # Still update other fields, just not position
                    new_lat = None
                    new_lon = None
                    node['altitude'] = None
                
                # Convert lastHeard Unix timestamp to datetime if present
                last_heard_dt = None
                if node.get('last_heard'):
                    try:
                        last_heard_dt = datetime.fromtimestamp(node['last_heard'])
                    except:
                        pass
                
                # Upsert with smart position handling
                cur.execute("""
                    INSERT INTO nodes (
                        node_id, node_num, long_name, short_name, hw_model, role,
                        latitude, longitude, altitude, battery_level, voltage,
                        snr, hops_away, source, source_interface, region, last_radio_contact, last_heard, last_updated
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                    )
                    ON CONFLICT (node_id) DO UPDATE SET
                        node_num = COALESCE(EXCLUDED.node_num, nodes.node_num),
                        long_name = COALESCE(EXCLUDED.long_name, nodes.long_name),
                        short_name = COALESCE(EXCLUDED.short_name, nodes.short_name),
                        hw_model = COALESCE(EXCLUDED.hw_model, nodes.hw_model),
                        role = COALESCE(EXCLUDED.role, nodes.role),
                        latitude = COALESCE(EXCLUDED.latitude, nodes.latitude),
                        longitude = COALESCE(EXCLUDED.longitude, nodes.longitude),
                        altitude = COALESCE(EXCLUDED.altitude, nodes.altitude),
                        battery_level = COALESCE(EXCLUDED.battery_level, nodes.battery_level),
                        voltage = COALESCE(EXCLUDED.voltage, nodes.voltage),
                        snr = COALESCE(EXCLUDED.snr, nodes.snr),
                        hops_away = COALESCE(EXCLUDED.hops_away, nodes.hops_away),
                        source = COALESCE(EXCLUDED.source, nodes.source),
                        source_interface = COALESCE(EXCLUDED.source_interface, nodes.source_interface),
                        region = COALESCE(EXCLUDED.region, nodes.region),
                        last_radio_contact = EXCLUDED.last_radio_contact,
                        last_heard = COALESCE(EXCLUDED.last_heard, nodes.last_heard),
                        last_updated = NOW()
                """, (
                    node_id,
                    node['node_num'],
                    node['long_name'],
                    node['short_name'],
                    node['hw_model'],
                    node['role'],
                    new_lat,  # Will be None if position shouldn't update
                    new_lon,
                    node['altitude'] if should_update_position else None,
                    node['battery_level'],
                    node['voltage'],
                    node['snr'],
                    node['hops_away'],
                    'radio',  # source
                    node['source'],  # source_interface (device name)
                    node.get('region'),  # region from device config
                    datetime.now(timezone.utc),  # last_radio_contact  
                    last_heard_dt
                ))
                
                # ========== HISTORICAL DATA STORAGE ==========
                # Save telemetry history with ALL available metrics
                telemetry_data = {}
                has_telemetry = False
                
                # Check if we have ANY telemetry data worth saving
                telemetry_fields = [
                    'battery_level', 'voltage', 'channel_utilization', 'air_util_tx', 'uptime_seconds',
                    'temperature', 'relative_humidity', 'barometric_pressure', 'gas_resistance', 'iaq',
                    'pm10_standard', 'pm25_standard', 'pm100_standard', 'co2', 'voc_idx', 'nox_idx',
                    'lux', 'white_lux', 'ir_lux', 'uv_lux', 'wind_direction', 'wind_speed',
                    'wind_gust', 'wind_lull', 'weight', 'distance',
                    'ch1_voltage', 'ch1_current', 'ch2_voltage', 'ch2_current', 'ch3_voltage', 'ch3_current',
                    'snr', 'rssi', 'hops_away'
                ]
                
                for field in telemetry_fields:
                    value = node.get(field)
                    telemetry_data[field] = value
                    if value is not None:
                        has_telemetry = True
                
                if has_telemetry:
                    try:
                        cur.execute("""
                            INSERT INTO telemetry (
                                node_id, timestamp,
                                battery_level, voltage, channel_utilization, air_util_tx, uptime_seconds,
                                temperature, relative_humidity, barometric_pressure, gas_resistance, iaq,
                                pm10_standard, pm25_standard, pm100_standard, co2, voc_idx, nox_idx,
                                lux, white_lux, ir_lux, uv_lux, wind_direction, wind_speed,
                                wind_gust, wind_lull, weight, distance,
                                ch1_voltage, ch1_current, ch2_voltage, ch2_current, ch3_voltage, ch3_current,
                                snr, rssi, hops_away,
                                has_power_metrics, has_environment_metrics, has_air_quality_metrics
                            ) VALUES (
                                %s, NOW(),
                                %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s,
                                %s, %s, %s,
                                %s, %s, %s
                            )
                        """, (
                            node_id,
                            telemetry_data['battery_level'], telemetry_data['voltage'],
                            telemetry_data['channel_utilization'], telemetry_data['air_util_tx'],
                            telemetry_data['uptime_seconds'],
                            telemetry_data['temperature'], telemetry_data['relative_humidity'],
                            telemetry_data['barometric_pressure'], telemetry_data['gas_resistance'],
                            telemetry_data['iaq'],
                            telemetry_data['pm10_standard'], telemetry_data['pm25_standard'],
                            telemetry_data['pm100_standard'], telemetry_data['co2'],
                            telemetry_data['voc_idx'], telemetry_data['nox_idx'],
                            telemetry_data['lux'], telemetry_data['white_lux'],
                            telemetry_data['ir_lux'], telemetry_data['uv_lux'],
                            telemetry_data['wind_direction'], telemetry_data['wind_speed'],
                            telemetry_data['wind_gust'], telemetry_data['wind_lull'],
                            telemetry_data['weight'], telemetry_data['distance'],
                            telemetry_data['ch1_voltage'], telemetry_data['ch1_current'],
                            telemetry_data['ch2_voltage'], telemetry_data['ch2_current'],
                            telemetry_data['ch3_voltage'], telemetry_data['ch3_current'],
                            telemetry_data['snr'], telemetry_data['rssi'],
                            telemetry_data['hops_away'],
                            node.get('has_power_sensor', False),
                            node.get('has_environment_sensor', False),
                            node.get('has_air_quality_sensor', False)
                        ))
                        logging.debug(f"📊 Saved complete telemetry history for {node_id}")
                    except Exception as tel_err:
                        logging.warning(f"Failed to save telemetry for {node_id}: {tel_err}")
                
                # Save position history (if position was updated and valid)
                if should_update_position and new_lat and new_lon:
                    try:
                        cur.execute("""
                            INSERT INTO positions (
                                node_id, timestamp, latitude, longitude, altitude, position_source
                            ) VALUES (%s, NOW(), %s, %s, %s, %s)
                        """, (
                            node_id,
                            new_lat,
                            new_lon,
                            node.get('altitude'),
                            'gps'  # From radio/GPS
                        ))
                        logging.debug(f"📍 Saved position history for {node_id}: {new_lat:.4f}, {new_lon:.4f}")
                    except Exception as pos_err:
                        logging.warning(f"Failed to save position for {node_id}: {pos_err}")
            
            conn.commit()
            cur.close()
            conn.close()
            
            logging.info(f"💾 Saved {len(nodes_data)} nodes to database (with history)")
            
        except Exception as e:
            logging.error(f"Database save failed: {e}")
    
    def select_primary_device(self) -> Optional[DeviceInfo]:
        """
        Select device with best coverage as primary.
        Returns the current primary device.
        """
        with self.devices_lock:
            if not self.devices:
                return None
                
            # Calculate priority scores for all devices
            for device in self.devices.values():
                device.priority_score = device.calculate_priority_score()
            
            # Sort by priority score (highest first)
            sorted_devices = sorted(
                self.devices.values(),
                key=lambda d: d.priority_score,
                reverse=True
            )
            
            # Select new primary
            new_primary = sorted_devices[0] if sorted_devices else None
            
            # Update primary status and log changes
            for device in self.devices.values():
                was_primary = device.is_primary
                device.is_primary = (device == new_primary)
                
                # Log role changes
                if device.is_primary and not was_primary:
                    health_pct = int(100 * (1.0 - min(1.0, device.fail_count * 0.1)))
                    logging.info(
                        f"👑 NEW PRIMARY: {device.name} "
                        f"(nodes: {device.node_count}, score: {device.priority_score:.1f}, "
                        f"health: {health_pct}%)"
                    )
                elif was_primary and not device.is_primary:
                    logging.info(f"⏸️  DEMOTED: {device.name} (now standby)")
            
            return new_primary
            
    def cleanup_dead_devices(self):
        """Remove devices that have failed too many times"""
        with self.devices_lock:
            to_remove = []
            for addr, device in self.devices.items():
                if device.should_remove(self.max_fail_count):
                    to_remove.append(addr)
                    
            for addr in to_remove:
                device = self.devices[addr]
                logging.warning(f"🗑️  Removing dead device: {device.name} (failed {device.fail_count} times)")
                del self.devices[addr]
                
    def discovery_loop(self):
        """Continuous device discovery thread"""
        while True:
            try:
                logging.info("🔍 Starting device discovery...")
                usb_devices = self.discover_usb_devices()
                wifi_devices = self.discover_wifi_devices()
                
                with self.devices_lock:
                    active_count = len(self.devices)
                    
                logging.info(f"📊 Discovery complete: {active_count} active devices")
                
            except Exception as e:
                logging.error(f"Discovery loop error: {e}")
                
            time.sleep(self.discovery_interval)
            
    def polling_loop(self):
        """Continuous device polling with intelligent primary/standby prioritization"""
        poll_cycle = 0
        
        while True:
            try:
                # Load manual devices from config file
                manual_devices = self.load_manual_devices()
                with self.devices_lock:
                    # Merge manual devices with discovered devices
                    self.devices.update(manual_devices)
                    
                if not self.devices:
                    logging.info("No devices to poll, waiting...")
                    time.sleep(self.poll_interval)
                    continue
                
                # Re-select primary based on latest coverage data
                primary_device = self.select_primary_device()
                
                # Determine which devices to poll this cycle
                devices_to_poll = []
                
                with self.devices_lock:
                    for device in self.devices.values():
                        if device.is_primary:
                            # Always poll primary device
                            devices_to_poll.append(device)
                        else:
                            # Poll standby devices less frequently (every Nth cycle)
                            device.standby_poll_counter += 1
                            if device.standby_poll_counter >= self.standby_poll_divisor:
                                devices_to_poll.append(device)
                                device.standby_poll_counter = 0
                
                if devices_to_poll:
                    logging.info(f"🔄 Polling {len(devices_to_poll)} device(s) (cycle {poll_cycle})...")
                    
                    # Poll primary first, then standby devices
                    primary_first = sorted(devices_to_poll, key=lambda d: not d.is_primary)
                    
                    for device in primary_first:
                        role = "PRIMARY" if device.is_primary else "STANDBY"
                        logging.info(f"  📡 [{role}] {device.name}")
                        self.poll_device(device)
                        time.sleep(1)  # Small delay between devices
                    
                    # Check if primary is failing - trigger immediate failover
                    if primary_device and primary_device.fail_count >= self.primary_failover_threshold:
                        logging.warning(
                            f"⚠️  Primary {primary_device.name} failing "
                            f"({primary_device.fail_count} failures), triggering re-selection..."
                        )
                        self.select_primary_device()
                
                self.cleanup_dead_devices()
                poll_cycle += 1
                
            except Exception as e:
                logging.error(f"Polling loop error: {e}")
                
            time.sleep(self.poll_interval)
            
    def run(self):
        """Start device manager with intelligent primary/standby management"""
        logging.info("🚀 Starting Meshtastic Device Manager")
        logging.info(f"  Primary failover threshold: {self.primary_failover_threshold} failures")
        logging.info(f"  Standby poll frequency: 1/{self.standby_poll_divisor} of primary")
        
        # Start discovery thread
        discovery_thread = threading.Thread(target=self.discovery_loop, daemon=True)
        discovery_thread.start()
        
        # Start polling thread
        polling_thread = threading.Thread(target=self.polling_loop, daemon=True)
        polling_thread.start()
        
        # Keep main thread alive and show enhanced status
        try:
            while True:
                time.sleep(60)
                with self.devices_lock:
                    if not self.devices:
                        continue
                        
                    active = len(self.devices)
                    working = sum(1 for d in self.devices.values() if d.fail_count == 0)
                    
                    logging.info(f"💓 Status: {working}/{active} devices responding")
                    
                    # Show detailed status for each device
                    for device in sorted(self.devices.values(), key=lambda d: not d.is_primary):
                        if device.is_primary:
                            health_pct = int(100 * (1.0 - min(1.0, device.fail_count * 0.1)))
                            logging.info(
                                f"  👑 PRIMARY: {device.name} "
                                f"(nodes: {device.node_count}, score: {device.priority_score:.1f}, "
                                f"health: {health_pct}%)"
                            )
                        else:
                            health_pct = int(100 * (1.0 - min(1.0, device.fail_count * 0.1)))
                            logging.info(
                                f"  ⏸️  STANDBY: {device.name} "
                                f"(nodes: {device.node_count}, score: {device.priority_score:.1f}, "
                                f"health: {health_pct}%)"
                            )
                            
        except KeyboardInterrupt:
            logging.info("Shutting down...")

if __name__ == '__main__':
    manager = MeshtasticDeviceManager()
    manager.run()
