#!/usr/bin/env python3
"""
MQTT Collector for Meshtastic
Subscribes to Mosquitto broker and stores node data in SQLite database.
Works with both global MQTT bridge and local Heltec V3 radio data.
"""

import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import paho.mqtt.client as mqtt
from meshtastic.protobuf import mesh_pb2, mqtt_pb2, portnums_pb2, telemetry_pb2

# Configuration from environment
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "meshlocal")
MQTT_PASS = os.getenv("MQTT_PASS", "meshLocal2025")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "msh/#")
DB_PATH = Path(os.getenv("DB_PATH", "/data/nodes.db"))

# Node storage
nodes_cache: Dict[str, Dict[str, Any]] = {}


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create database tables if they don't exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS positions (
            node_id TEXT NOT NULL,
            node_num INTEGER,
            timestamp INTEGER NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            altitude REAL,
            PRIMARY KEY (node_id, timestamp)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS nodes (
            node_id TEXT PRIMARY KEY,
            node_num INTEGER,
            long_name TEXT,
            short_name TEXT,
            hw_model TEXT,
            role TEXT,
            last_heard INTEGER,
            latitude REAL,
            longitude REAL,
            altitude REAL,
            battery_level INTEGER,
            voltage REAL,
            channel_util REAL,
            air_util_tx REAL,
            snr REAL,
            hops_away INTEGER
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_positions_timestamp ON positions(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_positions_node_id ON positions(node_id)")
    conn.commit()


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
            pos = mesh_pb2.Position()
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
        # Log parsing errors for debugging
        print(f"DEBUG: Failed to parse {topic}: {type(e).__name__}: {e}", flush=True)
        return None


def update_node(conn: sqlite3.Connection, node_id: str, node_num: int, data: Dict[str, Any]) -> None:
    """Update or insert node information in database."""
    timestamp = int(time.time())
    
    # Get existing node data
    if node_id not in nodes_cache:
        row = conn.execute("SELECT * FROM nodes WHERE node_id = ?", (node_id,)).fetchone()
        if row:
            cols = [d[0] for d in conn.execute("SELECT * FROM nodes LIMIT 0").description]
            nodes_cache[node_id] = dict(zip(cols, row))
        else:
            nodes_cache[node_id] = {"node_id": node_id, "node_num": node_num, "last_heard": timestamp}
    
    node = nodes_cache[node_id]
    node["last_heard"] = timestamp
    node["node_num"] = node_num
    
    # Update with new data
    if "user" in data:
        user = data["user"]
        node["long_name"] = user.get("long_name", node.get("long_name"))
        node["short_name"] = user.get("short_name", node.get("short_name"))
        node["hw_model"] = user.get("hw_model", node.get("hw_model"))
        node["role"] = user.get("role", node.get("role"))
    
    if "position" in data:
        pos = data["position"]
        if pos.get("latitude") and pos.get("longitude"):
            node["latitude"] = pos["latitude"]
            node["longitude"] = pos["longitude"]
            node["altitude"] = pos.get("altitude")
            
            # Store in positions table for trails
            store_position(
                conn,
                node_id,
                node_num,
                timestamp,
                pos["latitude"],
                pos["longitude"],
                pos.get("altitude"),
            )
    
    if "telemetry" in data:
        telem = data["telemetry"]
        node["battery_level"] = telem.get("battery_level", node.get("battery_level"))
        node["voltage"] = telem.get("voltage", node.get("voltage"))
        node["channel_util"] = telem.get("channel_utilization", node.get("channel_util"))
        node["air_util_tx"] = telem.get("air_util_tx", node.get("air_util_tx"))
    
    # Save to database
    conn.execute(
        """
        INSERT OR REPLACE INTO nodes 
        (node_id, node_num, long_name, short_name, hw_model, role, last_heard,
         latitude, longitude, altitude, battery_level, voltage, channel_util, air_util_tx, snr, hops_away)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            node["node_id"],
            node.get("node_num"),
            node.get("long_name"),
            node.get("short_name"),
            node.get("hw_model"),
            node.get("role"),
            node.get("last_heard"),
            node.get("latitude"),
            node.get("longitude"),
            node.get("altitude"),
            node.get("battery_level"),
            node.get("voltage"),
            node.get("channel_util"),
            node.get("air_util_tx"),
            node.get("snr"),
            node.get("hops_away"),
        ),
    )
    conn.commit()


def store_position(
    conn: sqlite3.Connection,
    node_id: str,
    node_num: Optional[int],
    ts: int,
    lat: float,
    lon: float,
    alt: Optional[float],
) -> None:
    """Store position in database and update node's latest position."""
    # Store in positions table
    conn.execute(
        "INSERT OR IGNORE INTO positions (node_id, node_num, timestamp, latitude, longitude, altitude)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (node_id, node_num, ts, lat, lon, alt),
    )
    
    # Update node's latest position
    conn.execute(
        """
        UPDATE nodes 
        SET latitude = ?, longitude = ?, altitude = ?, last_heard = ?
        WHERE node_id = ?
        """,
        (lat, lon, alt, ts, node_id),
    )
    
    conn.commit()


def on_connect(client, userdata, flags, rc):
    """Callback when connected to MQTT broker."""
    if rc == 0:
        print(f"Connected to MQTT broker at {MQTT_HOST}:{MQTT_PORT}", flush=True)
        client.subscribe(MQTT_TOPIC)
        print(f"Subscribed to topic: {MQTT_TOPIC}", flush=True)
    else:
        print(f"Failed to connect, return code {rc}", flush=True)


def on_message(client, userdata, msg):
    """Callback when MQTT message is received."""
    conn = userdata["db"]
    
    try:
        # Only process protobuf messages (map and encrypted)
        data = parse_service_envelope(msg.payload, msg.topic)
        
        if not data or "from" not in data:
            return
        
        node_id = data["from"]
        node_num = data.get("from_num", 0)
        
        if not node_id:
            return
        
        # Print updates for interesting messages
        if "position" in data or "user" in data:
            print(f"✓ {node_id} ({node_num}) - {msg.topic.split('/')[-2:]}", flush=True)
        
        update_node(conn, node_id, node_num, data)
        
    except Exception as e:
        print(f"ERROR processing {msg.topic}: {e}", flush=True)


def main():
    """Main loop."""
    import sys
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
    
    print("=" * 60, flush=True)
    print("Meshtastic MQTT Collector", flush=True)
    print("=" * 60, flush=True)
    print(f"Database: {DB_PATH}", flush=True)
    print(f"MQTT: {MQTT_USER}@{MQTT_HOST}:{MQTT_PORT}", flush=True)
    print(f"Topic: {MQTT_TOPIC}", flush=True)
    print("=" * 60, flush=True)
    
    # Initialize database
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    ensure_schema(conn)
    print("✓ Database initialized", flush=True)
    
    # Setup MQTT client
    client = mqtt.Client(userdata={"db": conn})
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_connect = on_connect
    client.on_message = on_message
    
    # Connect and loop
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    print("✓ Starting MQTT loop...", flush=True)
    print("=" * 60, flush=True)
    client.loop_forever()


if __name__ == "__main__":
    main()
