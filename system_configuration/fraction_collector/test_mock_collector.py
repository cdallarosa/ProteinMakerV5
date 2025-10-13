"""
Test script for Mock Fraction Collector
Demonstrates basic functionality and usage
"""

import time
import logging
from mock_fraction_collector import MockFractionCollector, CollectionMode

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_basic_operations():
    """Test basic fraction collector operations"""
    print("\n" + "="*60)
    print("Testing Mock Fraction Collector")
    print("="*60)
    
    # Create collector instance
    collector = MockFractionCollector()
    
    # Connect and initialize
    print("\n1. Connecting to collector...")
    collector.connect()
    
    print("\n2. Initializing collector...")
    collector.initialize()
    
    # Display initial status
    print("\n3. Initial Status:")
    status = collector.get_status()
    for key, value in status.items():
        print(f"   {key}: {value}")
    
    # Test movement
    print("\n4. Testing movement to Plate 2, Section 3...")
    collector.move_to_position(2, 3)
    
    print("\n5. Testing advance to next position...")
    collector.advance_position()
    
    # Test collection modes
    print("\n6. Setting collection mode to VOLUME (5 mL per fraction)...")
    collector.set_collection_mode(CollectionMode.VOLUME, 5.0)
    
    # Start collection
    print("\n7. Starting collection...")
    collector.start_collection()
    
    # Simulate volume being dispensed
    print("\n8. Simulating volume collection...")
    for i in range(3):
        print(f"   Dispensing 2 mL (iteration {i+1})...")
        collector.simulate_volume_collected(2.0)
        time.sleep(0.5)
    
    # Stop collection
    print("\n9. Stopping collection...")
    collector.stop_collection()
    
    # Display plate map
    print("\n10. Current Plate Map:")
    print(collector.get_plate_map())
    
    # Test time-based collection
    print("\n11. Testing TIME mode (2 seconds per fraction)...")
    collector.set_collection_mode(CollectionMode.TIME, 2.0)
    collector.start_collection()
    
    print("    Waiting for automatic advance...")
    for i in range(5):
        collector.update()  # Simulate system update loop
        collector.simulate_volume_collected(0.5)  # Simulate continuous flow
        time.sleep(1)
        print(f"    Time elapsed: {i+1} seconds")
    
    collector.stop_collection()
    
    # Final status
    print("\n12. Final Plate Map:")
    print(collector.get_plate_map())
    
    print("\n13. Collection Summary:")
    print(f"    Total fractions collected: {len(collector.collected_fractions)}")
    print(f"    Total volume collected: {collector.total_volume_collected:.2f} mL")
    
    if collector.collected_fractions:
        print("\n    Fraction Details:")
        for i, fraction in enumerate(collector.collected_fractions, 1):
            pos = fraction['position']
            print(f"    Fraction {i}: {pos}, Volume: {fraction['volume']:.2f} mL, Time: {fraction['time']:.1f} sec")
    
    # Disconnect
    print("\n14. Disconnecting...")
    collector.disconnect()
    
    print("\n" + "="*60)
    print("Test Complete!")
    print("="*60)

def test_plate_navigation():
    """Test navigation across all plate positions"""
    print("\n" + "="*60)
    print("Testing Plate Navigation")
    print("="*60)
    
    collector = MockFractionCollector()
    collector.connect()
    collector.initialize()
    
    print("\nNavigating through all positions:")
    print("-" * 40)
    
    # Move through specific positions
    test_positions = [
        (1, 1, "Home position"),
        (1, 6, "End of plate 1"),
        (2, 1, "Start of plate 2"),
        (3, 3, "Middle of plate 3"),
        (6, 6, "Last position"),
        (1, 1, "Return home")
    ]
    
    for plate, section, description in test_positions:
        print(f"\nMoving to Plate {plate}, Section {section} ({description})...")
        success = collector.move_to_position(plate, section, wait=False)
        
        if success:
            # Simulate movement time
            while collector.is_moving:
                print("  Moving...", end="\r")
                collector.update()
                time.sleep(0.5)
            print(f"  ✓ Arrived at Plate {plate}, Section {section}")
        else:
            print(f"  ✗ Failed to move to Plate {plate}, Section {section}")
    
    collector.disconnect()
    print("\n" + "="*60)
    print("Navigation Test Complete!")
    print("="*60)

if __name__ == "__main__":
    # Run tests
    test_basic_operations()
    print("\n" * 2)
    test_plate_navigation()