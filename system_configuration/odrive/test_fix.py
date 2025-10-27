#!/usr/bin/env python3
"""
Quick test script to verify ODrive connection and basic operations
"""
import time
import logging
from odrive_class import ODriveAxis, AxisConfig, AxisType, MotionProfile

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_connection():
    """Test basic connection and status reading"""
    
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
        
        # Motion profile
        motion_profile=MotionProfile(
            velocity_limit=0.5,  # turns/sec (0.5 rev/s)
            acceleration_limit=1.0,  # turns/sec^2
            deceleration_limit=1.0,  # turns/sec^2
        ),
    )
    
    # Create axis instance
    axis = ODriveAxis(config)
    
    try:
        # Connect to ODrive
        print("Connecting to ODrive...")
        if not axis.connect():
            print("Failed to connect to ODrive")
            return False
            
        print("Connected successfully!")
        
        # Test status reading for 5 seconds
        print("\nTesting status monitoring for 5 seconds...")
        print("(This verifies that position and current reading work)")
        
        for i in range(50):
            status = axis.get_status()
            print(f"Position: {status.position:.3f} turns, "
                  f"Velocity: {status.velocity:.3f} turns/s, "
                  f"Current: {status.current:.3f} A, "
                  f"Torque: {status.torque:.3f} Nm", end='\r')
            time.sleep(0.1)
        
        print("\n\nStatus monitoring successful!")
        
        # Get diagnostics
        print("\nDiagnostics:")
        diagnostics = axis.get_diagnostics()
        for key, value in diagnostics.items():
            print(f"  {key}: {value}")
        
        return True
        
    except Exception as e:
        print(f"\nError during test: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Always disconnect cleanly
        print("\nDisconnecting...")
        axis.disconnect()
        print("Test complete!")


if __name__ == "__main__":
    print("ODrive Connection Test")
    print("=" * 50)
    
    success = test_connection()
    
    if success:
        print("\nTEST PASSED: ODrive communication is working correctly!")
    else:
        print("\nTEST FAILED: Please check the error messages above")