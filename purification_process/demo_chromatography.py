"""
Demo script showing how to use the enhanced chromatography process system
"""

import os
import json
from chromatography_process import ChromatographyProcess, ChromatographyStepLibrary, ChromatographyStep, StepType


def demo_dictionary_based_process():
    """Demonstrate creating a process from a dictionary"""
    print("🔬 DEMO: Dictionary-Based Process Creation")
    print("=" * 50)
    
    # Define a simple process using dictionary
    process_config = {
        "process_name": "Demo Dictionary Process",
        "steps": [
            {
                "step_name": "Prime Lines",
                "step_type": "prime",
                "volume": 1000,
                "flowrate": 2000,
                "inlet_valve": 1,
                "outlet_valve": 1,
                "prime_pump": true,
                "prime_volume": 500,
                "description": "Prime all lines before starting"
            },
            {
                "step_name": "Sample Transfer",
                "step_type": "sample_application",
                "volume": 2500,
                "flowrate": 800,
                "inlet_valve": 2,
                "outlet_valve": 2,
                "prime_pump": false,
                "description": "Transfer sample from inlet 2 to outlet 2"
            },
            {
                "step_name": "Cleanup",
                "step_type": "cleaning",
                "volume": 1500,
                "flowrate": 1500,
                "inlet_valve": 3,
                "outlet_valve": 1,
                "prime_pump": true,
                "prime_volume": 200,
                "description": "Clean system with wash buffer"
            }
        ]
    }
    
    # Create process from dictionary
    process = ChromatographyProcess.from_dict(process_config)
    
    # Generate report without running
    print("📋 Process Report Preview:")
    report = process.generate_process_report(save_to_file=False)
    print(report[:500] + "...\n")  # Show first 500 chars
    
    return process


def demo_json_process_loading():
    """Demonstrate loading a process from JSON file"""
    print("📂 DEMO: Loading Process from JSON")
    print("=" * 50)
    
    # Load from example processes
    json_file = os.path.join(os.path.dirname(__file__), 'example_processes.json')
    
    with open(json_file, 'r') as f:
        all_processes = json.load(f)
    
    # Load the quick test process
    quick_test_config = all_processes['quick_test']
    process = ChromatographyProcess.from_dict(quick_test_config)
    
    print(f"Loaded process: {process.process_name}")
    print(f"Number of steps: {len(process.steps)}")
    
    for i, step in enumerate(process.steps, 1):
        print(f"  Step {i}: {step.step_name} - {step.volume}µL @ {step.flowrate}µL/min")
    
    return process


def demo_programmatic_process():
    """Demonstrate creating a process programmatically"""
    print("⚗️ DEMO: Programmatic Process Creation")
    print("=" * 50)
    
    # Create process with custom name
    process = ChromatographyProcess(process_name="Custom Lab Process")
    
    # Add steps using the library
    process.add_step(ChromatographyStepLibrary.create_equilibration_step(
        volume=3000, flowrate=1200, inlet=1, outlet=1
    ))
    
    process.add_step(ChromatographyStepLibrary.create_sample_application_step(
        volume=1500, flowrate=600, inlet=2, outlet=1
    ))
    
    # Add custom step
    custom_step = ChromatographyStep(
        step_name="Custom Gradient",
        step_type=StepType.ELUTION,
        volume=2000,
        flowrate=400,
        inlet_valve=4,
        outlet_valve=2,
        prime_pump=True,
        prime_volume=100,
        description="Custom gradient elution step"
    )
    process.add_step(custom_step)
    
    # Add cleaning step
    process.add_step(ChromatographyStepLibrary.create_cleaning_step(
        volume=4000, flowrate=2000, inlet=5, outlet=1
    ))
    
    print(f"Created process: {process.process_name}")
    print(f"Total steps: {len(process.steps)}")
    
    return process


def demo_process_calculations():
    """Demonstrate process calculations and reporting"""
    print("🧮 DEMO: Process Calculations")
    print("=" * 50)
    
    # Create a simple process
    process = ChromatographyProcess(process_name="Calculation Demo")
    
    # Add a step with known parameters
    step = ChromatographyStep(
        step_name="Calculation Test",
        step_type=StepType.SAMPLE_APPLICATION,
        volume=5000,  # 5 mL - larger than syringe
        flowrate=1000,  # 1 mL/min
        inlet_valve=1,
        outlet_valve=2,
        prime_pump=True,
        prime_volume=500,
        description="Test step for calculation demonstration"
    )
    process.add_step(step)
    
    # Calculate parameters
    params = process.calculate_step_parameters(step)
    
    print("Step Parameters:")
    print(f"  Volume: {step.volume} µL ({params['volume_ml']:.3f} mL)")
    print(f"  Flow Rate: {step.flowrate} µL/min ({params['flowrate_ml_min']:.3f} mL/min)")
    print(f"  Syringe Size: {params['syringe_size_ml']} mL")
    print(f"  Steps Required: {params['steps_needed']:,}")
    print(f"  Pump Speed: {params['pump_speed_steps_per_sec']:,} steps/sec")
    print(f"  Cycles: {params['cycles']}")
    print(f"  Remaining Steps: {params['remaining_steps']:,}")
    print(f"  Estimated Time: {params['estimated_time_min']:.2f} minutes")
    
    if params['prime_parameters']:
        prime = params['prime_parameters']
        print(f"  Prime Steps: {prime['steps']:,}")
        print(f"  Prime Time: {prime['estimated_time']:.1f} seconds")
    
    return process


