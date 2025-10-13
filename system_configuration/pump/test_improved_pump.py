"""
Test script for improved Cavro XLP 6000 pump class
Demonstrates proper connection verification and enhanced features
"""

import logging
import time
from pump_class import Pump, PumpConfig, ValvePosition

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_connection_and_verification():
    """Test proper device connection and verification"""
    print("\n" + "="*60)
    print("Testing Improved Pump Connection with Device Verification")
    print("="*60)
    
    # Create pump with custom configuration
    config = PumpConfig(
        port="COM12",  # Update to your COM port
        address=1,
        baudrate=9600,
        syringe_size_ml=1.0,
        default_speed=2000
    )
    
    pump = Pump(config)
    
    # Test connection with device verification
    print("\n1. Connecting with device verification...")
    if pump.connect(verify_device=True):
        print("   ✓ Connection successful - device responded correctly")
        
        # Get initial status
        status = pump.get_status()
        print("\n2. Initial pump status:")
        print(f"   State: {status['state']}")
        print(f"   Position: {status['position']} steps")
        print(f"   Is Idle: {status.get('is_idle', False)}")
        print(f"   Is Busy: {status.get('is_busy', False)}")
    else:
        print("   ✗ Connection failed - device did not respond or wrong device")
        return False
    
    return pump

def test_valve_control(pump):
    """Test complete valve control implementation"""
    print("\n" + "="*60)
    print("Testing Valve Control")
    print("="*60)
    
    if not pump or not pump.is_connected():
        print("Pump not connected!")
        return
    
    print("\n1. Testing valve positions:")
    
    # Test different valve positions
    test_positions = [
        (ValvePosition.INPUT_1, "Input 1"),
        (ValvePosition.INPUT_5, "Input 5"),
        (ValvePosition.OUTPUT, "Output"),
        (ValvePosition.BYPASS, "Bypass"),
    ]
    
    for position, description in test_positions:
        print(f"\n   Setting valve to {description}...")
        if pump.set_valve_position(position, wait=True):
            print(f"   ✓ Valve set to {description}")
        else:
            print(f"   ✗ Failed to set valve to {description}")
        time.sleep(0.5)
    
    # Test convenience methods
    print("\n2. Testing convenience methods:")
    
    print("   Setting valve to input 3...")
    pump.valve_input(3)
    print(f"   Current valve: {pump.current_valve.name}")
    
    print("   Setting valve to output...")
    pump.valve_output()
    print(f"   Current valve: {pump.current_valve.name}")

def test_aspiration_dispensing(pump):
    """Test improved aspiration and dispensing with valve control"""
    print("\n" + "="*60)
    print("Testing Aspiration and Dispensing")
    print("="*60)
    
    if not pump or not pump.is_connected():
        print("Pump not connected!")
        return
    
    # Initialize pump first
    print("\n1. Initializing pump...")
    if pump.initialize(wait=True):
        print("   ✓ Pump initialized")
    else:
        print("   ✗ Initialization failed")
        return
    
    # Test aspiration with valve selection
    print("\n2. Aspirating 500µL from input 1...")
    if pump.aspirate(500, inlet_valve=1, wait=True):
        print(f"   ✓ Aspiration complete")
        print(f"   Current position: {pump.current_position} steps")
        print(f"   Volume in syringe: {pump._steps_to_volume(pump.current_position):.1f}µL")
    else:
        print("   ✗ Aspiration failed")
    
    # Test dispensing with valve selection
    print("\n3. Dispensing 200µL to output...")
    if pump.dispense(200, outlet_valve=12, wait=True):
        print(f"   ✓ Dispensing complete")
        print(f"   Current position: {pump.current_position} steps")
        print(f"   Volume in syringe: {pump._steps_to_volume(pump.current_position):.1f}µL")
    else:
        print("   ✗ Dispensing failed")
    
    # Empty syringe
    print("\n4. Emptying syringe...")
    if pump.empty_syringe(wait=True):
        print("   ✓ Syringe emptied")
    else:
        print("   ✗ Failed to empty syringe")

def test_error_handling(pump):
    """Test error handling and recovery"""
    print("\n" + "="*60)
    print("Testing Error Handling and Recovery")
    print("="*60)
    
    if not pump or not pump.is_connected():
        print("Pump not connected!")
        return
    
    print("\n1. Testing invalid parameters:")
    
    # Test invalid valve position
    print("   Attempting to set invalid valve position (15)...")
    result = pump.set_valve_position(15)
    print(f"   Result: {result} (should be False)")
    
    # Test invalid aspiration volume
    print("\n   Attempting to aspirate 10000µL (exceeds capacity)...")
    result = pump.aspirate(10000)
    print(f"   Result: {result} (should be False)")
    
    # Test connection check
    print("\n2. Testing connection monitoring:")
    print(f"   Is connected: {pump.is_connected()}")
    print(f"   Is ready: {pump.is_ready()}")
    
    # Show command history
    print("\n3. Recent command history:")
    history = pump.get_command_history(limit=5)
    for i, cmd in enumerate(history, 1):
        print(f"   {i}. {cmd['timestamp']}: {cmd['command']}")

def test_continuous_operation(pump):
    """Test continuous pumping operation"""
    print("\n" + "="*60)
    print("Testing Continuous Pumping")
    print("="*60)
    
    if not pump or not pump.is_connected():
        print("Pump not connected!")
        return
    
    print("\n1. Setting up continuous pump operation:")
    print("   Volume: 5000µL")
    print("   Flow rate: 1000µL/min")
    print("   From input 1 to output")
    
    # Note: This will take time to complete
    print("\n2. Starting continuous pump...")
    if pump.continuous_pump(
        volume_ul=5000,
        flowrate_ul_min=1000,
        inlet=1,
        outlet=12,
        wait=False  # Don't wait for completion in test
    ):
        print("   ✓ Continuous pump started")
        
        # Monitor for a bit
        print("\n3. Monitoring pump status:")
        for i in range(3):
            time.sleep(2)
            status = pump.get_status()
            print(f"   Status: {status['state']}, Position: {status.get('position', 'N/A')}")
        
        # Stop the operation
        print("\n4. Stopping pump...")
        if pump.stop():
            print("   ✓ Pump stopped")
    else:
        print("   ✗ Failed to start continuous pump")

def main():
    """Run all tests"""
    print("\n" + "#"*60)
    print("# CAVRO XLP 6000 - IMPROVED PUMP CLASS TEST SUITE")
    print("#"*60)
    
    # Test connection with verification
    pump = test_connection_and_verification()
    
    if pump and pump.is_connected():
        # Run tests
        test_valve_control(pump)
        test_aspiration_dispensing(pump)
        test_error_handling(pump)
        
        # Optional: test continuous operation (takes time)
        # test_continuous_operation(pump)
        
        # Disconnect
        print("\n" + "="*60)
        print("Disconnecting from pump...")
        pump.disconnect()
        print("✓ Disconnected")
    else:
        print("\n✗ Could not establish connection - check COM port and pump power")
    
    print("\n" + "#"*60)
    print("# TEST SUITE COMPLETE")
    print("#"*60)

if __name__ == "__main__":
    main()