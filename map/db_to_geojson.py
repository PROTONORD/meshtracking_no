#!/usr/bin/env python3
"""
Generate GeoJSON from SQLite database populated by MQTT collector.
"""

import json
import os
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

OUTPUT = Path(os.getenv("OUTPUT_PATH", "/data/nodes.geojson"))
TRAILS_OUTPUT = Path(os.getenv("TRAILS_OUTPUT_PATH", "/data/trails.geojson"))
DB_PATH = Path(os.getenv("DB_PATH", "/data/nodes.db"))
FAVORITES_FILE = Path(os.getenv("FAVORITES_FILE", "/data/config/favorites.json"))
HISTORY_WINDOW_SECONDS = int(os.getenv("HISTORY_WINDOW_SECONDS", "86400"))
TRAIL_MIN_POINTS = int(os.getenv("TRAIL_MIN_POINTS", "2"))
MAX_POINTS_PER_NODE = int(os.getenv("TRAIL_MAX_POINTS", "500"))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))


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


def format_timestamp(ts: int | None) -> Dict[str, Any]:
    if not ts:
        return {"lastHeard": None, "lastHeardAgoSec": None, "lastHeardIso": None}

    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return {
        "lastHeard": dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "lastHeardAgoSec": int(time.time()) - int(ts),
        "lastHeardIso": dt.isoformat(),
    }


def fetch_trails(conn: sqlite3.Connection, cutoff: int) -> Iterable[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT node_id, timestamp, latitude, longitude FROM positions "
        "WHERE timestamp >= ? ORDER BY node_id, timestamp",
        (cutoff,),
    )

    grouped: Dict[str, List[Tuple[int, float, float]]] = defaultdict(list)
    for node_id, ts, lat, lon in rows:
        grouped[node_id].append((ts, lat, lon))

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


def prune_old_positions(conn: sqlite3.Connection, cutoff: int) -> None:
    conn.execute("DELETE FROM positions WHERE timestamp < ?", (cutoff,))
    conn.commit()


def generate_geojson(conn: sqlite3.Connection) -> None:
    """Generate nodes GeoJSON from database."""
    favs, labels, notes = load_favorites()
    
    # Fetch all nodes with position
    rows = conn.execute(
        """
        SELECT node_id, node_num, long_name, short_name, hw_model, role, last_heard,
               latitude, longitude, altitude, battery_level, voltage, 
               channel_util, air_util_tx, snr, hops_away
        FROM nodes
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        ORDER BY last_heard DESC
        """
    ).fetchall()
    
    features = []
    for row in rows:
        (node_id, node_num, long_name, short_name, hw_model, role, last_heard,
         lat, lon, alt, battery, voltage, chan_util, air_util, snr, hops) = row
        
        is_fav = node_id in favs
        
        properties = {
            "nodeId": node_id,
            "nodeNum": node_num,
            "longName": long_name or node_id,
            "shortName": short_name or node_id[-4:],
            "hwModel": hw_model,
            "role": role,
            "altitude": alt,
            "batteryLevel": battery,
            "voltage": voltage,
            "channelUtilization": chan_util,
            "airUtilTx": air_util,
            "snr": snr,
            "hopsAway": hops,
            "isFavorite": is_fav,
            **format_timestamp(last_heard),
        }
        
        if is_fav:
            properties["favoriteLabel"] = labels.get(node_id, "")
            properties["favoriteNote"] = notes.get(node_id, "")
        
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat, alt or 0]
            },
            "properties": properties
        })
    
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(geojson, indent=2))
    print(f"Generated {OUTPUT} with {len(features)} nodes")


def generate_trails(conn: sqlite3.Connection, cutoff: int) -> None:
    """Generate trails GeoJSON from database."""
    trails = list(fetch_trails(conn, cutoff))
    
    geojson = {
        "type": "FeatureCollection",
        "features": trails
    }
    
    TRAILS_OUTPUT.write_text(json.dumps(geojson, indent=2))
    print(f"Generated {TRAILS_OUTPUT} with {len(trails)} trails")


def main():
    """Main loop."""
    print("Starting GeoJSON generator from database...")
    print(f"Database: {DB_PATH}")
    print(f"Output: {OUTPUT}")
    print(f"Trails: {TRAILS_OUTPUT}")
    print(f"Poll interval: {POLL_INTERVAL}s")
    
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        print("Make sure mqtt_collector.py is running first!")
        return
    
    while True:
        try:
            conn = sqlite3.connect(str(DB_PATH))
            
            # Generate GeoJSON
            generate_geojson(conn)
            
            # Generate trails
            cutoff = int(time.time()) - HISTORY_WINDOW_SECONDS
            generate_trails(conn, cutoff)
            
            # Prune old data
            prune_old_positions(conn, cutoff)
            
            conn.close()
            
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
