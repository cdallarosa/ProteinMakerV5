"""
Simple Mock Process Runner for Testing
Run a single mock chromatography process on pump at COM12
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from system_configuration.pump.pump_class import Pump, PumpConfig
from system_configuration.process import ProcessLibrary, ProcessStep, ProcessConfig, ChromatographyProcess, ProcessType
from system_configuration.process_runner import ProcessRunner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimplifiedSystem:
    """Simplified system for single pump testing"""
    
    def __init__(self):
        self.pump_config = PumpConfig(
            port="COM12",
            address=1,
            syringe_size_ml=5.0
        )
        self.pump1 = Pump(self.pump_config)
        self.pumps = {"pump1": self.pump1}
        self.is_connected = False
        self.is_initialized = False
        
    def connect_all(self) -> bool:
        """Connect to pump"""
        logger.info("Connecting to pump...")
        self.is_connected = self.pump1.connect(verify_device=True)
        if self.is_connected:
            logger.info("Pump connected successfully")
        else:
            logger.error("Failed to connect to pump")
        return self.is_connected
        
    def initialize_all(self) -> bool:
        """Initialize pump"""
        if not self.is_connected:
            logger.error("Pump not connected")
            return False
            
        logger.info("Initializing pump...")
        self.is_initialized = self.pump1.initialize(wait=True)
        if self.is_initialized:
            logger.info("Pump initialized successfully")
        else:
            logger.error("Failed to initialize pump")
        return self.is_initialized
        
    def get_pump(self, pump_name: str):
        """Get pump by name"""
        return self.pumps.get(pump_name)
        
    def process_step(self, pump_name: str, inlet: int, outlet: int,
                    volume_ml: float, flow_rate_ml_min: float = 1.0,
                    prime: bool = False, wait: bool = False) -> bool:
        """Execute a single process step"""
        pump = self.pumps.get(pump_name)
        if not pump or not pump.is_connected():
            logger.error(f"Pump {pump_name} not available")
            return False
            
        logger.info(f"Executing: {volume_ml}mL from inlet {inlet} to outlet {outlet} @ {flow_rate_ml_min}mL/min")
        
        try:
            if prime:
                logger.info("Priming...")
                pump.prime(inlet=inlet, outlet=outlet, volume_ml=0.5, 
                          flow_rate_ml_min=2.0, wait=True)
            
            # Execute main operation
            volume_ul = volume_ml * 1000
            success = pump.continuous_pump(
                volume_ul=volume_ul,
                flowrate_ul_min=flow_rate_ml_min * 1000,
                inlet=inlet,
                outlet=outlet,
                wait=wait
            )
            
            if success:
                logger.info("Step completed successfully")
            return success
            
        except Exception as e:
            logger.error(f"Error during process step: {e}")
            return False


def create_simple_test_process() -> ChromatographyProcess:
    """Create a simple test process with minimal steps"""
    # Using 3-position valve: I=Input, O=Output, B=Bypass/Waste
    # Mapping: I=1, O=2, B=3
    steps = [
        ProcessStep(
            name="Equilibration",
            inlet=1,  # I (Input)
            outlet=3,  # B (Bypass/Waste)
            volume_ml=2.0,  # Small volume for testing
            flow_rate_ml_min=1.0,  # 1 mL/min as requested
            prime=True
        ),
        ProcessStep(
            name="Sample Loading", 
            inlet=1,  # I (Input)
            outlet=2,  # O (Output)
            volume_ml=3.0,
            flow_rate_ml_min=1.0,  # 1 mL/min
            delay_after_sec=2  # Short delay
        ),
        ProcessStep(
            name="Wash",
            inlet=1,  # I (Input)
            outlet=3,  # B (Bypass/Waste)
            volume_ml=2.0,
            flow_rate_ml_min=1.0  # 1 mL/min
        )
    ]
    
    config = ProcessConfig(
        name="Simple Test Process",
        process_type=ProcessType.CUSTOM,
        description="Minimal process for testing pump operation",
        steps=steps,
        total_time_min=5.0
    )
    
    return ChromatographyProcess(config)


def main():
    """Main execution"""
    print("\n" + "="*70)
    print("MOCK PROCESS RUNNER - PROTOTYPE TEST")
    print("="*70 + "\n")
    
    # Create simplified system
    print("Creating system...")
    system = SimplifiedSystem()
    
    # Connect to pump
    print("\n1. Connecting to pump on COM12...")
    if not system.connect_all():
        print("Failed to connect. Please check:")
        print("  - Pump is powered on")
        print("  - USB cable is connected")
        print("  - COM12 is the correct port")
        return
        
    # Initialize pump
    print("\n2. Initializing pump...")
    if not system.initialize_all():
        print("Failed to initialize pump")
        return
        
    # Create test process
    print("\n3. Creating test process...")
    process = create_simple_test_process()
    
    print(f"\nProcess: {process.config.name}")
    print(f"Description: {process.config.description}")
    print(f"Total steps: {len(process.config.steps)}")
    print(f"Estimated time: {process.get_total_time_estimate():.1f} minutes")
    print(f"Total volume: {process.get_total_volume():.1f} mL")
    
    print("\nSteps to execute:")
    valve_map = {1: "I (Input)", 2: "O (Output)", 3: "B (Bypass/Waste)"}
    for i, step in enumerate(process.config.steps):
        print(f"  {i+1}. {step.name}: {step.volume_ml}mL @ {step.flow_rate_ml_min}mL/min")
        print(f"      Valve: {valve_map[step.inlet]} -> {valve_map[step.outlet]}")
        
    # Ask user to continue
    input("\nPress Enter to start the process (Ctrl+C to cancel)...")
    
    # Run process
    print("\n4. Running process...")
    print("-"*70)
    
    runner = ProcessRunner(system)
    results = runner.run_process(
        process=process,
        pump_names=["pump1"],
        show_progress=True,
        progress_update_interval=1.0
    )
    
    # Show results
    print("\n" + "="*70)
    print("RESULTS:")
    print("="*70)
    for pump_name, success in results.items():
        status = "✓ SUCCESS" if success else "✗ FAILED"
        print(f"{pump_name}: {status}")
        
    print("\nPrototype test complete!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()