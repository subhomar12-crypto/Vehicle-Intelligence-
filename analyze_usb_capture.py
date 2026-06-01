"""
Analyze USB Capture for Nisscom Commands
=========================================

Parse the pcapng file to extract FTDI commands
"""

import subprocess
import re

def analyze_capture(pcap_file):
    """Analyze USB capture for FTDI commands"""

    print("="*70)
    print("ANALYZING USB CAPTURE FOR NISSCOM ACTIVATION COMMANDS")
    print("="*70)

    # Get all FTDI packets
    cmd = [
        r"C:\Program Files\Wireshark\tshark.exe",
        "-r", pcap_file,
        "-Y", "ftdi-ft",
        "-T", "json"
    ]

    print("\n[STEP 1] Extracting FTDI packets from capture...")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"[ERROR] tshark failed: {result.stderr}")

            # Fallback: Try basic USB analysis
            print("\n[FALLBACK] Trying basic USB packet analysis...")
            analyze_basic_usb(pcap_file)
            return

        output = result.stdout

        if not output or output.strip() == "[]":
            print("[INFO] No FTDI-specific packets found")
            print("[INFO] Trying to find USB bulk transfers...")
            analyze_bulk_transfers(pcap_file)
            return

        # Parse JSON output
        import json
        packets = json.loads(output)

        print(f"[FOUND] {len(packets)} FTDI packets\n")

        # Analyze each packet
        for i, packet in enumerate(packets[:20]):  # First 20
            print(f"\n--- Packet {i+1} ---")

            # Extract layers
            layers = packet.get('_source', {}).get('layers', {})

            # Frame info
            frame = layers.get('frame', {})
            print(f"Frame: {frame.get('frame.number', 'N/A')}")
            print(f"Time: {frame.get('frame.time_relative', 'N/A')}")

            # USB info
            usb = layers.get('usb', {})
            print(f"USB: {usb}")

            # FTDI info
            ftdi = layers.get('ftdi-ft', {})
            print(f"FTDI: {ftdi}")

    except FileNotFoundError:
        print("[ERROR] tshark not found. Make sure Wireshark is installed.")
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()


def analyze_basic_usb(pcap_file):
    """Basic USB packet analysis"""

    print("\n"+"="*70)
    print("BASIC USB ANALYSIS")
    print("="*70)

    # Get packets around the time Nisscom software starts
    cmd = [
        r"C:\Program Files\Wireshark\tshark.exe",
        "-r", pcap_file,
        "-c", "200",  # First 200 packets
        "-T", "fields",
        "-e", "frame.number",
        "-e", "frame.time_relative",
        "-e", "usb.src",
        "-e", "usb.dst",
        "-e", "frame.len"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print("\nPacket List (first 200):")
        print(result.stdout[:2000])  # First 2000 chars

    # Try to get URB type info
    print("\n\nLooking for URB Control packets...")
    cmd = [
        r"C:\Program Files\Wireshark\tshark.exe",
        "-r", pcap_file,
        "-Y", "usb",
        "-T", "text"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        # Search for interesting patterns
        lines = result.stdout.split('\n')

        print("\nInteresting USB transactions:")
        for line in lines[:100]:
            if 'FTDI' in line or 'SET' in line or 'Modem' in line or 'Baud' in line:
                print(line)


def analyze_bulk_transfers(pcap_file):
    """Analyze USB bulk data transfers"""

    print("\n"+"="*70)
    print("USB BULK DATA TRANSFERS")
    print("="*70)

    print("\nLooking for actual data sent/received...")

    cmd = [
        r"C:\Program Files\Wireshark\tshark.exe",
        "-r", pcap_file,
        "-Y", "usb.data_len > 0",
        "-T", "fields",
        "-e", "frame.number",
        "-e", "usb.data_len",
        "-e", "usb.capdata"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

    if result.returncode == 0:
        lines = result.stdout.strip().split('\n')

        print(f"\nFound {len(lines)} packets with data\n")
        print("First 30 data packets:")
        print("-" * 70)

        for i, line in enumerate(lines[:30]):
            parts = line.split('\t')
            if len(parts) >= 3:
                frame_num = parts[0]
                data_len = parts[1]
                data_hex = parts[2] if len(parts) > 2 else ""

                print(f"{frame_num:>5}: Len={data_len:>3} Data: {data_hex}")


def extract_commands(pcap_file):
    """Try to extract the exact command sequence"""

    print("\n"+"="*70)
    print("EXTRACTING COMMAND SEQUENCE")
    print("="*70)

    # Look for data in chronological order
    cmd = [
        r"C:\Program Files\Wireshark\tshark.exe",
        "-r", pcap_file,
        "-Y", "usb.capdata",
        "-T", "fields",
        "-e", "frame.time_relative",
        "-e", "usb.src",
        "-e", "usb.capdata"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

    if result.returncode == 0:
        lines = result.stdout.strip().split('\n')

        print(f"\nChronological data flow:\n")

        for line in lines[:50]:  # First 50
            parts = line.split('\t')
            if len(parts) >= 3:
                time = parts[0]
                src = parts[1]
                data = parts[2]

                direction = "PC->DEV" if "host" in src else "DEV->PC"
                print(f"[{time:>8}s] {direction:>9} {data}")


def main():
    pcap_file = r"C:\D Drive\Predict\nisscom_usb_capture.pcapng"

    print(f"\nAnalyzing: {pcap_file}\n")

    # Try multiple analysis methods
    analyze_capture(pcap_file)

    print("\n" + "="*70)
    print("Extracting chronological commands...")
    print("="*70)
    extract_commands(pcap_file)

    print("\n\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)
    print("\nLook for:")
    print("  1. Commands sent BEFORE the serial data starts")
    print("  2. Modem control or baud rate settings")
    print("  3. Vendor-specific control requests")
    print("  4. Any unusual USB setup packets")

    input("\nPress Enter to continue...")


if __name__ == "__main__":
    main()
