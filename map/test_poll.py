#!/usr/bin/env python3
"""
Manual device poll trigger - for testing
"""
import os
os.environ.setdefault('POLL_INTERVAL', '10')  # Override to 10s for testing
os.environ.setdefault('DISCOVERY_INTERVAL', '30')

from device_manager import MeshtasticDeviceManager

if __name__ == '__main__':
    print("🧪 Test mode: Quick polling")
    print("Discovery: 30s, Poll: 10s")
    manager = MeshtasticDeviceManager()
    manager.run()
