"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Test Module
"""

"""
SIMPLE TEST SCRIPT - Verify OBD Module Works
=============================================
Run this to quickly test your connection
"""

import sys
import time

# Colors for Windows
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
RESET = '\033[0m'

def test_imports():
    """Test that all imports work"""
    print(f"\n{CYAN}Testing imports...{RESET}")
    
    try:
        import serial
        print(f"{GREEN}✓ pyserial installed{RESET}")
    except ImportError:
        print(f"{RED}✗ pyserial NOT installed{RESET}")
        print(f"  Run: pip install pyserial")
        return False
    
    try:
        from connectivity_module_v4 import (
            ProfessionalConnectivityManager,
            DirectELM327,
            OBDProtocol,
            ALL_PIDS
        )
        print(f"{GREEN}✓ connectivity_module_v4 imported{RESET}")
        print(f"  Total PIDs in database: {len(ALL_PIDS)}")
    except ImportError as e:
        print(f"{RED}✗ connectivity_module_v4 import failed: {e}{RESET}")
        return False
    
    return True


def test_ports():
    """Test COM port detection"""
    print(f"\n{CYAN}Testing COM port detection...{RESET}")
    
    import serial.tools.list_ports
    ports = list(serial.tools.list_ports.comports())
    
    if ports:
        print(f"{GREEN}✓ Found {len(ports)} COM port(s):{RESET}")
        for p in ports:
            bt = " (Bluetooth)" if 'bluetooth' in p.description.lower() else ""
            print(f"  - {p.device}: {p.description}{bt}")
        return True
    else:
        print(f"{YELLOW}⚠ No COM ports found{RESET}")
        return False


def test_direct_elm(port: str):
    """Test DirectELM327 class"""
    print(f"\n{CYAN}Testing DirectELM327 connection to {port}...{RESET}")
    
    from connectivity_module_v4 import DirectELM327
    
    elm = DirectELM327(port, 38400)
    
    if not elm.connect():
        print(f"{RED}✗ Failed to connect to {port}{RESET}")
        return False
    
    print(f"{GREEN}✓ Connected to {port}{RESET}")
    
    # Initialize
    print(f"{CYAN}Initializing Protocol 3...{RESET}")
    if elm.initialize_protocol_3():
        print(f"{GREEN}✓ Protocol 3 initialized{RESET}")
        print(f"  Voltage: {elm.voltage}V")
    
    # Try reading PIDs
    print(f"\n{CYAN}Testing PID reads...{RESET}")
    
    test_pids = [
        ('rpm', 'RPM'),
        ('speed', 'Speed'),
        ('coolant_temp', 'Coolant Temp'),
        ('engine_load', 'Engine Load'),
        ('throttle_position', 'Throttle'),
    ]
    
    working = 0
    for pid_key, name in test_pids:
        value = elm.read_pid(pid_key)
        if value is not None:
            print(f"{GREEN}✓ {name}: {value}{RESET}")
            working += 1
        else:
            print(f"{RED}✗ {name}: No response{RESET}")
    
    elm.disconnect()
    print(f"\n{GREEN if working > 0 else RED}Result: {working}/{len(test_pids)} PIDs working{RESET}")
    
    return working > 0


def main():
    print("=" * 60)
    print("OBD MODULE TEST SCRIPT")
    print("=" * 60)
    
    # Test imports
    if not test_imports():
        print(f"\n{RED}Import test failed. Install missing packages.{RESET}")
        return
    
    # Test ports
    if not test_ports():
        print(f"\n{YELLOW}No ports found. Check adapter connection.{RESET}")
        return
    
    # Ask to test connection
    print(f"\n{CYAN}Test OBD connection? (y/n):{RESET}")
    try:
        if input().lower().strip() == 'y':
            print(f"\n{CYAN}Enter COM port (e.g., COM6):{RESET}")
            port = input().strip().upper()
            if port:
                test_direct_elm(port)
    except KeyboardInterrupt:
        pass
    
    print(f"\n{GREEN}Test complete!{RESET}")


if __name__ == "__main__":
    main()
