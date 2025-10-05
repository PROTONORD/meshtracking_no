#!/usr/bin/env python3
"""
Combined HTTP server that serves both static files and API endpoints
Replaces the separate Python HTTP server and Flask API server
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS
import psycopg2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Cache control for different content types
@app.after_request
def add_cache_headers(response):
    """
    Selective caching strategy:
    - User data (localStorage) persists permanently in browser
    - UI code (HTML/CSS/JS) has no cache for instant updates
    - Live data (GeoJSON/API) never cached for real-time accuracy
    """
    if request.endpoint == 'api_nodes' or request.path.startswith('/api/'):
        # API endpoints - no cache
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    elif request.path.endswith('.geojson') or request.path.endswith('.json'):
        # Live data files - no cache
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
    elif request.path.endswith(('.css', '.js')):
        # CSS/JS - no cache for instant UI updates (localStorage persists user data)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    elif request.path.endswith(('.png', '.jpg', '.ico', '.svg')):
        # Images/icons - cache for 1 hour (rarely change)
        response.headers['Cache-Control'] = 'public, max-age=3600'
    elif request.path.endswith('.html') or request.path == '/':
        # HTML pages - aggressive no-cache + ETag for instant updates
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        response.headers['Last-Modified'] = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')
        # Add ETag based on file modification time
        if hasattr(response, 'direct_passthrough') and not response.direct_passthrough:
            import hashlib
            content_hash = hashlib.md5(str(response.get_data()).encode()).hexdigest()[:8]
            response.headers['ETag'] = f'W/"{content_hash}"'
    
    return response

# Configuration
DATA_DIR = '/data'
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'meshtastic'),
    'user': os.getenv('DB_USER', 'meshuser'),
    'password': os.getenv('DB_PASSWORD')  # Required - no default
}
API_KEY = os.getenv('NODE_API_KEY')  # Required - no default

def get_db_connection():
    """Get PostgreSQL connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return None

def verify_api_key():
    """Verify API key from request"""
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return False
    
    try:
        scheme, token = auth_header.split(' ', 1)
        return scheme.lower() == 'bearer' and token == API_KEY
    except ValueError:
        return False

