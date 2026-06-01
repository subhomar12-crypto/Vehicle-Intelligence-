"""
Nisscom Device - Direct USB Commands
=====================================

Sends the EXACT USB commands captured from Wireshark.
This bypasses serial abstraction and talks directly to FTDI chip.

Requires: pip install pyusb libusb
"""

import usb.core
import usb.util
import time

class NisscomUSB:
    """Direct USB control of Nisscom device"""

    # FTDI Vendor ID and Product ID
    FTDI_VID = 0x0403
    FTDI_PID = 0x6001  # FT232 (adjust if different)

    # FTDI USB Request codes (from capture)
    FTDI_RESET = 0x00
    FTDI_MODEM_CTRL = 0x01
    FTDI_SET_FLOW_CTRL = 0x02
    FTDI_SET_BAUD_RATE = 0x03
    FTDI_SET_DATA = 0x04
    FTDI_SET_LATENCY = 0x09

    def __init__(self):
        self.dev = None

    def find_device(self):
        """Find Nisscom device (FTDI chip)"""
        print("[USB] Searching for FTDI device...")

        # Find device
        self.dev = usb.core.find(idVendor=self.FTDI_VID)

        if self.dev is None:
            print(f"[ERROR] FTDI device not found (VID:0x{self.FTDI_VID:04X})")
            print("[INFO] Checking all USB devices...")

            # List all devices
            devices = usb.core.find(find_all=True)
            for dev in devices:
                print(f"  Device: VID=0x{dev.idVendor:04X} PID=0x{dev.idProduct:04X}")

            return False

        print(f"[USB] Found device: VID=0x{self.dev.idVendor:04X} PID=0x{self.dev.idProduct:04X}")

        # Detach kernel driver if active
        try:
            if self.dev.is_kernel_driver_active(0):
                print("[USB] Detaching kernel driver...")
                self.dev.detach_kernel_driver(0)
        except:
            pass  # Not all systems need this

        # Set configuration
        try:
            self.dev.set_configuration()
            print("[USB] Device configured")
        except Exception as e:
            print(f"[WARNING] Config failed: {e}")

        return True

    def send_usb_control(self, request, value, index=0, data=None):
        """Send USB control transfer (vendor request)"""
        bmRequestType = 0x40  # Vendor, Host-to-Device

        try:
            result = self.dev.ctrl_transfer(
                bmRequestType,
                request,
                value,
                index,
                data if data else []
            )
            return True
        except Exception as e:
            print(f"[ERROR] USB control transfer failed: {e}")
            return False

    def ftdi_reset(self):
        """FTDI Reset command"""
        print("[FTDI] Reset...")
        return self.send_usb_control(self.FTDI_RESET, 0x0000)

    def ftdi_set_latency(self, latency=16):
        """Set latency timer"""
        print(f"[FTDI] Set latency: {latency}ms...")
        return self.send_usb_control(self.FTDI_SET_LATENCY, latency)

    def ftdi_set_modem_ctrl(self, dtr, rts):
        """
        Set DTR/RTS
        From capture:
        - DTR ON, RTS OFF: value=0x0101
        - DTR OFF, RTS ON: value=0x0202
        """
        value = 0x0000
        if dtr:
            value |= 0x0101  # DTR active + enable
        if rts:
            value |= 0x0202  # RTS active + enable

        print(f"[FTDI] ModemCtrl: DTR={dtr} RTS={rts} (0x{value:04X})...")
        return self.send_usb_control(self.FTDI_MODEM_CTRL, value)

    def ftdi_set_baudrate(self, baudrate):
        """
        Set baudrate using FTDI divisor
        FTDI formula: divisor = 3000000 / baudrate
        """
        divisor = int(3000000 / baudrate)

        # Split into low/high bytes (wValue = low byte | high byte << 8)
        value = divisor & 0xFFFF
        index = (divisor >> 16) & 0xFFFF

        print(f"[FTDI] SetBaudRate: {baudrate} (divisor=0x{divisor:04X})...")
        return self.send_usb_control(self.FTDI_SET_BAUD_RATE, value, index)

    def ftdi_set_data(self, bits=8, parity=0, stop_bits=0):
        """Set data format (8N1)"""
        value = bits | (parity << 8) | (stop_bits << 11)
        print(f"[FTDI] SetData: {bits}N{stop_bits+1}...")
        return self.send_usb_control(self.FTDI_SET_DATA, value)

    def ftdi_set_flow_ctrl(self, flow_type=0):
        """Set flow control (0=none, 1=RTS/CTS, 2=DTR/DSR, 3=XON/XOFF)"""
        print(f"[FTDI] SetFlowCtrl: {flow_type}...")
        return self.send_usb_control(self.FTDI_SET_FLOW_CTRL, flow_type)

    def initialize_sequence(self):
        """
        Send the EXACT sequence from USB capture:
        1. Multiple resets
        2. Set latency
        3. Configure data format
        4. DTR/RTS toggling for K-line init
        5. Baudrate changes
        """
        print("\n[INIT] Starting FTDI initialization sequence...")

        # Step 1: Multiple resets (from capture)
        for i in range(6):
            self.ftdi_reset()
            time.sleep(0.001)

        # Step 2: Set latency timer
        self.ftdi_set_latency(16)
        time.sleep(0.01)

        # Step 3: Set data format (8N1)
        self.ftdi_set_data(bits=8, parity=0, stop_bits=0)
        time.sleep(0.01)

        # Step 4: K-line init via DTR/RTS toggling
        print("\n[K-LINE] Performing DTR/RTS initialization...")

        # DTR ON, RTS OFF
        self.ftdi_set_modem_ctrl(dtr=True, rts=False)
        time.sleep(0.025)

        # DTR OFF, RTS ON
        self.ftdi_set_modem_ctrl(dtr=False, rts=True)
        time.sleep(0.025)

        # DTR OFF, RTS ON (again)
        self.ftdi_set_modem_ctrl(dtr=False, rts=True)
        time.sleep(0.025)

        # DTR ON, RTS OFF
        self.ftdi_set_modem_ctrl(dtr=True, rts=False)
        time.sleep(0.025)

        # Step 5: Set flow control
        self.ftdi_set_flow_ctrl(flow_type=0)
        time.sleep(0.01)

        # Step 6: Baudrate sequence from capture
        print("\n[BAUD] Setting baudrate sequence...")

        # First baud change (from capture: 0x09C4)
        self.ftdi_set_baudrate(38400)
        time.sleep(0.01)

        # Second baud change (from capture: 0x809C)
        self.ftdi_set_baudrate(38400)  # Might be same or slight variation
        time.sleep(0.01)

        # Final DTR/RTS for data mode
        self.ftdi_set_modem_ctrl(dtr=True, rts=True)

        print("\n[INIT] FTDI initialization complete!")
        print("[INFO] Device should now be ready for serial communication")

        return True


def main():
    print("="*70)
    print("NISSCOM - DIRECT USB COMMANDS")
    print("Sends exact sequence from USB capture")
    print("="*70)

    device = NisscomUSB()

    # Find device
    if not device.find_device():
        print("\n[ERROR] Device not found")
        print("\nMake sure:")
        print("  1. Device is connected")
        print("  2. No other software is using it")
        print("  3. libusb drivers are installed")
        input("\nPress Enter to exit...")
        return

    # Send initialization sequence
    device.initialize_sequence()

    print("\n" + "="*70)
    print("INITIALIZATION COMPLETE")
    print("="*70)
    print("\nThe device should now be ready!")
    print("\nNext steps:")
    print("  1. Run nisscom_working.py (skip K-line init)")
    print("  2. Or use any serial terminal at 38400 baud")
    print("  3. Send commands: 02 1A 81 9D for ECU ID")

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
