#!/usr/bin/env python3
"""
Meshtastic Node Poller
Polls local and remote Meshtastic nodes for their node database
Can discover nodes via USB serial, network (WiFi), and Tailscale
"""

import os
import sys
import time
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timezone
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'postgres'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'meshtastic'),
    'user': os.getenv('DB_USER', 'meshuser'),
    'password': os.getenv('DB_PASSWORD', 'meshpass2025')
}

SERIAL_PORT = os.getenv('SERIAL_PORT', '/dev/ttyUSB0')
POLL_INTERVAL = int(os.getenv('NODE_POLL_INTERVAL', 300))  # 5 minutes default
CONFIG_FILE = os.getenv('NODE_SOURCES_CONFIG', '/data/config/node_sources.json')

# Load node sources from config file or use default
def load_node_sources():
    """Load node sources from config file"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                sources = config.get('sources', [])
                # Filter enabled sources
                return [s for s in sources if s.get('enabled', True)]
        else:
            logger.warning(f"Config file not found: {CONFIG_FILE}, using default USB source")
    except Exception as e:
        logger.error(f"Failed to load config file: {e}, using default USB source")
    
    # Default: just USB
    return [{'type': 'serial', 'path': SERIAL_PORT, 'name': 'local-usb'}]

NODE_SOURCES = load_node_sources()


def get_db_connection():
    """Get PostgreSQL connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return None


def poll_serial_node(serial_port):
    """Poll a Meshtastic node via serial and get its node database"""
    try:
        import meshtastic.serial_interface
        from meshtastic import BROADCAST_ADDR
        
        logger.info(f"Connecting to serial node at {serial_port}")
        interface = meshtastic.serial_interface.SerialInterface(serial_port)
        
        # Get node database from device
        nodes = []
        if hasattr(interface, 'nodes') and interface.nodes:
            for node_num, node_info in interface.nodes.items():
                try:
                    node_data = {
                        'node_num': node_num,
                        'node_id': node_info.get('user', {}).get('id', f"!{node_num:08x}"),
                        'long_name': node_info.get('user', {}).get('longName'),
                        'short_name': node_info.get('user', {}).get('shortName'),
                        'hw_model': node_info.get('user', {}).get('hwModel'),
                        'role': node_info.get('user', {}).get('role'),
                        'latitude': node_info.get('position', {}).get('latitude'),
                        'longitude': node_info.get('position', {}).get('longitude'),
                        'altitude': node_info.get('position', {}).get('altitude'),
                        'battery_level': node_info.get('deviceMetrics', {}).get('batteryLevel'),
                        'voltage': node_info.get('deviceMetrics', {}).get('voltage'),
                        'snr': node_info.get('snr'),
                        'last_heard': datetime.fromtimestamp(
                            node_info.get('lastHeard', time.time()), 
                            tz=timezone.utc
                        )
                    }
                    nodes.append(node_data)
                    logger.debug(f"Found node: {node_data['node_id']} - {node_data['long_name']}")
                except Exception as e:
                    logger.warning(f"Error parsing node {node_num}: {e}")
                    continue
        
        interface.close()
        logger.info(f"Retrieved {len(nodes)} nodes from serial device")
        return nodes
        
    except Exception as e:
        logger.error(f"Failed to poll serial node: {e}")
        return []


