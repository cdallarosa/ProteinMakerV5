"""
Chromatography Process Control System
Manages chromatography steps with configurable parameters and automated process execution
"""

import time
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum
import sys
import os
import threading
import json
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from system_configuration.pump.pump_commands import PumpCommands
logger = logging.getLogger(__name__)


class StepType(Enum):
    EQUILIBRATION = "equilibration"
    SAMPLE_APPLICATION = "sample_application"
    WASH = "wash"
    ELUTION = "elution"
    CLEANING = "cleaning"
    PRIME = "prime"


@dataclass
class ChromatographyStep:
    """
    Represents a single chromatography step with configurable parameters
    """
    step_name: str
    step_type: StepType
    volume: float  # Volume in microliters (µL)
    flowrate: float  # Flow rate in µL/min
    inlet_valve: int  # Inlet valve position (1-10)
    outlet_valve: int  # Outlet valve position (1-2)
    prime_pump: bool = False  # Whether to prime the pump before this step
    prime_volume: Optional[float] = None  # Prime volume in µL (if different from step volume)
    wait_until_complete: bool = True  # Wait for step completion before proceeding
    timeout: Optional[int] = None  # Timeout in seconds (auto-calculated if None)
    description: str = ""  # Human-readable description of the step
    
    def __post_init__(self):
        if self.prime_pump and self.prime_volume is None:
            self.prime_volume = min(1000.0, self.volume * 0.1)  # Default prime volume
        
        # Auto-calculate timeout if not provided
        if self.timeout is None:
            self.timeout = self.calculate_timeout()
    
    def calculate_timeout(self, safety_factor: float = 3.0, min_timeout: int = 60) -> int:
        """
        Calculate optimal timeout based on volume, flowrate, and prime settings
        
        Args:
            safety_factor: Multiply estimated time by this factor for safety (default 3.0)
            min_timeout: Minimum timeout in seconds (default 60)
            
        Returns:
            int: Calculated timeout in seconds
        """
        # Calculate main operation time
        # Volume (µL) / Flow rate (µL/min) = time in minutes
        main_time_min = self.volume / self.flowrate
        main_time_sec = main_time_min * 60
        
        # Add prime time if applicable
        prime_time_sec = 0
        if self.prime_pump and self.prime_volume:
            # Assume prime at default aspirate speed (2000 steps/sec)
            # This is approximate - will be refined when pump is available
            prime_time_min = self.prime_volume / 2000  # Rough estimate
            prime_time_sec = prime_time_min * 60
        
        # Calculate total time with safety factor
        total_estimated_time = main_time_sec + prime_time_sec
        calculated_timeout = int(total_estimated_time * safety_factor)
        
        # Ensure minimum timeout
        return max(calculated_timeout, min_timeout)


class ChromatographyStepLibrary:
    """
    Library of pre-defined chromatography steps for common operations
    """
    
    @staticmethod
    def create_equilibration_step(volume: float = 5000, flowrate: float = 1000, 
                                inlet: int = 1, outlet: int = 1) -> ChromatographyStep:
        """Create an equilibration step"""
        return ChromatographyStep(
            step_name="Equilibration",
            step_type=StepType.EQUILIBRATION,
            volume=volume,
            flowrate=flowrate,
            inlet_valve=inlet,
            outlet_valve=outlet,
            prime_pump=True,
            description=f"Equilibrate column with {volume}µL at {flowrate}µL/min"
        )
    
    @staticmethod
    def create_sample_application_step(volume: float = 2000, flowrate: float = 500,
                                     inlet: int = 2, outlet: int = 1) -> ChromatographyStep:
        """Create a sample application step"""
        return ChromatographyStep(
            step_name="Sample Application",
            step_type=StepType.SAMPLE_APPLICATION,
            volume=volume,
            flowrate=flowrate,
            inlet_valve=inlet,
            outlet_valve=outlet,
            prime_pump=True,
            description=f"Apply {volume}µL sample at {flowrate}µL/min"
        )
    
    @staticmethod
    def create_wash_step(volume: float = 3000, flowrate: float = 1000,
                        inlet: int = 3, outlet: int = 1, wash_name: str = "Wash") -> ChromatographyStep:
        """Create a wash step"""
        return ChromatographyStep(
            step_name=wash_name,
            step_type=StepType.WASH,
            volume=volume,
            flowrate=flowrate,
            inlet_valve=inlet,
            outlet_valve=outlet,
            prime_pump=False,
            description=f"{wash_name} with {volume}µL at {flowrate}µL/min"
        )
    
    @staticmethod
    def create_elution_step(volume: float = 2000, flowrate: float = 500,
                          inlet: int = 4, outlet: int = 2) -> ChromatographyStep:
        """Create an elution step"""
        return ChromatographyStep(
            step_name="Elution",
            step_type=StepType.ELUTION,
            volume=volume,
            flowrate=flowrate,
            inlet_valve=inlet,
            outlet_valve=outlet,
            prime_pump=True,
            description=f"Elute with {volume}µL at {flowrate}µL/min"
        )
    
    @staticmethod
    def create_cleaning_step(volume: float = 5000, flowrate: float = 2000,
                           inlet: int = 5, outlet: int = 1) -> ChromatographyStep:
        """Create a cleaning step"""
        return ChromatographyStep(
            step_name="Cleaning",
            step_type=StepType.CLEANING,
            volume=volume,
            flowrate=flowrate,
            inlet_valve=inlet,
            outlet_valve=outlet,
            prime_pump=True,
            description=f"Clean with {volume}µL at {flowrate}µL/min"
        )


