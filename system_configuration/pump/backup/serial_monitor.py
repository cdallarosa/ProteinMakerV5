"""
Serial Monitor - Continuous monitoring of pump responses
Run this in a separate terminal while sending commands from another script
"""

import serial
import time
from datetime import datetime

PORT = 'COM8'
BAUD_RATE = 9600

print("="*60)
print("XLP6000 Serial Monitor - Continuous Reading")
print("="*60)
print(f"Port: {PORT}")
print(f"Baud Rate: {BAUD_RATE}")
print("Press Ctrl+C to stop")
print("="*60)

try:
    # Open serial connection
    ser = serial.Serial(
        port=PORT,
        baudrate=BAUD_RATE,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.1  # Short timeout to keep checking
    )

    print(f"\n✓ Connected to {PORT}")
    print("\n[MONITORING] Listening for data...\n")

    # Continuous monitoring loop
    while True:
        # Check if data is available
        if ser.in_waiting > 0:
            # Read all available data
            data = ser.read(ser.in_waiting)
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]

            # Decode and display
            try:
                text = data.decode('ascii', errors='replace')
            except:
                text = "[decode error]"

            # Create hex dump
            hex_dump = ' '.join([f'{b:02X}' for b in data])

            # Display with timestamp
            print(f"[{timestamp}] Received {len(data)} bytes:")
            print(f"  Text: {repr(text)}")
            print(f"  Hex:  {hex_dump}")
            print()

        # Small delay to prevent CPU spinning
        time.sleep(0.01)

except KeyboardInterrupt:
    print("\n\n[STOPPED] Monitor stopped by user")

except serial.SerialException as e:
    print(f"\n[ERROR] Serial port error: {e}")
    print("Make sure the pump is not open in another program")

except Exception as e:
    print(f"\n[ERROR] Unexpected error: {e}")

finally:
    if 'ser' in locals() and ser.is_open:
        ser.close()
        print("[CLOSED] Serial connection closed")