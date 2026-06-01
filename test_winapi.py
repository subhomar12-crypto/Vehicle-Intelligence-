"""Test Windows API directly"""
import ctypes
from ctypes import wintypes
import time

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

print('Opening COM5...')
port_name = b'\\\\.\\COM5'
handle = kernel32.CreateFileA(
    port_name,
    0x80000000 | 0x40000000,  # GENERIC_READ | GENERIC_WRITE
    0,
    None,
    3,  # OPEN_EXISTING
    0,
    None
)

print(f'Handle: {handle}')

if handle != -1 and handle != 0xFFFFFFFF:
    # Try EscapeCommFunction with SETBREAK
    print('Sending BREAK...')
    result = kernel32.EscapeCommFunction(handle, 8)  # SETBREAK
    print(f'SETBREAK result: {result}')
    time.sleep(0.3)
    kernel32.EscapeCommFunction(handle, 9)  # CLRBREAK
    print('BREAK cleared')

    # Try to write
    data = b'\x02\x1A\x81\x9D'
    bytes_written = wintypes.DWORD()
    result = kernel32.WriteFile(handle, data, len(data), ctypes.byref(bytes_written), None)
    print(f'Write result: {result}, bytes: {bytes_written.value}')

    time.sleep(0.5)

    # Try to read
    buffer = ctypes.create_string_buffer(256)
    bytes_read = wintypes.DWORD()
    result = kernel32.ReadFile(handle, buffer, 256, ctypes.byref(bytes_read), None)
    print(f'Read result: {result}, bytes: {bytes_read.value}')

    if bytes_read.value > 0:
        resp = list(buffer.raw[:bytes_read.value])
        print(f'Data: {" ".join([f"{b:02X}" for b in resp])}')

    kernel32.CloseHandle(handle)
else:
    print(f'Error opening port: {ctypes.get_last_error()}')

print('Done')
