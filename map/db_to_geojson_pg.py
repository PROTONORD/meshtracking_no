#!/usr/bin/env python3
"""
Generate GeoJSON from PostgreSQL database populated by MQTT collector and node poller.
"""

import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor

OUTPUT = Path(os.getenv("OUTPUT_PATH", "/data/nodes.geojson"))
TRAILS_OUTPUT = Path(os.getenv("TRAILS_OUTPUT_PATH", "/data/trails.geojson"))
FAVORITES_FILE = Path(os.getenv("FAVORITES_FILE", "/data/config/favorites.json"))
HISTORY_WINDOW_SECONDS = int(os.getenv("HISTORY_WINDOW_SECONDS", "86400"))
TRAIL_MIN_POINTS = int(os.getenv("TRAIL_MIN_POINTS", "2"))
MAX_POINTS_PER_NODE = int(os.getenv("TRAIL_MAX_POINTS", "500"))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'postgres'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'meshtastic'),
    'user': os.getenv('DB_USER', 'meshuser'),
    'password': os.getenv('DB_PASSWORD', 'meshpass2025')
}


def get_db_connection():
    """Get PostgreSQL connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"ERROR: Failed to connect to database: {e}", flush=True)
        return None


def load_favorites() -> Tuple[set[str], Dict[str, str], Dict[str, str]]:
    try:
        data = json.loads(FAVORITES_FILE.read_text())
    except FileNotFoundError:
        return set(), {}, {}
    except json.JSONDecodeError:
        return set(), {}, {}

    favs = {str(x) for x in data.get("favorites", [])}
    labels = {str(k): str(v) for k, v in data.get("labels", {}).items()}
    notes = {str(k): str(v) for k, v in data.get("notes", {}).items()}
    return favs, labels, notes


def format_timestamp(dt: datetime | None) -> Dict[str, Any]:
    if not dt:
        return {
            "lastHeard": None, 
            "lastHeardAgoSec": None, 
            "lastHeardIso": None,
            "lastHeardNorwegian": None,
            "status": "unknown"
        }

    # Convert to Oslo timezone
    from zoneinfo import ZoneInfo
    oslo_tz = ZoneInfo("Europe/Oslo")
    dt_oslo = dt.astimezone(oslo_tz)
    
    now = datetime.now(timezone.utc)
    ago = int((now - dt).total_seconds())
    
    # Determine status based on age
    if ago < 1800:  # < 30 minutes
        status = "online"
    elif ago < 7200:  # < 2 hours
        status = "recent"
    else:
        status = "offline"
    
    return {
        "lastHeard": dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "lastHeardAgoSec": ago,
        "lastHeardIso": dt.isoformat(),
        "lastHeardNorwegian": dt_oslo.strftime("%d.%m.%Y kl. %H:%M"),
        "status": status
    }


def fetch_trails(conn, cutoff_time: datetime) -> Iterable[Dict[str, Any]]:
    """Fetch position trails for all nodes within time window"""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT node_id, timestamp, latitude, longitude
        FROM positions
        WHERE timestamp >= %s
        ORDER BY node_id, timestamp
    """, (cutoff_time,))
    
    grouped: Dict[str, List[Tuple[datetime, float, float]]] = defaultdict(list)
    for row in cursor.fetchall():
        node_id, ts, lat, lon = row
        grouped[node_id].append((ts, lat, lon))
    
    cursor.close()
    
    for node_id, points in grouped.items():
        if len(points) < TRAIL_MIN_POINTS:
            continue
        
        # Keep only most recent points
        points = points[-MAX_POINTS_PER_NODE:]
        coords = [[lon, lat] for (_, lat, lon) in points]
        
        yield {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {"nodeId": node_id, "pointCount": len(coords)},
        }


def prune_old_positions(conn, cutoff_time: datetime) -> None:
    """Delete old position records"""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM positions WHERE timestamp < %s", (cutoff_time,))
    conn.commit()
    cursor.close()
    print(f"✓ Pruned positions older than {cutoff_time}", flush=True)


