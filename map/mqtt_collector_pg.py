#!/usr/bin/env python3
"""
MQTT Collector for Meshtastic (PostgreSQL version)
Subscribes to Mosquitto broker and stores node data in PostgreSQL database.
Works with both global MQTT bridge and local Heltec V3 radio data.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import paho.mqtt.client as mqtt
import psycopg2
from psycopg2.extras import RealDictCursor
from meshtastic.protobuf import mesh_pb2, mqtt_pb2, portnums_pb2, telemetry_pb2

# Configuration from environment
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "meshlocal")
MQTT_PASS = os.getenv("MQTT_PASS", "meshLocal2025")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "msh/#")

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'postgres'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'meshtastic'),
    'user': os.getenv('DB_USER', 'meshuser'),
    'password': os.getenv('DB_PASSWORD', 'meshpass2025')
}

# Node storage cache
nodes_cache: Dict[str, Dict[str, Any]] = {}


def get_db_connection():
    """Get PostgreSQL connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
        return conn
    except Exception as e:
        print(f"ERROR: Failed to connect to database: {e}", flush=True)
        return None


def parse_service_envelope(payload: bytes, topic: str) -> Optional[Dict[str, Any]]:
    """Parse Meshtastic ServiceEnvelope protobuf."""
    try:
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(payload)
        
        if not envelope.packet:
            return None
            
        packet = envelope.packet
        
        # Extract node ID (using 'from' not 'from_field' in newer protobuf)
        from_num = getattr(packet, 'from', None) or getattr(packet, 'from_field', None)
        to_num = getattr(packet, 'to', None)
        
        from_id = f"!{from_num:08x}" if from_num else None
        to_id = f"!{to_num:08x}" if to_num else None
        
        if not from_id:
            return None
        
        result = {
            "from": from_id,
            "from_num": from_num,
            "to": to_id,
            "packet_id": packet.id,
            "channel": packet.channel,
            "gateway_id": envelope.gateway_id,
            "channel_id": envelope.channel_id,
            "rx_snr": packet.rx_snr if hasattr(packet, 'rx_snr') else None,
            "hop_limit": packet.hop_limit if hasattr(packet, 'hop_limit') else None,
        }
        
        # Parse different payload types
        if packet.decoded.portnum == portnums_pb2.POSITION_APP:
            pos = mesh_pb2.Position()
            pos.ParseFromString(packet.decoded.payload)
            if pos.latitude_i and pos.longitude_i:
                result["position"] = {
                    "latitude": pos.latitude_i / 1e7,
                    "longitude": pos.longitude_i / 1e7,
                    "altitude": pos.altitude if pos.altitude else None,
                    "time": pos.time if pos.time else None,
                }
            
        elif packet.decoded.portnum == portnums_pb2.NODEINFO_APP:
            user = mesh_pb2.User()
            user.ParseFromString(packet.decoded.payload)
            result["user"] = {
                "id": user.id,
                "long_name": user.long_name,
                "short_name": user.short_name,
                "hw_model": mesh_pb2.HardwareModel.Name(user.hw_model) if user.hw_model else None,
                "role": mesh_pb2.Role.Name(user.role) if user.role else None,
            }
            
        elif packet.decoded.portnum == portnums_pb2.TELEMETRY_APP:
            telem = telemetry_pb2.Telemetry()
            telem.ParseFromString(packet.decoded.payload)
            if telem.HasField("device_metrics"):
                result["telemetry"] = {
                    "battery_level": telem.device_metrics.battery_level,
                    "voltage": telem.device_metrics.voltage,
                    "channel_utilization": telem.device_metrics.channel_utilization,
                    "air_util_tx": telem.device_metrics.air_util_tx,
                }
        
        # For MAP reports (position in user info)
        if "/map/" in topic and packet.decoded.portnum == portnums_pb2.MAP_REPORT_APP:
            user = mesh_pb2.User()
            user.ParseFromString(packet.decoded.payload)
            result["user"] = {
                "id": user.id,
                "long_name": user.long_name,
                "short_name": user.short_name,
                "hw_model": mesh_pb2.HardwareModel.Name(user.hw_model) if user.hw_model else None,
                "role": mesh_pb2.Role.Name(user.role) if user.role else None,
            }
            if user.position:
                result["position"] = {
                    "latitude": user.position.latitude_i / 1e7 if user.position.latitude_i else None,
                    "longitude": user.position.longitude_i / 1e7 if user.position.longitude_i else None,
                    "altitude": user.position.altitude if user.position.altitude else None,
                    "time": user.position.time if user.position.time else None,
                }
                
        return result
        
    except Exception as e:
        print(f"DEBUG: Failed to parse {topic}: {type(e).__name__}: {e}", flush=True)
        return None


