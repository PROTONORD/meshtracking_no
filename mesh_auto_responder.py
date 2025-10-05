#!/usr/bin/env python3
"""
PROTONORD Mesh Message Auto-Responder
Lytter kontinuerlig etter meldinger til PROTONORD WiFi node og svarer automatisk
"""

import logging
import time
import signal
import sys
from datetime import datetime
import meshtastic.tcp_interface

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProtonordAutoResponder:
    def __init__(self, wifi_host='172.19.228.51'):
        self.wifi_host = wifi_host
        self.interface = None
        self.running = False
        self.my_node_id = None
        self.response_count = 0
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def signal_handler(self, signum, frame):
        logger.info(f"🛑 Received signal {signum}, shutting down gracefully...")
        self.stop()
        
    def connect(self):
        """Connect to WiFi node"""
        try:
            logger.info(f"📡 Connecting to PROTONORD WiFi node at {self.wifi_host}...")
            self.interface = meshtastic.tcp_interface.TCPInterface(hostname=self.wifi_host)
            
            # Get our node info
            my_info = self.interface.getMyNodeInfo()
            self.my_node_id = my_info['user']['id']
            my_name = my_info['user']['longName']
            
            logger.info(f"✅ Connected as {my_name} ({self.my_node_id})")
            
            # Setup message handler
            self.interface.onReceive = self.on_message_received
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
    
    def on_message_received(self, packet, interface):
        """Handle incoming messages"""
        try:
            # Check if it's a text message directed to us
            if packet.get('decoded', {}).get('text'):
                from_node = packet.get('from', 0)
                to_node = packet.get('to', 0)
                message = packet['decoded']['text']
                
                from_hex = f'!{from_node:08x}'
                to_hex = f'!{to_node:08x}'
                
                # Check if message is directed to us (direct message or broadcast to our ID)
                is_direct_to_us = (to_node == int(self.my_node_id.replace('!', ''), 16))
                is_broadcast = (to_node == 0xffffffff)
                
                if is_direct_to_us:
                    logger.info(f"📨 DIRECT MESSAGE: {from_hex} → {self.my_node_id}: \"{message}\"")
                    self.send_auto_response(from_hex, message)
                elif is_broadcast:
                    logger.info(f"📢 BROADCAST: {from_hex}: \"{message}\"")
                    # Optional: respond to broadcasts mentioning PROTONORD
                    if 'PROTONORD' in message.upper() or 'WIFI' in message.upper():
                        logger.info("📢 Broadcast mentions PROTONORD - sending response")
                        self.send_auto_response(from_hex, message, is_broadcast=True)
                else:
                    logger.debug(f"📬 Other message: {from_hex} → {to_hex}: \"{message}\"")
                    
        except Exception as e:
            logger.error(f"❌ Error processing message: {e}")
    
    def send_auto_response(self, from_node_hex, original_message, is_broadcast=False):
        """Send automatic thumbs up response"""
        try:
            # Convert hex back to int for sending
            from_node_int = int(from_node_hex.replace('!', ''), 16)
            
            # Create response message
            timestamp = datetime.now().strftime("%H:%M")
            
            if is_broadcast:
                response = f"👍 PROTONORD WiFi auto-svar ({timestamp})"
            else:
                response = f"👍 Auto-svar fra PROTONORD WiFi! Mottok: '{original_message[:30]}...' ({timestamp})"
            
            # Send response back to sender
            logger.info(f"📤 Sending auto-response to {from_node_hex}: \"{response}\"")
            
            self.interface.sendText(response, destinationId=from_node_hex)
            
            self.response_count += 1
            logger.info(f"✅ Auto-response #{self.response_count} sent successfully!")
            
        except Exception as e:
            logger.error(f"❌ Failed to send auto-response: {e}")
    
    def start(self):
        """Start the auto-responder service"""
        logger.info("🚀 Starting PROTONORD Mesh Auto-Responder...")
        
        if not self.connect():
            return False
        
        self.running = True
        logger.info("🔊 Now listening for messages... Send a message to PROTONORD WiFi to test!")
        logger.info(f"📝 Our node ID: {self.my_node_id}")
        
        try:
            while self.running:
                time.sleep(1)  # Keep alive loop
                
                # Periodic status log (every 5 minutes)
                if int(time.time()) % 300 == 0:
                    logger.info(f"💓 Auto-responder alive - {self.response_count} responses sent so far")
                    
        except KeyboardInterrupt:
            logger.info("🛑 Keyboard interrupt received")
        except Exception as e:
            logger.error(f"❌ Runtime error: {e}")
        finally:
            self.stop()
            
        return True
    
    def stop(self):
        """Stop the auto-responder service"""
        logger.info("🛑 Stopping auto-responder...")
        self.running = False
        
        if self.interface:
            try:
                self.interface.close()
                logger.info("📡 Interface closed")
            except:
                pass
                
        logger.info(f"📊 Final stats: {self.response_count} auto-responses sent")
        logger.info("👋 PROTONORD Auto-Responder stopped")

def main():
    responder = ProtonordAutoResponder()
    
    try:
        responder.start()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()