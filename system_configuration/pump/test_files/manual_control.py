"""
XLP6000 Pump Manual Control Script with Status Polling Demonstrations

This script demonstrates various ways to use the new status polling features:
1. Blocking wait (wait=True) - simplest for sequential operations
2. Manual polling (wait_until_ready()) - for custom timeout/interval
3. Status checking (is_pump_ready()) - for conditional logic
4. Parsed status (get_parsed_status()) - for detailed status info
"""

from ..pump_commands import PumpCommands
import time

pump = PumpCommands()

# Connect to pump
print("=" * 60)
print("CONNECTING TO PUMP")
print("=" * 60)
connected = pump.connect()
if not connected:
    print("Failed to connect. Exiting.")
    exit(1)

print(f"\nConnection status: {pump.is_connected}")
print(f"Serial port open: {pump.serial_connection.is_open if pump.serial_connection else 'N/A'}")
time.sleep(1)

# ============================================================================
# METHOD 1: Blocking Wait (wait=True) - Simplest Approach
# ============================================================================
print("\n" + "=" * 60)
print("METHOD 1: BLOCKING WAIT (wait=True)")
print("=" * 60)
print("This is the simplest approach - the method blocks until complete.")
print("Perfect for sequential operations.\n")

# Initialize pump and wait for completion
print("Initializing pump (with wait=True, this will block until ready)...")
success = pump.initialize_pump(command="ZR", wait=True, timeout=30)
if success:
    print("✓ Initialization complete and pump is ready!\n")
else:
    print("✗ Initialization failed or timed out\n")

# Move syringe with blocking wait
print("Moving syringe to position 3000 (with wait=True)...")
success = pump.move_syringe_absolute(3000, wait=True, timeout=30)
if success:
    print("✓ Move complete and pump is ready!\n")
else:
    print("✗ Move failed or timed out\n")

# ============================================================================
# METHOD 2: Manual Polling (wait_until_ready) - Custom Timeout/Interval
# ============================================================================
print("\n" + "=" * 60)
print("METHOD 2: MANUAL POLLING (wait_until_ready)")
print("=" * 60)
print("Use this when you want custom timeout/interval or want to do")
print("something else while waiting.\n")

# Start a move without waiting
print("Starting move to position 6000 (without wait)...")
pump.move_syringe_absolute(6000, wait=False)

# Do other things here if needed...
print("Command sent, could do other work here...")
time.sleep(1)

# Now manually wait for it to complete with custom parameters
print("Now polling status with custom interval (0.3s)...")
ready = pump.wait_until_ready(timeout=60, poll_interval=0.3)
if ready:
    print("✓ Pump is ready!\n")
else:
    print("✗ Timeout waiting for pump\n")

# ============================================================================
# METHOD 3: Status Checking (is_pump_ready) - Conditional Logic
# ============================================================================
print("\n" + "=" * 60)
print("METHOD 3: STATUS CHECKING (is_pump_ready)")
print("=" * 60)
print("Use this for conditional logic or non-blocking checks.\n")

# Start a continuous pump operation
# Note: 1000 µL @ 1000 µL/min = 1 minute operation
print("Starting continuous pump (1000 µL @ 1000 µL/min)...")
print("This will take approximately 1 minute...")
pump.continuous_pump(1000, 1000, 1, 2, wait=False)
time.sleep(0.5)

# Check status periodically with custom logic
print("Checking status every 5 seconds...")
for i in range(15):  # Check for up to 75 seconds
    time.sleep(5)
    if pump.is_pump_ready():
        print(f"  Check {i+1}: ✓ Pump is ready!")
        break
    else:
        print(f"  Check {i+1}: Pump is still busy...")
else:
    print("  Pump still not ready after 15 checks (75 seconds)")

# ============================================================================
# METHOD 4: Detailed Status (get_parsed_status) - Full Status Info
# ============================================================================
print("\n" + "=" * 60)
print("METHOD 4: DETAILED STATUS (get_parsed_status)")
print("=" * 60)
print("Use this when you need detailed status information.\n")

# Move to a position
print("Moving to position 1500 (without wait)...")
pump.move_syringe_absolute(1500, wait=False)
time.sleep(0.5)

# Get detailed status
print("\nQuerying detailed status...")
for i in range(10):
    status = pump.get_parsed_status()
    print(f"\nStatus check {i+1}:")
    print(f"  Raw response: {repr(status.get('raw'))}")
    print(f"  Cleaned response: {status.get('cleaned')}")
    print(f"  Is busy: {status.get('is_busy')}")
    print(f"  Is idle: {status.get('is_idle')}")
    print(f"  Position: {status.get('position')}")
    if status.get('error'):
        print(f"  Error: {status.get('error')}")

    if status.get('is_idle'):
        print("  ✓ Pump is idle and ready!")
        break

    time.sleep(1)

# ============================================================================
# METHOD 5: Mixed Operations - Demonstrating Flexibility
# ============================================================================
print("\n" + "=" * 60)
print("METHOD 5: MIXED OPERATIONS")
print("=" * 60)
print("Combining different approaches for optimal workflow.\n")

# Prime pump with blocking wait (since we need it done before continuing)
print("1. Priming pump (blocking wait)...")
pump.prime_pump(500, 1, 2, wait=True, timeout=60)
print("   ✓ Priming complete\n")

# Start continuous pump without wait
# Note: 2000 µL @ 1500 µL/min = 1.33 minutes = ~80 seconds
print("2. Starting continuous pump (2000 µL @ 1500 µL/min, non-blocking)...")
print("   This will take approximately 80 seconds...")
pump.continuous_pump(2000, 1500, 1, 2, wait=False)

# Check if ready before next command
print("3. Waiting for pump to be ready before final command...")
pump.wait_until_ready(timeout=150)  # Increased timeout to 150 seconds

# Final move with blocking wait
print("4. Final move to home position (blocking wait)...")
pump.move_syringe_absolute(0, wait=True, timeout=30)
print("   ✓ All operations complete!\n")

# ============================================================================
# Summary
# ============================================================================
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Connection status: {pump.is_connected}")
print(f"Commands sent: {len(pump.get_command_history())}")
print(f"Errors: {len(pump.errors)}")

# Final status check
final_status = pump.get_parsed_status()
print(f"\nFinal pump status:")
print(f"  Is ready: {final_status.get('is_idle')}")
print(f"  Position: {final_status.get('position')}")

if pump.errors:
    print("\nErrors encountered:")
    for error in pump.errors:
        print(f"  - {error}")

print("\n" + "=" * 60)
print("DEMONSTRATION COMPLETE")
print("=" * 60)
print("\nKey Takeaways:")
print("  • Use wait=True for simple sequential operations")
print("  • Use wait_until_ready() for custom timeout/interval")
print("  • Use is_pump_ready() for conditional logic")
print("  • Use get_parsed_status() for detailed status info")
print("=" * 60)
