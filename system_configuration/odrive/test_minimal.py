#!/usr/bin/env python3
"""
Minimal ODrive test - bypasses complex configuration
Tests basic connectivity and homing with velocity control
"""

import odrive
from odrive.enums import AxisState, ControlMode, InputMode
import time

def minimal_homing_test():
    """Minimal test for homing with velocity control"""
    
    print("=" * 60)
    print("MINIMAL HOMING TEST")
    print("=" * 60)
    
    # Connect
    print("\nConnecting to ODrive...")
    try:
        odrv0 = odrive.find_any(serial_number="365733543432", timeout=10)
        if not odrv0:
            print("ODrive not found!")
            return
        print("Connected!")
    except Exception as e:
        print(f"Connection error: {e}")
        return
    
    axis = odrv0.axis0
    
    # E-stop flag
    stop_flag = False
    
    print("\n--- Current Status ---")
    print(f"Axis state: {axis.current_state}")
    print(f"Vbus voltage: {odrv0.vbus_voltage}V")
    
    # Check for errors first
    print(f"\nChecking for errors...")
    errors_found = False
    
    # Check axis error
    if hasattr(axis, 'error') and axis.error != 0:
        print(f"Axis error: 0x{axis.error:X}")
        errors_found = True
    
    # Check motor error
    if hasattr(axis, 'motor') and hasattr(axis.motor, 'error') and axis.motor.error != 0:
        print(f"Motor error: 0x{axis.motor.error:X}")
        errors_found = True
    
    # Check encoder error  
    if hasattr(axis, 'encoder') and hasattr(axis.encoder, 'error') and axis.encoder.error != 0:
        print(f"Encoder error: 0x{axis.encoder.error:X}")
        errors_found = True
    
    if errors_found:
        print("\nErrors found! Clearing errors...")
        try:
            odrv0.clear_errors()
        except:
            print("Could not clear errors")
    else:
        print("No errors found.")
    
    # Ask for calibration if needed
    if axis.current_state == AxisState.IDLE:
        print("\nMotor is idle. Run calibration? (y/n): ", end='')
        if input().lower() == 'y':
            print("Calibrating... (motor will beep and move)")
            axis.requested_state = AxisState.FULL_CALIBRATION_SEQUENCE
            
            # Wait for calibration
            timeout = time.time() + 30
            while axis.current_state != AxisState.IDLE:
                if time.time() > timeout:
                    print("\nCalibration timeout!")
                    break
                print(f"State: {axis.current_state}", end='\r')
                time.sleep(0.5)
            
            # Check if calibration succeeded
            if hasattr(axis, 'motor') and hasattr(axis.motor, 'is_calibrated'):
                if axis.motor.is_calibrated:
                    print("\nMotor calibrated successfully!")
                else:
                    print("\nMotor calibration failed!")
                    
            if hasattr(axis, 'encoder') and hasattr(axis.encoder, 'is_ready'):
                if axis.encoder.is_ready:
                    print("Encoder ready!")
                else:
                    print("Encoder not ready!")
                    
            # Set motor as pre-calibrated so we can enter closed loop
            print("\nSetting motor as pre-calibrated...")
            try:
                axis.motor.config.pre_calibrated = True
                axis.encoder.config.pre_calibrated = True
                print("Pre-calibration flags set. You may want to save configuration.")
            except:
                print("Could not set pre-calibration flags")
    
    # Enter closed loop
    print("\nEntering closed loop control...")
    axis.requested_state = AxisState.CLOSED_LOOP_CONTROL
    time.sleep(1)
    
    if axis.current_state != AxisState.CLOSED_LOOP_CONTROL:
        print(f"Failed to enter closed loop. State: {axis.current_state}")
        
        # Check for errors
        print("\nChecking for errors after closed loop attempt:")
        if hasattr(axis, 'error') and axis.error != 0:
            print(f"Axis error: 0x{axis.error:X}")
            # Decode common errors
            if axis.error & 0x01:
                print("  - INVALID_STATE")
            if axis.error & 0x40:
                print("  - MOTOR_NOT_CALIBRATED") 
            if axis.error & 0x100:
                print("  - ENCODER_NOT_READY")
                
        if hasattr(axis, 'motor') and hasattr(axis.motor, 'error') and axis.motor.error != 0:
            print(f"Motor error: 0x{axis.motor.error:X}")
            
        if hasattr(axis, 'encoder') and hasattr(axis.encoder, 'error') and axis.encoder.error != 0:
            print(f"Encoder error: 0x{axis.encoder.error:X}")
        
        print("\nPossible solutions:")
        print("1. Run calibration first (option y above)")
        print("2. Check encoder connections")
        print("3. Save configuration after successful calibration")
        return
    
    print("Closed loop active!")
    
    try:
        # Simple velocity-based homing
        print("\n" + "=" * 40)
        print("VELOCITY HOMING TEST")
        print("Press Ctrl+C to stop")
        print("=" * 40)
        
        # Switch to velocity control
        print("\nConfiguring velocity control...")
        axis.controller.config.control_mode = ControlMode.VELOCITY_CONTROL
        axis.controller.config.input_mode = InputMode.PASSTHROUGH  # Direct velocity input
        print("Velocity control configured!")
        
        # Find negative end stop
        print("\nMoving negative at 0.01 rev/s...")
        print("Waiting for motor to stall (position stops changing)...")
        
        axis.controller.input_vel = -0.01  # Very slow
        
        # Monitor for stall
        last_pos = 0
        stall_count = 0
        negative_end = None
        
        for i in range(300):  # 30 seconds max
            time.sleep(0.1)
            
            # Get current position
            if hasattr(axis, 'pos_vel_mapper'):
                current_pos = axis.pos_vel_mapper.pos_rel
            elif hasattr(axis, 'encoder'):
                current_pos = axis.encoder.pos_estimate
            else:
                current_pos = 0
            
            # Check for stall
            if abs(current_pos - last_pos) < 0.0001:
                stall_count += 1
                if stall_count > 10:  # 1 second of no movement
                    negative_end = current_pos
                    print(f"\nNegative end found at {negative_end:.3f}")
                    break
            else:
                stall_count = 0
            
            last_pos = current_pos
            print(f"Pos: {current_pos:7.3f} turns", end='\r')
        
        # Stop and back off
        axis.controller.input_vel = 0
        time.sleep(0.5)
        
        if negative_end is None:
            print("\nTimeout finding negative end")
            return
        
        # Back off
        print("Backing off...")
        axis.controller.input_vel = 0.02  # Faster backoff
        time.sleep(2)
        axis.controller.input_vel = 0
        time.sleep(0.5)
        
        # Find positive end stop
        print("\nMoving positive at 0.01 rev/s...")
        print("Waiting for motor to stall...")
        
        axis.controller.input_vel = 0.01
        
        stall_count = 0
        positive_end = None
        
        for i in range(300):  # 30 seconds max
            time.sleep(0.1)
            
            # Get current position
            if hasattr(axis, 'pos_vel_mapper'):
                current_pos = axis.pos_vel_mapper.pos_rel
            elif hasattr(axis, 'encoder'):
                current_pos = axis.encoder.pos_estimate
            else:
                current_pos = 0
            
            # Check for stall
            if abs(current_pos - last_pos) < 0.0001:
                stall_count += 1
                if stall_count > 10:
                    positive_end = current_pos
                    print(f"\nPositive end found at {positive_end:.3f}")
                    break
            else:
                stall_count = 0
            
            last_pos = current_pos
            print(f"Pos: {current_pos:7.3f} turns", end='\r')
        
        # Stop
        axis.controller.input_vel = 0
        
        if positive_end is None:
            print("\nTimeout finding positive end")
            return
        
        # Calculate middle
        travel = abs(positive_end - negative_end)
        middle = negative_end + travel/2
        
        print(f"\n--- Homing Results ---")
        print(f"Negative end: {negative_end:.3f}")
        print(f"Positive end: {positive_end:.3f}")
        print(f"Travel: {travel:.3f} turns")
        print(f"Middle: {middle:.3f}")
        
        # Move to middle using position control
        print("\nSwitching to position control...")
        axis.controller.config.control_mode = ControlMode.POSITION_CONTROL
        axis.controller.config.input_mode = InputMode.TRAP_TRAJ
        
        print(f"Moving to middle position...")
        axis.controller.input_pos = middle
        
        # Wait for move
        for i in range(50):
            time.sleep(0.1)
            if hasattr(axis, 'pos_vel_mapper'):
                current_pos = axis.pos_vel_mapper.pos_rel
            elif hasattr(axis, 'encoder'):
                current_pos = axis.encoder.pos_estimate
            else:
                current_pos = 0
            
            if abs(current_pos - middle) < 0.01:
                print(f"\nReached middle at {current_pos:.3f}")
                break
            print(f"Moving... Pos: {current_pos:.3f}", end='\r')
        
        # Set as zero
        print("\nSetting middle as zero...")
        axis.controller.input_pos = 0
        if hasattr(axis, 'pos_vel_mapper'):
            try:
                axis.pos_vel_mapper.set_pos_rel(0)
            except:
                print("Note: Could not reset position mapper")
        
        print("\nHoming complete!")
        print(f"Working range: [{-travel/2:.3f}, {travel/2:.3f}] turns")
        
    except KeyboardInterrupt:
        print("\n\nStopped by user!")
        axis.controller.input_vel = 0
        
    finally:
        print("\nReturning to idle...")
        axis.requested_state = AxisState.IDLE
        print("Done!")


if __name__ == "__main__":
    minimal_homing_test()