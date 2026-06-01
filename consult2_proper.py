"""
CONSULT-II Proper Implementation
================================

Based on capture analysis:
- Frame: Length + Command + Params + Checksum
- Init: 81 10 FC 81 0E -> ECU responds 83 FC 10 C1...
- Data: 22 command, 62 response
- Checksum: simple 8-bit sum
"""

from pyftdi.ftdi import Ftdi
import time

class Consult2:
    def __init__(self):
        self.ftdi = None
        self.session_active = False
        
    def connect(self):
        """Open FTDI device"""
        self.ftdi = Ftdi()
        self.ftdi.open(vendor=0x0403, product=0x6001)
        self.ftdi.set_latency_timer(1)  # Minimum latency
        print(f"[FTDI] Connected, latency: {self.ftdi.get_latency_timer()}ms")
        
    def close(self):
        if self.ftdi:
            self.ftdi.close()
            
    def calc_checksum(self, data):
        """Calculate CONSULT-II checksum"""
        return sum(data) & 0xFF
        
    def kline_wake(self):
        """
        K-Line wake-up pulse using bit-bang mode.
        Pull TX LOW for 25-70ms to wake ECU.
        """
        print("[WAKE] Generating K-line wake pulse...")
        
        # Switch to bit-bang mode
        # D0 = TXD, set as output
        from pyftdi.ftdi import Ftdi
        
        # Async bit-bang, D0 as output
        self.ftdi.set_bitmode(0x01, Ftdi.BitMode.BITBANG)
        self.ftdi.set_baudrate(9600)  # Affects bit-bang clock
        
        # Pull TX LOW (dominant) for 50ms
        self.ftdi.write_data(bytes([0x00]))  # D0 = 0
        time.sleep(0.050)  # 50ms wake pulse
        
        # Release TX HIGH (recessive)
        self.ftdi.write_data(bytes([0x01]))  # D0 = 1
        time.sleep(0.020)
        
        # Back to UART mode
        self.ftdi.set_bitmode(0x00, Ftdi.BitMode.RESET)
        time.sleep(0.100)  # Allow ECU to wake
        
        print("[WAKE] Done")
        
    def send_init(self, baudrate=10400):
        """
        Send CONSULT-II init sequence.
        Returns True if ECU responds.
        """
        print(f"[INIT] Starting at {baudrate} baud...")
        
        self.ftdi.set_baudrate(baudrate)
        self.ftdi.set_line_property(8, 1, 'N')
        self.ftdi.purge_buffers()
        time.sleep(0.100)
        
        # Init sequence from capture: 81 10 FC 81 0E
        init_bytes = [0x81, 0x10, 0xFC, 0x81, 0x0E]
        
        for b in init_bytes:
            self.ftdi.write_data(bytes([b]))
            time.sleep(0.020)  # 20ms inter-byte gap
            
            # Read echo
            time.sleep(0.030)
            resp = self.ftdi.read_data(16)
            if resp:
                print(f"  TX: {b:02X} -> RX: {' '.join(f'{x:02X}' for x in resp)}")
            else:
                print(f"  TX: {b:02X}")
                
        # Wait for ECU init response (83 FC 10 C1 ...)
        print("[INIT] Waiting for ECU response...")
        time.sleep(0.500)
        
        all_data = []
        for _ in range(10):  # Try reading multiple times
            resp = self.ftdi.read_data(64)
            if resp:
                all_data.extend(resp)
            time.sleep(0.050)
            
        if all_data:
            print(f"[INIT] Response: {' '.join(f'{b:02X}' for b in all_data)}")
            if 0x83 in all_data:
                print("[INIT] *** ECU SESSION ESTABLISHED! ***")
                self.session_active = True
                return True
        else:
            print("[INIT] No ECU response")
            
        return False
        
    def read_ecu_id(self):
        """Read ECU ID using command 0x1A"""
        if not self.session_active:
            print("[ERROR] No active session")
            return None
            
        # Frame: 02 1A 81 9D
        cmd = [0x02, 0x1A, 0x81]
        cmd.append(self.calc_checksum(cmd))
        
        print(f"[CMD] ECU ID: {' '.join(f'{b:02X}' for b in cmd)}")
        self.ftdi.write_data(bytes(cmd))
        time.sleep(0.300)
        
        resp = self.ftdi.read_data(64)
        if resp:
            print(f"[RSP] {' '.join(f'{b:02X}' for b in resp)}")
            # Look for 5A response
            if 0x5A in resp:
                idx = list(resp).index(0x5A)
                ecu_id = resp[idx+1:idx+7]
                return bytes(ecu_id).decode('ascii', errors='ignore')
        return None
        
    def read_sensor(self, addr_hi, addr_lo):
        """Read sensor data using command 0x22"""
        # Frame: 05 22 HI LO 04 01 CS
        cmd = [0x05, 0x22, addr_hi, addr_lo, 0x04, 0x01]
        cmd.append(self.calc_checksum(cmd))
        
        self.ftdi.write_data(bytes(cmd))
        time.sleep(0.200)
        
        resp = self.ftdi.read_data(64)
        if resp and 0x62 in resp:
            idx = list(resp).index(0x62)
            return list(resp[idx+3:idx+7])  # 4 bytes of sensor data
        return None


def test_with_wake():
    """Test with proper K-line wake-up"""
    print("=" * 60)
    print("CONSULT-II WITH K-LINE WAKE")
    print("=" * 60)
    
    c2 = Consult2()
    c2.connect()
    
    try:
        # Step 1: K-line wake pulse
        c2.kline_wake()
        
        # Step 2: Try init at different baudrates
        for baud in [10400, 9600, 38400]:
            print(f"\n--- Trying {baud} baud ---")
            if c2.send_init(baud):
                # Success! Try reading data
                ecu_id = c2.read_ecu_id()
                if ecu_id:
                    print(f"ECU ID: {ecu_id}")
                break
            time.sleep(0.500)
            
    finally:
        c2.close()
        

def test_without_wake():
    """Test without wake (in case ECU is already awake)"""
    print("=" * 60)
    print("CONSULT-II WITHOUT WAKE (ECU may be awake)")
    print("=" * 60)
    
    c2 = Consult2()
    c2.connect()
    
    try:
        for baud in [10400, 9600, 38400]:
            print(f"\n--- Trying {baud} baud ---")
            if c2.send_init(baud):
                ecu_id = c2.read_ecu_id()
                if ecu_id:
                    print(f"ECU ID: {ecu_id}")
                break
            time.sleep(0.500)
    finally:
        c2.close()


if __name__ == "__main__":
    print("Test 1: With K-line wake pulse")
    print()
    test_with_wake()
    
    print("\n" * 2)
    print("Test 2: Without wake (ECU may still be awake)")
    print()
    test_without_wake()
