"""
Interactive Pump Control with Live Response Monitoring
Sends commands and immediately monitors for responses
"""

import serial
import time
import threading
from datetime import datetime

PORT = 'COM9'
BAUD_RATE = 9600
PUMP_ADDRESS = 1

# Shared flag to control monitoring thread
monitoring = True
monitor_log = []

def monitor_responses(ser):
    """Background thread that continuously monitors for pump responses"""
    global monitoring, monitor_log

    print("[MONITOR] Response monitoring thread started")

    while monitoring:
        try:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]

                text = data.decode('ascii', errors='replace')
                hex_dump = ' '.join([f'{b:02X}' for b in data])

                msg = f"\n🔔 [{timestamp}] RESPONSE RECEIVED ({len(data)} bytes):\n"
                msg += f"   Text: {repr(text)}\n"
                msg += f"   Hex:  {hex_dump}\n"

                print(msg)
                monitor_log.append({
                    'timestamp': timestamp,
                    'data': data,
                    'text': text,
                    'hex': hex_dump
                })

            time.sleep(0.001)  # Check every 1ms

        except Exception as e:
            print(f"[MONITOR ERROR] {e}")
            break

    print("[MONITOR] Response monitoring thread stopped")


def send_command(ser, command):
    """Send a command to the pump"""
    full_command = f"/{PUMP_ADDRESS}{command}\r"
    cmd_bytes = full_command.encode('ascii')
    hex_dump = ' '.join([f'{b:02X}' for b in cmd_bytes])

    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]

    print(f"\n📤 [{timestamp}] Sending command:")
    print(f"   Text: {repr(full_command)}")
    print(f"   Hex:  {hex_dump}")

    ser.write(cmd_bytes)
    print(f"   ✓ Sent {len(cmd_bytes)} bytes")


def main():
    global monitoring

    print("="*70)
    print("Interactive Pump Control with Live Response Monitoring")
    print("="*70)
    print(f"Port: {PORT} | Baud: {BAUD_RATE} | Address: {PUMP_ADDRESS}")
    print("="*70)

    try:
        # Open serial connection
        ser = serial.Serial(
            port=PORT,
            baudrate=BAUD_RATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1
        )

        print(f"\n✓ Connected to {PORT}")
        time.sleep(0.1)

        # Start monitoring thread
        monitor_thread = threading.Thread(target=monitor_responses, args=(ser,), daemon=True)
        monitor_thread.start()

        # Give monitor a moment to start
        time.sleep(0.1)

        print("\n" + "="*70)
        print("Commands will be sent immediately and responses monitored in real-time")
        print("="*70)
        print("\nCommon commands:")
        print("  R       - Initialize")
        print("  ZR      - Reset")
        print("  Q       - Query status")
        print("  ?       - Request status (alternative)")
        print("  F       - Firmware version")
        print("  &       - Device info")
        print("  A0R     - Move to position 0")
        print("  A3000R  - Move to position 3000")
        print("  T       - Terminate")
        print("\nSpecial commands:")
        print("  'raw <text>' - Send raw command (e.g., 'raw /1R\\r')")
        print("  'monitor'    - Show monitoring statistics")
        print("  'clear'      - Clear monitor log")
        print("  'exit'       - Quit")
        print("="*70)

        # Interactive loop
        while True:
            try:
                user_input = input("\nCommand> ").strip()

                if not user_input:
                    continue

                if user_input.lower() == 'exit':
                    break

                elif user_input.lower() == 'monitor':
                    print(f"\n📊 Monitor Statistics:")
                    print(f"   Total responses received: {len(monitor_log)}")
                    if monitor_log:
                        print(f"   Last response: {monitor_log[-1]['timestamp']}")
                    continue

                elif user_input.lower() == 'clear':
                    monitor_log.clear()
                    print("✓ Monitor log cleared")
                    continue

                elif user_input.lower().startswith('raw '):
                    # Send raw command
                    raw_cmd = user_input[4:]
                    # Process escape sequences
                    raw_cmd = raw_cmd.replace('\\r', '\r').replace('\\n', '\n')
                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"\n📤 [{timestamp}] Sending RAW command:")
                    print(f"   Text: {repr(raw_cmd)}")
                    hex_dump = ' '.join([f'{b:02X}' for b in raw_cmd.encode('ascii')])
                    print(f"   Hex:  {hex_dump}")
                    ser.write(raw_cmd.encode('ascii'))
                    continue

                # Regular command
                send_command(ser, user_input)

                # Give a moment for response to arrive
                time.sleep(0.5)

            except KeyboardInterrupt:
                print("\n")
                break

    except serial.SerialException as e:
        print(f"\n❌ Serial port error: {e}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        monitoring = False
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("\n✓ Serial connection closed")

        print("\n" + "="*70)
        print(f"Session Summary:")
        print(f"  Commands sent: Check terminal output above")
        print(f"  Responses received: {len(monitor_log)}")
        if monitor_log:
            print(f"\n  Response Log:")
            for i, entry in enumerate(monitor_log, 1):
                print(f"    {i}. [{entry['timestamp']}] {repr(entry['text'])}")
        print("="*70)


if __name__ == "__main__":
    main()