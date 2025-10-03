#!/usr/bin/env python3
"""
Cleanup script for removing old nodes from both database AND physical Meshtastic nodes
Removes nodes that haven't been heard from in X days
"""

import os
import sys
import psycopg2
import meshtastic.tcp_interface
import meshtastic.serial_interface
from datetime import datetime, timezone, timedelta
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def cleanup_database(days_threshold=60):
    """
    Remove nodes from database that haven't been heard from in X days
    
    Args:
        days_threshold: Number of days of inactivity before deletion (default: 60 = 2 months)
    
    Returns:
        int: Number of nodes deleted
    """
    
    db_config = {
        'host': os.environ.get('DB_HOST', 'localhost'),
        'port': int(os.environ.get('DB_PORT', 5432)),
        'database': os.environ.get('DB_NAME', 'meshtastic'),
        'user': os.environ.get('DB_USER', 'meshuser'),
        'password': os.environ.get('DB_PASSWORD', 'meshpass')
    }
    
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        # Calculate cutoff date
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_threshold)
        
        logging.info(f"🧹 DATABASE: Starting cleanup of nodes older than {days_threshold} days (before {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')})")
        
        # First, get count and list of nodes to be deleted
        cursor.execute("""
            SELECT node_id, long_name, last_heard 
            FROM nodes 
            WHERE last_heard < %s 
            ORDER BY last_heard
        """, (cutoff_date,))
        
        old_nodes = cursor.fetchall()
        
        if not old_nodes:
            logging.info("✅ DATABASE: No old nodes found. Database is clean!")
            cursor.close()
            conn.close()
            return 0
        
        logging.info(f"📋 DATABASE: Found {len(old_nodes)} nodes to delete:")
        for node_id, long_name, last_heard in old_nodes[:10]:  # Show first 10
            days_ago = (datetime.now(timezone.utc) - last_heard.replace(tzinfo=timezone.utc)).days
            logging.info(f"  - {node_id} ({long_name or 'Unknown'}) - Last heard: {days_ago} days ago")
        
        if len(old_nodes) > 10:
            logging.info(f"  ... and {len(old_nodes) - 10} more")
        
        # Delete telemetry data first (foreign key constraint)
        cursor.execute("""
            DELETE FROM telemetry 
            WHERE node_id IN (
                SELECT node_id FROM nodes WHERE last_heard < %s
            )
        """, (cutoff_date,))
        telemetry_deleted = cursor.rowcount
        logging.info(f"🗑️  DATABASE: Deleted {telemetry_deleted} telemetry records")
        
        # Delete nodes
        cursor.execute("""
            DELETE FROM nodes 
            WHERE last_heard < %s
        """, (cutoff_date,))
        nodes_deleted = cursor.rowcount
        
        conn.commit()
        logging.info(f"✅ DATABASE: Successfully deleted {nodes_deleted} old nodes and {telemetry_deleted} telemetry records")
        
        # Show remaining node count
        cursor.execute("SELECT COUNT(*) FROM nodes")
        remaining = cursor.fetchone()[0]
        logging.info(f"📊 DATABASE: Remaining nodes in database: {remaining}")
        
        cursor.close()
        conn.close()
        
        return nodes_deleted
        
    except Exception as e:
        logging.error(f"❌ DATABASE: Error during cleanup: {e}")
        if 'conn' in locals():
            conn.rollback()
        raise

def cleanup_node_db(device_type, address, name):
    """
    Clear the node database on a physical Meshtastic device
    
    Args:
        device_type: 'tcp' or 'serial'
        address: IP:port or /dev/ttyUSB0
        name: Friendly name for logging
    
    Returns:
        bool: Success status
    """
    try:
        logging.info(f"🔧 {name}: Connecting...")
        
        if device_type == 'tcp':
            ip = address.split(':')[0]
            interface = meshtastic.tcp_interface.TCPInterface(hostname=ip)
        else:
            interface = meshtastic.serial_interface.SerialInterface(address)
        
        time.sleep(3)  # Wait for connection
        
        # Get local node
        node = interface.getNode("^all")
        
        # Count nodes before cleanup
        node_count_before = len(interface.nodes) if interface.nodes else 0
        logging.info(f"📊 {name}: Has {node_count_before} nodes in database before cleanup")
        
        # Reset node database (removes all heard nodes except self)
        logging.info(f"🗑️  {name}: Resetting node database...")
        node.resetNodeDb()
        time.sleep(2)
        
        logging.info(f"✅ {name}: Node database cleared successfully!")
        
        interface.close()
        return True
        
    except Exception as e:
        logging.error(f"❌ {name}: Failed to clear node database: {e}")
        return False

def cleanup_all_devices():
    """
    Clean node databases on all discovered devices
    """
    # Load device registry
    registry_file = '/data/config/device_registry.json'
    
    try:
        import json
        with open(registry_file, 'r') as f:
            devices = json.load(f)
        
        logging.info(f"🔍 Found {len(devices)} registered devices")
        
        success_count = 0
        for address, info in devices.items():
            if cleanup_node_db(info['type'], address, info['name']):
                success_count += 1
        
        logging.info(f"✅ DEVICES: Successfully cleaned {success_count}/{len(devices)} device node databases")
        return success_count
        
    except FileNotFoundError:
        logging.warning(f"⚠️  No device registry found at {registry_file}")
        return 0
    except Exception as e:
        logging.error(f"❌ DEVICES: Error cleaning device databases: {e}")
        return 0

def main():
    """Main entry point"""
    # Default to 60 days (2 months), but allow override via environment variable
    days_threshold = int(os.environ.get('CLEANUP_DAYS_THRESHOLD', '60'))
    
    # Check for command line arguments
    clean_devices = '--devices' in sys.argv or '--all' in sys.argv
    clean_database = '--database' in sys.argv or '--all' in sys.argv
    
    # If no specific flag, clean database only (safe default)
    if not clean_devices and not clean_database:
        clean_database = True
    
    # Override days threshold if provided
    for arg in sys.argv[1:]:
        if arg.isdigit():
            days_threshold = int(arg)
    
    logging.info("=" * 60)
    logging.info("🚀 Meshtastic Cleanup Starting")
    logging.info(f"   Database threshold: {days_threshold} days")
    logging.info(f"   Clean database: {clean_database}")
    logging.info(f"   Clean device node DBs: {clean_devices}")
    logging.info("=" * 60)
    
    db_deleted = 0
    devices_cleaned = 0
    
    if clean_database:
        logging.info("\n📦 PHASE 1: Database Cleanup")
        logging.info("-" * 60)
        db_deleted = cleanup_database(days_threshold)
    
    if clean_devices:
        logging.info("\n🔧 PHASE 2: Device Node Database Cleanup")
        logging.info("-" * 60)
        devices_cleaned = cleanup_all_devices()
    
    logging.info("\n" + "=" * 60)
    logging.info("🏁 Cleanup Complete")
    logging.info(f"   Database nodes deleted: {db_deleted}")
    logging.info(f"   Devices cleaned: {devices_cleaned}")
    logging.info("=" * 60)

if __name__ == '__main__':
    main()
