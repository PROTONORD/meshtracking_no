#!/usr/bin/env python3
"""
MQTT Collector for Meshtastic (PostgreSQL version)
Subscribes to Mosquitto broker and stores node data in PostgreSQL database.
Works with both global MQTT bridge and local Heltec V3 radio data.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import paho.mqtt.client as mqtt
import psycopg2
from psycopg2.extras import RealDictCursor
from meshtastic.protobuf import mesh_pb2, mqtt_pb2, portnums_pb2, telemetry_pb2

# Configuration from environment
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "meshlocal")
MQTT_PASS = os.getenv("MQTT_PASS", "meshLocal2025")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "msh/#")

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'postgres'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'meshtastic'),
    'user': os.getenv('DB_USER', 'meshuser'),
    'password': os.getenv('DB_PASSWORD', 'meshpass2025')
}

# Node storage cache
nodes_cache: Dict[str, Dict[str, Any]] = {}


def get_db_connection():
    """Get PostgreSQL connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
        return conn
    except Exception as e:
        print(f"ERROR: Failed to connect to database: {e}", flush=True)
        return None


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
            "rx_snr": packet.rx_snr if hasattr(packet, 'rx_snr') else None,
            "hop_limit": packet.hop_limit if hasattr(packet, 'hop_limit') else None,
        }
        
        # Parse different payload types
        # Parse packet based on portnum
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
            
            print(f"DEBUG: TELEMETRY_APP parsed. HasField device_metrics: {telem.HasField('device_metrics')}", flush=True)
            
            telemetry_data = {}
            
            # Device metrics (battery, voltage, etc.)
            if telem.HasField("device_metrics"):
                telemetry_data.update({
                    "battery_level": telem.device_metrics.battery_level,
                    "voltage": telem.device_metrics.voltage,
                    "channel_utilization": telem.device_metrics.channel_utilization,
                    "air_util_tx": telem.device_metrics.air_util_tx,
                    "uptime_seconds": telem.device_metrics.uptime_seconds if hasattr(telem.device_metrics, 'uptime_seconds') else None,
                })
            
            # Power metrics (INA219/INA260 external sensors)
            if telem.HasField("power_metrics"):
                pm = telem.power_metrics
                telemetry_data["power_metrics"] = {
                    "ch1_voltage": pm.ch1_voltage if pm.ch1_voltage > 0 else None,
                    "ch1_current": pm.ch1_current if pm.ch1_current > 0 else None,
                    "ch2_voltage": pm.ch2_voltage if pm.ch2_voltage > 0 else None,
                    "ch2_current": pm.ch2_current if pm.ch2_current > 0 else None,
                    "ch3_voltage": pm.ch3_voltage if pm.ch3_voltage > 0 else None,
                    "ch3_current": pm.ch3_current if pm.ch3_current > 0 else None,
                }
            
            # Environment metrics (weather, light, soil sensors)
            if telem.HasField("environment_metrics"):
                em = telem.environment_metrics
                telemetry_data["environment_metrics"] = {
                    "temperature": em.temperature if em.temperature != 0 else None,
                    "relative_humidity": em.relative_humidity if em.relative_humidity != 0 else None,
                    "barometric_pressure": em.barometric_pressure if em.barometric_pressure != 0 else None,
                    "gas_resistance": em.gas_resistance if em.gas_resistance > 0 else None,
                    "iaq": em.iaq if em.iaq > 0 else None,
                    "distance": em.distance if em.distance > 0 else None,
                    "lux": em.lux if em.lux >= 0 else None,
                    "white_lux": em.white_lux if em.white_lux >= 0 else None,
                    "ir_lux": em.ir_lux if em.ir_lux >= 0 else None,
                    "uv_lux": em.uv_lux if em.uv_lux >= 0 else None,
                    "wind_direction": em.wind_direction if em.wind_direction >= 0 else None,
                    "wind_speed": em.wind_speed if em.wind_speed >= 0 else None,
                    "wind_gust": em.wind_gust if em.wind_gust >= 0 else None,
                    "wind_lull": em.wind_lull if em.wind_lull >= 0 else None,
                    "weight": em.weight if em.weight > 0 else None,
                    "radiation": em.radiation if em.radiation >= 0 else None,
                    "rainfall_1h": em.rainfall_1h if em.rainfall_1h >= 0 else None,
                    "rainfall_24h": em.rainfall_24h if em.rainfall_24h >= 0 else None,
                    "soil_moisture": em.soil_moisture if em.soil_moisture >= 0 else None,
                    "soil_temperature": em.soil_temperature if em.soil_temperature != 0 else None,
                }
            
            # Air quality metrics (PM sensors, CO2, VOC, NOx)
            if telem.HasField("air_quality_metrics"):
                aq = telem.air_quality_metrics
                telemetry_data["air_quality_metrics"] = {
                    "pm10_standard": aq.pm10_standard if aq.pm10_standard > 0 else None,
                    "pm25_standard": aq.pm25_standard if aq.pm25_standard > 0 else None,
                    "pm100_standard": aq.pm100_standard if aq.pm100_standard > 0 else None,
                    "co2": aq.co2 if aq.co2 > 0 else None,
                    "voc_idx": aq.pm_voc_idx if hasattr(aq, 'pm_voc_idx') and aq.pm_voc_idx > 0 else None,
                    "nox_idx": aq.pm_nox_idx if hasattr(aq, 'pm_nox_idx') and aq.pm_nox_idx > 0 else None,
                }
            
            print(f"DEBUG: Parsed telemetry_data keys: {list(telemetry_data.keys())}", flush=True)
            if telemetry_data:
                result["telemetry"] = telemetry_data
        
        elif packet.decoded.portnum == portnums_pb2.TEXT_MESSAGE_APP:
            try:
                message_text = packet.decoded.payload.decode('utf-8')
                result["text_message"] = message_text
            except Exception as e:
                print(f"DEBUG: Failed to decode text message: {e}", flush=True)
        
        # For MAP reports (position in user info)
        if "/map/" in topic and packet.decoded.portnum == portnums_pb2.MAP_REPORT_APP:
            user = mesh_pb2.User()
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
        print(f"DEBUG: Failed to parse {topic}: {type(e).__name__}: {e}", flush=True)
        return None