def update_node(node_id: str, node_num: int, data: Dict[str, Any]) -> None:
    """Update or insert node information in database."""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        now = datetime.now(timezone.utc)
        
        # Build update data
        node_data = {
            'node_id': node_id,
            'node_num': node_num,
            'last_heard': now,
            'source': 'mqtt',
            'long_name': None,
            'short_name': None,
            'hw_model': None,
            'role': None,
            'latitude': None,
            'longitude': None,
            'altitude': None,
            'battery_level': None,
            'voltage': None,
            'snr': None
        }
        
        # Extract user info
        if "user" in data:
            user = data["user"]
            node_data['long_name'] = user.get("long_name")
            node_data['short_name'] = user.get("short_name")
            node_data['hw_model'] = user.get("hw_model")
            node_data['role'] = user.get("role")
        
        # Extract position
        if "position" in data:
            pos = data["position"]
            if pos.get("latitude") and pos.get("longitude"):
                node_data['latitude'] = pos["latitude"]
                node_data['longitude'] = pos["longitude"]
                node_data['altitude'] = pos.get("altitude")
        
        # Extract telemetry
        if "telemetry" in data:
            telem = data["telemetry"]
            node_data['battery_level'] = telem.get("battery_level")
            node_data['voltage'] = telem.get("voltage")
        
        # Extract SNR
        if "rx_snr" in data:
            node_data['snr'] = data["rx_snr"]
        
        # Upsert node
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
        """, node_data)
        
        # Store position if we have coordinates
        if node_data.get('latitude') and node_data.get('longitude'):
            cursor.execute("""
                INSERT INTO positions (
                    node_id, timestamp, latitude, longitude, altitude, source
                ) VALUES (
                    %(node_id)s, %(timestamp)s, %(latitude)s, %(longitude)s,
                    %(altitude)s, %(source)s
                )
                ON CONFLICT DO NOTHING
            """, {
                'node_id': node_id,
                'timestamp': now,
                'latitude': node_data['latitude'],
                'longitude': node_data['longitude'],
                'altitude': node_data.get('altitude'),
                'source': 'mqtt'
            })
        
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        # Don't spam errors for missing data - nodes without full info are normal
        if 'long_name' not in str(e):
            print(f"ERROR: Failed to update node {node_id}: {e}", flush=True)
    finally:
        cursor.close()
        conn.close()


def on_connect(client, userdata, flags, rc):
    """MQTT connection callback"""
    if rc == 0:
        print(f"✓ Connected to MQTT broker at {MQTT_HOST}:{MQTT_PORT}", flush=True)
        client.subscribe(MQTT_TOPIC)
        print(f"✓ Subscribed to topic: {MQTT_TOPIC}", flush=True)
    else:
        print(f"✗ Failed to connect to MQTT, return code: {rc}", flush=True)


def on_message(client, userdata, msg):
    """MQTT message callback"""
    try:
        data = parse_service_envelope(msg.payload, msg.topic)
        if data:
            node_id = data["from"]
            node_num = data["from_num"]
            
            # Log interesting packets
            packet_type = "unknown"
            if "position" in data:
                packet_type = "position"
            elif "user" in data:
                packet_type = "nodeinfo"
            elif "telemetry" in data:
                packet_type = "telemetry"
            
            print(f"📡 {packet_type}: {node_id} via {msg.topic}", flush=True)
            
            # Update node in database
            update_node(node_id, node_num, data)
            
    except Exception as e:
        print(f"ERROR: Failed to process message: {e}", flush=True)


def main():
    """Main MQTT listener loop"""
    print("=== Meshtastic MQTT Collector (PostgreSQL) ===", flush=True)
    print(f"MQTT Broker: {MQTT_HOST}:{MQTT_PORT}", flush=True)
    print(f"Topic: {MQTT_TOPIC}", flush=True)
    print(f"Database: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}", flush=True)
    
    # Test database connection
    conn = get_db_connection()
    if not conn:
        print("FATAL: Cannot connect to database. Exiting.", flush=True)
        sys.exit(1)
    conn.close()
    print("✓ Database connection OK", flush=True)
    
    # Connect to MQTT
    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        print("✓ Starting MQTT loop...", flush=True)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n✓ Shutting down gracefully...", flush=True)
        client.disconnect()
    except Exception as e:
        print(f"FATAL: MQTT connection error: {e}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
