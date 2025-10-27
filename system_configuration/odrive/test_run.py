#!/usr/bin/env python3
"""
Test script for ODriveAxis class
Demonstrates connection, homing, and basic motion control
"""

import time
import logging
import threading
from odrive_class import ODriveAxis, AxisConfig, AxisType, MotionProfile

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_single_axis():
    """Test a single ODrive axis"""
    
    # Configure the axis
    config = AxisConfig(
        serial_number="365733543432",  # Replace with your ODrive serial number
        axis_type=AxisType.X_AXIS,
        axis_number=0,  # axis0
        
        # Motor parameters (adjust to match your motor)
        pole_pairs=4,
        torque_constant=0.095,
        encoder_cpr=3070,
        
        # Current limits
        current_soft_max=30.0,
        current_hard_max=49.0,
        calibration_current=10.0,
        
        # Torque limits for safety
        torque_soft_limit=0.5,  # Nm - will stop if exceeded
        torque_hard_limit=1.0,  # Nm
        homing_torque_threshold=0.2,  # Nm - for home detection
        
        # Position limits (optional)
        position_min=-100.0,  # turns
        position_max=100.0,   # turns
        
        # Motion profile
        motion_profile=MotionProfile(
            velocity_limit=0.5,  # turns/sec (0.5 rev/s)
            acceleration_limit=1.0,  # turns/sec^2
            deceleration_limit=1.0,  # turns/sec^2
        ),
        
        # Homing settings
        homing_velocity=0.01,  # turns/sec (0.01 rev/s for very slow homing)
        homing_backoff_turns=0.5,
    )
    
    # Create axis instance
    axis = ODriveAxis(config)
    
    try:
        # Connect to ODrive
        print("Connecting to ODrive...")
        if not axis.connect():
            print("Failed to connect to ODrive")
            return
            
        print("Connected successfully!")
        
        # Get initial diagnostics
        diagnostics = axis.get_diagnostics()
        print(f"\nInitial diagnostics:")
        for key, value in diagnostics.items():
            print(f"  {key}: {value}")
        
        # Option 1: Run calibration (uncomment if needed)
        # print("\nRunning motor calibration...")
        # if axis.calibrate():
        #     print("Calibration successful!")
        # else:
        #     print("Calibration failed!")
        #     return
        
        # Option 2: Skip calibration and go straight to closed loop
        # (assumes motor is already calibrated)
        
        # Set up virtual e-stop
        e_stop_triggered = False
        
        def check_e_stop():
            """Check if e-stop has been triggered"""
            return e_stop_triggered
        
        # Home the axis with new velocity control method
        print("\nHoming axis with velocity control...")
        print("The axis will move at 0.01 rev/s to find both end stops")
        print("Press Ctrl+C at any time to trigger virtual E-stop")
        input("Press Enter to start homing...")
        
        try:
            # Use the new homing method with 0.01 rev/s speed
            if axis.home_with_velocity_control(homing_speed=0.01, e_stop_callback=check_e_stop):
                print("Homing successful!")
                print(f"Axis is now at center position (0.0)")
                print(f"Working range: [{axis.config.position_min:.3f}, {axis.config.position_max:.3f}] turns")
            else:
                print("Homing failed!")
                return
        except KeyboardInterrupt:
            print("\nE-stop triggered! Stopping motor...")
            e_stop_triggered = True
            axis.stop(emergency=True)
            print("Motor stopped. Homing aborted.")
            return
        
        # Test position moves
        print("\n--- Testing Position Control ---")
        
        # Move to position 5 turns
        print("\nMoving to position 5 turns at 0.5 rev/s...")
        axis.move_to_position(5.0, velocity=0.5)
        
        # Wait for move to complete
        while axis.status.state.value == "moving":
            status = axis.get_status()
            print(f"Position: {status.position:.2f}, Torque: {status.torque:.2f} Nm", end='\r')
            time.sleep(0.1)
        
        print(f"\nMove completed. Final position: {axis.status.position:.2f}")
        
        # Move back to home
        print("\nMoving back to home position at 0.5 rev/s...")
        axis.move_to_position(0.0, velocity=0.5)
        
        while axis.status.state.value == "moving":
            status = axis.get_status()
            print(f"Position: {status.position:.2f}, Torque: {status.torque:.2f} Nm", end='\r')
            time.sleep(0.1)
        
        print(f"\nAt home. Position: {axis.status.position:.2f}")
        
        # Test relative moves
        print("\n--- Testing Relative Moves ---")
        
        print("Moving +2 turns relative at 0.5 rev/s...")
        axis.move_relative(2.0, velocity=0.5)
        time.sleep(5)  # Adjusted for slower speed
        print(f"Position after relative move: {axis.status.position:.2f}")
        
        print("Moving -2 turns relative at 0.5 rev/s...")
        axis.move_relative(-2.0, velocity=0.5)
        time.sleep(3)
        print(f"Position after relative move: {axis.status.position:.2f}")
        
        # Test different speeds (within our 0.5 rev/s limit)
        print("\n--- Testing Speed Control ---")
        
        speeds = [0.2, 0.3, 0.5]  # All within our velocity limit
        for speed in speeds:
            print(f"\nMoving at {speed} turns/sec...")
            axis.move_to_position(3.0, velocity=speed)
            time.sleep(3.0/speed + 1)  # Wait for move to complete
            axis.move_to_position(0.0, velocity=speed)
            time.sleep(3.0/speed + 1)  # Wait for move to complete
        
        # Test emergency stop
        print("\n--- Testing Emergency Stop ---")
        print("Starting move at 0.5 rev/s...")
        axis.move_to_position(10.0, velocity=0.5)
        time.sleep(1)
        print("Emergency stop!")
        axis.stop(emergency=True)
        print(f"Stopped at position: {axis.status.position:.2f}")
        
        # Final diagnostics
        print("\n--- Final Diagnostics ---")
        diagnostics = axis.get_diagnostics()
        for key, value in diagnostics.items():
            print(f"  {key}: {value}")
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        axis.stop(emergency=True)
        
    except Exception as e:
        print(f"\nError: {e}")
        
    finally:
        # Always disconnect cleanly
        print("\nDisconnecting...")
        axis.disconnect()
        print("Test complete!")