def update_node(node_id: str, node_num: int, data: Dict[str, Any]) -> None:
    """Update or insert node information in database."""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        now = datetime.now(timezone.utc)
        
        # Build update data
        node_data = {
            'node_id': node_id,
            'node_num': node_num,
            'last_heard': now,
            'source': 'mqtt',
            'long_name': None,
            'short_name': None,
            'hw_model': None,
            'role': None,
            'latitude': None,
            'longitude': None,
            'altitude': None,
            'battery_level': None,
            'voltage': None,
            'snr': None
        }
        
        # Extract user info
        if "user" in data:
            user = data["user"]
            node_data['long_name'] = user.get("long_name")
            node_data['short_name'] = user.get("short_name")
            node_data['hw_model'] = user.get("hw_model")
            node_data['role'] = user.get("role")
        
        # Extract position
        if "position" in data:
            pos = data["position"]
            if pos.get("latitude") and pos.get("longitude"):
                node_data['latitude'] = pos["latitude"]
                node_data['longitude'] = pos["longitude"]
                node_data['altitude'] = pos.get("altitude")
        
        # Extract telemetry
        if "telemetry" in data:
            telem = data["telemetry"]
            node_data['battery_level'] = telem.get("battery_level")
            node_data['voltage'] = telem.get("voltage")
        
        # Extract SNR
        if "rx_snr" in data:
            node_data['snr'] = data["rx_snr"]
        
        # Upsert node
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
        """, node_data)
        
        # Store position if we have coordinates
        if node_data.get('latitude') and node_data.get('longitude'):
            cursor.execute("""
                INSERT INTO positions (
                    node_id, timestamp, latitude, longitude, altitude, source
                ) VALUES (
                    %(node_id)s, %(timestamp)s, %(latitude)s, %(longitude)s,
                    %(altitude)s, %(source)s
                )
                ON CONFLICT DO NOTHING
            """, {
                'node_id': node_id,
                'timestamp': now,
                'latitude': node_data['latitude'],
                'longitude': node_data['longitude'],
                'altitude': node_data.get('altitude'),
                'source': 'mqtt'
            })
        
        # Store telemetry data
        if "telemetry" in data:
            print(f"DEBUG: Telemetry found for {node_id}", flush=True)
            telem = data["telemetry"]
            
            # Build telemetry record with all fields initialized to None
            telem_record = {
                'node_id': node_id,
                'timestamp': now,
                'battery_level': telem.get('battery_level'),
                'voltage': telem.get('voltage'),
                'channel_utilization': telem.get('channel_utilization'),
                'air_util_tx': telem.get('air_util_tx'),
                'uptime_seconds': telem.get('uptime_seconds'),
                # Power metrics
                'ch1_voltage': None,
                'ch1_current': None,
                'ch2_voltage': None,
                'ch2_current': None,
                'ch3_voltage': None,
                'ch3_current': None,
                # Environment metrics
                'temperature': None,
                'relative_humidity': None,
                'barometric_pressure': None,
                'gas_resistance': None,
                'iaq': None,
                'distance': None,
                'lux': None,
                'white_lux': None,
                'ir_lux': None,
                'uv_lux': None,
                'wind_direction': None,
                'wind_speed': None,
                'wind_gust': None,
                'wind_lull': None,
                'weight': None,
                'radiation': None,
                'rainfall_1h': None,
                'rainfall_24h': None,
                'soil_moisture': None,
                'soil_temperature': None,
                # Air quality metrics
                'pm10_standard': None,
                'pm25_standard': None,
                'pm100_standard': None,
                'co2': None,
                'voc_idx': None,
                'nox_idx': None,
            }
            
            # Add power metrics if present
            has_power = False
            if "power_metrics" in telem:
                pm = telem["power_metrics"]
                if any(v is not None for v in pm.values()):  # Check if any power value is not None
                    has_power = True
                    telem_record.update(pm)
            
            # Add environment metrics if present
            has_environment = False
            if "environment_metrics" in telem:
                em = telem["environment_metrics"]
                if any(v is not None for v in em.values()):  # Check if any environment value is not None
                    has_environment = True
                    telem_record.update(em)
            
            # Add air quality metrics if present
            has_air_quality = False
            if "air_quality_metrics" in telem:
                aq = telem["air_quality_metrics"]
                if any(v is not None for v in aq.values()):  # Check if any air quality value is not None
                    has_air_quality = True
                    telem_record.update(aq)
            
            # Insert telemetry
            try:
                print(f"DEBUG: Storing telemetry for {node_id}: battery={telem_record.get('battery_level')}, voltage={telem_record.get('voltage')}", flush=True)
                cursor.execute("""
                    INSERT INTO telemetry (
                        node_id, timestamp, battery_level, voltage, channel_utilization,
                        air_util_tx, uptime_seconds,
                        ch1_voltage, ch1_current, ch2_voltage, ch2_current,
                        ch3_voltage, ch3_current,
                        temperature, relative_humidity, barometric_pressure,
                        gas_resistance, iaq, distance, lux, white_lux, ir_lux, uv_lux,
                        wind_direction, wind_speed, wind_gust, wind_lull,
                        weight, radiation, rainfall_1h, rainfall_24h,
                        soil_moisture, soil_temperature,
                        pm10_standard, pm25_standard, pm100_standard,
                        co2, voc_idx, nox_idx,
                        has_power_metrics, has_environment_metrics, has_air_quality_metrics
                    ) VALUES (
                        %(node_id)s, %(timestamp)s, %(battery_level)s, %(voltage)s,
                        %(channel_utilization)s, %(air_util_tx)s, %(uptime_seconds)s,
                        %(ch1_voltage)s, %(ch1_current)s, %(ch2_voltage)s, %(ch2_current)s,
                        %(ch3_voltage)s, %(ch3_current)s,
                        %(temperature)s, %(relative_humidity)s, %(barometric_pressure)s,
                        %(gas_resistance)s, %(iaq)s, %(distance)s, %(lux)s, %(white_lux)s,
                        %(ir_lux)s, %(uv_lux)s, %(wind_direction)s, %(wind_speed)s,
                        %(wind_gust)s, %(wind_lull)s, %(weight)s, %(radiation)s,
                        %(rainfall_1h)s, %(rainfall_24h)s, %(soil_moisture)s, %(soil_temperature)s,
                        %(pm10_standard)s, %(pm25_standard)s, %(pm100_standard)s,
                        %(co2)s, %(voc_idx)s, %(nox_idx)s,
                        %(has_power)s, %(has_environment)s, %(has_air_quality)s
                    )
                """, {**telem_record, 'has_power': has_power, 
                      'has_environment': has_environment, 
                      'has_air_quality': has_air_quality})
                print(f"DEBUG: Telemetry stored successfully for {node_id}", flush=True)
            except Exception as e:
                print(f"ERROR: Failed to store telemetry for {node_id}: {e}", flush=True)
                import traceback
                traceback.print_exc()
            
            # Update sensor flags in nodes table
            if has_power or has_environment or has_air_quality:
                cursor.execute("""
                    UPDATE nodes SET
                        has_power_sensor = COALESCE(%(has_power)s, has_power_sensor),
                        has_environment_sensor = COALESCE(%(has_environment)s, has_environment_sensor),
                        has_air_quality_sensor = COALESCE(%(has_air_quality)s, has_air_quality_sensor)
                    WHERE node_id = %(node_id)s
                """, {
                    'node_id': node_id,
                    'has_power': has_power,
                    'has_environment': has_environment,
                    'has_air_quality': has_air_quality
                })
        
        # Store text message if present
        if "text_message" in data:
            cursor.execute("""
                INSERT INTO messages (
                    from_node, to_node, channel, packet_id, timestamp,
                    message_text, portnum, want_ack
                ) VALUES (
                    %(from_node)s, %(to_node)s, %(channel)s, %(packet_id)s,
                    %(timestamp)s, %(message_text)s, 'TEXT_MESSAGE_APP', FALSE
                )
                ON CONFLICT DO NOTHING
            """, {
                'from_node': node_id,
                'to_node': data.get('to'),
                'channel': data.get('channel', 0),
                'packet_id': data.get('packet_id', 0),
                'timestamp': now,
                'message_text': data['text_message']
            })
        
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        # Don't spam errors for missing data - nodes without full info are normal
        if 'long_name' not in str(e):
            print(f"ERROR: Failed to update node {node_id}: {e}", flush=True)
    finally:
        cursor.close()
        conn.close()


def on_connect(client, userdata, flags, rc):
    """MQTT connection callback"""
    if rc == 0:
        print(f"✓ Connected to MQTT broker at {MQTT_HOST}:{MQTT_PORT}", flush=True)
        client.subscribe(MQTT_TOPIC)
        print(f"✓ Subscribed to topic: {MQTT_TOPIC}", flush=True)
    else:
        print(f"✗ Failed to connect to MQTT, return code: {rc}", flush=True)


def on_message(client, userdata, msg):
    """MQTT message callback"""
    try:
        data = parse_service_envelope(msg.payload, msg.topic)
        if data:
            node_id = data["from"]
            node_num = data["from_num"]
            
            # Log interesting packets
            packet_type = "unknown"
            if "position" in data:
                packet_type = "position"
            elif "user" in data:
                packet_type = "nodeinfo"
            elif "telemetry" in data:
                packet_type = "telemetry"
                print(f"DEBUG: Telemetry packet detected! Keys in data: {list(data.keys())}", flush=True)
            elif "text_message" in data:
                packet_type = "message"
                msg_preview = data['text_message'][:30] + "..." if len(data['text_message']) > 30 else data['text_message']
                print(f"💬 {packet_type}: {node_id} → \"{msg_preview}\" via {msg.topic}", flush=True)
                update_node(node_id, node_num, data)
                return
            
            print(f"📡 {packet_type}: {node_id} via {msg.topic}", flush=True)
            
            # Update node in database
            update_node(node_id, node_num, data)
            
    except Exception as e:
        print(f"ERROR: Failed to process message: {e}", flush=True)


def main():
    """Main MQTT listener loop"""
    print("=== Meshtastic MQTT Collector (PostgreSQL) ===", flush=True)
    print(f"MQTT Broker: {MQTT_HOST}:{MQTT_PORT}", flush=True)
    print(f"Topic: {MQTT_TOPIC}", flush=True)
    print(f"Database: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}", flush=True)
    
    # Test database connection
    conn = get_db_connection()
    if not conn:
        print("FATAL: Cannot connect to database. Exiting.", flush=True)
        sys.exit(1)
    conn.close()
    print("✓ Database connection OK", flush=True)
    
    # Connect to MQTT
    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        print("✓ Starting MQTT loop...", flush=True)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n✓ Shutting down gracefully...", flush=True)
        client.disconnect()
    except Exception as e:
        print(f"FATAL: MQTT connection error: {e}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
