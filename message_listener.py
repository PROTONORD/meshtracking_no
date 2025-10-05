#!/usr/bin/env python3
"""
Meshtastic Message Listener and Auto-Responder
Listens for all messages on the mesh network, stores them in database,
and implements intelligent auto-response based on message content and history.
"""

import os
import time
import json
import logging
import psycopg2
from datetime import datetime, timezone
from typing import Dict, List, Optional
import meshtastic
import meshtastic.tcp_interface
import meshtastic.serial_interface
import signal
import sys
import threading
from pubsub import pub

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class MessageListener:
    """Listens for messages and implements auto-response logic"""
    
    def __init__(self):
        self.db_config = {
            'host': os.environ.get('DB_HOST', 'localhost'),
            'database': os.environ.get('DB_NAME', 'meshtastic'),
            'user': os.environ.get('DB_USER', 'meshuser'),
            'password': os.environ.get('DB_PASSWORD'),  # Required - no default
            'port': int(os.environ.get('DB_PORT', 5432))
        }
        
        # Our node info
        self.our_node_id = None
        self.our_node_name = "PROTONORD"
        
        # Interface management
        self.interface = None
        self.connected = False
        self.running = True
        
        # Stats
        self.messages_received = 0
        self.responses_sent = 0
        self.start_time = time.time()
        
        # Auto-response settings
        self.response_cooldown = {}  # Track response cooldowns per node
        self.cooldown_seconds = 300  # 5 minutes between responses to same node
        
        # Response messages
        self.responses = [
            "👍 Takk for meldingen!",
            "📡 PROTONORD WiFi her - mottatt!",
            "🤖 Auto-respons fra PROTONORD",
            "✅ Melding registrert i database",
        ]
        
        # Keywords that trigger special responses
        self.special_responses = {
            'test': "🧪 Test mottatt og bekreftet!",
            'status': f"📊 Status: {self.messages_received} meldinger mottatt",
            'help': "💡 Send 'test' for test, 'status' for statistikk",
            'ping': "🏓 Pong!",
        }
        
    def connect_to_radio(self):
        """Connect to radio interface"""
        try:
            # Use WiFi node to avoid conflict with device_manager polling USB
            # device_manager.py polls USB for node data, message_listener uses WiFi
            for connection_type, address in [('tcp', '172.19.228.51')]:
                try:
                    logging.info(f"📡 Attempting to connect via {connection_type}: {address}")
                    
                    if connection_type == 'tcp':
                        self.interface = meshtastic.tcp_interface.TCPInterface(address)
                    else:
                        self.interface = meshtastic.serial_interface.SerialInterface(address)
                    
                    # Wait for connection
                    time.sleep(3)
                    
                    # Get our node info
                    node_info = self.interface.getMyNodeInfo()
                    self.our_node_id = f"!{node_info.get('num', 0):08x}"
                    
                    logging.info(f"✅ Connected via {connection_type} as {self.our_node_id}")
                    self.connected = True
                    
                    # Subscribe to message events
                    pub.subscribe(self.on_message_received, "meshtastic.receive")
                    
                    return True
                    
                except Exception as e:
                    logging.warning(f"❌ {connection_type} connection failed: {e}")
                    if self.interface:
                        try:
                            self.interface.close()
                        except:
                            pass
                        self.interface = None
                    continue
            
            logging.error("❌ All connection attempts failed")
            return False
            
        except Exception as e:
            logging.error(f"❌ Connection error: {e}")
            return False
    
    def on_message_received(self, packet, interface):
        """Called when a message is received"""
        try:
            # Only process text messages
            if 'decoded' not in packet or 'text' not in packet['decoded']:
                return
                
            # Extract message details
            from_node = packet.get('from')
            to_node = packet.get('to') 
            message_text = packet['decoded']['text']
            channel = packet.get('channel', 0)
            packet_id = packet.get('id')
            hop_limit = packet.get('hopLimit')
            want_ack = packet.get('wantAck', False)
            
            # Convert node numbers to hex IDs
            from_node_id = f"!{from_node:08x}" if from_node else None
            to_node_id = f"!{to_node:08x}" if to_node else None
            
            self.messages_received += 1
            
            logging.info(f"📨 Message received:")
            logging.info(f"   From: {from_node_id}")
            logging.info(f"   To: {to_node_id}")
            logging.info(f"   Text: {message_text}")
            logging.info(f"   Channel: {channel}")
            
            # Save to database
            self.save_message(from_node_id, to_node_id, message_text, channel, packet_id, hop_limit, want_ack)
            
            # Check if we should auto-respond
            self.check_auto_response(from_node_id, to_node_id, message_text, channel)
            
        except Exception as e:
            logging.error(f"❌ Error processing message: {e}")
    
    def save_message(self, from_node, to_node, message, channel, packet_id, hop_limit, want_ack):
        """Save message to database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO messages (from_node, to_node, message, channel, packet_id, hop_limit, want_ack, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (from_node, to_node, message, channel, packet_id, hop_limit, want_ack, datetime.now(timezone.utc)))
            
            conn.commit()
            conn.close()
            
            logging.info(f"💾 Message saved to database")
            
        except Exception as e:
            logging.error(f"❌ Database save failed: {e}")
    
    def check_auto_response(self, from_node, to_node, message_text, channel):
        """Check if we should send an auto-response"""
        try:
            # Don't respond to our own messages
            if from_node == self.our_node_id:
                return
            
            # Only respond to direct messages to us or broadcasts
            if to_node and to_node != self.our_node_id:
                return
            
            # Check cooldown
            now = time.time()
            if from_node in self.response_cooldown:
                if now - self.response_cooldown[from_node] < self.cooldown_seconds:
                    logging.info(f"⏰ Cooldown active for {from_node}, not responding")
                    return
            
            # Determine response
            response_text = self.get_response_text(message_text)
            
            if response_text:
                # Send response
                self.send_response(from_node, response_text)
                
                # Update cooldown
                self.response_cooldown[from_node] = now
                self.responses_sent += 1
                
        except Exception as e:
            logging.error(f"❌ Auto-response error: {e}")
    
    def get_response_text(self, message_text):
        """Determine appropriate response text"""
        message_lower = message_text.lower()
        
        # Check for special keywords
        for keyword, response in self.special_responses.items():
            if keyword in message_lower:
                if keyword == 'status':
                    # Update status response with current stats
                    return f"📊 Status: {self.messages_received} meldinger mottatt, {self.responses_sent} svar sendt"
                return response
        
        # Check if message contains specific patterns
        if any(word in message_lower for word in ['protonord', 'test', 'hello', 'hei', 'hi']):
            import random
            return random.choice(self.responses)
        
        # Don't respond to everything - only specific triggers
        return None
    
    def send_response(self, to_node_id, response_text):
        """Send auto-response message"""
        try:
            if not self.connected or not self.interface:
                logging.error("❌ Not connected, cannot send response")
                return
            
            # Convert hex ID back to node number for sending
            to_node_num = int(to_node_id.replace('!', ''), 16)
            
            logging.info(f"📤 Sending auto-response to {to_node_id}: {response_text}")
            
            # Send the message
            self.interface.sendText(response_text, destinationId=to_node_id)
            
            logging.info(f"✅ Auto-response sent successfully")
            
        except Exception as e:
            logging.error(f"❌ Failed to send response: {e}")
    
    def get_message_stats(self):
        """Get message statistics from database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            # Total messages
            cur.execute("SELECT COUNT(*) FROM messages")
            total_messages = cur.fetchone()[0]
            
            # Messages in last hour
            cur.execute("""
                SELECT COUNT(*) FROM messages 
                WHERE timestamp > NOW() - INTERVAL '1 hour'
            """)
            recent_messages = cur.fetchone()[0]
            
            # Top senders
            cur.execute("""
                SELECT from_node, COUNT(*) as message_count 
                FROM messages 
                GROUP BY from_node 
                ORDER BY message_count DESC 
                LIMIT 5
            """)
            top_senders = cur.fetchall()
            
            conn.close()
            
            return {
                'total_messages': total_messages,
                'recent_messages': recent_messages,
                'top_senders': top_senders,
                'responses_sent': self.responses_sent,
                'uptime_hours': (time.time() - self.start_time) / 3600
            }
            
        except Exception as e:
            logging.error(f"❌ Stats error: {e}")
            return {}
    
    def print_status(self):
        """Print status information"""
        stats = self.get_message_stats()
        logging.info(f"📊 Message Listener Status:")
        logging.info(f"   Connected: {self.connected}")
        logging.info(f"   Our Node: {self.our_node_id}")
        logging.info(f"   Messages Received (session): {self.messages_received}")
        logging.info(f"   Responses Sent (session): {self.responses_sent}")
        logging.info(f"   Total DB Messages: {stats.get('total_messages', 0)}")
        logging.info(f"   Recent Messages (1h): {stats.get('recent_messages', 0)}")
        logging.info(f"   Uptime: {stats.get('uptime_hours', 0):.1f} hours")
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logging.info(f"🛑 Received signal {signum}, shutting down...")
        self.running = False
        
        if self.interface:
            try:
                self.interface.close()
            except:
                pass
        
        self.print_status()
        logging.info("👋 Message Listener stopped")
        sys.exit(0)
    
    def run(self):
        """Main run loop"""
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        logging.info("🚀 Starting PROTONORD Message Listener...")
        
        # Connect to radio
        if not self.connect_to_radio():
            logging.error("❌ Failed to connect to radio")
            sys.exit(1)
        
        logging.info("🔊 Now listening for messages...")
        logging.info(f"📝 Our node ID: {self.our_node_id}")
        
        # Status reporting thread
        def status_reporter():
            while self.running:
                time.sleep(300)  # Every 5 minutes
                if self.running:
                    self.print_status()
        
        status_thread = threading.Thread(target=status_reporter, daemon=True)
        status_thread.start()
        
        # Main loop - just keep the interface alive
        try:
            while self.running:
                time.sleep(1)
                
                # Check connection health
                if not self.connected:
                    logging.warning("❌ Connection lost, attempting to reconnect...")
                    self.connect_to_radio()
                
        except KeyboardInterrupt:
            pass
        
        self.signal_handler(0, None)

if __name__ == "__main__":
    listener = MessageListener()
    listener.run()