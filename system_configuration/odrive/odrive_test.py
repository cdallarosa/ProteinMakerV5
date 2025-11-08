#!/usr/bin/env python3
"""
Example usage of the ODrive python library to monitor and control two separate ODrive devices
"""
import math
import time
import sys

import odrive
from odrive.enums import AxisState, ControlMode, InputMode
from odrive.utils import dump_errors, request_state

# Your ODrive serial numbers
ODRIVE_SERIAL_1 = "366133543432"  # First ODrive
ODRIVE_SERIAL_2 = "365733543432"  # Second ODrive

print("Connecting to ODrives...")

# Connect to first ODrive
print(f"Connecting to first ODrive (serial: {ODRIVE_SERIAL_1})...")
odrv0 = odrive.find_any(serial_number=ODRIVE_SERIAL_1, timeout=10)
if odrv0 is None:
    print(f"ERROR: Could not find ODrive with serial {ODRIVE_SERIAL_1}")
    print("Please check the connection and serial number.")
    sys.exit(1)
print(f"Connected to first ODrive: {odrv0._dev.serial_number}")

# Connect to second ODrive
print(f"Connecting to second ODrive (serial: {ODRIVE_SERIAL_2})...")
odrv1 = odrive.find_any(serial_number=ODRIVE_SERIAL_2, timeout=10)
if odrv1 is None:
    print(f"ERROR: Could not find ODrive with serial {ODRIVE_SERIAL_2}")
    print("Please check the connection and serial number.")
    sys.exit(1)
print(f"Connected to second ODrive: {odrv1._dev.serial_number}")

print(f"\nSuccessfully connected to both ODrives!")
print(f"ODrive 1: {odrv0._dev.serial_number}")
print(f"ODrive 2: {odrv1._dev.serial_number}")

# Configure both ODrives' axis0 for closed loop control
print("\nConfiguring first ODrive axis0...")
odrv0.axis0.controller.config.input_mode = InputMode.PASSTHROUGH
odrv0.axis0.controller.config.control_mode = ControlMode.POSITION_CONTROL

print("Configuring second ODrive axis0...")
odrv1.axis0.controller.config.input_mode = InputMode.PASSTHROUGH
odrv1.axis0.controller.config.control_mode = ControlMode.POSITION_CONTROL

# Enter closed loop control on both ODrives
print("Entering closed loop control on first ODrive...")
request_state(odrv0.axis0, AxisState.CLOSED_LOOP_CONTROL)
print("Entering closed loop control on second ODrive...")
request_state(odrv1.axis0, AxisState.CLOSED_LOOP_CONTROL)

# Run homing and sine waves on both ODrives until error or user hits Ctrl+C
try:
    # Get initial positions for both ODrives
    initial_pos_odrv0 = odrv0.axis0.controller.input_pos
    initial_pos_odrv1 = odrv1.axis0.controller.input_pos
    
    print("\n" + "=" * 50)
    print("HOMING SEQUENCE")
    print("=" * 50)
    print(f"Current positions - ODrive0: {initial_pos_odrv0:.3f}, ODrive1: {initial_pos_odrv1:.3f}")
    print("Moving to zero position slowly...")
    
    # Homing sequence - slowly move to position 0
    homing_duration = 5.0  # Take 5 seconds to home
    homing_start = time.monotonic()
    
    while time.monotonic() - homing_start < homing_duration:
        elapsed_homing = time.monotonic() - homing_start
        progress = elapsed_homing / homing_duration
        
        # Smooth interpolation from current position to 0
        # Using a smoothstep function for smooth acceleration/deceleration
        smooth_progress = progress * progress * (3 - 2 * progress)
        
        current_pos_odrv0 = initial_pos_odrv0 * (1 - smooth_progress)
        current_pos_odrv1 = initial_pos_odrv1 * (1 - smooth_progress)
        
        odrv0.axis0.controller.input_pos = current_pos_odrv0
        odrv1.axis0.controller.input_pos = current_pos_odrv1
        
        print(f"Homing: ODrive0: {current_pos_odrv0:+6.3f} | ODrive1: {current_pos_odrv1:+6.3f} | Progress: {progress*100:5.1f}%", end='\r')
        
        time.sleep(0.01)
    
    # Ensure we're exactly at zero
    odrv0.axis0.controller.input_pos = 0
    odrv1.axis0.controller.input_pos = 0
    
    print(f"\nHoming complete! Both ODrives at position 0.000")
    print("\n" + "=" * 50)
    print("STARTING MOTION CONTROL")
    print("=" * 50)
    print("Motion range: -2 to +2")
    print("Speed: Slow (one cycle ~6.3 seconds)")
    print("Press Ctrl+C to stop")
    print("-" * 50)
    
    # Now start from position 0
    t0 = time.monotonic()
    
    while (odrv0.axis0.current_state == AxisState.CLOSED_LOOP_CONTROL and 
           odrv1.axis0.current_state == AxisState.CLOSED_LOOP_CONTROL):
        
        elapsed = time.monotonic() - t0
        
        # ODrive 0: sine wave with amplitude 2.0 (range -2 to 2) starting from 0
        setpoint_odrv0 = 4 * math.sin(elapsed * 1)  # Slower frequency for safety
        
        # ODrive 1: sine wave with amplitude 2.0 (range -2 to 2), 90 degrees phase shifted (cosine)
        setpoint_odrv1 = 4 * math.cos(elapsed * 1)
        
        # Update position with status display
        print(f"ODrive0: {setpoint_odrv0:+6.3f} | ODrive1: {setpoint_odrv1:+6.3f} | Time: {elapsed:6.1f}s", end='\r')
        
        odrv0.axis0.controller.input_pos = setpoint_odrv0
        odrv1.axis0.controller.input_pos = setpoint_odrv1
        
        time.sleep(0.01)

except KeyboardInterrupt:
    print("\n\nMotion stopped by user")
except Exception as e:
    print(f"\nError occurred: {e}")
    dump_errors(odrv0, True)
    dump_errors(odrv1, True)

finally:
    print("\nReturning both ODrives to IDLE state...")
    try:
        request_state(odrv0.axis0, AxisState.IDLE)
        print(f"ODrive {ODRIVE_SERIAL_1} is now in IDLE state")
    except Exception as e:
        print(f"Could not set ODrive {ODRIVE_SERIAL_1} to IDLE: {e}")
    
    try:
        request_state(odrv1.axis0, AxisState.IDLE)
        print(f"ODrive {ODRIVE_SERIAL_2} is now in IDLE state")
    except Exception as e:
        print(f"Could not set ODrive {ODRIVE_SERIAL_2} to IDLE: {e}")
    
    print("\nProgram completed.")