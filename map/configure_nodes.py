#!/usr/bin/env python3
"""
Configure Meshtastic nodes with name and fixed GPS position
"""
import meshtastic.tcp_interface
import meshtastic.serial_interface
import time
import sys

# Ishavsvegen 69B, 9010 Tromsø coordinates
LATITUDE = 69.6812
LONGITUDE = 18.9895
ALTITUDE = 10  # meters above sea level

def configure_wifi_node():
    """Configure WiFi node via TCP"""
    print("🌐 Connecting to WiFi node at 172.19.228.51...")
    try:
        interface = meshtastic.tcp_interface.TCPInterface(hostname="172.19.228.51")
        time.sleep(3)  # Wait for connection
        
        # Get local node (the one we're connected to)
        node = interface.getNode("^all")
        
        print("📝 Setting name: PROTONORD wifi (short: WIFI)")
        node.setOwner(long_name="PROTONORD wifi", short_name="WIFI")
        time.sleep(2)
        
        print(f"📍 Setting fixed position: {LATITUDE}, {LONGITUDE}, {ALTITUDE}m")
        node.setFixedPosition(lat=LATITUDE, lon=LONGITUDE, alt=ALTITUDE)
        time.sleep(2)
        
        print("✅ WiFi node configured successfully!")
        interface.close()
        return True
        
    except Exception as e:
        print(f"❌ Failed to configure WiFi node: {e}")
        return False

def configure_usb_node():
    """Configure USB node via serial"""
    print("\n🔌 Connecting to USB node at /dev/ttyUSB0...")
    try:
        interface = meshtastic.serial_interface.SerialInterface("/dev/ttyUSB0")
        time.sleep(3)  # Wait for connection
        
        # Get local node (the one we're connected to)
        node = interface.getNode("^all")
        
        print("📝 Setting name: PROTONORD usb (short: USB)")
        node.setOwner(long_name="PROTONORD usb", short_name="USB")
        time.sleep(2)
        
        print(f"📍 Setting fixed position: {LATITUDE}, {LONGITUDE}, {ALTITUDE}m")
        node.setFixedPosition(lat=LATITUDE, lon=LONGITUDE, alt=ALTITUDE)
        time.sleep(2)
        
        print("✅ USB node configured successfully!")
        interface.close()
        return True
        
    except Exception as e:
        print(f"❌ Failed to configure USB node: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Configuring Meshtastic nodes...")
    print(f"📍 Location: Ishavsvegen 69B, 9010 Tromsø")
    print(f"   Coordinates: {LATITUDE}°N, {LONGITUDE}°E, {ALTITUDE}m")
    print()
    
    wifi_ok = configure_wifi_node()
    usb_ok = configure_usb_node()
    
    print("\n" + "="*50)
    if wifi_ok and usb_ok:
        print("✅ All nodes configured successfully!")
        sys.exit(0)
    else:
        print("⚠️  Some nodes failed to configure")
        sys.exit(1)
