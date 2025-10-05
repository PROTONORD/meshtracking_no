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
    'password': os.getenv('DB_PASSWORD')  # Required - no default
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


def format_timestamp(dt: datetime) -> Dict[str, Any]:
    """Format timestamp with Norwegian timezone and status"""
    if dt is None:
        return {
            "lastHeard": "Never",
            "lastHeardAgoSec": 999999999,
            "lastHeardIso": None,
            "lastHeardNorwegian": "Aldri sett",
            "status": "dead"
        }
    
    # Ensure datetime is timezone-aware
    if dt.tzinfo is None:
        # Assume UTC if naive
        dt = dt.replace(tzinfo=timezone.utc)
    
    # Convert to Oslo timezone
    from zoneinfo import ZoneInfo
    oslo_tz = ZoneInfo("Europe/Oslo")
    dt_oslo = dt.astimezone(oslo_tz)
    
    now = datetime.now(timezone.utc)
    ago = int((now - dt).total_seconds())


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
    
    # Fetch active nodes with coordinates (GPS or manual) and latest telemetry
    cursor.execute("""
        SELECT 
            n.node_id, n.node_num, n.long_name, n.short_name, n.hw_model, n.role,
            n.effective_latitude as latitude, 
            n.effective_longitude as longitude, 
            n.effective_altitude as altitude,
            n.effective_position_source as position_source,
            n.battery_level, n.voltage, n.snr,
            n.last_heard, n.source, n.source_interface, n.region, n.notes, n.manual_address,
            n.has_power_sensor, n.has_environment_sensor, n.has_air_quality_sensor,
            n.tags,
            t.channel_utilization, t.air_util_tx,
            p.timestamp as position_time
        FROM nodes_with_tags n
        LEFT JOIN LATERAL (
            SELECT channel_utilization, air_util_tx, 
                   temperature, relative_humidity, barometric_pressure,
                   ch1_voltage, ch1_current, ch2_voltage, ch2_current, ch3_voltage, ch3_current,
                   pm10_standard, pm25_standard, pm100_standard,
                   wind_speed, wind_direction, wind_gust,
                   soil_temperature, soil_moisture,
                   gas_resistance, iaq, co2, voc_idx, nox_idx,
                   lux, white_lux, ir_lux, uv_lux,
                   distance, weight, radiation, uptime_seconds,
                   rainfall_1h, rainfall_24h
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
        WHERE n.effective_latitude IS NOT NULL 
          AND n.effective_longitude IS NOT NULL
          AND n.last_heard > NOW() - INTERVAL '60 days'  -- Show nodes active within 2 months
        ORDER BY n.last_heard DESC
    """)
    
    nodes = cursor.fetchall()
    
    # Debug: Check if telemetry data is being fetched
    for node in nodes[:3]:  # Check first 3 nodes
        print(f"DEBUG: Node {node.get('node_id')} telemetry: temp={node.get('temperature')}, humidity={node.get('relative_humidity')}, pressure={node.get('barometric_pressure')}")
    
    # Fetch recent messages for each node (last 5 messages per node)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT DISTINCT ON (from_node, message)
            from_node, to_node, message, timestamp
        FROM messages
        WHERE timestamp >= NOW() - INTERVAL '24 hours'
        ORDER BY from_node, message, timestamp DESC
    """)
    
    messages_by_node = defaultdict(list)
    for msg in cursor.fetchall():
        messages_by_node[msg['from_node']].append({
            'text': msg['message'],
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
        try:
            time_data = format_timestamp(node['last_heard'])
        except Exception as e:
            print(f"ERROR formatting timestamp for {node_id}: {e}", flush=True)
            time_data = {
                "lastHeard": "Unknown",
                "lastHeardAgoSec": 999999,
                "lastHeardIso": None,
                "lastHeardNorwegian": "Ukjent",
                "status": "dead"
            }
        
        # Parse tags from JSON (psycopg2 returns JSON as Python list/dict already)
        tags_raw = node.get('tags')
        tags = []
        if tags_raw:
            if isinstance(tags_raw, str):
                # If string, parse as JSON
                try:
                    tags = json.loads(tags_raw)
                except:
                    tags = []
            elif isinstance(tags_raw, list):
                # Already a list - convert to expected format [{"tag": "value"}, ...]
                tags = [{"tag": tag} if isinstance(tag, str) else tag for tag in tags_raw]
            else:
                tags = []
        
        # Debug for first few nodes
        if node_id in ['!db2fa9a4', '!b4d2d339']:
            print(f"DEBUG: Node {node_id} tags_raw={tags_raw} type={type(tags_raw)} tags={tags}", flush=True)
        
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
            "source_interface": node.get('source_interface'),
            "region": node.get('region'),
            "positionSource": node.get('position_source', 'gps'),
            "manualAddress": node.get('manual_address'),
            "channelUtil": node.get('channel_utilization'),
            "airUtilTx": node.get('air_util_tx'),
            # Environment sensors
            "temperature": node.get('temperature'),
            "relativeHumidity": node.get('relative_humidity'),
            "barometricPressure": node.get('barometric_pressure'),
            "gasResistance": node.get('gas_resistance'),
            "iaq": node.get('iaq'),
            # Power sensors
            "ch1Voltage": node.get('ch1_voltage'),
            "ch1Current": node.get('ch1_current'),
            "ch2Voltage": node.get('ch2_voltage'),
            "ch2Current": node.get('ch2_current'),
            "ch3Voltage": node.get('ch3_voltage'),
            "ch3Current": node.get('ch3_current'),
            # Air quality sensors
            "pm10Standard": node.get('pm10_standard'),
            "pm25Standard": node.get('pm25_standard'),
            "pm100Standard": node.get('pm100_standard'),
            "co2": node.get('co2'),
            "vocIdx": node.get('voc_idx'),
            "noxIdx": node.get('nox_idx'),
            # Weather sensors
            "windSpeed": node.get('wind_speed'),
            "windDirection": node.get('wind_direction'),
            "windGust": node.get('wind_gust'),
            "soilTemperature": node.get('soil_temperature'),
            "soilMoisture": node.get('soil_moisture'),
            "rainfall1h": node.get('rainfall_1h'),
            "rainfall24h": node.get('rainfall_24h'),
            # Light sensors
            "lux": node.get('lux'),
            "whiteLux": node.get('white_lux'),
            "irLux": node.get('ir_lux'),
            "uvLux": node.get('uv_lux'),
            # Other sensors
            "distance": node.get('distance'),
            "weight": node.get('weight'),
            "radiation": node.get('radiation'),
            "uptimeSeconds": node.get('uptime_seconds'),
            "hasPowerSensor": node.get('has_power_sensor', False),
            "hasEnvironmentSensor": node.get('has_environment_sensor', False),
            "hasAirQualitySensor": node.get('has_air_quality_sensor', False),
            "positionTime": node.get('position_time').isoformat() if node.get('position_time') else None,
            "isFavorite": node_id in favs,
            # Use manual_address from DB first, fallback to favorites.json
            "customLabel": node.get('manual_address') or labels.get(node_id),
            # Use notes from DB first, fallback to favorites.json  
            "notes": node.get('notes') or notes.get(node_id),
            "tags": tags,
            "recentMessages": messages_by_node.get(node_id, [])[:5],  # Last 5 messages
        }
        
        # Merge time_data into props (handle None gracefully)
        if time_data:
            props.update(time_data)
        
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
