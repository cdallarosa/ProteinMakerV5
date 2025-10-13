"""
Simple Status Polling Test Script
Tests the status polling functionality with detailed debugging output
"""

from ..pump_commands import PumpCommands
import time

pump = PumpCommands()

# Connect to pump
print("=" * 60)
print("STATUS POLLING TEST")
print("=" * 60)
print(f"Connecting to {pump.port}...")
connected = pump.connect()
if not connected:
    print("Failed to connect. Exiting.")
    exit(1)

print(f"✓ Connected to {pump.port}\n")

# Test 1: Query status while idle
print("=" * 60)
print("TEST 1: Status Query While Idle")
print("=" * 60)
status = pump.get_parsed_status()
print(f"Raw response: {repr(status.get('raw'))}")
print(f"Cleaned response: {status.get('cleaned')}")
print(f"Is busy: {status.get('is_busy')}")
print(f"Is idle: {status.get('is_idle')}")
print(f"Position: {status.get('position')}")
if status.get('error'):
    print(f"Error: {status.get('error')}")
print()

# Test 2: Initialize and wait
print("=" * 60)
print("TEST 2: Initialize and Wait for Ready")
print("=" * 60)
print("Initializing pump...")
success = pump.initialize_pump(wait=True, timeout=30)
if success:
    print("✓ Initialization complete\n")
else:
    print("✗ Initialization failed or timed out\n")

# Test 3: Status query after initialization
print("=" * 60)
print("TEST 3: Status Query After Initialization")
print("=" * 60)
status = pump.get_parsed_status()
print(f"Raw response: {repr(status.get('raw'))}")
print(f"Cleaned response: {status.get('cleaned')}")
print(f"Is busy: {status.get('is_busy')}")
print(f"Is idle: {status.get('is_idle')}")
print(f"Position: {status.get('position')}")
if status.get('error'):
    print(f"Error: {status.get('error')}")
print()

# Test 4: Start a short move and monitor status
print("=" * 60)
print("TEST 4: Monitor Status During Move")
print("=" * 60)
print("Starting move to position 1000...")
pump.move_syringe_absolute(1000, wait=False)
time.sleep(0.2)

print("\nPolling status every 0.5 seconds:")
for i in range(20):
    status = pump.get_parsed_status()
    print(f"  Poll {i+1:2d}: cleaned='{status.get('cleaned')}' | "
          f"idle={status.get('is_idle')} | busy={status.get('is_busy')} | "
          f"pos={status.get('position')}")

    if status.get('is_idle'):
        print(f"  --> Pump became idle after {i+1} polls")
        break

    time.sleep(0.5)
else:
    print("  --> Pump still busy after 20 polls (10 seconds)")

print()

# Test 5: Test wait_until_ready
print("=" * 60)
print("TEST 5: Test wait_until_ready() Method")
print("=" * 60)
print("Starting move to position 3000...")
pump.move_syringe_absolute(3000, wait=False)
time.sleep(0.2)

print("Calling wait_until_ready(timeout=30, poll_interval=0.5)...")
start = time.time()
ready = pump.wait_until_ready(timeout=30, poll_interval=0.5)
elapsed = time.time() - start

if ready:
    print(f"✓ Pump ready after {elapsed:.2f} seconds")
else:
    print(f"✗ Timeout after {elapsed:.2f} seconds")

print()

# Test 6: Command history
print("=" * 60)
print("TEST 6: Command History")
print("=" * 60)
history = pump.get_command_history()
print(f"Total commands sent: {len(history)}")
print("\nLast 5 commands:")
for cmd in history[-5:]:
    print(f"  [{cmd['timestamp']}] {cmd['command']}")

print()

# Summary
print("=" * 60)
print("TEST SUMMARY")
print("=" * 60)
print(f"Connection: {'OK' if pump.is_connected else 'FAILED'}")
print(f"Commands sent: {len(pump.get_command_history())}")
print(f"Errors: {len(pump.errors)}")
if pump.errors:
    print("\nErrors:")
    for error in pump.errors:
        print(f"  - {error}")

print("\n" + "=" * 60)
print("If you see 'Unknown status format' errors, the pump may be")
print("using a different status response format. Check the cleaned")
print("response strings above to identify the actual format.")
print("=" * 60)
