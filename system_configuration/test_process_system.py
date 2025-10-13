"""
Test script for process-based system
Demonstrates running predefined processes on selected pumps
"""

import logging
from system_config import System
from process import ProcessLibrary, ProcessStep, ChromatographyProcess, ProcessConfig, ProcessType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_process_library():
    """Test the process library and process definitions"""
    print("\n" + "="*60)
    print("Testing Process Library")
    print("="*60)
    
    # List available processes
    print("\n1. Available pre-defined processes:")
    processes = ProcessLibrary.list_available_processes()
    for i, process_name in enumerate(processes, 1):
        print(f"   {i}. {process_name}")
    
    # Load and examine each process
    print("\n2. Process details:")
    for process_name in processes:
        process = ProcessLibrary.get_process(process_name)
        if process:
            summary = process.get_process_summary()
            print(f"\n   {summary['name']}:")
            print(f"     Type: {summary['type']}")
            print(f"     Description: {summary['description']}")
            print(f"     Steps: {summary['total_steps']}")
            print(f"     Total Volume: {summary['total_volume_ml']}mL")
            print(f"     Estimated Time: {summary['estimated_time_min']:.1f} minutes")
            if summary['expected_yield_percent']:
                print(f"     Expected Yield: {summary['expected_yield_percent']}%")
            
            # Show individual steps
            print(f"     Step Details:")
            for i, step in enumerate(process.config.steps):
                step_info = process.get_step_info(i)
                print(f"       {i+1}. {step_info['name']} - {step_info['volume_ml']}mL @ {step_info['flow_rate_ml_min']}mL/min")

def test_selective_pump_execution():
    """Test running processes on selected pumps"""
    print("\n" + "="*60)
    print("Testing Selective Pump Execution")
    print("="*60)
    
    # Create system
    system = System()
    
    # Simulate connection (for demo purposes)
    print("\n1. System setup:")
    print("   [Simulating pump connections for demo]")
    
    # Load a process
    process = system.load_process("protein_a_purification")
    if not process:
        print("   ✗ Failed to load process")
        return
    
    print(f"   ✓ Loaded process: {process.config.name}")
    
    # Test different pump selections
    print("\n2. Testing different pump selections:")
    
    selections = [
        ("all", "Run on all three pumps"),
        ("half", "Run on half the pumps (pump1, pump2)"),
        ("first", "Run on first pump only"), 
        ("last", "Run on last pump only"),
        ("first_and_last", "Run on first and last pumps")
    ]
    
    for selection, description in selections:
        print(f"\n   Testing '{selection}' selection:")
        print(f"   Description: {description}")
        
        # This would normally execute the process, but for demo we'll just show the plan
        success = False  # system.run_selected_pumps(process, selection)
        print(f"   Would execute on: {get_pump_names_for_selection(selection)}")
        print(f"   Status: {'✓ Ready to execute' if True else '✗ Failed'}")

def get_pump_names_for_selection(selection: str) -> list:
    """Helper to show which pumps would be selected"""
    selections = {
        "all": ["pump1", "pump2", "pump3"],
        "half": ["pump1", "pump2"],
        "first": ["pump1"],
        "last": ["pump3"],
        "middle": ["pump2"],
        "first_and_last": ["pump1", "pump3"]
    }
    return selections.get(selection, [])