def generate_geojson(conn) -> None:
    """Generate nodes.geojson and trails.geojson"""
    favs, labels, notes = load_favorites()
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=HISTORY_WINDOW_SECONDS)
    
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Fetch active nodes with coordinates and latest telemetry
    cursor.execute("""
        SELECT 
            n.node_id, n.node_num, n.long_name, n.short_name, n.hw_model, n.role,
            n.latitude, n.longitude, n.altitude, n.battery_level, n.voltage, n.snr,
            n.last_heard, n.source,
            n.has_power_sensor, n.has_environment_sensor, n.has_air_quality_sensor,
            t.channel_utilization, t.air_util_tx,
            p.timestamp as position_time
        FROM nodes n
        LEFT JOIN LATERAL (
            SELECT channel_utilization, air_util_tx
            FROM telemetry
            WHERE node_id = n.node_id
            ORDER BY timestamp DESC
            LIMIT 1
        ) t ON TRUE
        LEFT JOIN LATERAL (
            SELECT timestamp
            FROM positions
            WHERE node_id = n.node_id
            ORDER BY timestamp DESC
            LIMIT 1
        ) p ON TRUE
        WHERE n.latitude IS NOT NULL 
          AND n.longitude IS NOT NULL
          AND n.is_active = TRUE
        ORDER BY n.last_heard DESC
    """)
    
    nodes = cursor.fetchall()
    
    # Fetch recent messages for each node (last 5 messages per node)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT DISTINCT ON (from_node, message_text)
            from_node, to_node, message_text, timestamp
        FROM messages
        WHERE timestamp >= NOW() - INTERVAL '24 hours'
        ORDER BY from_node, message_text, timestamp DESC
    """)
    
    messages_by_node = defaultdict(list)
    for msg in cursor.fetchall():
        messages_by_node[msg['from_node']].append({
            'text': msg['message_text'],
            'timestamp': msg['timestamp'].isoformat(),
            'to': msg['to_node']
        })
    
    cursor.close()
    
    print(f"📍 Found {len(nodes)} nodes with coordinates", flush=True)
    print(f"💬 Found messages from {len(messages_by_node)} nodes", flush=True)
    
    # Build GeoJSON features
    features = []
    for node in nodes:
        node_id = node['node_id']
        
        # Format timestamp and get status
        time_data = format_timestamp(node['last_heard'])
        
        props = {
            "nodeId": node_id,
            "nodeNum": node['node_num'],
            "longName": node['long_name'] or node_id,
            "shortName": node['short_name'] or node_id[-4:],
            "hwModel": node['hw_model'],
            "role": node['role'],
            "altitude": node['altitude'],
            "batteryLevel": node['battery_level'],
            "voltage": node['voltage'],
            "snr": node['snr'],
            "source": node['source'],
            "channelUtil": node.get('channel_utilization'),
            "airUtilTx": node.get('air_util_tx'),
            "hasPowerSensor": node.get('has_power_sensor', False),
            "hasEnvironmentSensor": node.get('has_environment_sensor', False),
            "hasAirQualitySensor": node.get('has_air_quality_sensor', False),
            "positionTime": node.get('position_time').isoformat() if node.get('position_time') else None,
            "isFavorite": node_id in favs,
            "customLabel": labels.get(node_id),
            "notes": notes.get(node_id),
            "recentMessages": messages_by_node.get(node_id, [])[:5],  # Last 5 messages
            **time_data
        }
        
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [node['longitude'], node['latitude']]
            },
            "properties": props
        })
    
    # Write nodes GeoJSON
    geojson = {
        "type": "FeatureCollection",
        "features": features,
        "generated": datetime.now(timezone.utc).isoformat(),
        "nodeCount": len(features)
    }
    
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(geojson, indent=2))
    print(f"✓ Wrote {len(features)} nodes to {OUTPUT}", flush=True)
    
    # Generate trails
    trail_features = list(fetch_trails(conn, cutoff))
    trails_geojson = {
        "type": "FeatureCollection",
        "features": trail_features,
        "generated": datetime.now(timezone.utc).isoformat(),
        "trailCount": len(trail_features)
    }
    
    TRAILS_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    TRAILS_OUTPUT.write_text(json.dumps(trails_geojson, indent=2))
    print(f"✓ Wrote {len(trail_features)} trails to {TRAILS_OUTPUT}", flush=True)
    
    # Prune old positions
    prune_old_positions(conn, cutoff)


def main():
    """Main loop to regenerate GeoJSON periodically"""
    print("=== Meshtastic GeoJSON Generator (PostgreSQL) ===", flush=True)
    print(f"Output: {OUTPUT}", flush=True)
    print(f"Trails: {TRAILS_OUTPUT}", flush=True)
    print(f"Poll interval: {POLL_INTERVAL}s", flush=True)
    print(f"History window: {HISTORY_WINDOW_SECONDS}s", flush=True)
    
    while True:
        try:
            conn = get_db_connection()
            if not conn:
                print("ERROR: Cannot connect to database, retrying in 10s...", flush=True)
                time.sleep(10)
                continue
            
            generate_geojson(conn)
            conn.close()
            
            time.sleep(POLL_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n✓ Shutting down...", flush=True)
            break
        except Exception as e:
            print(f"ERROR: {e}", flush=True)
            time.sleep(10)


if __name__ == "__main__":
    main()
