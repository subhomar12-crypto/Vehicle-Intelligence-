"""
Analyze Nisscom Executable
===========================

Extract configuration and initialization sequences from the binary.
"""

import os
import re

def extract_hex_sequences(file_path):
    """Look for byte sequences that might be initialization commands"""

    print(f"[ANALYZE] Reading: {file_path}")

    with open(file_path, 'rb') as f:
        data = f.read()

    print(f"[INFO] File size: {len(data)} bytes")

    # Look for our known command sequences
    known_sequences = [
        b'\x81',  # Init command
        b'\x10\xFC\x81',  # Handshake
        b'\x0E',  # Final handshake
        b'\x05\x22',  # Read command prefix
        b'\x02\x1A',  # ECU ID command
    ]

    print("\n[SEARCH] Looking for known command sequences...")
    for seq in known_sequences:
        positions = []
        start = 0
        while True:
            pos = data.find(seq, start)
            if pos == -1:
                break
            positions.append(pos)
            start = pos + 1

        if positions:
            print(f"\n  Found {len(positions)} occurrences of {seq.hex().upper()}:")
            for pos in positions[:5]:  # Show first 5
                # Show context (10 bytes before and after)
                context_start = max(0, pos - 10)
                context_end = min(len(data), pos + len(seq) + 10)
                context = data[context_start:context_end]
                print(f"    Offset 0x{pos:08X}: {context.hex(' ').upper()}")

    # Look for baudrate values (as 32-bit integers)
    print("\n\n[SEARCH] Looking for baudrate values...")
    baudrates = [300, 1200, 9600, 10400, 38400, 115200]

    for baud in baudrates:
        # Search as little-endian 32-bit integer
        baud_bytes = baud.to_bytes(4, 'little')
        positions = []
        start = 0
        while True:
            pos = data.find(baud_bytes, start)
            if pos == -1:
                break
            positions.append(pos)
            start = pos + 1

        if positions:
            print(f"\n  Found {len(positions)} occurrences of baudrate {baud}:")
            for pos in positions[:3]:
                context = data[max(0, pos-10):min(len(data), pos+14)]
                print(f"    Offset 0x{pos:08X}: {context.hex(' ').upper()}")

    # Look for ASCII strings related to communication
    print("\n\n[SEARCH] Looking for communication-related strings...")
    patterns = [
        b'COM[0-9]',
        b'baud',
        b'init',
        b'FTDI',
        b'serial',
        b'port',
    ]

    for pattern in patterns:
        # Find printable ASCII strings containing pattern
        matches = re.finditer(pattern, data, re.IGNORECASE)
        found = []
        for match in matches:
            pos = match.start()
            # Extract surrounding printable ASCII
            start = pos
            while start > 0 and 32 <= data[start-1] < 127:
                start -= 1
            end = pos + len(pattern)
            while end < len(data) and 32 <= data[end] < 127:
                end += 1

            string = data[start:end].decode('ascii', errors='ignore')
            if len(string) > 3:
                found.append((pos, string))

        if found:
            print(f"\n  Pattern '{pattern.decode()}' found {len(found)} times:")
            for pos, string in found[:5]:
                print(f"    0x{pos:08X}: {string}")


def analyze_dll_exports():
    """Analyze DLL exports to understand the API"""

    print("\n" + "="*70)
    print("MTS.DLL API FUNCTIONS")
    print("="*70)

    # These are from the DLL analysis
    functions = [
        ("mtsInitialize", "Initialize the MTS library/device"),
        ("mtsCleanup", "Cleanup and close connections"),
        ("mtsGetPortList", "Get list of available COM ports"),
        ("mtsSendSerial", "Send data to serial port"),
        ("mtsReadSerial", "Read data from serial port"),
        ("mtsSendSerialChar", "Send single character"),
        ("mtsReadSerialChar", "Read single character"),
        ("mtsPurgeSerialRx", "Clear receive buffer"),
        ("mtsGetSettings", "Get communication settings"),
        ("mtsIsOldSerial", "Check if old serial protocol"),
    ]

    print("\nKey functions to call in order:")
    print("  1. mtsInitialize() - Setup device")
    print("  2. mtsGetPortList() - Find COM ports")
    print("  3. Open port with specific settings")
    print("  4. mtsSendSerial() - Send commands")
    print("  5. mtsReadSerial() - Read responses")
    print("  6. mtsCleanup() - Close")

    print("\nThe magic is likely in mtsInitialize()!")
    print("This function probably:")
    print("  - Opens the COM port")
    print("  - Sets DTR/RTS for K-line init")
    print("  - Changes baudrates")
    print("  - Sends initialization commands")


def main():
    print("="*70)
    print("NISSCOM BINARY ANALYSIS")
    print("="*70)

    base_path = r"C:\Program Files (x86)\Nissan Data Scan\Nissan DataScan II 2.53"

    files_to_analyze = [
        "mts.dll",
        "NDS II 2_53.exe",
    ]

    for filename in files_to_analyze:
        filepath = os.path.join(base_path, filename)
        if os.path.exists(filepath):
            print(f"\n{'='*70}")
            print(f"ANALYZING: {filename}")
            print("="*70)
            extract_hex_sequences(filepath)
        else:
            print(f"[WARNING] File not found: {filepath}")

    # Show DLL API info
    analyze_dll_exports()

    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)
    print("\nNext step: Try calling mtsInitialize() from Python using ctypes!")


if __name__ == "__main__":
    main()
