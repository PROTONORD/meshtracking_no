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
        
    def to_dict(self) -> dict:
        """Serialize device info"""
        return {
            'type': self.type,
            'address': self.address,
            'name': self.name,
            'last_seen': self.last_seen,
            'fail_count': self.fail_count,
            'node_count': self.node_count,
            'last_success': self.last_success
        }

class MeshtasticDeviceManager:
    """Manages discovery and polling of Meshtastic devices"""
    
    def __init__(self):
        self.db_config = {
            'host': os.environ.get('DB_HOST', 'localhost'),
            'port': int(os.environ.get('DB_PORT', 5432)),
            'database': os.environ.get('DB_NAME', 'meshtastic'),
            'user': os.environ.get('DB_USER', 'meshuser'),
            'password': os.environ.get('DB_PASSWORD', 'meshpass')
        }
        
        # Configuration
        self.discovery_interval = int(os.environ.get('DISCOVERY_INTERVAL', '60'))  # seconds
        self.poll_interval = int(os.environ.get('POLL_INTERVAL', '300'))  # seconds
        self.max_fail_count = int(os.environ.get('MAX_FAIL_COUNT', '10'))  # remove after X fails
        self.tcp_port = int(os.environ.get('MESHTASTIC_TCP_PORT', '4403'))
        self.auto_detect_networks = os.environ.get('AUTO_DETECT_NETWORKS', 'true').lower() == 'true'
        self.manual_networks = os.environ.get('MANUAL_SCAN_NETWORKS', '').split(',') if os.environ.get('MANUAL_SCAN_NETWORKS') else []
        
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
                        
                        node_data = {
                            'node_id': node_id,
                            'node_num': node.get('num'),
                            'long_name': node.get('user', {}).get('longName'),
                            'short_name': node.get('user', {}).get('shortName'),
                            'hw_model': node.get('user', {}).get('hwModel'),
                            'role': node.get('user', {}).get('role'),
                            'latitude': position.get('latitude'),
                            'longitude': position.get('longitude'),
                            'altitude': position.get('altitude'),
                            'battery_level': node.get('deviceMetrics', {}).get('batteryLevel'),
                            'voltage': node.get('deviceMetrics', {}).get('voltage'),
                            'snr': node.get('snr'),
                            'hops_away': node.get('hopsAway'),
                            'last_heard': last_heard,
                            'source': device.name,
                            'has_fixed_position': has_fixed_position,
                            'is_self_report': is_self_report
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
                        from datetime import datetime
                        last_heard_dt = datetime.fromtimestamp(node['last_heard'])
                    except:
                        pass
                
                # Upsert with smart position handling
                cur.execute("""
                    INSERT INTO nodes (
                        node_id, node_num, long_name, short_name, hw_model, role,
                        latitude, longitude, altitude, battery_level, voltage,
                        snr, hops_away, source, last_heard, last_updated
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
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
                    node['source'],
                    last_heard_dt
                ))
            
            conn.commit()
            cur.close()
            conn.close()
            
            logging.info(f"💾 Saved {len(nodes_data)} nodes to database")
            
        except Exception as e:
            logging.error(f"Database save failed: {e}")
            
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
        """Continuous device polling thread with staggered intervals"""
        poll_cycle = 0  # Counter for staggered polling
        
        while True:
            try:
                # Load manual devices from config file
                manual_devices = self.load_manual_devices()
                with self.devices_lock:
                    # Merge manual devices with discovered devices
                    self.devices.update(manual_devices)
                    devices_to_poll = list(self.devices.values())
                    
                if not devices_to_poll:
                    logging.info("No devices to poll, waiting...")
                    time.sleep(self.poll_interval)
                    continue
                
                # Stagger polling: USB on even cycles, WiFi on odd cycles
                # This prevents both nodes from updating at the same time
                filtered_devices = []
                for device in devices_to_poll:
                    if poll_cycle % 2 == 0:
                        # Even cycle: poll USB devices
                        if 'USB' in device.name or device.type == 'serial':
                            filtered_devices.append(device)
                    else:
                        # Odd cycle: poll WiFi/TCP devices  
                        if 'WiFi' in device.name or device.type == 'tcp':
                            filtered_devices.append(device)
                
                if filtered_devices:
                    logging.info(f"🔄 Polling {len(filtered_devices)} devices (cycle {poll_cycle % 2})...")
                    
                    for device in filtered_devices:
                        self.poll_device(device)
                        time.sleep(1)  # Small delay between devices
                    
                self.cleanup_dead_devices()
                poll_cycle += 1
                
            except Exception as e:
                logging.error(f"Polling loop error: {e}")
                
            time.sleep(self.poll_interval)
            
    def run(self):
        """Start device manager"""
        logging.info("🚀 Starting Meshtastic Device Manager")
        
        # Start discovery thread
        discovery_thread = threading.Thread(target=self.discovery_loop, daemon=True)
        discovery_thread.start()
        
        # Start polling thread
        polling_thread = threading.Thread(target=self.polling_loop, daemon=True)
        polling_thread.start()
        
        # Keep main thread alive
        try:
            while True:
                time.sleep(60)
                with self.devices_lock:
                    active = len(self.devices)
                    working = sum(1 for d in self.devices.values() if d.fail_count == 0)
                    logging.info(f"💓 Status: {working}/{active} devices responding")
        except KeyboardInterrupt:
            logging.info("Shutting down...")

if __name__ == '__main__':
    manager = MeshtasticDeviceManager()
    manager.run()