def demo_save_and_load():
    """Demonstrate saving and loading processes"""
    print("💾 DEMO: Save and Load Process")
    print("=" * 50)
    
    # Create a process
    process = ChromatographyProcess(process_name="Save Demo Process")
    process.create_standard_purification_process()
    
    # Save to JSON
    save_path = os.path.join(os.path.dirname(__file__), 'demo_saved_process.json')
    process.save_to_json(save_path)
    
    # Load it back
    loaded_process = ChromatographyProcess.load_from_json(save_path)
    
    print(f"Original: {process.process_name} - {len(process.steps)} steps")
    print(f"Loaded: {loaded_process.process_name} - {len(loaded_process.steps)} steps")
    
    # Clean up
    if os.path.exists(save_path):
        os.remove(save_path)
        print("Demo file cleaned up")
    
    return loaded_process


def interactive_demo_menu():
    """Interactive demo menu"""
    print("\n" + "=" * 60)
    print("🧪 CHROMATOGRAPHY PROCESS SYSTEM DEMO")
    print("=" * 60)
    
    demos = {
        '1': ("Dictionary-Based Process", demo_dictionary_based_process),
        '2': ("JSON Process Loading", demo_json_process_loading),
        '3': ("Programmatic Creation", demo_programmatic_process),
        '4': ("Process Calculations", demo_process_calculations),
        '5': ("Save and Load", demo_save_and_load),
    }
    
    print("\nAvailable Demos:")
    for key, (name, func) in demos.items():
        print(f"  {key}. {name}")
    print("  6. Run All Demos")
    print("  q. Quit")
    
    while True:
        choice = input("\nSelect demo (1-6, q): ").strip().lower()
        
        if choice == 'q':
            print("👋 Demo complete!")
            break
        elif choice in demos:
            print(f"\n🔬 Running: {demos[choice][0]}")
            try:
                process = demos[choice][1]()
                
                # Ask if user wants to see full report
                if input("\nShow full process report? (y/n): ").lower() == 'y':
                    report = process.generate_process_report(save_to_file=False)
                    print("\n" + report)
                
                # Ask if user wants to simulate running the process
                if input("\nSimulate running this process? (y/n): ").lower() == 'y':
                    print("\n⚠️  SIMULATION MODE - No actual pump commands will be sent")
                    print("Press Ctrl+C to stop simulation\n")
                    try:
                        # In a real scenario, you'd connect to the actual pump
                        # For demo, we'll just show what would happen
                        print("📋 Process would execute the following steps:")
                        for i, step in enumerate(process.steps, 1):
                            params = process.calculate_step_parameters(step)
                            print(f"\nStep {i}: {step.step_name}")
                            print(f"  Volume: {step.volume:,} µL")
                            print(f"  Flow Rate: {step.flowrate:,} µL/min")
                            print(f"  Estimated Time: {params['estimated_time_min']:.2f} min")
                            if step.prime_pump:
                                print(f"  Prime: {step.prime_volume:,} µL")
                        print("\n✅ Simulation complete!")
                    except KeyboardInterrupt:
                        print("\n🛑 Simulation stopped by user")
                
            except Exception as e:
                print(f"❌ Demo failed: {e}")
            
            print("\n" + "-" * 40)
        
        elif choice == '6':
            print("\n🚀 Running all demos...")
            for key, (name, func) in demos.items():
                print(f"\n🔬 {name}")
                try:
                    func()
                except Exception as e:
                    print(f"❌ Demo failed: {e}")
                print("-" * 40)
            print("✅ All demos complete!")
        
        else:
            print("❓ Invalid choice. Please select 1-6 or q.")


if __name__ == "__main__":
    # Set up logging to reduce noise during demo
    import logging
    logging.basicConfig(level=logging.WARNING)
    
    print("🧪 Chromatography Process System - Enhanced Demo")
    print("This demo shows the new features:")
    print("  ✅ Console progress display")
    print("  ✅ Interactive process control")
    print("  ✅ Detailed process reports with calculations")
    print("  ✅ Dictionary-based process creation")
    print("  ✅ JSON configuration files")
    print("  ✅ Step parameter calculations")
    
    interactive_demo_menu()