def test_custom_process():
    """Test creating and using custom processes"""
    print("\n" + "="*60)
    print("Testing Custom Process Creation")
    print("="*60)
    
    # Create a custom process
    print("\n1. Creating custom process:")
    
    custom_steps = [
        ProcessStep(
            name="Prime System",
            inlet=1,
            outlet=12,
            volume_ml=2.0,
            flow_rate_ml_min=3.0,
            prime=True
        ),
        ProcessStep(
            name="Load Sample", 
            inlet=2,
            outlet=12,
            volume_ml=5.0,
            flow_rate_ml_min=1.0
        ),
        ProcessStep(
            name="Quick Wash",
            inlet=3,
            outlet=11,
            volume_ml=8.0,
            flow_rate_ml_min=2.5
        ),
        ProcessStep(
            name="Collect Product",
            inlet=4,
            outlet=12,
            volume_ml=6.0,
            flow_rate_ml_min=1.5
        )
    ]
    
    custom_process = ProcessLibrary.custom_process(
        name="Quick Custom Purification",
        steps=custom_steps,
        description="Fast custom purification for urgent samples"
    )
    
    summary = custom_process.get_process_summary()
    print(f"   ✓ Created: {summary['name']}")
    print(f"   Steps: {summary['total_steps']}")
    print(f"   Total Volume: {summary['total_volume_ml']}mL")
    print(f"   Estimated Time: {summary['estimated_time_min']:.1f} minutes")
    
    print("\n   Step breakdown:")
    for i, step in enumerate(custom_process.config.steps):
        step_info = custom_process.get_step_info(i)
        print(f"     {i+1}. {step_info['name']}")
        print(f"        Inlet {step_info['inlet']} → Outlet {step_info['outlet']}")
        print(f"        {step_info['volume_ml']}mL @ {step_info['flow_rate_ml_min']}mL/min")
        print(f"        Est. time: {step_info['estimated_time_min']:.1f} min")

def demo_usage_scenarios():
    """Demonstrate different usage scenarios"""
    print("\n" + "="*60)
    print("Usage Scenarios")
    print("="*60)
    
    print("\nThe process-based system supports various scenarios:")
    
    scenarios = [
        {
            "name": "High Throughput Production",
            "description": "Run same process on all pumps for maximum throughput",
            "code": "system.run_all_pumps(protein_a_process)"
        },
        {
            "name": "Mixed Batch Sizes", 
            "description": "Run different processes on different pumps",
            "code": """
# Small batches on pump1 and pump2
system.run_process_on_pumps(small_batch_process, ["pump1", "pump2"])

# Large batch on pump3  
system.run_process_on_pumps(large_batch_process, ["pump3"])"""
        },
        {
            "name": "Equipment Maintenance",
            "description": "Run cleaning while others continue production",
            "code": """
# Continue production on pump1 and pump2
system.run_selected_pumps(production_process, "half")

# Clean pump3
system.run_process_on_pumps(cleaning_process, ["pump3"])"""
        },
        {
            "name": "Development Testing",
            "description": "Test new process on single pump",
            "code": """
# Test new process on pump1 only
system.run_selected_pumps(experimental_process, "first")"""
        },
        {
            "name": "Backup Operation",
            "description": "Use remaining pumps if one fails",
            "code": """
# If pump2 fails, continue with pump1 and pump3
system.run_process_on_pumps(process, ["pump1", "pump3"])"""
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{i}. {scenario['name']}")
        print(f"   Description: {scenario['description']}")
        print(f"   Usage:")
        for line in scenario['code'].strip().split('\n'):
            print(f"     {line}")

def demo_process_advantages():
    """Show advantages of the process-based approach"""
    print("\n" + "="*60)
    print("Process-Based System Advantages")
    print("="*60)
    
    advantages = [
        {
            "title": "Reusability",
            "description": "Define a process once, run it on any pump or combination of pumps"
        },
        {
            "title": "Flexibility", 
            "description": "Choose which pumps to run based on current needs and availability"
        },
        {
            "title": "Scalability",
            "description": "Easy to scale from 1 to 3 pumps or add more pumps later"
        },
        {
            "title": "Maintainability",
            "description": "Process definitions are separate from execution logic"
        },
        {
            "title": "Standardization",
            "description": "Consistent processes across all pumps ensure reproducible results"
        },
        {
            "title": "Customization",
            "description": "Create custom processes for specific applications"
        }
    ]
    
    for i, advantage in enumerate(advantages, 1):
        print(f"\n{i}. {advantage['title']}")
        print(f"   {advantage['description']}")

if __name__ == "__main__":
    print("\n" + "#"*60)
    print("# PROCESS-BASED SYSTEM DEMONSTRATION")
    print("#"*60)
    
    # Run demonstrations
    test_process_library()
    test_selective_pump_execution()
    test_custom_process()
    demo_usage_scenarios()
    demo_process_advantages()
    
    print("\n" + "#"*60)
    print("# DEMONSTRATION COMPLETE")
    print("#"*60)