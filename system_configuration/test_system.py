"""
Test script for improved System class
Demonstrates simple process steps and column tracking
"""

import logging
import time
from system_config import System

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_system_basic_operations():
    """Test basic system operations"""
    print("\n" + "="*60)
    print("Testing System with Process Steps")
    print("="*60)
    
    # Create system
    system = System()
    
    # Connect all pumps
    print("\n1. Connecting to all pumps...")
    if system.connect_all():
        print("   ✓ All pumps connected")
    else:
        print("   ✗ Failed to connect pumps")
        return
    
    # Initialize all pumps
    print("\n2. Initializing all pumps...")
    if system.initialize_all():
        print("   ✓ All pumps initialized")
    else:
        print("   ✗ Failed to initialize pumps")
        return
    
    # Show initial status
    print("\n3. Initial system status:")
    status = system.get_system_status()
    print(f"   Connected: {status['connected']}")
    print(f"   Initialized: {status['initialized']}")
    
    print("\n   Pump states:")
    for pump_name, pump_status in status['pumps'].items():
        print(f"     {pump_name}: {pump_status.get('state', 'unknown')}")
    
    print("\n   Column info:")
    for col_name, col_info in status['columns'].items():
        print(f"     {col_name}: {col_info['type']} - {col_info['cycles_run']} cycles")

def test_process_steps():
    """Test individual process steps"""
    print("\n" + "="*60)
    print("Testing Process Steps")
    print("="*60)
    
    system = System()
    
    # Quick connect and init (assuming pumps are available)
    if not (system.connect_all() and system.initialize_all()):
        print("   ✗ Could not connect/initialize - using simulation")
        return
    
    # Example process steps for a purification
    
    print("\n1. Prime pump1 with buffer...")
    success = system.process_step(
        pump_name="pump1",
        inlet=1,          # Buffer inlet
        outlet=12,        # To column
        volume_ml=2.0,    # 2mL
        flow_rate_ml_min=2.0,
        prime=True        # Prime first
    )
    print(f"   Result: {'✓ Success' if success else '✗ Failed'}")
    
    print("\n2. Load sample onto column...")
    success = system.process_step(
        pump_name="pump1",
        inlet=2,          # Sample inlet
        outlet=12,        # To column
        volume_ml=1.0,    # 1mL sample
        flow_rate_ml_min=0.5  # Slow for loading
    )
    print(f"   Result: {'✓ Success' if success else '✗ Failed'}")
    
    print("\n3. Wash column...")
    success = system.process_step(
        pump_name="pump2",
        inlet=3,          # Wash buffer
        outlet=11,        # To waste (bypass)
        volume_ml=5.0,    # 5mL wash
        flow_rate_ml_min=2.0
    )
    print(f"   Result: {'✓ Success' if success else '✗ Failed'}")
    
    print("\n4. Elute protein...")
    success = system.process_step(
        pump_name="pump3",
        inlet=4,          # Elution buffer
        outlet=12,        # To fraction collector
        volume_ml=3.0,    # 3mL elution
        flow_rate_ml_min=1.0
    )
    print(f"   Result: {'✓ Success' if success else '✗ Failed'}")
    
    # Show final status
    print("\n5. Final system status:")
    status = system.get_system_status()
    
    print("   Column tracking:")
    col_info = status['columns']['column1']
    print(f"     Cycles run: {col_info['cycles_run']}")
    print(f"     Total volume processed: {col_info['total_volume_ml']}mL")
    print(f"     Equilibrated: {col_info['is_equilibrated']}")
    
    # Disconnect
    system.disconnect_all()
    print("\n   ✓ System disconnected")

def demo_flexible_process():
    """Demonstrate the flexibility of the process_step method"""
    print("\n" + "="*60)
    print("Demonstrating Flexible Process Steps")
    print("="*60)
    
    print("\nThe process_step method is very flexible:")
    print("  - Any pump (pump1, pump2, pump3)")
    print("  - Any inlet valve (1-10)")
    print("  - Any outlet valve (11=bypass/waste, 12=output/collector)")
    print("  - Any volume and flow rate")
    print("  - Optional priming")
    print("  - Wait or non-blocking operation")
    
    print("\nExample configurations:")
    
    examples = [
        {
            'description': 'Prime system with buffer',
            'pump': 'pump1', 'inlet': 1, 'outlet': 12, 
            'volume': 1.0, 'flow_rate': 2.0, 'prime': True
        },
        {
            'description': 'Load sample slowly',
            'pump': 'pump1', 'inlet': 2, 'outlet': 12,
            'volume': 0.5, 'flow_rate': 0.2, 'prime': False
        },
        {
            'description': 'Fast wash to waste',
            'pump': 'pump2', 'inlet': 3, 'outlet': 11,
            'volume': 10.0, 'flow_rate': 5.0, 'prime': False
        },
        {
            'description': 'Gradient elution',
            'pump': 'pump3', 'inlet': 4, 'outlet': 12,
            'volume': 2.0, 'flow_rate': 0.5, 'prime': False
        }
    ]
    
    for i, ex in enumerate(examples, 1):
        print(f"\n{i}. {ex['description']}:")
        print(f"   system.process_step(")
        print(f"       pump_name='{ex['pump']}',")
        print(f"       inlet={ex['inlet']}, outlet={ex['outlet']},")
        print(f"       volume_ml={ex['volume']}, flow_rate_ml_min={ex['flow_rate']},")
        print(f"       prime={ex['prime']}")
        print(f"   )")

if __name__ == "__main__":
    print("\n" + "#"*60)
    print("# IMPROVED SYSTEM TEST SUITE")
    print("#"*60)
    
    # Run tests
    test_system_basic_operations()
    test_process_steps()
    demo_flexible_process()
    
    print("\n" + "#"*60)
    print("# TESTS COMPLETE")
    print("#"*60)