# Static file serving
@app.route('/')
def serve_index():
    """Serve the main index.html file with API key injected"""
    try:
        with open(os.path.join(DATA_DIR, 'index.html'), 'r', encoding='utf-8') as f:
            content = f.read()
        # Inject API key from environment variable
        if API_KEY:
            content = content.replace(
                "const API_KEY = 'REPLACE_ME_WITH_ENV_VAR';",
                f"const API_KEY = '{API_KEY}';"
            )
        return content, 200, {'Content-Type': 'text/html; charset=utf-8'}
    except Exception as e:
        logger.error(f"Failed to serve index.html: {e}")
        return "Internal Server Error", 500

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files from data directory"""
    try:
        return send_from_directory(DATA_DIR, filename)
    except FileNotFoundError:
        abort(404)

# API endpoints
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'service': 'meshtastic-combined-server',
        'status': 'ok',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/api/nodes', methods=['GET'])
def get_nodes():
    """Get nodes with optional source filtering and status calculation"""
    source = request.args.get('source')  # 'radio', 'mqtt', or None for all
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        
        # Build query based on source filter - join with node_tags to get tags
        base_query = """
            SELECT n.node_id, n.short_name, n.long_name, 
                   n.latitude, 
                   n.longitude,
                   n.source, n.source_interface, n.last_heard,
                   EXTRACT(EPOCH FROM (NOW() - n.last_heard)) as seconds_ago,
                   n.hw_model, n.role, n.battery_level, n.voltage, n.snr, n.rssi,
                   n.channel_utilization, n.air_util_tx, 
                   n.altitude, 
                   n.hops_away,
                   NULL as notes,
                   NULL as manual_address,
                   COALESCE(
                       json_agg(
                           json_build_object('tag', nt.tag)
                           ORDER BY nt.created_at
                       ) FILTER (WHERE nt.tag IS NOT NULL),
                       '[]'::json
                   ) as tags
            FROM nodes n
            LEFT JOIN node_tags nt ON n.node_id = nt.node_id
        """
        
        if source == 'radio':
            query = base_query + " WHERE n.source = 'radio' GROUP BY n.node_id, n.short_name, n.long_name, n.latitude, n.longitude, n.source, n.source_interface, n.last_heard, n.hw_model, n.role, n.battery_level, n.voltage, n.snr, n.rssi, n.channel_utilization, n.air_util_tx, n.altitude, n.hops_away ORDER BY n.last_heard DESC NULLS LAST"
        elif source == 'mqtt':
            query = base_query + " WHERE n.source = 'mqtt' GROUP BY n.node_id, n.short_name, n.long_name, n.latitude, n.longitude, n.source, n.source_interface, n.last_heard, n.hw_model, n.role, n.battery_level, n.voltage, n.snr, n.rssi, n.channel_utilization, n.air_util_tx, n.altitude, n.hops_away ORDER BY n.last_heard DESC NULLS LAST"
        else:
            query = base_query + " GROUP BY n.node_id, n.short_name, n.long_name, n.latitude, n.longitude, n.source, n.source_interface, n.last_heard, n.hw_model, n.role, n.battery_level, n.voltage, n.snr, n.rssi, n.channel_utilization, n.air_util_tx, n.altitude, n.hops_away ORDER BY n.last_heard DESC NULLS LAST"
        
        cursor.execute(query)
        nodes = []
        for row in cursor.fetchall():
            seconds_ago = row[8] if row[8] else None
            
            # Calculate status based on time since last_heard
            status = None
            if seconds_ago is not None:
                if seconds_ago < 1800:  # < 30 minutes
                    status = 'online'
                elif seconds_ago < 7200:  # < 2 hours
                    status = 'recent'
                elif seconds_ago < 1209600:  # < 2 weeks
                    status = 'offline'
                else:
                    status = 'dead'
            
            # Map role integer to string
            role_map = {0: 'CLIENT_MUTE', 1: 'CLIENT', 2: 'ROUTER', 3: 'ROUTER_CLIENT'}
            role_str = role_map.get(row[10], 'CLIENT') if row[10] is not None else 'CLIENT'
            
            # Tags come as JSON array of objects from SQL query
            tags_data = row[21] if row[21] else []
            
            nodes.append({
                'node_id': row[0],
                'short_name': row[1], 
                'long_name': row[2],
                'latitude': row[3],
                'longitude': row[4],
                'source': row[5],
                'source_interface': row[6],
                'last_heard': row[7].isoformat() if row[7] else None,
                'last_heard_ago_sec': int(seconds_ago) if seconds_ago else None,
                'status': status,
                'hw_model': row[9],
                'role': role_str,
                'battery_level': row[11],
                'voltage': float(row[12]) if row[12] else None,
                'snr': float(row[13]) if row[13] else None,
                'rssi': row[14],
                'channel_utilization': float(row[15]) if row[15] else None,
                'air_util_tx': float(row[16]) if row[16] else None,
                'altitude': row[17],
                'hops_away': row[18],
                'notes': row[19],
                'customLabel': row[20],
                'tags': tags_data
            })
        
        return jsonify({
            'nodes': nodes,
            'total': len(nodes),
            'source_filter': source
        })
    
    except Exception as e:
        logger.error(f"Error getting nodes: {e}")
        return jsonify({'error': 'Database error'}), 500
    finally:
        conn.close()

@app.route('/api/nodes/search', methods=['GET'])
def search_nodes():
    """Search for nodes by name or ID - includes nodes WITHOUT GPS"""
    query_term = request.args.get('q', '').strip().lower()
    
    if not query_term or len(query_term) < 2:
        return jsonify({'results': [], 'message': 'Query too short'})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        
        # Search in node_id, short_name, long_name, tags
        search_query = """
            SELECT n.node_id, n.short_name, n.long_name,
                   n.latitude, n.longitude,
                   n.source, n.last_heard,
                   EXTRACT(EPOCH FROM (NOW() - n.last_heard)) as seconds_ago,
                   n.hw_model, n.role,
                   COALESCE(
                       (SELECT json_agg(json_build_object('tag', nt2.tag))
                        FROM node_tags nt2 
                        WHERE nt2.node_id = n.node_id),
                       '[]'::json
                   ) as tags
            FROM nodes n
            WHERE n.last_heard > NOW() - INTERVAL '60 days'
              AND (
                  LOWER(n.node_id) LIKE %s
                  OR LOWER(COALESCE(n.short_name, '')) LIKE %s
                  OR LOWER(COALESCE(n.long_name, '')) LIKE %s
                  OR EXISTS (
                      SELECT 1 FROM node_tags nt 
                      WHERE nt.node_id = n.node_id 
                      AND LOWER(nt.tag) LIKE %s
                  )
              )
            ORDER BY n.last_heard DESC
            LIMIT 50
        """
        
        search_pattern = f'%{query_term}%'
        cursor.execute(search_query, (search_pattern, search_pattern, search_pattern, search_pattern))
        
        results = []
        for row in cursor.fetchall():
            seconds_ago = row[7] if row[7] else None
            
            # Calculate status
            status = None
            if seconds_ago is not None:
                if seconds_ago < 1800:
                    status = 'online'
                elif seconds_ago < 7200:
                    status = 'recent'
                else:
                    status = 'offline'
            
            results.append({
                'node_id': row[0],
                'short_name': row[1],
                'long_name': row[2],
                'latitude': row[3],
                'longitude': row[4],
                'has_gps': row[3] is not None and row[4] is not None and (row[3] != 0 or row[4] != 0),
                'source': row[5],
                'last_heard': row[6].isoformat() if row[6] else None,
                'status': status,
                'hw_model': row[8],
                'role': row[9],
                'tags': row[10] if row[10] else []
            })
        
        cursor.close()
        return jsonify({
            'results': results,
            'count': len(results),
            'query': query_term
        })
    
    except Exception as e:
        logger.error(f"Error searching nodes: {e}")
        return jsonify({'error': 'Database error'}), 500
    finally:
        conn.close()

@app.route('/api/nodes/geojson', methods=['GET'])
@app.route('/nodes.geojson', methods=['GET'])  # Backwards compatibility
def get_nodes_geojson():
    """Get nodes in GeoJSON format for map display - ONLY nodes with valid GPS"""
    source = request.args.get('source')  # 'radio', 'mqtt', or None for all
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        
        # Query with all available node data including tags and notes
        # ONLY include nodes with valid GPS coordinates (not 0,0 and not NULL)
        query = """
            SELECT n.node_id, n.short_name, n.long_name, 
                   n.latitude, 
                   n.longitude,
                   n.source, n.source_interface, n.last_heard,
                   EXTRACT(EPOCH FROM (NOW() - n.last_heard)) as seconds_ago,
                   n.hw_model, n.role, n.battery_level, n.voltage, n.snr, n.rssi,
                   n.channel_utilization, n.air_util_tx, 
                   n.altitude, 
                   n.hops_away,
                   n.notes,
                   NULL as manual_address,
                   COALESCE(
                       json_agg(
                           json_build_object('tag', nt.tag)
                           ORDER BY nt.created_at
                       ) FILTER (WHERE nt.tag IS NOT NULL),
                       '[]'::json
                   ) as tags
            FROM nodes n
            LEFT JOIN node_tags nt ON n.node_id = nt.node_id
            WHERE n.latitude IS NOT NULL 
              AND n.longitude IS NOT NULL
              AND n.latitude != 0 
              AND n.longitude != 0
              AND (n.latitude != 0 OR n.longitude != 0)
              AND n.last_heard > NOW() - INTERVAL '60 days'
            GROUP BY n.node_id, n.short_name, n.long_name, n.latitude, n.longitude, 
                     n.source, n.source_interface, n.last_heard, n.hw_model, n.role, 
                     n.battery_level, n.voltage, n.snr, n.rssi, n.channel_utilization, 
                     n.air_util_tx, n.altitude, n.hops_away, n.notes
            ORDER BY n.last_heard DESC NULLS LAST
        """
        
        cursor.execute(query)
        features = []
        for row in cursor.fetchall():
            seconds_ago = row[8] if row[8] else None
            
            # Calculate status based on time since last_heard
            status = None
            if seconds_ago is not None:
                if seconds_ago < 1800:  # < 30 minutes
                    status = 'online'
                elif seconds_ago < 7200:  # < 2 hours
                    status = 'recent'
                elif seconds_ago < 1209600:  # < 2 weeks
                    status = 'offline'
                else:
                    status = 'dead'
            
            # Map role integer to string
            role_map = {0: 'CLIENT_MUTE', 1: 'CLIENT', 2: 'ROUTER', 3: 'ROUTER_CLIENT'}
            role_str = role_map.get(row[10], 'CLIENT') if row[10] is not None else 'CLIENT'
            
            # Format last_heard in Norwegian timezone
            lastHeardNorwegian = None
            if row[7]:
                from datetime import timezone
                import pytz
                tz = pytz.timezone('Europe/Oslo')
                dt_utc = row[7].replace(tzinfo=timezone.utc)
                dt_norway = dt_utc.astimezone(tz)
                lastHeardNorwegian = dt_norway.strftime('%Y-%m-%d %H:%M:%S')
            
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(row[4]), float(row[3])]  # [longitude, latitude]
                },
                "properties": {
                    "nodeId": row[0],
                    "shortName": row[1] or "Unknown",
                    "longName": row[2] or "Unknown Node",
                    "source": row[5] or "unknown",
                    "source_interface": row[6] or "unknown",
                    "lastHeard": row[7].isoformat() if row[7] else None,
                    "lastHeardNorwegian": lastHeardNorwegian,
                    "lastHeardAgoSec": int(seconds_ago) if seconds_ago else None,
                    "status": status,
                    "hwModel": row[9],
                    "role": role_str,
                    "batteryLevel": row[11],
                    "voltage": float(row[12]) if row[12] else None,
                    "snr": float(row[13]) if row[13] else None,
                    "rssi": row[14],
                    "channelUtil": float(row[15]) if row[15] else None,
                    "airUtilTx": float(row[16]) if row[16] else None,
                    "altitude": row[17],
                    "hopsAway": row[18],
                    "notes": row[19],  # notes from database
                    "customLabel": row[20],  # manual_address from nodes_with_tags
                    "tags": row[21] if row[21] else []  # tags array from view (pre-aggregated)
                }
            }
            features.append(feature)
        
        geojson = {
            "type": "FeatureCollection",
            "features": features
        }
        
        return jsonify(geojson)
    
    except Exception as e:
        logger.error(f"Error getting nodes GeoJSON: {e}")
        return jsonify({'error': 'Database error'}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/node/<node_id>/tags', methods=['GET'])
def get_node_tags(node_id):
    """Get tags for a specific node"""
    if not verify_api_key():
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        # Only select columns that exist in database
        cursor.execute("""
            SELECT tag, created_at
            FROM node_tags 
            WHERE node_id = %s
            ORDER BY created_at DESC
        """, (node_id,))
        
        tags = []
        for row in cursor.fetchall():
            # Infer type from tag prefix/content if possible
            tag_text = row[0]
            tag_type = 'custom'  # Default type
            if tag_text.lower() in ['router', 'client', 'repeater', 'gateway']:
                tag_type = 'category'
            elif len(tag_text) < 15 and ' ' not in tag_text:
                tag_type = 'nickname'
            
            tags.append({
                'tag': tag_text,
                'type': tag_type,  # Derived, not from DB
                'created_at': row[1].isoformat() if row[1] else None
            })
        
        return jsonify({'tags': tags})
    
    except Exception as e:
        logger.error(f"Error getting tags for node {node_id}: {e}")
        return jsonify({'error': 'Database error'}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/node/<node_id>/tags', methods=['POST'])
def add_node_tag(node_id):
    """Add a tag to a node"""
    if not verify_api_key():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400
    
    tag = data.get('tag', '').strip()
    # Ignore type and color - not in database schema
    
    if not tag:
        return jsonify({'error': 'Tag is required'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        
        # Simple insert or ignore - unique constraint on (node_id, tag)
        cursor.execute("""
            INSERT INTO node_tags (node_id, tag, created_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (node_id, tag) DO NOTHING
        """, (node_id, tag))
        
        conn.commit()
        logger.info(f"Added tag '{tag}' for node {node_id}")
        
        return jsonify({
            'success': True,
            'tag': tag
        })
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Error adding tag for node {node_id}: {e}")
        return jsonify({'error': 'Database error'}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/node/<node_id>/tags', methods=['DELETE'])
def delete_node_tag(node_id):
    """Delete a tag from a node"""
    if not verify_api_key():
        return jsonify({'error': 'Unauthorized'}), 401
    
    tag = request.args.get('tag')
    if not tag:
        return jsonify({'error': 'Tag parameter is required'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM node_tags 
            WHERE node_id = %s AND tag = %s
        """, (node_id, tag))
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Tag not found'}), 404
        
        conn.commit()
        logger.info(f"Deleted tag '{tag}' for node {node_id}")
        
        return jsonify({'success': True})
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting tag for node {node_id}: {e}")
        return jsonify({'error': 'Database error'}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/node/<node_id>/position', methods=['POST'])
def set_node_position(node_id):
    """Set manual position for a node"""
    if not verify_api_key():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400
    
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    altitude = data.get('altitude', 0)
    # address and position_source not supported - no columns in DB
    
    # Validate coordinates
    if latitude is None or longitude is None:
        return jsonify({'error': 'Latitude and longitude are required'}), 400
    
    try:
        latitude = float(latitude)
        longitude = float(longitude)
        if altitude is not None:
            altitude = int(altitude)
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid coordinate format'}), 400
    
    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        return jsonify({'error': 'Invalid coordinate range'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        
        # Update position directly (overwrite existing GPS data)
        cursor.execute("""
            INSERT INTO nodes (node_id, latitude, longitude, altitude, last_updated)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (node_id) 
            DO UPDATE SET 
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                altitude = EXCLUDED.altitude,
                last_updated = NOW()
        """, (node_id, latitude, longitude, altitude))
        
        conn.commit()
        logger.info(f"Set manual position for node {node_id}: {latitude}, {longitude}")
        
        return jsonify({
            'success': True,
            'latitude': latitude,
            'longitude': longitude,
            'altitude': altitude
        })
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Error setting position for node {node_id}: {e}")
        return jsonify({'error': 'Database error'}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/node/<node_id>/position', methods=['DELETE'])
def delete_node_position(node_id):
    """Delete manual position for a node (reverts to GPS if available)"""
    if not verify_api_key():
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        
        # Check if node exists and has manual position
        cursor.execute("""
            SELECT position_source FROM nodes WHERE node_id = %s
        """, (node_id,))
        
        result = cursor.fetchone()
        if not result:
            return jsonify({'error': 'Node not found'}), 404
        
        if result[0] != 'manual':
            return jsonify({'error': 'Node does not have manual position'}), 400
        
        # Reset position to GPS or remove if no GPS data
        cursor.execute("""
            UPDATE nodes 
            SET position_source = CASE 
                WHEN latitude IS NOT NULL AND longitude IS NOT NULL AND position_source = 'gps'
                THEN 'gps'
                ELSE NULL
            END,
            manual_latitude = NULL,
            manual_longitude = NULL,
            manual_altitude = NULL,
            manual_address = NULL,
            last_updated = NOW()
            WHERE node_id = %s
        """, (node_id,))
        
        conn.commit()
        logger.info(f"Removed manual position for node {node_id}")
        
        return jsonify({'success': True})
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Error removing position for node {node_id}: {e}")
        return jsonify({'error': 'Database error'}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/node/<node_id>/notes', methods=['POST'])
def set_node_notes(node_id):
    """Set notes for a node"""
    if not verify_api_key():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400
    
    notes = data.get('notes', '').strip()
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        
        # Update or insert notes
        cursor.execute("""
            INSERT INTO nodes (node_id, notes, last_updated)
            VALUES (%s, %s, NOW())
            ON CONFLICT (node_id) 
            DO UPDATE SET 
                notes = EXCLUDED.notes,
                last_updated = NOW()
        """, (node_id, notes))
        
        conn.commit()
        logger.info(f"Updated notes for node {node_id}")
        
        return jsonify({
            'success': True,
            'notes': notes
        })
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Error setting notes for node {node_id}: {e}")
        return jsonify({'error': 'Database error'}), 500
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    port = int(os.getenv('WEB_PORT', 8080))
    logger.info(f"Starting combined server on port {port}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False
    )