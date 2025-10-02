#!/usr/bin/env python3
"""
USB Collector for Meshtastic
Reads data directly from Heltec V3 via USB serial connection.
Stores node data to SQLite database.
"""

import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import meshtastic
import meshtastic.serial_interface
from meshtastic.protobuf import mesh_pb2, portnums_pb2, telemetry_pb2

# Configuration
SERIAL_PORT = os.getenv("SERIAL_PORT", "/dev/ttyUSB0")
DB_PATH = Path(os.getenv("DB_PATH", "/home/kau005/meshtastic-data/nodes.db"))

# Global database connection
db_conn = None


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
            latitude REAL,
            longitude REAL,
            altitude REAL,
            battery_level INTEGER,
            voltage REAL,
            channel_util REAL,
            air_util_tx REAL,
            snr REAL,
            hops_away INTEGER,
            last_heard INTEGER
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_positions_timestamp ON positions(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_positions_node_id ON positions(node_id)")
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


def update_node(conn: sqlite3.Connection, node_id: str, node_num: int, data: Dict[str, Any]) -> None:
    """Update or insert node information in database."""
    timestamp = int(time.time())
    
    # Start with basic node info
    values = {
        "node_id": node_id,
        "node_num": node_num,
        "last_heard": timestamp,
    }
    
    # Update with user info if present
    if "user" in data:
        user = data["user"]
        values.update({
            "long_name": user.get("longName") or user.get("long_name"),
            "short_name": user.get("shortName") or user.get("short_name"),
            "hw_model": user.get("hwModel") or user.get("hw_model"),
            "role": user.get("role"),
        })
    
    # Update with position if present
    if "position" in data:
        pos = data["position"]
        lat = pos.get("latitude") or pos.get("latitudeI", 0) / 1e7
        lon = pos.get("longitude") or pos.get("longitudeI", 0) / 1e7
        alt = pos.get("altitude")
        
        if lat and lon:
            values.update({
                "latitude": lat,
                "longitude": lon,
                "altitude": alt,
            })
            # Also store in positions table
            store_position(conn, node_id, node_num, timestamp, lat, lon, alt)
    
    # Update with telemetry if present
    if "deviceMetrics" in data:
        metrics = data["deviceMetrics"]
        values.update({
            "battery_level": metrics.get("batteryLevel"),
            "voltage": metrics.get("voltage"),
            "channel_util": metrics.get("channelUtilization"),
            "air_util_tx": metrics.get("airUtilTx"),
        })
    
    # Insert or update node
    columns = ", ".join(values.keys())
    placeholders = ", ".join(["?" for _ in values])
    update_clause = ", ".join([f"{k} = excluded.{k}" for k in values.keys() if k != "node_id"])
    
    conn.execute(
        f"INSERT INTO nodes ({columns}) VALUES ({placeholders}) "
        f"ON CONFLICT(node_id) DO UPDATE SET {update_clause}",
        list(values.values()),
    )
    conn.commit()


def on_receive(packet, interface):
    """Callback for received packets from Meshtastic device."""
    global db_conn
    
    try:
        if not packet or not hasattr(packet, "get"):
            return
        
        # Extract node ID
        from_id = packet.get("fromId")
        from_num = packet.get("from")
        
        if not from_id:
            return
        
        # Build data dict
        data = {
            "from": from_id,
            "from_num": from_num,
        }
        
        # Extract decoded data
        decoded = packet.get("decoded")
        if decoded:
            portnum = decoded.get("portnum")
            
            # User info
            if portnum == "NODEINFO_APP" and "user" in decoded:
                data["user"] = decoded["user"]
                print(f"✓ USER: {from_id} - {decoded['user'].get('longName', 'unknown')}", flush=True)
            
            # Position
            if portnum == "POSITION_APP" and "position" in decoded:
                pos = decoded["position"]
                lat = pos.get("latitudeI", 0) / 1e7
                lon = pos.get("longitudeI", 0) / 1e7
                if lat != 0 and lon != 0:
                    data["position"] = {
                        "latitude": lat,
                        "longitude": lon,
                        "altitude": pos.get("altitude"),
                    }
                    print(f"✓ POS: {from_id} @ ({lat:.4f}, {lon:.4f})", flush=True)
            
            # Telemetry
            if portnum == "TELEMETRY_APP" and "telemetry" in decoded:
                telem = decoded["telemetry"]
                if "deviceMetrics" in telem:
                    data["deviceMetrics"] = telem["deviceMetrics"]
        
        # Store to database
        if "user" in data or "position" in data or "deviceMetrics" in data:
            update_node(db_conn, from_id, from_num, data)
        
    except Exception as e:
        print(f"ERROR processing packet: {e}", flush=True)


def main():
    """Main loop."""
    global db_conn
    
    print("=" * 60, flush=True)
    print("Meshtastic USB Collector", flush=True)
    print("=" * 60, flush=True)
    print(f"Database: {DB_PATH}", flush=True)
    print(f"Serial Port: {SERIAL_PORT}", flush=True)
    print("=" * 60, flush=True)
    
    # Initialize database
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db_conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    ensure_schema(db_conn)
    print("✓ Database initialized", flush=True)
    
    # Connect to Meshtastic device
    print(f"Connecting to {SERIAL_PORT}...", flush=True)
    
    try:
        interface = meshtastic.serial_interface.SerialInterface(
            devPath=SERIAL_PORT,
            connectNow=True,
        )
        
        print("✓ Connected to Meshtastic device", flush=True)
        
        # Subscribe to all packets
        pub.subscribe(on_receive, "meshtastic.receive")
        
        print("✓ Listening for packets...", flush=True)
        print("=" * 60, flush=True)
        
        # Keep running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nShutting down...", flush=True)
    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        sys.exit(1)
    finally:
        if db_conn:
            db_conn.close()


if __name__ == "__main__":
    # Import pubsub for meshtastic callbacks
    from pubsub import pub
    main()
