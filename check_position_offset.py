#!/usr/bin/env python3
"""
Check GPS position offset between fixed position and reported position
"""
import meshtastic.serial_interface
import meshtastic.tcp_interface
import time

def check_usb_node():
    print('=== USB NODE (!db2f13c0 - PROTONORD usb) ===')
    try:
        interface = meshtastic.serial_interface.SerialInterface('/dev/ttyUSB0')
        time.sleep(3)
        
        # Get local node info
        local_node = interface.getNode('^local')
        if local_node and hasattr(local_node, 'position'):
            pos = local_node.position
            
            # latitudeI and longitudeI are stored as integers (degrees * 1e7)
            if hasattr(pos, 'latitudeI') and hasattr(pos, 'longitudeI'):
                lat_fixed = pos.latitudeI / 1e7
                lon_fixed = pos.longitudeI / 1e7
                print(f'Fixed position (satt i node):')
                print(f'  Latitude:  {lat_fixed:.7f}')
                print(f'  Longitude: {lon_fixed:.7f}')
            
            # latitude and longitude are the floating point values
            if hasattr(pos, 'latitude') and hasattr(pos, 'longitude'):
                print(f'\nReported position (sendt ut):')
                print(f'  Latitude:  {pos.latitude:.7f}')
                print(f'  Longitude: {pos.longitude:.7f}')
                
                if hasattr(pos, 'latitudeI') and hasattr(pos, 'longitudeI'):
                    lat_diff = pos.latitude - lat_fixed
                    lon_diff = pos.longitude - lon_fixed
                    print(f'\nOffset:')
                    print(f'  Latitude:  {lat_diff:.7f}° ({lat_diff * 111319:.2f}m)')
                    print(f'  Longitude: {lon_diff:.7f}° ({lon_diff * 111319 * 0.4:.2f}m at 70°N)')
        else:
            print('Ingen posisjon funnet')
        
        interface.close()
    except Exception as e:
        print(f'Error: {e}')
    print()

def check_wifi_node():
    print('=== WIFI NODE (!db2fa9a4 - PROTONORD wifi) ===')
    try:
        interface = meshtastic.tcp_interface.TCPInterface('172.19.228.51')
        time.sleep(3)
        
        # Get local node info
        local_node = interface.getNode('^local')
        if local_node and hasattr(local_node, 'position'):
            pos = local_node.position
            
            if hasattr(pos, 'latitudeI') and hasattr(pos, 'longitudeI'):
                lat_fixed = pos.latitudeI / 1e7
                lon_fixed = pos.longitudeI / 1e7
                print(f'Fixed position (satt i node):')
                print(f'  Latitude:  {lat_fixed:.7f}')
                print(f'  Longitude: {lon_fixed:.7f}')
            
            if hasattr(pos, 'latitude') and hasattr(pos, 'longitude'):
                print(f'\nReported position (sendt ut):')
                print(f'  Latitude:  {pos.latitude:.7f}')
                print(f'  Longitude: {pos.longitude:.7f}')
                
                if hasattr(pos, 'latitudeI') and hasattr(pos, 'longitudeI'):
                    lat_diff = pos.latitude - lat_fixed
                    lon_diff = pos.longitude - lon_fixed
                    print(f'\nOffset:')
                    print(f'  Latitude:  {lat_diff:.7f}° ({lat_diff * 111319:.2f}m)')
                    print(f'  Longitude: {lon_diff:.7f}° ({lon_diff * 111319 * 0.4:.2f}m at 70°N)')
        else:
            print('Ingen posisjon funnet')
        
        interface.close()
    except Exception as e:
        print(f'Error: {e}')
    print()

if __name__ == '__main__':
    check_usb_node()
    check_wifi_node()
