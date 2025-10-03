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

# Configuration
DATA_DIR = '/data'
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'postgres'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'meshtastic'),
    'user': os.getenv('DB_USER', 'meshuser'),
    'password': os.getenv('DB_PASSWORD', 'meshpass2025')
}
API_KEY = os.getenv('NODE_API_KEY', 'meshtastic-secret-2025')

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
    """Serve the main index.html file"""
    return send_from_directory(DATA_DIR, 'index.html')

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
        cursor.execute("""
            SELECT tag, tag_type, color 
            FROM node_tags 
            WHERE node_id = %s
        """, (node_id,))
        
        tags = []
        for row in cursor.fetchall():
            tags.append({
                'tag': row[0],
                'type': row[1],
                'color': row[2]
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
    tag_type = data.get('type', 'category')
    color = data.get('color', '#FF5722')
    
    if not tag:
        return jsonify({'error': 'Tag is required'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        
        # Insert or update tag
        cursor.execute("""
            INSERT INTO node_tags (node_id, tag, tag_type, color, created_at, updated_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (node_id, tag) 
            DO UPDATE SET 
                tag_type = EXCLUDED.tag_type,
                color = EXCLUDED.color,
                updated_at = NOW()
        """, (node_id, tag, tag_type, color))
        
        conn.commit()
        logger.info(f"Added/updated tag '{tag}' for node {node_id}")
        
        return jsonify({
            'success': True,
            'tag': tag,
            'type': tag_type,
            'color': color
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
    address = data.get('address', '')
    
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
        
        # Update or insert manual position
        cursor.execute("""
            INSERT INTO nodes (node_id, manual_latitude, manual_longitude, manual_altitude, manual_address, position_source, last_updated)
            VALUES (%s, %s, %s, %s, %s, 'manual', NOW())
            ON CONFLICT (node_id) 
            DO UPDATE SET 
                manual_latitude = EXCLUDED.manual_latitude,
                manual_longitude = EXCLUDED.manual_longitude,
                manual_altitude = EXCLUDED.manual_altitude,
                manual_address = EXCLUDED.manual_address,
                latitude = EXCLUDED.manual_latitude,
                longitude = EXCLUDED.manual_longitude,
                altitude = EXCLUDED.manual_altitude,
                position_source = 'manual',
                last_updated = NOW()
        """, (node_id, latitude, longitude, altitude, address))
        
        conn.commit()
        logger.info(f"Set manual position for node {node_id}: {latitude}, {longitude}")
        
        return jsonify({
            'success': True,
            'latitude': latitude,
            'longitude': longitude,
            'altitude': altitude,
            'address': address,
            'position_source': 'manual'
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