"""
Experiment 4: USB Device Inspection
====================================

Check if the device has multiple endpoints or special USB features.
Maybe we need to talk to a different endpoint!
"""

try:
    import usb.core
    import usb.util
    USB_AVAILABLE = True
except:
    USB_AVAILABLE = False
    print("[WARNING] pyusb not installed. Install with: pip install pyusb")


def inspect_usb_device():
    """Inspect USB device structure"""
    if not USB_AVAILABLE:
        print("[ERROR] pyusb not available")
        return

    print("="*70)
    print("USB DEVICE INSPECTION")
    print("="*70)

    # Find FTDI device
    print("\n[SEARCH] Looking for FTDI device (VID:0x0403)...")
    dev = usb.core.find(idVendor=0x0403)

    if dev is None:
        print("[ERROR] FTDI device not found")
        print("\n[INFO] Listing all USB devices:")

        for device in usb.core.find(find_all=True):
            print(f"  VID:0x{device.idVendor:04X} PID:0x{device.idProduct:04X}")

        return

    print(f"\n[FOUND] Device:")
    print(f"  VID: 0x{dev.idVendor:04X}")
    print(f"  PID: 0x{dev.idProduct:04X}")
    print(f"  Manufacturer: {usb.util.get_string(dev, dev.iManufacturer)}")
    print(f"  Product: {usb.util.get_string(dev, dev.iProduct)}")
    print(f"  Serial: {usb.util.get_string(dev, dev.iSerialNumber)}")

    print(f"\n[CONFIG] Configurations: {dev.bNumConfigurations}")

    # Iterate through configurations
    for cfg in dev:
        print(f"\n  Configuration {cfg.bConfigurationValue}:")
        print(f"    Interfaces: {cfg.bNumInterfaces}")

        for intf in cfg:
            print(f"\n    Interface {intf.bInterfaceNumber}:")
            print(f"      Class: {intf.bInterfaceClass}")
            print(f"      SubClass: {intf.bInterfaceSubClass}")
            print(f"      Protocol: {intf.bInterfaceProtocol}")
            print(f"      Endpoints: {intf.bNumEndpoints}")

            for ep in intf:
                print(f"\n      Endpoint 0x{ep.bEndpointAddress:02X}:")
                print(f"        Type: {usb.util.endpoint_type(ep.bmAttributes)}")
                print(f"        Direction: {'IN' if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN else 'OUT'}")
                print(f"        Max Packet Size: {ep.wMaxPacketSize}")

    print("\n" + "="*70)


def check_multiple_interfaces():
    """Check if device has multiple serial interfaces"""
    import serial.tools.list_ports

    print("\n" + "="*70)
    print("CHECKING FOR MULTIPLE INTERFACES")
    print("="*70)

    ports = list(serial.tools.list_ports.comports())

    ftdi_ports = [p for p in ports if 'FTDI' in p.description or 'USB Serial' in p.description]

    print(f"\n[FOUND] {len(ftdi_ports)} FTDI/USB Serial ports:")

    for port in ftdi_ports:
        print(f"\n  {port.device}:")
        print(f"    Description: {port.description}")
        print(f"    HWID: {port.hwid}")

        # Try to parse interface number from HWID
        if 'MI_' in port.hwid:
            import re
            match = re.search(r'MI_(\d+)', port.hwid)
            if match:
                interface = match.group(1)
                print(f"    Interface: {interface}")


def main():
    # USB device inspection
    if USB_AVAILABLE:
        inspect_usb_device()

    # Check for multiple interfaces
    check_multiple_interfaces()

    print("\n[INFO] If device has multiple endpoints/interfaces,")
    print("       we might need to use a different one!")

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