def test_velocity_homing():
    """Test the new velocity-controlled homing with e-stop"""
    
    config = AxisConfig(
        serial_number="365733543432",
        axis_type=AxisType.X_AXIS,
        axis_number=0,
        pole_pairs=4,
        torque_constant=0.095,
        encoder_cpr=3070,
        current_soft_max=30.0,
        current_hard_max=49.0,
        calibration_current=10.0,
        torque_soft_limit=0.5,
        torque_hard_limit=1.0,
        homing_torque_threshold=0.2,  # Low threshold for gentle homing
        motion_profile=MotionProfile(
            velocity_limit=0.5,
        ),
        homing_velocity=0.01,  # Very slow for safety
        homing_timeout=120.0,  # Longer timeout for slow homing
    )
    
    axis = ODriveAxis(config)
    
    # E-stop control
    e_stop_event = threading.Event()
    
    def e_stop_monitor():
        """Monitor for e-stop input"""
        input("Press Enter at any time to trigger E-STOP\n")
        e_stop_event.set()
        print("\n!!! E-STOP TRIGGERED !!!")
    
    def check_e_stop():
        """Check if e-stop has been triggered"""
        return e_stop_event.is_set()
    
    try:
        print("=" * 60)
        print("VELOCITY-CONTROLLED HOMING TEST")
        print("=" * 60)
        
        # Connect
        if not axis.connect():
            print("Failed to connect to ODrive")
            return
        
        print("\nConnected successfully!")
        print("\nThis test will:")
        print("1. Move at 0.01 rev/s to find the negative end stop")
        print("2. Back off and find the positive end stop")
        print("3. Calculate and move to the center position")
        print("4. Set the center as zero position")
        print("\nYou can press Enter at any time to trigger an E-stop")
        
        input("\nPress Enter to begin homing sequence...")
        
        # Start e-stop monitor thread
        e_stop_thread = threading.Thread(target=e_stop_monitor, daemon=True)
        e_stop_thread.start()
        
        # Run homing with e-stop callback
        print("\nStarting homing sequence...")
        success = axis.home_with_velocity_control(
            homing_speed=0.01,
            e_stop_callback=check_e_stop
        )
        
        if e_stop_event.is_set():
            print("\nHoming aborted due to E-stop")
            axis.stop(emergency=True)
        elif success:
            print("\n" + "=" * 60)
            print("HOMING SUCCESSFUL!")
            print("=" * 60)
            print(f"Current position: {axis.status.position:.3f} (should be 0.0)")
            print(f"Working range: [{axis.config.position_min:.3f}, {axis.config.position_max:.3f}] turns")
            
            # Test a few moves within the range
            print("\n--- Testing moves within homed range ---")
            
            if not e_stop_event.is_set():
                print("\nMoving to +2 turns...")
                axis.move_to_position(2.0, velocity=0.2)
                time.sleep(5)
                print(f"Position: {axis.status.position:.3f}")
            
            if not e_stop_event.is_set():
                print("\nMoving to -2 turns...")
                axis.move_to_position(-2.0, velocity=0.2)
                time.sleep(5)
                print(f"Position: {axis.status.position:.3f}")
            
            if not e_stop_event.is_set():
                print("\nReturning to center (0.0)...")
                axis.move_to_position(0.0, velocity=0.2)
                time.sleep(5)
                print(f"Final position: {axis.status.position:.3f}")
        else:
            print("\nHoming failed!")
            
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        axis.stop(emergency=True)
        
    except Exception as e:
        print(f"\nError during test: {e}")
        
    finally:
        print("\nDisconnecting...")
        axis.disconnect()
        print("Test complete!")


