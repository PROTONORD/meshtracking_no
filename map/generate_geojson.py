import json
import os
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from meshtastic.tcp_interface import TCPInterface

OUTPUT = Path(os.getenv("OUTPUT_PATH", "/data/nodes.geojson"))
TRAILS_OUTPUT = Path(os.getenv("TRAILS_OUTPUT_PATH", "/data/trails.geojson"))
HOST = os.getenv("MESHTASTIC_HOST", "meshtasticd")
PORT = int(os.getenv("MESHTASTIC_PORT", "4403"))
INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))
DB_PATH = Path(os.getenv("DB_PATH", "/data/nodes.db"))
FAVORITES_FILE = Path(os.getenv("FAVORITES_FILE", "/data/config/favorites.json"))
HISTORY_WINDOW_SECONDS = int(os.getenv("HISTORY_WINDOW_SECONDS", "86400"))
TRAIL_MIN_POINTS = int(os.getenv("TRAIL_MIN_POINTS", "2"))
MAX_POINTS_PER_NODE = int(os.getenv("TRAIL_MAX_POINTS", "500"))


def safe_float(value: Any) -> Any:
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def format_timestamp(ts: int | None) -> Dict[str, Any]:
    if not ts:
        return {"lastHeard": None, "lastHeardAgoSec": None, "lastHeardIso": None}

    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return {
        "lastHeard": dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "lastHeardAgoSec": int(time.time()) - int(ts),
        "lastHeardIso": dt.isoformat(),
    }


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


def ensure_schema(conn: sqlite3.Connection) -> None:
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


def store_position(
    conn: sqlite3.Connection,
    node_id: str,
    node_num: int | None,
    ts: int,
    lat: float,
    lon: float,
    alt: float | None,
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO positions (node_id, node_num, timestamp, latitude, longitude, altitude)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (node_id, node_num, ts, lat, lon, alt),
    )


def prune_old_positions(conn: sqlite3.Connection, cutoff: int) -> None:
    conn.execute("DELETE FROM positions WHERE timestamp < ?", (cutoff,))


def fetch_trails(conn: sqlite3.Connection, cutoff: int) -> Iterable[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT node_id, timestamp, latitude, longitude FROM positions "
        "WHERE timestamp >= ? ORDER BY node_id, timestamp",
        (cutoff,),
    )

    grouped: Dict[str, List[Tuple[int, float, float]]] = defaultdict(list)
    for node_id, ts, lat, lon in rows:
        grouped[node_id].append((ts, lat, lon))

    features = []
    for node_id, points in grouped.items():
        if len(points) < TRAIL_MIN_POINTS:
            continue
        limited = points[-MAX_POINTS_PER_NODE:]
        coordinates = [[lon, lat] for _, lat, lon in limited]
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "nodeId": node_id,
                    "start": limited[0][0],
                    "end": limited[-1][0],
                    "points": len(limited),
                },
                "geometry": {"type": "LineString", "coordinates": coordinates},
            }
        )
    return features


def build_properties(
    node: Dict[str, Any],
    favorites: set[str],
    labels: Dict[str, str],
    notes: Dict[str, str],
) -> Dict[str, Any]:
    position = node.get("position") or {}
    lat = position.get("latitude")
    lon = position.get("longitude")
    if lat is None and position.get("latitudeI") is not None:
        lat = position["latitudeI"] / 1e7
    if lon is None and position.get("longitudeI") is not None:
        lon = position["longitudeI"] / 1e7
    if lat is None or lon is None:
        return {}

    user = node.get("user") or {}
    metrics = node.get("deviceMetrics") or {}

    timestamp_info = format_timestamp(node.get("lastHeard"))
    node_id = user.get("id") or str(node.get("num"))
    favorite = node_id in favorites

    props: Dict[str, Any] = {
        "id": node.get("num"),
        "nodeId": node_id,
        "longName": user.get("longName") or user.get("shortName"),
        "shortName": user.get("shortName"),
        "hardware": user.get("hwModel"),
        "hopsAway": node.get("hopsAway"),
        "viaMqtt": node.get("viaMqtt"),
        "isFavorite": node.get("isFavorite"),
        "favorite": favorite,
        "favoriteLabel": labels.get(node_id),
        "note": notes.get(node_id),
        "latitude": safe_float(lat),
        "longitude": safe_float(lon),
        "altitude": safe_float(position.get("altitude")),
        "locationSource": position.get("locationSource"),
        "batteryLevel": metrics.get("batteryLevel"),
        "voltage": safe_float(metrics.get("voltage")),
        "airUtilTx": safe_float(metrics.get("airUtilTx")),
        "channelUtilization": safe_float(metrics.get("channelUtilization")),
        "uptimeSeconds": metrics.get("uptimeSeconds"),
    }
    props.update(timestamp_info)
    search_terms = [
        props.get("longName"),
        props.get("shortName"),
        node_id,
        props.get("favoriteLabel"),
    ]
    props["searchIndex"] = " ".join(str(term).lower() for term in search_terms if term)

    cleaned = {k: v for k, v in props.items() if v is not None}
    cleaned["_geometry"] = {"type": "Point", "coordinates": [safe_float(lon), safe_float(lat)]}
    return cleaned


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    TRAILS_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    iface = TCPInterface(HOST, portNumber=PORT)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    ensure_schema(conn)

    try:
        while True:
            favorites, labels, notes = load_favorites()
            now_ts = int(time.time())
            cutoff = now_ts - HISTORY_WINDOW_SECONDS
            prune_old_positions(conn, cutoff)

            features = []
            for node in iface.nodes.values():
                properties = build_properties(node, favorites, labels, notes)
                geometry = properties.pop("_geometry", None)
                if not properties or geometry is None:
                    continue

                node_id = properties.get("nodeId")
                if node_id:
                    ts = node.get("lastHeard") or now_ts
                    lat = geometry["coordinates"][1]
                    lon = geometry["coordinates"][0]
                    alt = properties.get("altitude")
                    store_position(
                        conn,
                        node_id,
                        properties.get("id"),
                        int(ts),
                        float(lat),
                        float(lon),
                        float(alt) if isinstance(alt, (int, float)) else None,
                    )

                features.append(
                    {
                        "type": "Feature",
                        "properties": properties,
                        "geometry": geometry,
                    }
                )

            conn.commit()

            geojson = {"type": "FeatureCollection", "features": features}
            tmp_path = OUTPUT.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(geojson, indent=2))
            tmp_path.replace(OUTPUT)

            trails_geojson = {
                "type": "FeatureCollection",
                "features": list(fetch_trails(conn, cutoff)),
            }
            tmp_trails = TRAILS_OUTPUT.with_suffix(".tmp")
            tmp_trails.write_text(json.dumps(trails_geojson, indent=2))
            tmp_trails.replace(TRAILS_OUTPUT)

            time.sleep(INTERVAL)
    finally:
        conn.close()
        iface.close()


if __name__ == "__main__":
    main()
