"""
Test script for parallel chromatography system
Demonstrates running 3 independent purification processes simultaneously
"""

import logging
import time
from system_config import System

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_parallel_chromatography():
    """Test running parallel chromatography on all 3 pumps"""
    print("\n" + "="*60)
    print("Testing Parallel Chromatography System")
    print("="*60)
    
    # Create system
    system = System()
    
    # Connect and initialize
    print("\n1. Setting up system...")
    if not (system.connect_all() and system.initialize_all()):
        print("   ✗ Failed to setup system - using simulation mode")
        # Continue with simulation for demo
    
    # Define parallel chromatography configurations
    # Each pump runs its own independent purification
    parallel_configs = {
        "pump1": {
            "inlet": 1,              # Sample inlet 1
            "outlet": 12,            # To fraction collector
            "volume_ml": 10.0,       # 10mL purification
            "flow_rate_ml_min": 1.0, # 1 mL/min
            "prime": True            # Prime before starting
        },
        "pump2": {
            "inlet": 2,              # Sample inlet 2  
            "outlet": 12,            # To fraction collector
            "volume_ml": 8.0,        # 8mL purification
            "flow_rate_ml_min": 1.5, # 1.5 mL/min
            "prime": True            # Prime before starting
        },
        "pump3": {
            "inlet": 3,              # Sample inlet 3
            "outlet": 12,            # To fraction collector  
            "volume_ml": 12.0,       # 12mL purification
            "flow_rate_ml_min": 0.8, # 0.8 mL/min (slower)
            "prime": False           # No priming needed
        }
    }
    
    print("\n2. Configuration for parallel processes:")
    for pump_name, config in parallel_configs.items():
        print(f"   {pump_name}: {config['volume_ml']}mL @ {config['flow_rate_ml_min']}mL/min from inlet {config['inlet']}")
    
    # Start all processes in parallel
    print("\n3. Starting all chromatography processes...")
    if system.run_parallel_chromatography(parallel_configs):
        print("   ✓ All processes started successfully")
        
        # Monitor progress
        print("\n4. Monitoring parallel processes:")
        monitor_parallel_processes(system)
        
    else:
        print("   ✗ Failed to start some processes")
    
    # Cleanup
    system.disconnect_all()
    print("\n5. System disconnected")

def monitor_parallel_processes(system: System, max_duration: int = 300):
    """Monitor parallel processes until completion"""
    start_time = time.time()
    check_interval = 5  # Check every 5 seconds
    
    print(f"   Monitoring for up to {max_duration} seconds...")
    print("   " + "-" * 50)
    
    while True:
        # Get current status
        status = system.get_parallel_status()
        elapsed = time.time() - start_time
        
        # Print status update
        print(f"   Time: {elapsed:6.1f}s | Running: {status['pumps_running']} | Ready: {status['pumps_ready']}")
        
        # Show individual pump status
        for pump_name, pump_status in status['pumps'].items():
            state = pump_status['state']
            pos = pump_status.get('position', 0)
            print(f"     {pump_name}: {state:12} (pos: {pos:4})")
        
        # Check if all done or timeout
        if status['pumps_running'] == 0:
            print("\n   ✓ All processes completed!")
            break
        elif elapsed > max_duration:
            print("\n   ⚠ Monitoring timeout reached")
            break
        else:
            print("   " + "-" * 50)
            time.sleep(check_interval)

def demo_parallel_workflow():
    """Demonstrate a complete parallel workflow"""
    print("\n" + "="*60)
    print("Parallel Chromatography Workflow Demo")
    print("="*60)
    
    print("\nThis system enables:")
    print("  • 3 independent purification processes running simultaneously")
    print("  • Each pump controls its own chromatography column")
    print("  • Different samples, volumes, and flow rates per pump")
    print("  • Parallel processing dramatically increases throughput")
    
    print("\nTypical workflow:")
    print("  1. Connect and initialize all pumps")
    print("  2. Configure each pump's purification parameters")
    print("  3. Start all processes simultaneously (non-blocking)")
    print("  4. Monitor progress of all pumps in real-time")
    print("  5. Handle completion or errors independently per pump")
    
    print("\nExample configurations:")
    
    examples = [
        {
            "scenario": "High-throughput screening",
            "pump1": "Sample A - 5mL @ 2.0 mL/min",
            "pump2": "Sample B - 5mL @ 2.0 mL/min", 
            "pump3": "Sample C - 5mL @ 2.0 mL/min"
        },
        {
            "scenario": "Different sample sizes",
            "pump1": "Large batch - 20mL @ 1.0 mL/min",
            "pump2": "Medium batch - 10mL @ 1.5 mL/min",
            "pump3": "Small batch - 5mL @ 2.0 mL/min"
        },
        {
            "scenario": "Mixed protocols",
            "pump1": "Standard purification - 10mL @ 1.0 mL/min",
            "pump2": "Fast wash - 15mL @ 3.0 mL/min",
            "pump3": "Gentle elution - 8mL @ 0.5 mL/min"
        }
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"\n{i}. {example['scenario']}:")
        print(f"   Pump 1: {example['pump1']}")
        print(f"   Pump 2: {example['pump2']}")
        print(f"   Pump 3: {example['pump3']}")

def calculate_throughput_improvement():
    """Calculate throughput improvement with parallel processing"""
    print("\n" + "="*60)
    print("Throughput Analysis")
    print("="*60)
    
    # Example purification times
    purifications = [
        {"name": "Sample A", "volume_ml": 10, "rate_ml_min": 1.0},
        {"name": "Sample B", "volume_ml": 8, "rate_ml_min": 1.5},
        {"name": "Sample C", "volume_ml": 12, "rate_ml_min": 0.8}
    ]
    
    # Calculate sequential vs parallel times
    sequential_time = 0
    max_parallel_time = 0
    
    print("\nPurification parameters:")
    for p in purifications:
        time_min = p["volume_ml"] / p["rate_ml_min"]
        print(f"  {p['name']}: {p['volume_ml']}mL @ {p['rate_ml_min']}mL/min = {time_min:.1f} minutes")
        
        sequential_time += time_min
        max_parallel_time = max(max_parallel_time, time_min)
    
    print(f"\nTime comparison:")
    print(f"  Sequential (one pump): {sequential_time:.1f} minutes")
    print(f"  Parallel (three pumps): {max_parallel_time:.1f} minutes")
    print(f"  Time savings: {sequential_time - max_parallel_time:.1f} minutes")
    print(f"  Throughput improvement: {sequential_time / max_parallel_time:.1f}x faster")

if __name__ == "__main__":
    print("\n" + "#"*60)
    print("# PARALLEL CHROMATOGRAPHY SYSTEM TEST")
    print("#"*60)
    
    # Run demonstrations
    test_parallel_chromatography()
    demo_parallel_workflow()
    calculate_throughput_improvement()
    
    print("\n" + "#"*60)
    print("# PARALLEL TESTING COMPLETE")
    print("#"*60)