class ChromatographyProcess:
    """
    Main chromatography process controller that manages step execution
    """
    
    def __init__(self, pump: Optional[PumpCommands] = None, process_name: str = "Chromatography Process"):
        """
        Initialize chromatography process
        
        Args:
            pump: PumpCommands instance (if None, creates new instance)
            process_name: Name of the process for reporting
        """
        self.pump = pump if pump else PumpCommands()
        self.process_name = process_name
        self.steps: List[ChromatographyStep] = []
        self.current_step_index = 0
        self.is_running = False
        self.is_paused = False
        self.stop_requested = False
        self.execution_log: List[Dict[str, Any]] = []
        self.console_monitor_thread = None
        self.step_start_time = None
        self.process_start_time = None
        
    def add_step(self, step: ChromatographyStep) -> None:
        """Add a step to the process"""
        self.steps.append(step)
        logger.info(f"Added step: {step.step_name} ({step.step_type.value})")
    
    def update_step_timeouts(self) -> None:
        """
        Update all step timeouts based on pump parameters and calculated timing
        Call this after pump is connected to get accurate timeout calculations
        """
        if not self.pump:
            logger.warning("No pump available for timeout calculations")
            return
        
        for step in self.steps:
            try:
                params = self.calculate_step_parameters(step)
                old_timeout = step.timeout
                step.timeout = params['optimal_timeout_sec']
                logger.info(f"Updated timeout for '{step.step_name}': {old_timeout}s → {step.timeout}s")
            except Exception as e:
                logger.warning(f"Could not update timeout for '{step.step_name}': {e}")
    
    def add_steps(self, steps: List[ChromatographyStep]) -> None:
        """Add multiple steps to the process"""
        for step in steps:
            self.add_step(step)
    
    def create_standard_purification_process(self) -> None:
        """Create a standard protein purification process"""
        steps = [
            ChromatographyStepLibrary.create_equilibration_step(
                volume=5000, flowrate=1000, inlet=1, outlet=1
            ),
            ChromatographyStepLibrary.create_sample_application_step(
                volume=2000, flowrate=500, inlet=2, outlet=1
            ),
            ChromatographyStepLibrary.create_wash_step(
                volume=3000, flowrate=1000, inlet=3, outlet=1, wash_name="Wash Buffer"
            ),
            ChromatographyStepLibrary.create_elution_step(
                volume=2000, flowrate=500, inlet=4, outlet=2
            ),
            ChromatographyStepLibrary.create_cleaning_step(
                volume=5000, flowrate=2000, inlet=5, outlet=1
            )
        ]
        self.add_steps(steps)
        logger.info("Created standard purification process with 5 steps")
    
    def connect_pump(self) -> bool:
        """Connect to the pump"""
        if not self.pump.is_connected:
            success = self.pump.connect()
            if success:
                self.pump.initialize_pump()
                # Update step timeouts based on actual pump parameters
                self.update_step_timeouts()
                logger.info("Pump connected, initialized, and timeouts updated")
                return True
            else:
                logger.error("Failed to connect to pump")
                return False
        return True
    
    def display_step_progress(self, step: ChromatographyStep, params: Dict[str, Any]):
        """
        Display step progress information
        
        Args:
            step: Current step
            params: Calculated step parameters
        """
        print("\n" + "=" * 60)
        print(f"🧪 EXECUTING: {step.step_name} ({step.step_type.value.title()})")
        print(f"📝 Description: {step.description}")
        print(f"💧 Volume: {step.volume:,.0f} µL ({params['volume_ml']:.3f} mL)")
        print(f"⚡ Flow Rate: {step.flowrate:,.0f} µL/min ({params['flowrate_ml_min']:.3f} mL/min)")
        print(f"🔀 Valves: Inlet={step.inlet_valve}, Outlet={step.outlet_valve}")
        print(f"🔧 Pump Speed: {params['pump_speed_steps_per_sec']:,} steps/sec")
        print(f"📊 Steps Required: {params['steps_needed']:,} steps")
        if params['cycles'] > 0:
            print(f"🔄 Cycles: {params['cycles']} full + {params['remaining_steps']} remaining")
        print(f"⏱️  Estimated Time: {params['estimated_time_min']:.2f} minutes")
        print(f"⏰ Timeout: {step.timeout} seconds (optimal: {params['optimal_timeout_sec']}s)")
        if step.prime_pump:
            print(f"🚰 Prime Volume: {step.prime_volume:,.0f} µL")
        print("=" * 60)
    
    def start_console_monitor(self):
        """
        Start console monitoring thread for user input during process execution
        """
        def monitor_console():
            print("\n" + "=" * 60)
            print("🎛️  PROCESS CONTROL - Available Commands:")
            print("   'p' or 'pause' - Pause the current step")
            print("   'r' or 'resume' - Resume paused step")
            print("   's' or 'stop' - Stop the entire process")
            print("   'status' - Show current status")
            print("=" * 60 + "\n")
            
            while self.is_running:
                try:
                    # Simple Windows-compatible approach
                    time.sleep(0.5)
                        
                except KeyboardInterrupt:
                    print("\n🛑 Keyboard interrupt - stopping process...")
                    self.stop_requested = True
                    self.is_running = False
                    break
                except Exception:
                    pass
        
        self.console_monitor_thread = threading.Thread(target=monitor_console, daemon=True)
        self.console_monitor_thread.start()
    
    def handle_console_command(self, command: str):
        """
        Handle console commands during process execution
        
        Args:
            command: User command string
        """
        if command in ['p', 'pause']:
            if not self.is_paused:
                print("⏸️  Pausing process...")
                self.pause_process()
            else:
                print("⚠️  Process is already paused")
        
        elif command in ['r', 'resume']:
            if self.is_paused:
                print("▶️  Resuming process...")
                self.resume_process()
            else:
                print("⚠️  Process is not paused")
        
        elif command in ['s', 'stop']:
            print("🛑 Stopping process...")
            self.stop_requested = True
            self.stop_process()
        
        elif command == 'status':
            status = self.get_process_status()
            elapsed = time.time() - self.step_start_time if self.step_start_time else 0
            print(f"\n📊 STATUS: Step {status['current_step']+1}/{status['total_steps']} - {status['current_step_name']}")
            print(f"   Running: {status['is_running']}, Paused: {status['is_paused']}")
            print(f"   Step Time: {elapsed:.1f}s, Pump: {'Connected' if status['pump_connected'] else 'Disconnected'}\n")
        
        else:
            print(f"❓ Unknown command: '{command}'. Use 'p', 'r', 's', or 'status'")
    
    def execute_step(self, step: ChromatographyStep) -> bool:
        """
        Execute a single chromatography step
        
        Args:
            step: ChromatographyStep to execute
            
        Returns:
            bool: True if step executed successfully
        """
        if not self.pump.is_connected:
            logger.error("Pump not connected")
            return False
        
        self.step_start_time = time.time()
        
        # Calculate and display step parameters
        params = self.calculate_step_parameters(step)
        self.display_step_progress(step, params)
        
        logger.info(f"Executing step: {step.step_name}")
        logger.info(f"Description: {step.description}")
        
        try:
            # Prime pump if required
            if step.prime_pump:
                logger.info(f"Priming pump with {step.prime_volume}µL")
                prime_success = self.pump.prime_pump(
                    volume=step.prime_volume,
                    inlet=step.inlet_valve,
                    outlet=step.outlet_valve,
                    wait=True,
                    timeout=step.timeout
                )
                if not prime_success:
                    logger.error(f"Failed to prime pump for step: {step.step_name}")
                    return False
            
            # Execute main pump operation
            logger.info(f"Pumping {step.volume}µL at {step.flowrate}µL/min")
            pump_success = self.pump.continuous_pump(
                volume=step.volume,
                flowrate=step.flowrate,
                inlet=step.inlet_valve,
                outlet=step.outlet_valve,
                wait=step.wait_until_complete,
                timeout=step.timeout
            )
            
            if not pump_success:
                logger.error(f"Failed to execute pump operation for step: {step.step_name}")
                return False
            
            step_duration = time.time() - self.step_start_time
            
            print(f"✅ Step '{step.step_name}' completed successfully in {step_duration:.2f}s\n")
            
            # Log execution details
            execution_record = {
                'step_name': step.step_name,
                'step_type': step.step_type.value,
                'volume': step.volume,
                'flowrate': step.flowrate,
                'inlet_valve': step.inlet_valve,
                'outlet_valve': step.outlet_valve,
                'prime_pump': step.prime_pump,
                'duration': step_duration,
                'timestamp': time.time(),
                'success': True
            }
            self.execution_log.append(execution_record)
            
            logger.info(f"Step '{step.step_name}' completed successfully in {step_duration:.2f}s")
            return True
            
        except Exception as e:
            logger.error(f"Error executing step '{step.step_name}': {str(e)}")
            execution_record = {
                'step_name': step.step_name,
                'error': str(e),
                'timestamp': time.time(),
                'success': False
            }
            self.execution_log.append(execution_record)
            return False
    
    def run_process(self, start_from_step: int = 0) -> bool:
        """
        Run the complete chromatography process
        
        Args:
            start_from_step: Index of step to start from (default 0)
            
        Returns:
            bool: True if all steps completed successfully
        """
        if not self.steps:
            logger.error("No steps defined in process")
            return False
        
        if not self.connect_pump():
            logger.error("Failed to connect to pump")
            return False
        
        # Generate and display process report
        print("\n🔍 Generating process report...")
        report = self.generate_process_report(save_to_file=True)
        
        self.is_running = True
        self.stop_requested = False
        self.current_step_index = start_from_step
        self.process_start_time = time.time()
        
        # Start console monitoring for interactive control
        self.start_console_monitor()
        
        print(f"\n🚀 Starting chromatography process: {self.process_name}")
        print(f"📋 Total steps: {len(self.steps)}")
        logger.info(f"Starting chromatography process with {len(self.steps)} steps")
        
        try:
            for i in range(start_from_step, len(self.steps)):
                if not self.is_running or self.stop_requested:
                    print("\n🛑 Process stopped by user")
                    logger.info("Process stopped by user")
                    break
                
                while self.is_paused and not self.stop_requested:
                    print("\r⏸️  Process paused - waiting for resume...", end="", flush=True)
                    time.sleep(1)
                
                if self.stop_requested:
                    break
                
                self.current_step_index = i
                step = self.steps[i]
                
                print(f"\n📍 Starting Step {i+1}/{len(self.steps)}")
                logger.info(f"Step {i+1}/{len(self.steps)}: {step.step_name}")
                
                success = self.execute_step(step)
                if not success:
                    print(f"\n❌ Step {i+1} failed, stopping process")
                    logger.error(f"Step {i+1} failed, stopping process")
                    self.is_running = False
                    return False
                
                # Brief pause between steps
                time.sleep(1)
            
            process_duration = time.time() - self.process_start_time
            print(f"\n🎉 PROCESS COMPLETED SUCCESSFULLY!")
            print(f"⏱️  Total Duration: {process_duration/60:.2f} minutes ({process_duration:.1f} seconds)")
            print(f"📊 Steps Executed: {len(self.steps)}")
            print("=" * 60 + "\n")
            
            logger.info(f"Chromatography process completed successfully in {process_duration:.2f}s")
            self.is_running = False
            return True
            
        except KeyboardInterrupt:
            print("\n🛑 Process interrupted by user (Ctrl+C)")
            self.stop_process()
            return False
        except Exception as e:
            print(f"\n💥 Process failed with error: {str(e)}")
            logger.error(f"Process failed with error: {str(e)}")
            self.is_running = False
            return False
        finally:
            self.is_running = False
    
    def stop_process(self) -> None:
        """Stop the running process"""
        self.is_running = False
        if self.pump.is_connected:
            self.pump.terminate()
        logger.info("Process stopped")
    
    def pause_process(self) -> None:
        """Pause the running process"""
        self.is_paused = True
        if self.pump.is_connected:
            self.pump.pause()
        logger.info("Process paused")
    
    def resume_process(self) -> None:
        """Resume the paused process"""
        self.is_paused = False
        if self.pump.is_connected:
            self.pump.resume()
        logger.info("Process resumed")
    
    def get_process_status(self) -> Dict[str, Any]:
        """Get current process status"""
        return {
            'is_running': self.is_running,
            'is_paused': self.is_paused,
            'current_step': self.current_step_index,
            'total_steps': len(self.steps),
            'current_step_name': self.steps[self.current_step_index].step_name if self.current_step_index < len(self.steps) else None,
            'pump_connected': self.pump.is_connected if self.pump else False
        }
    
    def get_execution_log(self) -> List[Dict[str, Any]]:
        """Get execution log"""
        return self.execution_log.copy()
    
    def clear_steps(self) -> None:
        """Clear all steps from the process"""
        self.steps.clear()
        self.current_step_index = 0
        logger.info("All steps cleared")
    
    def save_process_to_dict(self) -> Dict[str, Any]:
        """Save process configuration to dictionary"""
        return {
            'process_name': self.process_name,
            'creation_date': datetime.now().isoformat(),
            'steps': [
                {
                    'step_name': step.step_name,
                    'step_type': step.step_type.value,
                    'volume': step.volume,
                    'flowrate': step.flowrate,
                    'inlet_valve': step.inlet_valve,
                    'outlet_valve': step.outlet_valve,
                    'prime_pump': step.prime_pump,
                    'prime_volume': step.prime_volume,
                    'wait_until_complete': step.wait_until_complete,
                    'timeout': step.timeout,
                    'description': step.description
                }
                for step in self.steps
            ]
        }
    
    def calculate_step_parameters(self, step: ChromatographyStep) -> Dict[str, Any]:
        """
        Calculate pump parameters for a step
        
        Args:
            step: ChromatographyStep to calculate parameters for
            
        Returns:
            dict: Calculated parameters including steps, speeds, and timing
        """
        # Get pump configuration
        syringe_size_ml = self.pump.syringe_size  # mL
        max_position = self.pump.max_position  # steps
        
        # Calculate steps needed for volume
        volume_ml = step.volume / 1000  # Convert µL to mL
        steps_needed = int((volume_ml / syringe_size_ml) * max_position)
        
        # Calculate pump speed from flowrate
        flowrate_ml_min = step.flowrate / 1000  # Convert µL/min to mL/min
        flowrate_ml_sec = flowrate_ml_min / 60  # Convert to mL/sec
        steps_per_sec = (flowrate_ml_sec / syringe_size_ml) * max_position
        pump_speed = int(steps_per_sec)
        
        # Calculate cycles and remaining if volume > syringe capacity
        cycles = steps_needed // max_position
        remaining_steps = steps_needed % max_position
        
        # Calculate estimated time
        if cycles > 0:
            cycle_time = (max_position / steps_per_sec) * 2  # Fill + dispense
            remaining_time = (remaining_steps / steps_per_sec) if remaining_steps > 0 else 0
            estimated_time = (cycles * cycle_time) + remaining_time
        else:
            estimated_time = steps_needed / steps_per_sec
        
        # Prime calculations
        prime_params = None
        if step.prime_pump:
            prime_volume_ml = step.prime_volume / 1000
            prime_steps = int((prime_volume_ml / syringe_size_ml) * max_position)
            prime_time = prime_steps / self.pump.aspirate_speed
            prime_params = {
                'volume_ml': prime_volume_ml,
                'steps': prime_steps,
                'estimated_time': prime_time
            }
        
        # Calculate optimal timeout with safety margin
        total_time_with_prime = estimated_time
        if prime_params:
            total_time_with_prime += prime_params['estimated_time']
        
        optimal_timeout = int(total_time_with_prime * 2.5)  # 2.5x safety factor
        optimal_timeout = max(optimal_timeout, 60)  # Minimum 60 seconds
        
        return {
            'volume_ml': volume_ml,
            'steps_needed': steps_needed,
            'pump_speed_steps_per_sec': pump_speed,
            'flowrate_ml_min': flowrate_ml_min,
            'cycles': cycles,
            'remaining_steps': remaining_steps,
            'estimated_time_sec': estimated_time,
            'estimated_time_min': estimated_time / 60,
            'syringe_size_ml': syringe_size_ml,
            'max_position_steps': max_position,
            'prime_parameters': prime_params,
            'optimal_timeout_sec': optimal_timeout
        }
    
    def generate_process_report(self, save_to_file: bool = True) -> str:
        """
        Generate detailed process report with calculations
        
        Args:
            save_to_file: If True, save report to file
            
        Returns:
            str: Report content
        """
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append(f"CHROMATOGRAPHY PROCESS REPORT")
        report_lines.append(f"Process Name: {self.process_name}")
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        # Pump configuration
        report_lines.append("PUMP CONFIGURATION:")
        report_lines.append(f"  Syringe Size: {self.pump.syringe_size} mL")
        report_lines.append(f"  Max Position: {self.pump.max_position} steps")
        report_lines.append(f"  Port: {self.pump.port}")
        report_lines.append(f"  Baud Rate: {self.pump.baud_rate}")
        report_lines.append("")
        
        # Process summary
        total_volume = sum(step.volume for step in self.steps)
        total_prime_volume = sum(step.prime_volume or 0 for step in self.steps if step.prime_pump)
        total_estimated_time = 0
        
        report_lines.append("PROCESS SUMMARY:")
        report_lines.append(f"  Total Steps: {len(self.steps)}")
        report_lines.append(f"  Total Volume: {total_volume:,.0f} µL ({total_volume/1000:.2f} mL)")
        report_lines.append(f"  Total Prime Volume: {total_prime_volume:,.0f} µL ({total_prime_volume/1000:.2f} mL)")
        report_lines.append("")
        
        # Detailed step information
        report_lines.append("DETAILED STEP ANALYSIS:")
        report_lines.append("=" * 80)
        
        for i, step in enumerate(self.steps, 1):
            params = self.calculate_step_parameters(step)
            total_estimated_time += params['estimated_time_sec']
            
            report_lines.append(f"Step {i}: {step.step_name}")
            report_lines.append(f"  Type: {step.step_type.value.title()}")
            report_lines.append(f"  Description: {step.description}")
            report_lines.append(f"  Volume: {step.volume:,.0f} µL ({params['volume_ml']:.3f} mL)")
            report_lines.append(f"  Flow Rate: {step.flowrate:,.0f} µL/min ({params['flowrate_ml_min']:.3f} mL/min)")
            report_lines.append(f"  Valves: Inlet={step.inlet_valve}, Outlet={step.outlet_valve}")
            report_lines.append(f"  Timeout: {step.timeout} seconds")
            report_lines.append("")
            
            # Pump calculations
            report_lines.append("  PUMP CALCULATIONS:")
            report_lines.append(f"    Steps Required: {params['steps_needed']:,} steps")
            report_lines.append(f"    Pump Speed: {params['pump_speed_steps_per_sec']:,} steps/sec")
            report_lines.append(f"    Cycles: {params['cycles']}")
            if params['remaining_steps'] > 0:
                report_lines.append(f"    Remaining Steps: {params['remaining_steps']:,} steps")
            report_lines.append(f"    Estimated Time: {params['estimated_time_min']:.2f} minutes ({params['estimated_time_sec']:.1f} seconds)")
            report_lines.append(f"    Optimal Timeout: {params['optimal_timeout_sec']} seconds (2.5x safety margin)")
            if step.timeout != params['optimal_timeout_sec']:
                report_lines.append(f"    Current Timeout: {step.timeout} seconds (manually set)")
            
            # Prime calculations
            if step.prime_pump and params['prime_parameters']:
                prime = params['prime_parameters']
                report_lines.append(f"")
                report_lines.append(f"  PRIME CALCULATIONS:")
                report_lines.append(f"    Prime Volume: {step.prime_volume:,.0f} µL ({prime['volume_ml']:.3f} mL)")
                report_lines.append(f"    Prime Steps: {prime['steps']:,} steps")
                report_lines.append(f"    Prime Time: {prime['estimated_time']:.1f} seconds")
                total_estimated_time += prime['estimated_time']
            
            report_lines.append("-" * 80)
        
        # Process totals
        report_lines.append("")
        report_lines.append("PROCESS TOTALS:")
        report_lines.append(f"  Estimated Total Time: {total_estimated_time/60:.2f} minutes ({total_estimated_time:.1f} seconds)")
        report_lines.append(f"  Total Fluid Volume: {(total_volume + total_prime_volume):,.0f} µL")
        report_lines.append("")
        
        # Commands that will be sent
        report_lines.append("PUMP COMMANDS PREVIEW:")
        report_lines.append("=" * 80)
        for i, step in enumerate(self.steps, 1):
            params = self.calculate_step_parameters(step)
            report_lines.append(f"Step {i}: {step.step_name}")
            
            if step.prime_pump:
                prime_steps = params['prime_parameters']['steps']
                report_lines.append(f"  Prime Command: V{self.pump.aspirate_speed}IA{prime_steps}R")
                report_lines.append(f"  Prime Dispense: V{self.pump.dispense_speed}A0GR")
            
            if params['cycles'] > 0:
                report_lines.append(f"  Main Command: V{self.pump.aspirate_speed}IA{self.pump.max_position}OV{params['pump_speed_steps_per_sec']}A0G{params['cycles']}R")
                if params['remaining_steps'] > 0:
                    report_lines.append(f"  Remaining: V{self.pump.aspirate_speed}IA{params['remaining_steps']}OV{params['pump_speed_steps_per_sec']}A0R")
            else:
                report_lines.append(f"  Main Command: V{self.pump.aspirate_speed}IA{params['steps_needed']}OV{params['pump_speed_steps_per_sec']}A0GR")
            
            report_lines.append("")
        
        report_content = "\n".join(report_lines)
        
        if save_to_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.process_name.replace(' ', '_').lower()}_report_{timestamp}.txt"
            filepath = os.path.join(os.path.dirname(__file__), filename)
            
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(report_content)
                print(f"\n📄 Process report saved to: {filepath}")
            except Exception as e:
                print(f"⚠️  Warning: Could not save report to file: {e}")
        
        return report_content
    
    @classmethod
    def from_dict(cls, process_dict: Dict[str, Any], pump: Optional[PumpCommands] = None) -> 'ChromatographyProcess':
        """
        Create ChromatographyProcess from dictionary configuration
        
        Args:
            process_dict: Dictionary containing process configuration
            pump: Optional PumpCommands instance
            
        Returns:
            ChromatographyProcess: Configured process instance
        """
        process_name = process_dict.get('process_name', 'Unnamed Process')
        process = cls(pump=pump, process_name=process_name)
        
        for step_dict in process_dict.get('steps', []):
            step = ChromatographyStep(
                step_name=step_dict['step_name'],
                step_type=StepType(step_dict['step_type']),
                volume=step_dict['volume'],
                flowrate=step_dict['flowrate'],
                inlet_valve=step_dict['inlet_valve'],
                outlet_valve=step_dict['outlet_valve'],
                prime_pump=step_dict.get('prime_pump', False),
                prime_volume=step_dict.get('prime_volume'),
                wait_until_complete=step_dict.get('wait_until_complete', True),
                timeout=step_dict.get('timeout'),  # None will trigger auto-calculation
                description=step_dict.get('description', '')
            )
            process.add_step(step)
        
        return process
    
    @classmethod
    def load_from_json(cls, filepath: str, pump: Optional[PumpCommands] = None) -> 'ChromatographyProcess':
        """
        Load process from JSON file
        
        Args:
            filepath: Path to JSON file
            pump: Optional PumpCommands instance
            
        Returns:
            ChromatographyProcess: Loaded process
        """
        with open(filepath, 'r') as f:
            process_dict = json.load(f)
        return cls.from_dict(process_dict, pump)
    
    def save_to_json(self, filepath: str) -> None:
        """
        Save process configuration to JSON file
        
        Args:
            filepath: Path to save JSON file
        """
        process_dict = self.save_process_to_dict()
        with open(filepath, 'w') as f:
            json.dump(process_dict, f, indent=2)
        print(f"💾 Process saved to: {filepath}")