def poll_tcp_node(host, port=4403):
    """Poll a Meshtastic node via TCP and get its node database"""
    try:
        import meshtastic.tcp_interface
        
        logger.info(f"Connecting to TCP node at {host}:{port}")
        interface = meshtastic.tcp_interface.TCPInterface(hostname=host, portNumber=port)
        
        nodes = []
        if hasattr(interface, 'nodes') and interface.nodes:
            for node_num, node_info in interface.nodes.items():
                try:
                    node_data = {
                        'node_num': node_num,
                        'node_id': node_info.get('user', {}).get('id', f"!{node_num:08x}"),
                        'long_name': node_info.get('user', {}).get('longName'),
                        'short_name': node_info.get('user', {}).get('shortName'),
                        'hw_model': node_info.get('user', {}).get('hwModel'),
                        'role': node_info.get('user', {}).get('role'),
                        'latitude': node_info.get('position', {}).get('latitude'),
                        'longitude': node_info.get('position', {}).get('longitude'),
                        'altitude': node_info.get('position', {}).get('altitude'),
                        'battery_level': node_info.get('deviceMetrics', {}).get('batteryLevel'),
                        'voltage': node_info.get('deviceMetrics', {}).get('voltage'),
                        'snr': node_info.get('snr'),
                        'last_heard': datetime.fromtimestamp(
                            node_info.get('lastHeard', time.time()), 
                            tz=timezone.utc
                        )
                    }
                    nodes.append(node_data)
                    logger.debug(f"Found node: {node_data['node_id']} - {node_data['long_name']}")
                except Exception as e:
                    logger.warning(f"Error parsing node {node_num}: {e}")
                    continue
        
        interface.close()
        logger.info(f"Retrieved {len(nodes)} nodes from TCP device at {host}")
        return nodes
        
    except Exception as e:
        logger.error(f"Failed to poll TCP node at {host}:{port}: {e}")
        return []


def store_nodes_to_db(nodes, source_name):
    """Store or update nodes in PostgreSQL database"""
    if not nodes:
        logger.info(f"No nodes to store from source: {source_name}")
        return
    
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        for node in nodes:
            # Update or insert node
            cursor.execute("""
                INSERT INTO nodes (
                    node_id, node_num, long_name, short_name, hw_model, role,
                    latitude, longitude, altitude, battery_level, voltage, snr,
                    last_heard, last_updated, source, is_active
                ) VALUES (
                    %(node_id)s, %(node_num)s, %(long_name)s, %(short_name)s, 
                    %(hw_model)s, %(role)s, %(latitude)s, %(longitude)s, %(altitude)s,
                    %(battery_level)s, %(voltage)s, %(snr)s, %(last_heard)s, 
                    NOW(), %(source)s, TRUE
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
                    last_heard = GREATEST(EXCLUDED.last_heard, nodes.last_heard),
                    last_updated = NOW(),
                    source = EXCLUDED.source,
                    is_active = TRUE
            """, {**node, 'source': source_name})
            
            # Also store position if we have coordinates
            if node.get('latitude') and node.get('longitude'):
                cursor.execute("""
                    INSERT INTO positions (
                        node_id, timestamp, latitude, longitude, altitude, source
                    ) VALUES (
                        %(node_id)s, %(last_heard)s, %(latitude)s, %(longitude)s, 
                        %(altitude)s, %(source)s
                    )
                    ON CONFLICT DO NOTHING
                """, {**node, 'source': source_name})
        
        conn.commit()
        logger.info(f"✓ Stored {len(nodes)} nodes from {source_name} to database")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to store nodes to database: {e}")
    finally:
        cursor.close()
        conn.close()


def poll_all_sources():
    """Poll all configured node sources"""
    logger.info(f"Starting polling cycle for {len(NODE_SOURCES)} sources")
    
    for source in NODE_SOURCES:
        try:
            source_type = source.get('type')
            source_name = source.get('name', 'unknown')
            
            logger.info(f"Polling source: {source_name} ({source_type})")
            
            if source_type == 'serial':
                nodes = poll_serial_node(source.get('path'))
            elif source_type == 'tcp':
                nodes = poll_tcp_node(source.get('host'), source.get('port', 4403))
            else:
                logger.warning(f"Unknown source type: {source_type}")
                continue
            
            if nodes:
                store_nodes_to_db(nodes, source_name)
            else:
                logger.warning(f"No nodes retrieved from {source_name}")
                
        except Exception as e:
            logger.error(f"Error polling source {source.get('name')}: {e}")
            continue
    
    logger.info("Polling cycle completed")


def main():
    """Main polling loop"""
    logger.info("=== Meshtastic Node Poller Started ===")
    logger.info(f"Poll interval: {POLL_INTERVAL} seconds")
    logger.info(f"Configured sources: {len(NODE_SOURCES)}")
    
    # Initial poll
    poll_all_sources()
    
    # Continuous polling
    while True:
        try:
            time.sleep(POLL_INTERVAL)
            poll_all_sources()
        except KeyboardInterrupt:
            logger.info("Shutting down node poller...")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(10)  # Wait a bit before retrying


if __name__ == "__main__":
    main()
