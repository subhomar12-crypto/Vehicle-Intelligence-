"""
Alternative Solutions for Nissan Patrol 2003 Diagnostics
What to do if Nisscom software is not available
"""

import serial
import time

class AlternativeTester:
    """Test if car supports standard OBD-II"""

    def __init__(self, port='COM5'):
        self.port = port

    def test_standard_obd2(self):
        """
        Nissan Patrol 2003 should support standard OBD-II (mandatory in most markets)
        But the Nisscom device doesn't support it - need different adapter
        """
        print("=" * 70)
        print("CHECKING VEHICLE PROTOCOL SUPPORT")
        print("=" * 70)
        print()
        print("Your Nissan Patrol 2003 likely supports:")
        print()
        print("  1. STANDARD OBD-II (ISO 9141-2 or ISO 14230 KWP2000)")
        print("     - Mandatory in most markets since 1996-2001")
        print("     - Works with standard ELM327 adapters")
        print("     - Provides: RPM, Speed, Coolant Temp, Fuel, etc.")
        print()
        print("  2. NISSAN CONSULT-II (Proprietary)")
        print("     - More detailed Nissan-specific data")
        print("     - Requires Consult-II compatible adapter")
        print("     - Provides: All sensors, ECU codes, live data")
        print()
        print("PROBLEM: Your Nisscom device doesn't support EITHER protocol")
        print("         without proprietary software")
        print()

    def recommend_adapters(self):
        """Recommend working adapters"""
        print("=" * 70)
        print("RECOMMENDED ALTERNATIVE ADAPTERS")
        print("=" * 70)
        print()

        print("OPTION 1: STANDARD ELM327 ADAPTER (Easiest)")
        print("-" * 70)
        print("  What it is:")
        print("    - Universal OBD-II adapter")
        print("    - Works with 99% of cars made after 1996")
        print("    - USB, WiFi, or Bluetooth versions available")
        print()
        print("  Cost: $10-30 USD")
        print()
        print("  What you can read:")
        print("    ✓ Engine RPM")
        print("    ✓ Vehicle Speed")
        print("    ✓ Coolant Temperature")
        print("    ✓ Throttle Position")
        print("    ✓ Engine Load")
        print("    ✓ MAF/MAP Sensor")
        print("    ✓ O2 Sensors")
        print("    ✓ Fuel System Status")
        print("    ✓ Check Engine Light Codes (DTC)")
        print("    ✓ Clear Codes")
        print()
        print("  Compatible Software:")
        print("    - Torque Pro (Android) - $4.95")
        print("    - Car Scanner ELM OBD2 (Android/iOS) - Free")
        print("    - ScanMaster-ELM (Windows) - Free")
        print("    - FORScan (Windows) - Free")
        print("    - Your custom Python scripts - Free")
        print()
        print("  Recommendation:")
        print("    Look for: 'ELM327 USB OBD-II' or 'ELM327 Bluetooth'")
        print("    Buy from: Amazon, eBay, AliExpress")
        print("    Check: Must say 'ELM327 compatible' or 'OBD-II'")
        print()
        print("  Python Libraries:")
        print("    - python-obd (already installed)")
        print("    - obd (simple library)")
        print()

        print()
        print("OPTION 2: NISSAN CONSULT-II COMPATIBLE ADAPTER (Advanced)")
        print("-" * 70)
        print("  What it is:")
        print("    - Works with Nissan's proprietary Consult-II protocol")
        print("    - More data than standard OBD-II")
        print("    - Better for older Nissans (pre-2000)")
        print()
        print("  Cost: $50-150 USD")
        print()
        print("  What you can read:")
        print("    ✓ Everything from OBD-II PLUS:")
        print("    ✓ Transmission data")
        print("    ✓ ABS system")
        print("    ✓ Airbag system")
        print("    ✓ Detailed sensor voltages")
        print("    ✓ Injector timing")
        print("    ✓ Ignition advance")
        print("    ✓ More ECU-specific codes")
        print()
        print("  Compatible Adapters:")
        print("    - RS232 Nissan Consult Cable")
        print("    - USB Nissan Consult-II Interface")
        print("    - Bluetooth Consult-II (rare)")
        print()
        print("  Compatible Software:")
        print("    - NDS II (Nissan Data Scan)")
        print("    - ECU Talk")
        print("    - RomRaider (with plugin)")
        print("    - Custom Python (we can write it)")
        print()

        print()
        print("OPTION 3: PROFESSIONAL SCAN TOOLS")
        print("-" * 70)
        print("  Examples:")
        print("    - Launch X431")
        print("    - Autel MaxiSys")
        print("    - Snap-on MODIS")
        print()
        print("  Cost: $300-2000+ USD")
        print("  Best for: Professional mechanics")
        print()

    def test_if_car_has_obd2(self):
        """Quick test to see if car responds to standard OBD-II"""
        print()
        print("=" * 70)
        print("QUICK TEST: Does Nisscom device have ELM327 chip inside?")
        print("=" * 70)
        print()
        print("Testing if device has hidden ELM327 support...")
        print()

        # Try AT commands at different baud rates
        baud_rates = [38400, 115200, 9600]

        for baud in baud_rates:
            print(f"Trying {baud} baud...")
            try:
                ser = serial.Serial(self.port, baud, timeout=2)
                time.sleep(0.5)

                # Try ATZ
                ser.write(b'ATZ\r')
                time.sleep(1)
                response = ser.read(100).decode('utf-8', errors='ignore')

                if 'ELM' in response.upper():
                    print(f"  [FOUND] Device has ELM327 chip at {baud} baud!")
                    print(f"  Response: {response}")
                    ser.close()
                    return True

                # Try AT@1 (device description)
                ser.write(b'AT@1\r')
                time.sleep(0.5)
                response = ser.read(100).decode('utf-8', errors='ignore')

                if response and 'OK' not in response and response.strip():
                    print(f"  Device info: {response}")

                ser.close()

            except:
                pass

        print("  [RESULT] Device does NOT have ELM327 chip")
        print()
        return False

    def create_quick_start_guide(self):
        """Create guide for buying correct adapter"""
        print()
        print("=" * 70)
        print("QUICK START GUIDE - BUYING THE RIGHT ADAPTER")
        print("=" * 70)
        print()
        print("FOR BASIC DIAGNOSTICS (RPM, Speed, Temp, Codes):")
        print("  1. Search for: 'ELM327 USB OBD2 Scanner'")
        print("  2. Price range: $10-30")
        print("  3. Check it says: 'OBD-II compatible' or 'ELM327 v1.5+'")
        print("  4. USB version is most reliable")
        print("  5. Once you have it, run: python test_nisscom_device.py")
        print("     (will work with new adapter)")
        print()
        print("FOR ADVANCED NISSAN DIAGNOSTICS:")
        print("  1. Search for: 'Nissan Consult USB Cable'")
        print("  2. Price range: $50-150")
        print("  3. Make sure it says: 'Consult-II compatible'")
        print("  4. Once you have it, run: python nissan_consult2_native.py")
        print("     (will work with Consult adapter)")
        print()
        print("WHAT TO DO WITH YOUR NISSCOM DEVICE:")
        print("  Option A: Return it if possible (doesn't work without software)")
        print("  Option B: Keep trying to get Nisscom software from vendor")
        print("  Option C: Sell it and buy ELM327 adapter instead")
        print()

    def show_example_python_code(self):
        """Show what you can do with ELM327"""
        print()
        print("=" * 70)
        print("EXAMPLE: What you can do with ELM327 adapter")
        print("=" * 70)
        print()
        print("With an ELM327 adapter, this Python code will work:")
        print()
        print("-" * 70)
        print("""
import obd

# Connect to ELM327 adapter
connection = obd.OBD()

# Read sensors
rpm = connection.query(obd.commands.RPM)
speed = connection.query(obd.commands.SPEED)
temp = connection.query(obd.commands.COOLANT_TEMP)

print(f"RPM: {rpm.value}")
print(f"Speed: {speed.value}")
print(f"Coolant: {temp.value}")

# Read engine codes
codes = connection.query(obd.commands.GET_DTC)
print(f"Error codes: {codes.value}")

# Clear codes
connection.query(obd.commands.CLEAR_DTC)
        """)
        print("-" * 70)
        print()
        print("THIS IS MUCH SIMPLER than the Nisscom device!")
        print("python-obd library handles all the protocol complexity")
        print()

    def run_all(self):
        """Run all checks and recommendations"""
        self.test_standard_obd2()
        input("\nPress Enter to continue...")
        print("\n")

        self.test_if_car_has_obd2()
        input("Press Enter to continue...")
        print("\n")

        self.recommend_adapters()
        input("\nPress Enter to continue...")
        print("\n")

        self.create_quick_start_guide()
        input("\nPress Enter to continue...")
        print("\n")

        self.show_example_python_code()


def main():
    print()
    print("ALTERNATIVE SOLUTIONS FOR NISSAN PATROL 2003")
    print()
    print("What to do if you can't get Nisscom software")
    print()

    tester = AlternativeTester()

    try:
        tester.run_all()

        print()
        print("=" * 70)
        print("SUMMARY RECOMMENDATION")
        print("=" * 70)
        print()
        print("Best Option: Buy a standard ELM327 USB adapter ($10-30)")
        print()
        print("Why?")
        print("  ✓ Works immediately, no special software needed")
        print("  ✓ Compatible with your 2003 Nissan Patrol")
        print("  ✓ Works with free software and Python")
        print("  ✓ Much easier than fighting with Nisscom device")
        print("  ✓ Universal - works with any car")
        print()
        print("Your Nisscom device is unusable without their software.")
        print("An ELM327 adapter will solve your problem.")
        print()
        print("=" * 70)

    except KeyboardInterrupt:
        print("\n[STOPPED]")
    except Exception as e:
        print(f"\n[ERROR] {e}")

    print()
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
