"""Quick script to check available COM ports"""
import serial.tools.list_ports

print("=" * 60)
print("AVAILABLE COM PORTS")
print("=" * 60)

ports = list(serial.tools.list_ports.comports())

if not ports:
    print("No COM ports found!")
else:
    for port in ports:
        print(f"\nPort: {port.device}")
        print(f"  Description: {port.description}")
        print(f"  Manufacturer: {port.manufacturer}")

        # Highlight virtual and real ports
        if "com0com" in port.description.lower() or "virtual" in port.description.lower():
            print("  >>> VIRTUAL PORT (use for bridge)")
        elif "USB" in port.description or "Serial" in port.description:
            print("  >>> REAL PORT")

print("\n" + "=" * 60)
print(f"Total ports found: {len(ports)}")
print("=" * 60)
