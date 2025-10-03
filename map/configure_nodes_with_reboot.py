#!/usr/bin/env python3
"""
Configure Meshtastic nodes with name and fixed GPS position, then reboot
"""
import meshtastic.tcp_interface
import meshtastic.serial_interface
import time
import sys

# Ishavsvegen 69B, 9010 Tromsø coordinates
LATITUDE = 69.6812
LONGITUDE = 18.9895
ALTITUDE = 10

def configure_wifi_node():
    """Configure WiFi node via TCP"""
    print("=" * 60)
    print("🌐 WIFI NODE CONFIGURATION")
    print("=" * 60)
    
    try:
        print("Connecting to 172.19.228.51...")
        interface = meshtastic.tcp_interface.TCPInterface(hostname="172.19.228.51")
        time.sleep(4)
        
        if not interface.myInfo:
            print("❌ Could not get node info")
            return False
        
        my_id = f"!{interface.myInfo.my_node_num:08x}"
        print(f"✅ Connected to: {my_id}")
        
        node = interface.getNode("^all")
        
        # Set name
        print("\n📝 Setting name: 'PROTONORD wifi' (short: WIFI)")
        node.setOwner(long_name="PROTONORD wifi", short_name="WIFI")
        time.sleep(2)
        
        # Set position
        print(f"📍 Setting position: {LATITUDE}, {LONGITUDE}, {ALTITUDE}m")
        node.setFixedPosition(lat=LATITUDE, lon=LONGITUDE, alt=ALTITUDE)
        time.sleep(2)
        
        # Reboot to apply changes
        print("🔄 Rebooting node to apply changes...")
        node.reboot()
        
        interface.close()
        
        print("⏳ Waiting 30 seconds for node to reboot...")
        time.sleep(30)
        
        # Verify
        print("\n🔍 Verifying changes...")
        interface = meshtastic.tcp_interface.TCPInterface(hostname="172.19.228.51")
        time.sleep(5)
        
        if interface.myInfo and interface.myInfo.my_node_num in interface.nodes:
            node_data = interface.nodes[interface.myInfo.my_node_num]
            user = node_data.get('user', {})
            pos = node_data.get('position', {})
            
            new_name = user.get('longName', 'Unknown')
            new_short = user.get('shortName', 'Unknown')
            new_lat = pos.get('latitude')
            new_lon = pos.get('longitude')
            
            print(f"Name: {new_name} ({new_short})")
            print(f"Position: {new_lat}, {new_lon}")
            
            success = (new_name == "PROTONORD wifi" and 
                      new_short == "WIFI" and
                      abs(new_lat - LATITUDE) < 0.001 and
                      abs(new_lon - LONGITUDE) < 0.001)
            
            if success:
                print("✅ WiFi node configured successfully!")
            else:
                print("⚠️ Some changes may not have applied")
        
        interface.close()
        return True
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def configure_usb_node():
    """Configure USB node via serial"""
    print("\n" + "=" * 60)
    print("🔌 USB NODE CONFIGURATION")
    print("=" * 60)
    
    try:
        print("Connecting to /dev/ttyUSB0...")
        interface = meshtastic.serial_interface.SerialInterface("/dev/ttyUSB0")
        time.sleep(4)
        
        if not interface.myInfo:
            print("❌ Could not get node info")
            return False
        
        my_id = f"!{interface.myInfo.my_node_num:08x}"
        print(f"✅ Connected to: {my_id}")
        
        node = interface.getNode("^all")
        
        # Set name
        print("\n📝 Setting name: 'PROTONORD usb' (short: USB)")
        node.setOwner(long_name="PROTONORD usb", short_name="USB")
        time.sleep(2)
        
        # Set position
        print(f"📍 Setting position: {LATITUDE}, {LONGITUDE}, {ALTITUDE}m")
        node.setFixedPosition(lat=LATITUDE, lon=LONGITUDE, alt=ALTITUDE)
        time.sleep(2)
        
        # Reboot to apply changes
        print("🔄 Rebooting node to apply changes...")
        node.reboot()
        
        interface.close()
        
        print("⏳ Waiting 30 seconds for node to reboot...")
        time.sleep(30)
        
        # Verify
        print("\n🔍 Verifying changes...")
        interface = meshtastic.serial_interface.SerialInterface("/dev/ttyUSB0")
        time.sleep(5)
        
        if interface.myInfo and interface.myInfo.my_node_num in interface.nodes:
            node_data = interface.nodes[interface.myInfo.my_node_num]
            user = node_data.get('user', {})
            pos = node_data.get('position', {})
            
            new_name = user.get('longName', 'Unknown')
            new_short = user.get('shortName', 'Unknown')
            new_lat = pos.get('latitude')
            new_lon = pos.get('longitude')
            
            print(f"Name: {new_name} ({new_short})")
            print(f"Position: {new_lat}, {new_lon}")
            
            success = (new_name == "PROTONORD usb" and 
                      new_short == "USB" and
                      abs(new_lat - LATITUDE) < 0.001 and
                      abs(new_lon - LONGITUDE) < 0.001)
            
            if success:
                print("✅ USB node configured successfully!")
            else:
                print("⚠️ Some changes may not have applied")
        
        interface.close()
        return True
        
    except Exception as e:
        print("❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 MESHTASTIC NODE CONFIGURATION")
    print("="*60)
    print(f"📍 Location: Ishavsvegen 69B, 9010 Tromsø")
    print(f"   Coordinates: {LATITUDE}°N, {LONGITUDE}°E, {ALTITUDE}m")
    print("="*60)
    
    # Check which node to configure
    if len(sys.argv) > 1:
        if sys.argv[1] == "wifi":
            configure_wifi_node()
        elif sys.argv[1] == "usb":
            configure_usb_node()
        else:
            print("Usage: python configure_nodes_with_reboot.py [wifi|usb]")
    else:
        # Configure both
        wifi_ok = configure_wifi_node()
        usb_ok = configure_usb_node()
        
        print("\n" + "=" * 60)
        print("📊 SUMMARY")
        print("=" * 60)
        print(f"WiFi node: {'✅ SUCCESS' if wifi_ok else '❌ FAILED'}")
        print(f"USB node: {'✅ SUCCESS' if usb_ok else '❌ FAILED'}")
        print("=" * 60)
