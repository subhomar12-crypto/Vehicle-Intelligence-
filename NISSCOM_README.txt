================================================================================
NISSCOM DIAGNOSTIC DEVICE - QUICK START GUIDE
================================================================================

Device: Nisscom USB Diagnostic Adapter
Vehicle: Nissan Patrol 2003
Port: COM5
Date: 2026-01-25

================================================================================
IMPORTANT FINDINGS
================================================================================

After extensive testing, your Nisscom device requires PROPRIETARY SOFTWARE
from Nisscom to function. It does NOT work with:
  - Standard OBD-II protocols
  - ELM327 commands
  - Open-source Consult-II protocols
  - Free diagnostic software (NDS II, ECU Talk, DDLReader)

The device echoes all commands back but doesn't process them without
Nisscom's official software.

================================================================================
WHAT WAS TESTED (ALL FAILED)
================================================================================

✗ OBD-II/ELM327 protocol
✗ Consult-II protocol at 9600 baud (correct standard)
✗ Consult-II protocol at 38400 baud
✗ Alternative initialization sequences
✗ Different baud rates (9600, 19200, 38400, 57600, 115200)
✗ Hardware flow control variations
✗ RTS/DTR line control
✗ Free software alternatives

================================================================================
NEXT STEPS
================================================================================

STEP 1: GET NISSCOM SOFTWARE
  Contact your device vendor or Nisscom directly to get official software:
    - Request software download link
    - Check if device came with installation CD/DVD
    - Ask for technical support

STEP 2: USE PROTOCOL SNIFFER (When you have software)
  1. Open command prompt
  2. Run: cd "C:\D Drive\Predict"
  3. Run: python nisscom_helper.py
  4. Select option 2 (Protocol Sniffer)
  5. Follow instructions to capture protocol
  6. Send captured logs for custom implementation

STEP 3: CUSTOM IMPLEMENTATION (After capture)
  Once we have captured logs, we can:
    - Reverse engineer the protocol
    - Create Python implementation
    - Build custom diagnostic software

================================================================================
QUICK START - RUN THE HELPER
================================================================================

To access all tools and options:

  cd "C:\D Drive\Predict"
  python nisscom_helper.py

The helper menu provides:
  [1] Read detailed analysis report
  [2] Run protocol sniffer (when software available)
  [3] Re-test device
  [4] View all test scripts
  [5] Check captured logs

================================================================================
FILES CREATED
================================================================================

Test Scripts (9 files):
  test_nisscom_device.py           - OBD-II test
  test_nisscom_basic.py            - Basic serial test
  test_elm327_mode.py              - ELM327 test
  consult2_reader.py               - Consult-II reader
  consult2_live_monitor.py         - Live monitoring
  consult2_calibrate.py            - Register scanner
  nissan_consult2_native.py        - Native Consult-II
  nissan_consult2_alternative.py   - Alternative methods
  nisscom_hardware_test.py         - Hardware tests

Tools (1 file):
  nisscom_protocol_sniffer.py      - Protocol capture tool ⭐

Helper (1 file):
  nisscom_helper.py                - Central menu tool ⭐

Documentation (3 files):
  NISSCOM_DEVICE_ANALYSIS.md       - Detailed analysis
  NISSCOM_README.txt               - This file
  serial_port_sniffer.py           - Alternative sniffer

================================================================================
ALTERNATIVE SOLUTION
================================================================================

If you cannot get Nisscom software, consider purchasing a different adapter:

  Option A: Standard ELM327 Adapter
    - Works with any OBD-II software
    - Wide compatibility
    - Cheaper alternatives available

  Option B: Official Nissan Consult-II Adapter
    - Native Nissan protocol support
    - Better compatibility with older Nissans
    - Works with open-source software

================================================================================
TECHNICAL SUMMARY
================================================================================

Device Behavior:
  ✓ Properly detected on COM5
  ✓ Serial communication functional
  ✓ Echoes all commands at all baud rates
  ✗ Does not process any standard protocols
  ✗ Requires proprietary initialization

Protocol Tests:
  - OBD-II: Failed (not ELM327 compatible)
  - Consult-II 9600: Failed (echoes FF FF EF)
  - Consult-II 38400: Failed (echoes commands)
  - Alternative sequences: All failed
  - Hardware flow control: No effect

Conclusion:
  Device is a passthrough adapter that MUST have Nisscom's software
  to initialize and communicate with vehicle ECU.

================================================================================
SUPPORT
================================================================================

For Nisscom Software:
  - Contact device vendor/seller
  - Request official software download
  - Ask for technical documentation

For Custom Implementation:
  - First, capture protocol with sniffer
  - Save logs from C:\D Drive\Predict\nisscom_logs\
  - Share logs for Python implementation

================================================================================
