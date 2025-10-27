#!/usr/bin/env python3
"""
Simple test for velocity control on ODrive
Tests basic velocity commands without complex homing
"""

import odrive
from odrive.enums import AxisState, ControlMode, InputMode
import time
import sys

def test_velocity_control():
    """Simple velocity control test"""
    
    print("=" * 60)
    print("SIMPLE VELOCITY CONTROL TEST")
    print("=" * 60)
    
    # Connect to ODrive
    print("\nSearching for ODrive...")
    try:
        odrv0 = odrive.find_any(serial_number="365733543432", timeout=10)
        if not odrv0:
            print("ODrive not found!")
            return
        print("ODrive connected!")
    except Exception as e:
        print(f"Connection error: {e}")
        return
    
    axis = odrv0.axis0
    
    try:
        # Check current state
        print(f"\nCurrent axis state: {axis.current_state}")
        print(f"Current control mode: {axis.controller.config.control_mode}")
        print(f"Current input mode: {axis.controller.config.input_mode}")
        
        # Clear any errors
        print("\nClearing errors...")
        try:
            axis.clear_errors()
        except AttributeError:
            # Older firmware uses different method
            odrv0.clear_errors()
        except:
            print("Note: Could not clear errors (may not be needed)")
        
        # Enter closed loop control
        print("Entering closed loop control...")
        axis.requested_state = AxisState.CLOSED_LOOP_CONTROL
        time.sleep(1)
        
        if axis.current_state != AxisState.CLOSED_LOOP_CONTROL:
            print(f"Failed to enter closed loop! State: {axis.current_state}")
            
            # Try to get error info
            try:
                if hasattr(axis, 'error'):
                    print(f"Axis error: {axis.error}")
                if hasattr(axis, 'motor'):
                    if hasattr(axis.motor, 'error'):
                        print(f"Motor error: {axis.motor.error}")
                if hasattr(axis, 'encoder'):
                    if hasattr(axis.encoder, 'error'):
                        print(f"Encoder error: {axis.encoder.error}")
            except:
                pass
            
            print("\nThe motor may need calibration first.")
            print("Would you like to run calibration? (y/n)")
            
            choice = input().lower()
            if choice == 'y':
                print("\nRunning motor calibration...")
                print("The motor will beep and move. This is normal.")
                axis.requested_state = AxisState.FULL_CALIBRATION_SEQUENCE
                
                # Wait for calibration to complete
                start_time = time.time()
                while axis.current_state != AxisState.IDLE:
                    if time.time() - start_time > 30:
                        print("Calibration timeout!")
                        return
                    print(f"Calibrating... State: {axis.current_state}", end='\r')
                    time.sleep(0.5)
                
                print("\nCalibration complete! Trying closed loop again...")
                axis.requested_state = AxisState.CLOSED_LOOP_CONTROL
                time.sleep(1)
                
                if axis.current_state != AxisState.CLOSED_LOOP_CONTROL:
                    print("Still couldn't enter closed loop after calibration.")
                    return
            else:
                print("Cannot proceed without closed loop control.")
                return
        
        print("Closed loop control active!")
        
        # Configure for velocity control
        print("\nConfiguring velocity control...")
        print(f"  Original control mode: {axis.controller.config.control_mode}")
        print(f"  Original input mode: {axis.controller.config.input_mode}")
        
        # Store original settings
        original_control = axis.controller.config.control_mode
        original_input = axis.controller.config.input_mode
        
        # Set velocity control
        axis.controller.config.control_mode = ControlMode.VELOCITY_CONTROL
        axis.controller.config.input_mode = InputMode.VEL_RAMP
        axis.controller.config.vel_ramp_rate = 1.0  # turns/s^2
        
        print(f"  New control mode: {axis.controller.config.control_mode}")
        print(f"  New input mode: {axis.controller.config.input_mode}")
        
        # Test velocity commands
        print("\n" + "=" * 40)
        print("STARTING VELOCITY TEST")
        print("Press Ctrl+C to stop at any time")
        print("=" * 40)
        
        speeds = [0.01, -0.01, 0.02, -0.02, 0]  # Very slow speeds
        
        for speed in speeds:
            print(f"\nSetting velocity to {speed:.3f} turns/sec...")
            axis.controller.input_vel = speed
            
            # Monitor for 3 seconds
            for i in range(30):
                try:
                    # Get position and velocity
                    if hasattr(axis, 'pos_vel_mapper'):
                        pos = axis.pos_vel_mapper.pos_rel
                        vel = axis.pos_vel_mapper.vel
                    else:
                        pos = axis.encoder.pos_estimate if hasattr(axis.encoder, 'pos_estimate') else 0
                        vel = axis.encoder.vel_estimate if hasattr(axis.encoder, 'vel_estimate') else 0
                    
                    # Get current
                    if hasattr(axis.motor, 'current_control'):
                        current = axis.motor.current_control.Iq_measured
                    elif hasattr(axis.motor, 'foc'):
                        current = axis.motor.foc.Iq_measured
                    else:
                        current = 0
                    
                    print(f"  Pos: {pos:7.3f} | Vel: {vel:7.3f} | Current: {current:6.2f}A", end='\r')
                    time.sleep(0.1)
                    
                except KeyboardInterrupt:
                    print("\n\nStopping motor...")
                    axis.controller.input_vel = 0
                    raise
                    
        print("\n\nVelocity test complete!")
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        
    except Exception as e:
        print(f"\nError during test: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Stop motor and restore settings
        print("\nStopping motor and restoring settings...")
        try:
            axis.controller.input_vel = 0
            try:
                axis.controller.config.control_mode = original_control
                axis.controller.config.input_mode = original_input
            except NameError:
                # original_control/input not defined if we failed early
                pass
            axis.requested_state = AxisState.IDLE
        except:
            pass
        
        print("Test complete!")


if __name__ == "__main__":
    test_velocity_control()