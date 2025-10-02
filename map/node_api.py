#!/usr/bin/env python3
"""
Meshtastic Node API
HTTP API for receiving node data from multiple sources
Allows remote Meshtastic nodes to push their data via HTTP
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone
from flask import Flask, request, jsonify
import psycopg2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Database configuration
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
    if not auth_header or not auth_header.startswith('Bearer '):
        return False
    
    token = auth_header.split(' ')[1]
    return token == API_KEY


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'service': 'meshtastic-node-api',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })


@app.route('/api/v1/nodes', methods=['POST'])
def receive_nodes():
    """
    Receive node data from external sources
    
    Expected JSON format:
    {
        "source": "node-name-or-id",
        "timestamp": "2025-10-02T19:00:00Z",
        "nodes": [
            {
                "node_id": "!433ad9f8",
                "node_num": 1128140280,
                "long_name": "Nord GA3 d9f8",
                "short_name": "GA3",
                "hw_model": "HELTEC_V3",
                "role": "ROUTER",
                "latitude": 69.7041,
                "longitude": 19.0579,
                "altitude": 48,
                "battery_level": 100,
                "voltage": 4.2,
                "snr": 9.5,
                "last_heard": "2025-10-02T16:47:00Z"
            },
            ...
        ]
    }
    """
    # Verify API key
    if not verify_api_key():
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        
        if not data or 'nodes' not in data:
            return jsonify({'error': 'Invalid request format'}), 400
        
        source = data.get('source', 'unknown')
        nodes = data.get('nodes', [])
        
        if not isinstance(nodes, list):
            return jsonify({'error': 'nodes must be an array'}), 400
        
        # Store nodes to database
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        stored_count = 0
        try:
            cursor = conn.cursor()
            
            for node in nodes:
                try:
                    # Parse timestamp if provided
                    last_heard = node.get('last_heard')
                    if last_heard and isinstance(last_heard, str):
                        last_heard = datetime.fromisoformat(last_heard.replace('Z', '+00:00'))
                    else:
                        last_heard = datetime.now(timezone.utc)
                    
                    # Insert or update node
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
                    """, {
                        'node_id': node.get('node_id'),
                        'node_num': node.get('node_num'),
                        'long_name': node.get('long_name'),
                        'short_name': node.get('short_name'),
                        'hw_model': node.get('hw_model'),
                        'role': node.get('role'),
                        'latitude': node.get('latitude'),
                        'longitude': node.get('longitude'),
                        'altitude': node.get('altitude'),
                        'battery_level': node.get('battery_level'),
                        'voltage': node.get('voltage'),
                        'snr': node.get('snr'),
                        'last_heard': last_heard,
                        'source': source
                    })
                    
                    # Store position if coordinates exist
                    if node.get('latitude') and node.get('longitude'):
                        cursor.execute("""
                            INSERT INTO positions (
                                node_id, timestamp, latitude, longitude, altitude, source
                            ) VALUES (
                                %(node_id)s, %(timestamp)s, %(latitude)s, %(longitude)s,
                                %(altitude)s, %(source)s
                            )
                            ON CONFLICT DO NOTHING
                        """, {
                            'node_id': node.get('node_id'),
                            'timestamp': last_heard,
                            'latitude': node.get('latitude'),
                            'longitude': node.get('longitude'),
                            'altitude': node.get('altitude'),
                            'source': source
                        })
                    
                    stored_count += 1
                    
                except Exception as e:
                    logger.warning(f"Error storing node {node.get('node_id')}: {e}")
                    continue
            
            conn.commit()
            logger.info(f"✓ Stored {stored_count}/{len(nodes)} nodes from source: {source}")
            
            return jsonify({
                'success': True,
                'stored': stored_count,
                'total': len(nodes),
                'source': source
            }), 200
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            return jsonify({'error': 'Database error'}), 500
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/v1/nodes', methods=['GET'])
def get_nodes():
    """
    Get all active nodes from database
    """
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                node_id, node_num, long_name, short_name, hw_model, role,
                latitude, longitude, altitude, battery_level, voltage, snr,
                last_heard, source
            FROM nodes
            WHERE is_active = TRUE
            ORDER BY last_heard DESC
        """)
        
        nodes = []
        for row in cursor.fetchall():
            nodes.append({
                'node_id': row[0],
                'node_num': row[1],
                'long_name': row[2],
                'short_name': row[3],
                'hw_model': row[4],
                'role': row[5],
                'latitude': row[6],
                'longitude': row[7],
                'altitude': row[8],
                'battery_level': row[9],
                'voltage': row[10],
                'snr': row[11],
                'last_heard': row[12].isoformat() if row[12] else None,
                'source': row[13]
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'nodes': nodes,
            'count': len(nodes)
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching nodes: {e}")
        return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    logger.info("=== Meshtastic Node API Started ===")
    logger.info(f"Listening on port {os.getenv('NODE_API_PORT', 8081)}")
    
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('NODE_API_PORT', 8081)),
        debug=False
    )