def test_torque_monitoring():
    """Test torque monitoring and limits"""
    
    config = AxisConfig(
        serial_number="365733543432",
        axis_type=AxisType.X_AXIS,
        axis_number=0,
        torque_soft_limit=0.5,  # 0.5 Nm limit
        homing_torque_threshold=0.2,  # 0.2 Nm for homing detection
        motion_profile=MotionProfile(
            velocity_limit=0.5,  # 0.5 rev/s
        ),
    )
    
    axis = ODriveAxis(config)
    
    try:
        if not axis.connect():
            print("Failed to connect")
            return
            
        print("Connected. Monitoring torque...")
        print("Try to manually resist the motor movement")
        print("The motor will stop if torque exceeds 0.5 Nm")
        
        # Start a slow move at 0.5 rev/s
        axis.move_to_position(50.0, velocity=0.5)
        
        # Monitor torque
        while axis.status.state.value == "moving":
            status = axis.get_status()
            bar_length = int(abs(status.torque) * 20)
            bar = '█' * bar_length
            print(f"Torque: {status.torque:+.2f} Nm [{bar:<20}]", end='\r')
            
            if axis.status.state.value == "torque_limit_reached":
                print("\n\nTorque limit reached! Motor stopped for safety.")
                break
                
            time.sleep(0.05)
        
    finally:
        axis.disconnect()


if __name__ == "__main__":
    print("ODrive Axis Test Program")
    print("=" * 50)
    print("1. Test single axis (full test)")
    print("2. Test torque monitoring")
    print("3. Test velocity-controlled homing with E-stop")
    print("=" * 50)
    
    choice = input("Select test (1, 2, or 3): ")
    
    if choice == "1":
        test_single_axis()
    elif choice == "2":
        test_torque_monitoring()
    elif choice == "3":
        test_velocity_homing()
    else:
        print("Invalid choice")